import asyncio
import copyreg
import json
import logging
import random
import string
import sys
import uuid
from base64 import b64encode
from copy import copy
from enum import Enum

import webexteamssdk
import websockets
from errbot import rendering
from errbot.backends.base import Message
from errbot.backends.base import OFFLINE
from errbot.backends.base import Person
from errbot.backends.base import Room
from errbot.backends.base import RoomDoesNotExistError
from errbot.backends.base import RoomOccupant
from errbot.backends.base import Stream
from errbot.core import ErrBot
from markdown import markdown
from webexteamssdk.models.cards import AdaptiveCard

__version__ = "1.24.0"

log = logging.getLogger("errbot.backends.CiscoWebexTeams")

CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT = 7439

DEVICES_URL = "https://wdm-a.wbx2.com/wdm/api/v1/devices"

DEVICE_DATA = {
    "deviceName": "pywebsocket-client",
    "deviceType": "DESKTOP",
    "localizedModel": "python",
    "model": "python",
    "name": f"python-webex-teams-client-{''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))}",
    "systemName": "python-webex-teams-client",
    "systemVersion": "0.1",
}

# TODO - Need to look at service catalog (somehow?) to determine cluster
#        for now, static to us cluster
HYDRA_PREFIX = "ciscospark://us"


class HydraTypes(Enum):
    # https://github.com/webex/webex-js-sdk/blob/master/packages/node_modules/%40webex/common/src/constants.js#L62
    ATTACHMENT_ACTION = "ATTACHMENT_ACTION"
    CONTENT = "CONTENT"
    MEMBERSHIP = "MEMBERSHIP"
    MESSAGE = "MESSAGE"
    ORGANIZATION = "ORGANIZATION"
    PEOPLE = "PEOPLE"
    ROOM = "ROOM"
    TEAM = "TEAM"


class FailedToCreateWebexDevice(Exception):
    pass


class FailedToFindWebexTeamsPerson(Exception):
    pass


class FailedToFindWebexTeamsRoom(Exception):
    pass


class CiscoWebexTeamsMessage(Message):
    """
    A Cisco Webex Teams Message
    """

    def __init__(self, *args, **kwargs):
        super(CiscoWebexTeamsMessage, self).__init__(*args, **kwargs)
        self.card = None
        self.card_action = None
        self.files = None

    @property
    def is_direct(self) -> bool:
        return self.extras["roomType"] == "direct"

    @property
    def is_group(self) -> bool:
        return not self.is_direct


# noinspection PyProtectedMember
class CiscoWebexTeamsPerson(Person):
    """
    A Cisco Webex Teams Person
    """

    def __init__(self, backend, attributes=None):
        self._backend = backend
        attributes = attributes or {}

        if isinstance(attributes, webexteamssdk.Person):
            self.teams_person = attributes
        else:
            self.teams_person = webexteamssdk.Person(attributes)

    @property
    def id(self):
        return self.teams_person.id

    @id.setter
    def id(self, val):
        self.teams_person._json_data["id"] = val

    @property
    def emails(self):
        return self.teams_person.emails

    @emails.setter
    def emails(self, val):
        self.teams_person._json_data["emails"] = val

    @property
    def email(self):
        if type(self.emails) is list:
            if len(self.emails):
                # Note sure why a person can have multiple email addresses
                return self.emails[0]

        return None

    @email.setter
    def email(self, val):
        self.emails = [val]

    @property
    def aclattr(self):
        return self.teams_person.email

    @property
    def displayName(self):
        return self.teams_person.displayName

    @property
    def created(self):
        return self.teams_person.created

    @property
    def avatar(self):
        return self.teams_person.avatar

    @property
    def nickName(self):
        return self.teams_person.nickName

    def find_using_email(self):
        """
        Return the FIRST Cisco Webex Teams person found when searching using an email address
        """
        try:
            for person in self._backend.webex_teams_api.people.list(email=self.email):
                self.teams_person = person
                return
        except:
            raise FailedToFindWebexTeamsPerson(
                f"Could not find a user using the email address {self.email}"
            )

    def find_using_name(self):
        """
        Return the FIRST Cisco Webex Teams person found when searching using the display name
        """
        try:
            for person in self._backend.webex_teams_api.people.list(
                displayName=self.displayName
            ):
                self.teams_person = person
                return
        except:
            raise FailedToFindWebexTeamsPerson(
                f"Could not find the user using the displayName {self.displayName}"
            )

    def get_using_id(self):
        """
        Return a Cisco Webex Teams person when searching using an ID
        """
        try:
            self.teams_person = self._backend.webex_teams_api.people.get(self.id)
        except:
            raise FailedToFindWebexTeamsPerson(
                f"Could not find the user using the id {self.id}"
            )

    # Required by the Err API

    @property
    def person(self):
        return self.email

    @property
    def client(self):
        return self.id

    @property
    def nick(self):
        return self.nickName

    @property
    def group_prefix(self):
        return f"@{self.nick}" or (f"@{self.email.split('@')[0]}" if self.email else "")

    @property
    def fullname(self):
        return self.displayName

    def json(self):
        return self.teams_person.json()

    def __eq__(self, other):
        return str(self) == str(other)

    def __unicode__(self):
        return self.email

    __str__ = __unicode__


class CiscoWebexTeamsRoomOccupant(CiscoWebexTeamsPerson, RoomOccupant):
    """
    A Cisco Webex Teams Person that Occupies a Cisco Webex Teams Room
    """

    def __init__(self, backend, room=None, person=None):
        room = room or {}
        person = person or {}

        if isinstance(room, CiscoWebexTeamsRoom):
            self._room = room
        else:
            self._room = CiscoWebexTeamsRoom(backend=backend, room_id=room)

        if isinstance(person, CiscoWebexTeamsPerson):
            self.teams_person = person
        else:
            self.teams_person = CiscoWebexTeamsPerson(
                backend=backend, attributes=person
            )

    @property
    def room(self):
        return self._room


class CiscoWebexTeamsRoom(Room):
    """
    A Cisco Webex Teams Room
    """

    def __init__(self, backend, room_id=None, room_title=None):
        self._backend = backend
        self._room_id = room_id
        self._room_title = room_title
        self._room = None

        if room_id is not None and room_title is not None:
            raise ValueError("room_id and room_title are mutually exclusive")

        if not room_id and not room_title:
            raise ValueError("room_id or room_title is needed")

        if room_title is not None:
            self.load_room_from_title()
        else:
            self.load_room_from_id()

    def load_room_from_title(self):
        """
        Load a room object from a title. If no room is found, return a new Room object.
        """
        rooms = self._backend.webex_teams_api.rooms.list()
        room = [room for room in rooms if room.title == self._room_title]

        if not len(room) > 0:
            self._room = webexteamssdk.models.immutable.Room({})
            self._room_id = None
        else:
            # TODO: not sure room title will duplicate
            self._room = room[0]
            self._room_id = self._room.id

    def load_room_from_id(self):
        """
        Load a room object from a webex room id. If no room is found, return a new Room object.
        """
        try:
            self._room = self._backend.webex_teams_api.rooms.get(self._room_id)
            self._room_title = self._room.title
        except webexteamssdk.exceptions.ApiError:
            self._room = webexteamssdk.models.immutable.Room({})

    @property
    def id(self):
        """Return the ID of this room"""
        return self._room_id

    @property
    def room(self):
        """Return the webexteamssdk.models.immutable.Room instance"""
        return self._room

    @property
    def created(self):
        return self._room.created

    @property
    def title(self):
        return self._room_title

    @property
    def type(self):
        return self._room.type

    # Errbot API

    def join(self, username=None, password=None):
        log.debug(f"Joining room {self.title} ({self.id})")

        # noinspection PyBroadException
        try:
            self._backend.webex_teams_api.memberships.create(
                self.id, self._backend.bot_identifier.id
            )
            log.debug(
                f"{self._backend.bot_identifier.displayName} is NOW a member of {self.title} ({self.id}"
            )

        except webexteamssdk.exceptions.ApiError as error:
            # API now returning a 403 when trying to add user to a direct conversation and they are already in the
            # conversation. For groups if the user is already a member a 409 is returned.
            if error.response.status_code == 403 or error.response.status_code == 409:
                log.debug(
                    f"{self._backend.bot_identifier.displayName} is already a member of {self.title} ({self.id})"
                )
            else:
                log.exception(
                    f"HTTP Exception: Failed to join room {self.title} ({self.id})"
                )
                return

        except Exception:
            log.exception(f"Failed to join room {self.title} ({self.id})")

    def leave(self, reason=None):
        """
        Leave a room

        Webex Teams does not support leaving a room via the API.
        """
        log.debug("Leave room yet to be implemented")
        pass

    def create(self):
        """
        Create a new room. Membership to the room is provided by default.
        """
        self._room = self._backend.webex_teams_api.rooms.create(self.title)
        self._room_id = self._room.id
        self._backend.webex_teams_api.messages.create(
            roomId=self._room_id, text="Welcome to the room!"
        )
        log.debug(f"Created room: {self.title}")

    def destroy(self):
        """
        Destroy (delete) a room
        :return:
        """
        self._backend.webex_teams_api.rooms.delete(self.id)
        # We want to re-init this room so that is accurately reflected that
        # it no longer exists
        self.load_room_from_title()
        log.debug(f"Deleted room: {self.title}")

    @property
    def exists(self):
        return self._room.created is not None

    @property
    def joined(self):
        rooms = self._backend.webex_teams_api.rooms.list()
        return len([room for room in rooms if room.title == room.title]) > 0

    @property
    def topic(self):
        return self.title

    @topic.setter
    def topic(self, topic):
        log.debug("Topic room yet to be implemented")  # TODO
        pass

    @property
    def occupants(self):
        if not self.exists:
            raise RoomDoesNotExistError(
                f"Room {self.title or self.id} does not exist, or the bot does not have access"
            )

        occupants = []

        for person in self._backend.webex_teams_api.memberships.list(roomId=self.id):
            p = CiscoWebexTeamsPerson(backend=self._backend)
            p.id = person.personId
            p.email = person.personEmail
            occupants.append(
                CiscoWebexTeamsRoomOccupant(backend=self._backend, room=self, person=p)
            )

        log.debug(
            f"Total occupants for room {self.title} ({self.id}) is {len(occupants)}"
        )

        return occupants

    def invite(self, *args):
        log.debug("Invite room yet to be implemented")  # TODO
        pass

    def __eq__(self, other):
        return str(self) == str(other)

    def __unicode__(self):
        return self.title

    __str__ = __unicode__


# noinspection PyUnresolvedReferences,PyShadowingBuiltins
class CiscoWebexTeamsBackend(ErrBot):
    """
    This is the CiscoWebexTeams backend for errbot.
    """

    def __init__(self, config):
        super().__init__(config)

        bot_identity = config.BOT_IDENTITY

        self.md = rendering.md()

        # Do we have the basic mandatory config needed to operate the bot
        self._bot_token = bot_identity.get("TOKEN", None)
        if not self._bot_token:
            log.fatal(
                "You need to define the Cisco Webex Teams Bot TOKEN in the BOT_IDENTITY of config.py."
            )
            sys.exit(1)

        # Adjust message size limit to cater for the non-standard size limit
        if config.MESSAGE_SIZE_LIMIT > CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT:
            log.info(
                f"Capping MESSAGE_SIZE_LIMIT to {CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT} "
                "which is the maximum length allowed by CiscoWebexTeams"
            )
            config.MESSAGE_SIZE_LIMIT = CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT

        self.permitted_domains = getattr(config, "PERMITTED_DOMAINS", [])
        if type(self.permitted_domains) not in [list, set]:
            log.fatal("PERMITTED_DOMAINS must be of type 'list' or 'set' in config.py.")
            sys.exit(1)

        log.debug("Setting up WebexAPI")
        self.webex_teams_api = webexteamssdk.WebexTeamsAPI(access_token=self._bot_token)

        log.debug("Setting up device on Webex Teams")
        self.device_info = self._get_device_info()

        log.debug("Fetching and building identifier for the bot itself.")
        self.bot_identifier = CiscoWebexTeamsPerson(
            self, self.webex_teams_api.people.me()
        )

        log.debug(f"Done! I'm connected as {self.bot_identifier.email}")

        self._register_identifiers_pickling()

    @property
    def mode(self):
        return "CiscoWebexTeams"

    def is_from_self(self, message):
        return message.frm.id == message.to.id

    def process_websocket(self, message):
        """
        Process the data from the websocket and determine if we need to ack on it
        :param message: The message received from the websocket
        :return:
        """
        message = json.loads(message.decode("utf-8"))
        if message["data"]["eventType"] != "conversation.activity":
            logging.debug(
                "Ignoring message where Event Type is not conversation.activity"
            )
            return

        activity = message["data"]["activity"]
        new_message = None

        if activity["verb"] == "post":
            new_message = self.webex_teams_api.messages.get(
                self.build_hydra_id(activity["id"])
            )

            if new_message.personEmail in self.bot_identifier.emails:
                logging.debug("Ignoring message from myself")
                return

            if (
                self.permitted_domains
                and new_message.personEmail.split("@")[1] not in self.permitted_domains
            ):
                logging.debug(
                    f"Ignoring message from `{new_message.personEmail}` "
                    f"as not in permitted domains `{self.permitted_domains}`"
                )
                return

            logging.info(
                f"Message from {new_message.personEmail}: {new_message.text}\n"
            )

            self.callback_message(self.get_message(new_message))
            return

        if activity["verb"] == "cardAction":
            new_message = self.webex_teams_api.attachment_actions.get(
                self.build_hydra_id(
                    activity["id"], message_type=HydraTypes.ATTACHMENT_ACTION.value
                )
            )
            callback_card = new_message.inputs.get("_callback_card")

            # When a cardAction is sent it includes the messageId of the message from which
            # the card triggered the action, but includes no parentId that we need to be able
            # to remain within a thread. So we need to take the messageID and lookup the details
            # of the message to be ble to determine the parentID.
            reply_message = self.webex_teams_api.messages.get(new_message.messageId)
            new_message.parentId = reply_message.parentId

            self.callback_card(self.get_card_message(new_message), callback_card)
            return

        if not new_message:
            logging.debug(
                f'Ignoring message where the verb is not type "post" or "cardAction". Verb is {activity["verb"]}'
            )

    def callback_card(self, message, callback_card):
        """
        Process a card callback.
        :param message: Message to be processed
        :param callback_card: Function to trigger
        """
        if not callback_card:
            callback_card = "callback_card"

        for plugin in self.plugin_manager.get_all_active_plugins():
            plugin_name = plugin.name
            log.debug(
                f"Triggering {callback_card} on {plugin_name}.",
            )
            # noinspection PyBroadException
            try:
                # As this is a custom callback specific to this backend, there is no
                # expectation that all plugins with have implemented this method
                if hasattr(plugin, callback_card):
                    getattr(plugin, callback_card)(message)
            except Exception:
                log.exception(f"{callback_card} on {plugin_name} crashed.")

    def get_card_message(self, message):
        """
        Create an errbot message object with attached card
        :param message: Message to be processed
        :return:
        """

        card_person = CiscoWebexTeamsPerson(self)
        card_person.id = message.personId
        card_person.get_using_id()

        try:
            parent_id = message.parentId
        except AttributeError:
            parent_id = message.id

        card_room = CiscoWebexTeamsRoom(backend=self, room_id=message.roomId)
        card_occupant = CiscoWebexTeamsRoomOccupant(
            self, person=card_person, room=card_room
        )

        card_msg = CiscoWebexTeamsMessage(
            body="",
            frm=card_occupant,
            to=card_room,
            parent=parent_id,
            extras={"roomType": card_room.type, "message_id": message.id},
        )
        card_msg.card_action = message

        return card_msg

    def get_message(self, message):
        """
        Create an errbot message object
        :param message: The message to be processed
        :return:
        """

        person = CiscoWebexTeamsPerson(self)
        person.id = message.personId

        try:
            person.email = message.personEmail
        except AttributeError:
            person.get_using_id()

        try:
            parent_id = message.parentId
        except AttributeError:
            parent_id = message.id

        room = CiscoWebexTeamsRoom(backend=self, room_id=message.roomId)
        occupant = CiscoWebexTeamsRoomOccupant(self, person=person, room=room)
        msg = CiscoWebexTeamsMessage(
            body=message.markdown or message.text,
            frm=occupant,
            to=room,
            parent=parent_id,
            extras={"roomType": message.roomType, "message_id": message.id},
        )
        return msg

    def rooms(self):
        """
        Backend: Rooms that the bot is a member of

        :return:
            List of rooms
        """
        return [
            f"{room.title} ({room.type})" for room in self.webex_teams_api.rooms.list()
        ]

    def build_identifier(self, strrep):
        """
        Build an errbot identifier using the Webex Teams email address of the person

        :param strrep: The email address of the Cisco Webex Teams person
        :return: CiscoWebexTeamsPerson
        """
        person = CiscoWebexTeamsPerson(self)
        person.email = strrep
        person.find_using_email()
        return person

    def query_room(self, room_id_or_name):
        """
        Create a CiscoWebexTeamsRoom object identified by the ID or name of the room

        :param room_id_or_name:
            The Cisco Webex Teams room ID or a room name
        :return:
            :class: CiscoWebexTeamsRoom
        """
        if isinstance(room_id_or_name, webexteamssdk.Room):
            return CiscoWebexTeamsRoom(backend=self, room_id=room_id_or_name.id)

        # query_room can provide us either a room name of an ID, so we need to check
        # for both
        room = CiscoWebexTeamsRoom(backend=self, room_id=room_id_or_name)

        if not room.exists:
            room = CiscoWebexTeamsRoom(backend=self, room_title=room_id_or_name)

        return room

    def send_card(self, mess):
        """
        Send a card out to Webex Teams.

        :param mess: A CiscoWebexTeamsMessage
        """
        if not hasattr(mess, "card"):
            mess.card = []

        # card backward compatibility for now based on previous contribution
        if hasattr(mess, "layout"):
            mess.card = mess.layout

        if not isinstance(mess.card, list) and mess.card is not None:
            mess.card = [mess.card]

        self.send_message(mess)

    def send_message(self, mess):
        """
        Send a message to Cisco Webex Teams

        :param mess: A CiscoWebexTeamsMessage

        """

        if not hasattr(mess, "card"):
            mess.card = None

        if not hasattr(mess, "files"):
            mess.files = None

        if not isinstance(mess.files, list) and mess.files is not None:
            mess.files = [mess.files]

        # Webex teams does not support a message that contains both a message/text AND a file
        # so lets hide this shortcoming here by creating two separate messages
        if mess.body and mess.files:
            new_msg = copy(mess)

            # First send text message
            new_msg.files = None
            self.send_message(new_msg)

            # And then the message with the file(s)
            new_msg.body = None
            new_msg.files = mess.files
            self.send_message(new_msg)

            return

        # Webex teams does not support more than one file in a single message
        # so lets hide this shortcoming here by creating multiple separate messages
        if mess.files and len(mess.files) > 1:
            new_msg = copy(mess)

            for file in mess.files:
                new_msg.files = [file]
                self.send_message(new_msg)

            return

        md = None
        if mess.body:
            # Need to strip out "markdown extra" as not supported by Webex Teams
            md = markdown(
                self.md.convert(mess.body),
                extensions=[
                    "markdown.extensions.nl2br",
                    "markdown.extensions.fenced_code",
                ],
            )

        if type(mess.to) == CiscoWebexTeamsPerson:
            self.webex_teams_api.messages.create(
                toPersonId=mess.to.id,
                text=mess.body,
                markdown=md,
                parentId=mess.parent,
                attachments=mess.card,
                files=mess.files,
            )
            return

        self.callback_send_message(
            self.webex_teams_api.messages.create(
                roomId=mess.to.room.id,
                text=mess.body,
                markdown=md,
                parentId=mess.parent,
                attachments=mess.card,
                files=mess.files,
            )
        )

    def callback_send_message(self, message):
        """
        Send the message to the send message callback if a plugin is listening
        :param message: The message to send via the callback
        """
        for plugin in self.plugin_manager.get_all_active_plugins():
            # noinspection PyBroadException
            try:
                # As this is a custom callback specific to this backend, there is no
                # expectation that all plugins with have implemented this method
                if hasattr(plugin, "callback_send_message"):
                    log.debug(f"Triggering 'callback_send_message' on {plugin.name}.")
                    getattr(plugin, "callback_send_message")(message)
            except Exception:
                log.exception(
                    f"'callback_send_message' on {plugin.name} raised an exception."
                )

    def _teams_upload(self, stream):
        """
        Performs an upload defined in a stream
        :param stream: Stream object
        :return: None
        """

        try:
            stream.accept()
            log.exception(
                f"Upload of {stream.raw.name} to {stream.identifier} has started."
            )

            if type(stream.identifier) == CiscoWebexTeamsPerson:
                self.webex_teams_api.messages.create(
                    toPersonId=stream.identifier.id, files=[stream.raw.name]
                )
            else:
                self.webex_teams_api.messages.create(
                    roomId=stream.identifier.room.id, files=[stream.raw.name]
                )

            stream.success()
            log.exception(
                f"Upload of {stream.raw.name} to {stream.identifier} has completed."
            )

        except Exception:
            stream.error()
            log.exception(
                f"Upload of {stream.raw.name} to {stream.identifier} has failed."
            )

        finally:
            stream.close()

    def send_stream_request(
        self, identifier, fsource, name="file", size=None, stream_type=None
    ):
        """
        Send a file to Cisco Webex Teams

        :param identifier: is the identifier of the person or room you want to send it to.
        :param fsource: is a file object you want to send.
        :param name: is an optional filename for it.
        :param size: not supported in Webex Teams backend
        :param stream_type: not supported in Webex Teams backend
        """
        log.debug(f"Requesting upload of {fsource.name} to {identifier}.")
        stream = Stream(identifier, fsource, name, size, stream_type)
        self.thread_pool.apply_async(self._teams_upload, (stream,))
        return stream

    def build_reply(self, mess, text=None, private=False, threaded=True):
        """
        Build a reply in the format expected by errbot by swapping the "to" and
        "from" source and destination

        :param mess: The original CiscoWebexTeamsMessage object that will be replied to
        :param text: The text that is to be sent in reply to the message
        :param private: Boolean indicating whether the message should be directed as a private message in lieu of
                        sending it back to the room
        :param threaded: Consider threading when creating the reply message
        :return: CiscoWebexTeamsMessage
        """
        response = self.build_message(text)
        response.frm = mess.to
        response.to = mess.frm

        if threaded:
            response.parent = mess.parent

        return response

    def disconnect_callback(self):
        """
        Disconnection has been requested, lets make sure we clean up
        """
        super().disconnect_callback()

    def serve_once(self):
        """
        Signal that we are connected to the Webex Teams Service and hang around waiting for disconnection request
        """
        self.connect_callback()
        try:
            while True:

                async def _run():
                    logging.debug(
                        "Opening websocket connection to %s"
                        % self.device_info["webSocketUrl"]
                    )
                    async with websockets.connect(
                        self.device_info["webSocketUrl"]
                    ) as ws:
                        logging.info("WebSocket Opened\n")
                        msg = {
                            "id": str(uuid.uuid4()),
                            "type": "authorization",
                            "data": {"token": "Bearer " + self._bot_token},
                        }
                        await ws.send(json.dumps(msg))

                        self.reset_reconnection_count()

                        while True:
                            message = await ws.recv()
                            logging.debug(
                                "WebSocket Received Message(raw): %s\n" % message
                            )
                            try:
                                loop = asyncio.get_event_loop()
                                loop.run_in_executor(
                                    None, self.process_websocket, message
                                )
                            except:
                                logging.warning(
                                    "An exception occurred while processing message. Ignoring. "
                                )

                asyncio.get_event_loop().run_until_complete(_run())
        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down..")
            return True
        finally:
            self.disconnect_callback()

    # noinspection PyProtectedMember
    def _get_device_info(self):
        """
        Setup device in Webex Teams to bridge events across websocket
        :return:
        """
        logging.debug("Getting device list from Webex Teams")

        try:
            resp = self.webex_teams_api._session.get(DEVICES_URL)
            for device in resp["devices"]:
                if device["name"] == DEVICE_DATA["name"]:
                    self.device_info = device
                    return device
        except webexteamssdk.ApiError:
            pass

        logging.info("Device does not exist in Webex Teams, creating")

        resp = self.webex_teams_api._session.post(DEVICES_URL, json=DEVICE_DATA)
        if resp is None:
            raise FailedToCreateWebexDevice(
                f"Could not create Webex Teams device using {DEVICES_URL}"
            )

        self.device_info = resp
        return resp

    def change_presence(self, status=OFFLINE, message=""):
        """
        Backend: Change presence yet to be implemented

        Not implemented in Webex Teams API:
        https://ciscocollabcustomer.ideas.aha.io/ideas/WXCUST-I-3455

        :param status:
        :param message:
        :return:
        """
        log.debug("Backend: Change presence yet to be implemented")
        pass

    def prefix_groupchat_reply(
        self, message: Message, identifier: CiscoWebexTeamsPerson
    ):
        """
        Backend: Prefix group chat reply

        :param message: The message to be sent
        :param identifier : The identifier of the person
        """
        super().prefix_groupchat_reply(message, identifier)
        message.body = f"{identifier.group_prefix} {message.body}"

    @staticmethod
    def build_hydra_id(uuid, message_type=HydraTypes.MESSAGE.value):
        """
        Convert a UUID into Hydra ID that includes geo routing
        :param uuid: The UUID to be encoded
        :param message_type: The type of message to be encoded
        :return (str): The encoded uuid
        """
        return (
            b64encode(f"{HYDRA_PREFIX}/{message_type}/{uuid}".encode("ascii")).decode(
                "ascii"
            )
            if "-" in uuid
            else uuid
        )

    def remember(self, id, key, value):
        """
        Save the value of a key to a dictionary specific to a Webex Teams room or person
        This is available in backend to provide easy access to variables that can be shared between plugins

        :param id: Webex Teams ID of room or person
        :param key: The dictionary key
        :param value:  The value to be assigned to the key
        """
        values = self.recall(id)
        values[key] = value
        self[id] = values

    def forget(self, id, key):
        """
        Delete a key from a dictionary specific to a Webex Teams room or person

        :param id: Webex Teams ID of room or person
        :param key: The dictionary key
        :return: The popped value or None if the key was not found
        """
        values = self.recall(id)
        value = values.pop(key, None)
        self[id] = values
        return value

    def recall(self, id):
        """
        Access a dictionary for a room or person using the Webex Teams ID as the key

        :param id: Webex Teams ID of room or person
        :return: A dictionary. If no dictionary was found an empty dictionary will be returned.
        """
        return self.get(id, {})

    def recall_key(self, id, key):
        """
        Access the value of a specific key from a Webex Teams room or person dictionary

        :param id: Webex Teams ID of room or person
        :param key: The dictionary key
        :return: Either the value of the key or None if the key is not found
        """
        return self.recall(id).get(key)

    @staticmethod
    def _unpickle_identifier(identifier_str):
        return CiscoWebexTeamsBackend.__build_identifier(identifier_str)

    @staticmethod
    def _pickle_identifier(identifier):
        return CiscoWebexTeamsBackend._unpickle_identifier, (str(identifier),)

    def _register_identifiers_pickling(self):
        """
        Register identifiers pickling.
        """
        CiscoWebexTeamsBackend.__build_identifier = self.build_identifier
        for cls in (
            CiscoWebexTeamsPerson,
            CiscoWebexTeamsRoomOccupant,
            CiscoWebexTeamsRoom,
        ):
            copyreg.pickle(
                cls,
                CiscoWebexTeamsBackend._pickle_identifier,
                CiscoWebexTeamsBackend._unpickle_identifier,
            )
