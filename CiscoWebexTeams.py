import asyncio
import json
import sys
import logging
import uuid
import websockets
from markdown import markdown

from errbot.core import ErrBot
from errbot.backends.base import Message, Person, Room, RoomOccupant, OFFLINE
from errbot import rendering

import webexteamssdk

log = logging.getLogger('errbot.backends.CiscoWebexTeams')

CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT = 7439

DEVICES_URL = 'https://wdm-a.wbx2.com/wdm/api/v1/devices'

DEVICE_DATA = {
    "deviceName"    : "pywebsocket-client",
    "deviceType"    : "DESKTOP",
    "localizedModel": "python",
    "model"         : "python",
    "name"          : "python-webex-teams-client",
    "systemName"    : "python-webex-teams-client",
    "systemVersion" : "0.1"
}


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
    @property
    def is_direct(self) -> bool:
        return self.extras['roomType'] == 'direct'

    @property
    def is_group(self) -> bool:
        return not self.is_direct


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
        self.teams_person._json_data['id'] = val

    @property
    def emails(self):
        return self.teams_person.emails

    @emails.setter
    def emails(self, val):
        self.teams_person._json_data['emails'] = val

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

    def find_using_email(self):
        """
        Return the FIRST Cisco Webex Teams person found when searching using an email address
        """
        for person in self._backend.webex_teams_api.people.list(email=self.email):
            self.teams_person = person
            return

        raise FailedToFindWebexTeamsPerson(f'Could not find a user using the email address {self.email}')

    def find_using_name(self):
        """
        Return the FIRST Cisco Webex Teams person found when searching using the display name
        """
        for person in self._backend.webex_teams_api.people.list(displayName=self.displayName):
            self.teams_person = person
            return

        raise FailedToFindWebexTeamsPerson(f'Could not find the user using the displayName {self.displayName}')

    def get_using_id(self):
        """
        Return a Cisco Webex Teams person when searching using an ID
        """
        try:
            self._backend.webex_teams_api.people.get(self.id)
        except:
          raise FailedToFindWebexTeamsPerson(f'Could not find the user using the id {self.id}')

    # Required by the Err API

    @property
    def person(self):
        return self.id

    @property
    def client(self):
        return ''

    @property
    def nick(self):
        return ''

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
            self._room = CiscoWebexTeamsRoom(bot=backend, room_title=room)

        if isinstance(person, CiscoWebexTeamsPerson):
            self.teams_person = person
        else:
            super().__init__(person)

    @property
    def room(self):
        return self._room


class CiscoWebexTeamsRoom(Room):
    """
    A Cisco Webex Teams Room
    """
    def __init__(self, room_id=None, room_title=None, bot=None):
        if room_id is not None and room_title is not None:
            raise ValueError("room_id and room_title are mutually exclusive")
        if not room_id  and not room_title:
            raise ValueError("room_id or room_title is needed")

        if room_title is not None:
            self._name = room_title
        else:
            self._name = bot.roomid_to_roomtitle(room_id)

        self._bot = bot
        self._id = None
        self._occupants = []
    @property
    def _room(self):
        """
        The room object
        """
        rooms = self._bot.webex_teams_api.rooms.list()
        room = [room for room in rooms if room.title == self._name]

        if not len(room) > 0:
            raise RoomDoesNotExistError(f'No room with {self} exists.')
        # TODO: not sure room title will duplicate
        return room[0]

    @property
    def id(self):
        """Return the ID of this room"""
        if self._id is None:
            self._id = self._room.id
        return self._id

    @property
    def sipAddress(self):
        return self._room.sipAddress

    @property
    def created(self):
        return self._room.created

    @property
    def title(self):
        return self._title

    def update_occupants(self):

        log.debug("Updating occupants for room {} ({})".format(self.title, self.id))
        self._occupants.clear()

        for person in self._bot.webex_teams_api.memberships.get(self.id):
            self._occupants.append(CiscoWebexTeamsRoomOccupant(self.id, person=person))

        log.debug("Total occupants for room {} ({}) is {} ".format(self.title, self.id, len(self._occupants)))

    # Errbot API

    def join(self, username=None, password=None):

        log.debug(f'Joining room {self.title} ({self.id})')
        try:
            self._bot.webex_teams_api.memberships.create(self.id, self._bot.bot_identifier.id)
            log.debug(f'{self._bot.bot_identifier.displayName} is NOW a member of {self.title} ({self.id}')

        except webexteamssdk.exceptions.SparkApiError as error:
            # API now returning a 403 when trying to add user to a direct conversation and they are already in the
            # conversation. For groups if the user is already a member a 409 is returned.
            if error.response.status_code == 403 or error.response.status_code == 409:
                log.debug('{self._bot.bot_identifier.displayName} is already a member of {self.title} ({self.id})')
            else:
                log.exception(f'HTTP Exception: Failed to join room {self.title} ({self.id})')
                return

        except Exception:
            log.exception("Failed to join room {} ({})".format(self.title, self.id))
            return

    def leave(self, reason=None):
        log.debug("Leave room yet to be implemented")  # TODO
        pass

    def create(self):
        new_room = self._bot.webex_teams_api.rooms.create(self.title)
        email_addresses = [self._bot.bot_identifier.id]
        for email in email_addresses:
            self._bot.webex_teams_api.memberships.create(new_room.id, personEmail=email)

        api.messages.create(new_room.id, text="Welcome to the room!")
        log.debug(f'Create room: {new_room}')

    def destroy(self):
        log.debug("Destroy room yet to be implemented")  # TODO
        pass

    @property
    def exists(self):
        rooms = self._bot.webex_teams_api.rooms.list()
        return len([room for room in rooms if room_title == self.room.title]) > 0

    @property
    def joined(self):
        rooms = self._bot.webex_teams_api.rooms.list()
        return len([room for room in rooms if room_title == room.title]) > 0

    @property
    def topic(self):
        log.debug("Topic room yet to be implemented")  # TODO
        return "TODO"

    @topic.setter
    def topic(self, topic):
        log.debug("Topic room yet to be implemented")  # TODO
        pass

    @property
    def occupants(self, session=None):
        return self._occupants

    def invite(self, *args):
        log.debug("Invite room yet to be implemented")  # TODO
        pass

    def __eq_(self, other):
        return str(self) == str(other)

    def __unicode__(self):
        return self.id

    __str__ = __unicode__


class CiscoWebexTeamsBackend(ErrBot):
    """
    This is the CiscoWebexTeams backend for errbot.
    """

    def __init__(self, config):

        super().__init__(config)

        bot_identity = config.BOT_IDENTITY

        self.md = rendering.md()

        # Do we have the basic mandatory config needed to operate the bot
        self._bot_token = bot_identity.get('TOKEN', None)
        if not self._bot_token:
            log.fatal('You need to define the Cisco Webex Teams Bot TOKEN in the BOT_IDENTITY of config.py.')
            sys.exit(1)

        # Adjust message size limit to cater for the non-standard size limit
        if config.MESSAGE_SIZE_LIMIT > CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT:
            log.info(
                "Capping MESSAGE_SIZE_LIMIT to {} which is the maximum length allowed by CiscoWebexTeams".
                    format(CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT)
            )
            config.MESSAGE_SIZE_LIMIT = CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT

        log.debug("Setting up SparkAPI")
        self.webex_teams_api = webexteamssdk.WebexTeamsAPI(access_token=self._bot_token)

        log.debug("Setting up device on Webex Teams")
        self.device_info = self._get_device_info()

        log.debug("Fetching and building identifier for the bot itself.")
        self.bot_identifier = CiscoWebexTeamsPerson(self, self.webex_teams_api.people.me())

        log.debug("Done! I'm connected as {}".format(self.bot_identifier.email))

    @property
    def mode(self):
        return 'CiscoWebexTeams'

    def is_from_self(self, message):
      return message.frm.id == message.to.id

    def process_websocket(self, message):
        """
        Process the data from the websocket and determine if we need to ack on it
        :param message: The message received from the websocket
        :return:
        """
        message = json.loads(message.decode('utf-8'))
        if message['data']['eventType'] != 'conversation.activity':
            logging.debug('Ignoring message where Event Type is not conversation.activity')
            return

        activity = message['data']['activity']

        if activity['verb'] != 'post':
            logging.debug('Ignoring message where the verb is not type "post"')
            return

        spark_message = self.webex_teams_api.messages.get(activity['id'])

        if spark_message.personEmail in self.bot_identifier.emails:
            logging.debug('Ignoring message from myself')
            return

        logging.info('Message from %s: %s\n' % (spark_message.personEmail, spark_message.text))
        self.callback_message(self.get_message(spark_message))

    def get_message(self, message):
        """
        Create an errbot message object
        """
        person = CiscoWebexTeamsPerson(self)
        person.id = message.id
        person.email = message.personEmail

        room = CiscoWebexTeamsRoom(room_id=message.roomId, bot=self)

        occupant = CiscoWebexTeamsRoomOccupant(self, person=person, room=room)
        body = message.markdown or message.text
        body = ' '.join(body.split()[1:])
        msg = CiscoWebexTeamsMessage(body=body,
                                     frm=occupant,
                                     to=room,
                                     extras={'roomType': message.roomType})
        return msg

    def follow_room(self, room):
        """
        Backend: Follow Room yet to be implemented

        :param room:
        :return:
        """
        log.debug("Backend: Follow Room yet to be implemented")  # TODO
        pass

    def rooms(self):
        """
        Backend: Rooms yet to be implemented

        :return:
        """
        return self.webex_teams_api.rooms.list()

    def contacts(self):
        """
        Backend: Contacts yet to be implemented

        :return:
        """
        log.debug("Backend: Contacts yet to be implemented")  # TODO
        pass

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

    def query_room(self, room):
        """
        Create a CiscoWebexTeamsRoom object identified by the ID of the room

        :param room: The Cisco Webex Teams room ID
        :return: CiscoWebexTeamsRoom object
        """
        if isinstance(room, webexteamssdk.Room):
            return CiscoWebexTeamsRoom(room=room, bot=self)
        return CiscoWebexTeamsRoom(room_title=room, bot=self)

    def send_message(self, mess):
        """
        Send a message to Cisco Webex Teams

        :param mess: A CiscoWebexTeamsMessage
        """
        # Need to strip out "markdown extra" as not supported by Webex Teams
        md = markdown(self.md.convert(mess.body),
                      extensions=['markdown.extensions.nl2br', 'markdown.extensions.fenced_code'])

        if type(mess.to) == CiscoWebexTeamsPerson:
            self.webex_teams_api.messages.create(toPersonId=mess.to.id, text=mess.body, markdown=md)
        else:
            self.webex_teams_api.messages.create(roomId=mess.to.room.id, text=mess.body, markdown=md)

    def build_reply(self, mess, text=None, private=False, threaded=False):
        """
        Build a reply in the format expected by errbot by swapping the to and from source and destination

        :param mess: The original CiscoWebexTeamsMessage object that will be replied to
        :param text: The text that is to be sent in reply to the message
        :param private: Boolean indiciating whether the message should be directed as a private message in lieu of
                        sending it back to the room
        :return: CiscoWebexTeamsMessage
        """
        response = self.build_message(text)
        response.frm = mess.to
        response.to = mess.frm
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
                    logging.debug("Opening websocket connection to %s" % self.device_info['webSocketUrl'])
                    async with websockets.connect(self.device_info['webSocketUrl']) as ws:
                        logging.info("WebSocket Opened\n")
                        msg = {'id'  : str(uuid.uuid4()),
                               'type': 'authorization',
                               'data': {
                                   'token': 'Bearer ' + self._bot_token
                               }
                               }
                        await ws.send(json.dumps(msg))

                        while True:
                            message = await ws.recv()
                            logging.debug("WebSocket Received Message(raw): %s\n" % message)
                            try:
                                loop = asyncio.get_event_loop()
                                loop.run_in_executor(None, self.process_websocket, message)
                            except:
                                logging.warning('An exception occurred while processing message. Ignoring. ')

                asyncio.get_event_loop().run_until_complete(_run())
        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down..")
            return True
        finally:
            self.disconnect_callback()

    def _get_device_info(self):
        """
        Setup device in Webex Teams to bridge events across websocket
        :return:
        """
        logging.debug('Getting device list from Webex Teams')

        try:
            resp = self.webex_teams_api._session.get(DEVICES_URL)
            for device in resp['devices']:
                if device['name'] == DEVICE_DATA['name']:
                    self.device_info = device
                    return device
        except webexteamssdk.ApiError:
            pass

        logging.info('Device does not exist in Webex Teams, creating')

        resp = self.webex_teams_api._session.post(DEVICES_URL, json=DEVICE_DATA)
        if resp is None:
            raise FailedToCreateWebexDevice("Could not create Webex Teams device using {}".format(DEVICES_URL))

        self.device_info = resp
        return resp

    def change_presence(self, status=OFFLINE, message=''):
        """
        Backend: Change presence yet to be implemented

        :param status:
        :param message:
        :return:
        """
        log.debug("Backend: Change presence yet to be implemented")  # TODO
        pass

    def prefix_groupchat_reply(self, message, identifier):
        """
        Backend: Prefix group chat reply yet to be implemented

        :param message:
        :param identifier:
        :return:
        """
        log.debug("Backend: Prefix group chat reply yet to be implemented")  # TODO
        pass

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
        values = self.get(id)
        return values if values else {}

    def recall_key(self, id, key):
        """
        Access the value of a specific key from a Webex Teams room or person dictionary

        :param id: Webex Teams ID of room or person
        :param key: The dictionary key
        :return: Either the value of the key or None if the key is not found
        """
        return self.recall(id).get(key)

    def roomid_to_roomtitle(self, id_):
        """Convert a Slack channel ID to its channel name"""
        try:
            room = self.webex_teams_api.rooms.get(id_)
        except:
            raise RoomDoesNotExistError(f'No room with ID {id_} exists.')
        return room.title
