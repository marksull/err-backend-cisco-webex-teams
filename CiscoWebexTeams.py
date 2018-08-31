import asyncio
import json
import sys
import logging
import uuid
import websockets
from markdown import markdown

from errbot.core import ErrBot
from errbot.backends.base import Message, Person, Room, RoomOccupant
from errbot import rendering

import ciscosparkapi

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
    def __init__(self, bot, attributes={}):

        self._bot = bot

        if isinstance(attributes, ciscosparkapi.Person):
            self.teams_person = attributes
        else:
            self.teams_person = ciscosparkapi.Person(attributes)

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

    @staticmethod
    def build_from_json(obj):
        return CiscoWebexTeamsPerson(ciscosparkapi.Person(obj))

    @classmethod
    def find_using_email(cls, bot, value):
        """
        Return the FIRST Cisco Webex Teams person found when searching using an email address

        :param bot: The bot
        :param value: the value to search for
        :return: A CiscoWebexTeamsPerson
        """
        for person in bot.session.people.list(email=value):
            return CiscoWebexTeamsPerson(bot, person)

        raise FailedToFindWebexTeamsPerson(f'Could not find the user {value}')

    @classmethod
    def find_using_name(cls, session, value):
        """
        Return the FIRST Cisco Webex Teams person found when searching using the display name

        :param session: The CiscoSparkAPI session handle
        :param value: the value to search for
        :return: A CiscoWebexTeamsPerson
        """
        for person in session.people.list(displayName=value):
            return CiscoWebexTeamsPerson(person)
        return CiscoWebexTeamsPerson()

    @classmethod
    def get_using_id(cls, session, value):
        """
        Return a Cisco Webex Teams person when searching using an ID

        :param session: The CiscoSparkAPI session handle
        :param value: the Spark ID
        :return: A CiscoWebexTeamsPerson
        """
        return CiscoWebexTeamsPerson(session.people.get(value))

    def load(self):
        self.teams_person = self._bot.session.Person(self.id)

    # Err API

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
    def __init__(self, bot, room={}, person={}):

        if isinstance(room, CiscoWebexTeamsRoom):
            self._room = room
        else:
            self._room = CiscoWebexTeamsRoom(bot, room)

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

    def __init__(self, bot, val={}):

        self._bot = bot
        self._webhook = None
        self._occupants = []

        if isinstance(val, ciscosparkapi.Room):
            self.teams_room = val
        else:
            self.teams_room = ciscosparkapi.Room(val)

    @property
    def sipAddress(self):
        return self.teams_room.sipAddress

    @property
    def created(self):
        return self.teams_room.created

    @property
    def id(self):
        return self.teams_room.id

    @id.setter
    def id(self, val):
        self.teams_room._json_data['id'] = val

    @property
    def title(self):
        return self.teams_room.title

    @classmethod
    def get_using_id(cls, backend, val):
        return CiscoWebexTeamsRoom(backend, backend.session.rooms.get(val))

    def update_occupants(self):

        log.debug("Updating occupants for room {} ({})".format(self.title, self.id))
        self._occupants.clear()

        for member in self._bot.session.memberships.get(self.id):
            self._occupants.append(CiscoWebexTeamsRoomOccupant(self.id, membership=member))

        log.debug("Total occupants for room {} ({}) is {} ".format(self.title, self.id, len(self._occupants)))

    def load(self):
        self.teams_room = self._bot.session.Room(self.id)

    # Errbot API

    def join(self, username=None, password=None):

        log.debug("Joining room {} ({})".format(self.title, self.id))

        try:
            self._bot.session.memberships.create(self.id, self._bot.bot_identifier.id)
            log.debug("{} is NOW a member of {} ({})".format(self._bot.bot_identifier.displayName, self.title, self.id))

        except ciscosparkapi.exceptions.SparkApiError as error:
            # API now returning a 403 when trying to add user to a direct conversation and they are already in the
            # conversation. For groups if the user is already a member a 409 is returned.
            if error.response.status_code == 403 or error.response.status_code == 409:
                log.debug("{} is already a member of {} ({})".format(self._bot.bot_identifier.displayName, self.title,
                                                                     self.id))
            else:
                log.exception("HTTP Exception: Failed to join room {} ({})".format(self.title, self.id))
                return

        except Exception:
            log.exception("Failed to join room {} ({})".format(self.title, self.id))
            return

    def leave(self, reason=None):
        log.debug("Leave room yet to be implemented")  # TODO
        pass

    def create(self):
        log.debug("Create room yet to be implemented")  # TODO
        pass

    def destroy(self):
        log.debug("Destroy room yet to be implemented")  # TODO
        pass

    exists = True  # TODO
    joined = True  # TODO

    @property
    def topic(self):
        log.debug("Topic room yet to be implemented")  # TODO
        return "TODO"

    @topic.setter
    def topic(self, topic: str) -> None:
        log.debug("Topic room yet to be implemented")  # TODO
        pass

    @property
    def occupants(self, session=None):
        return self._occupants

    def invite(self, *args) -> None:
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
        self.api = ciscosparkapi.CiscoSparkAPI(access_token=self._bot_token)

        log.debug("Setting up device on Webex Teams")
        self.device_info = self._get_device_info()

        log.debug("Fetching and building identifier for the bot itself.")
        self.bot_identifier = CiscoWebexTeamsPerson(self, self.api.people.me())

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

        spark_message = self.api.messages.get(activity['id'])

        if spark_message.personEmail in self.bot_identifier.emails:
            logging.debug('Ignoring message from myself')
            return

        logging.info('Message from %s: %s\n' % (spark_message.personEmail, spark_message.text))
        self.callback_message(self.get_message(spark_message))

    def get_message(self, message):
        """
        Create an errbot message object
        """
        person = CiscoWebexTeamsPerson(bot=self)
        person.id = message.id
        person.email = message.personEmail

        room = self.create_room_using_id(message.roomId)
        occupant = self.get_occupant_using_id(person=person, room=room)
        msg = self.create_message(body=message.markdown or message.text, frm=occupant, to=room,
                                  extras={'roomType': message.roomType})
        return msg

    def get_person_using_email(self, email):
        """
        Loads a person from Spark using the email address for the search criteria

        :param email: The email address to use for the search
        :return: CiscoWebexTeamsPerson
        """
        return CiscoWebexTeamsPerson.find_using_email(self.api, email)

    def get_person_using_id(self, id):
        """
        Loads a person from Spark using the spark id for the search criteria

        :param id: The spark id to use for the search
        :return: CiscoWebexTeamsPerson
        """
        return CiscoWebexTeamsPerson.get_using_id(self.api, id)

    def create_person_using_id(self, id):
        """
        Create a new person and sets the ID. This method DOES NOT load the person details from Webex Teams

        :param id: The Webex Teams id of the person
        :return: CiscoWebexTeamsPerson
        """
        person = CiscoWebexTeamsPerson(self)
        person.id = id
        return person

    def get_room_using_id(self, id):
        """
        Loads a room from Webex Teams using the id for the search criteria

        :param id: The Spark id of the room
        :return: CiscoWebexTeamsRoom
        """
        return CiscoWebexTeamsRoom.get_using_id(self, id)

    def create_room_using_id(self, id):
        """
        Create a new room and sets the ID. This method DOES NOT load the room details from Webex Teams
        :param id:
        :return:
        """
        room = CiscoWebexTeamsRoom(self)
        room.id = id
        return room

    def create_message(self, body, frm, to, extras):
        """
        Creates a new message ready for sending

        :param body: The text that contains the message to be sent
        :param frm: A CiscoWebexTeamsPerson from whom the message will originate
        :param to: A CiscoWebexTeamsPerson to whom the message will be sent
        :param extras: A dictionary of extra items
        :return: CiscoWebexTeamsMessage
        """
        return CiscoWebexTeamsMessage(body=body, frm=frm, to=to, extras=extras)

    def get_message_using_id(self, id):
        """
        Loads a message from Webex Teams using the id for the search criteria

        :param id: The id of the message to load
        :return: Message
        """
        return self.session.messages.get(id)

    def get_occupant_using_id(self, person, room):
        """
        Builds a CiscoWebexTeamsRoomOccupant using a person and a room

        :param person: A CiscoWebexTeamsPerson
        :param room: A CiscoWebexTeamsRoom
        :return: CiscoWebexTeamsRoomOccupant
        """
        return CiscoWebexTeamsRoomOccupant(bot=self, person=person, room=room)

    @property
    def session(self):
        """
        The session handle for sparkapi.CiscoSparkAPI
        :return:
        """
        return self.api

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
        log.debug("Backend: Rooms yet to be implemented")  # TODO
        pass

    def contacts(self):
        """
        Backend: Contacts yet to be implemented

        :return:
        """
        log.debug("Backend: Contacts yet to be implemented")  # TODO
        pass

    def build_identifier(self, strrep):
        """
        Build an errbot identifier using the Webex Teams ID of the person

        :param strrep: The ID of the Cisco Webex Teams person
        :return: CiscoWebexTeamsPerson
        """
        return CiscoWebexTeamsPerson.find_using_email(self, strrep)

    def query_room(self, room):
        """
        Create a CiscoWebexTeamsRoom object identified by the ID of the room

        :param room: The Cisco Webex Teams room ID
        :return: CiscoWebexTeamsRoom object
        """
        return CiscoWebexTeamsRoom.get_using_id(self, room)

    def send_message(self, mess):
        """
        Send a message to Cisco Webex Teams

        :param mess: A CiscoWebexTeamsMessage
        """
        # Need to strip out markdown - extra as not supported by Webex Teams
        md = markdown(self.md.convert(mess.body),
                      extensions=['markdown.extensions.nl2br', 'markdown.extensions.fenced_code'])

        if type(mess.to) == CiscoWebexTeamsPerson:
            self.session.messages.create(toPersonId=mess.to.id, text=mess.body, markdown=md)
        else:
            self.session.messages.create(roomId=mess.to.room.id, text=mess.body, markdown=md)

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

    def change_presence(self, status, message):
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

    def _get_device_info(self):
        """
        Setup device in Webex Teams to bridge events across websocket
        :return:
        """
        logging.debug('Getting device list from Webex Teams')

        try:
            resp = self.api._session.get(DEVICES_URL)
            for device in resp['devices']:
                if device['name'] == DEVICE_DATA['name']:
                    self.device_info = device
                    return device
        except ciscosparkapi.SparkApiError:
            pass

        logging.info('Device does not exist in Webex Teams, creating')

        resp = self.api._session.post(DEVICES_URL, json=DEVICE_DATA)
        if resp is None:
            raise FailedToCreateWebexDevice("Could not create Webex Teams device using {}".format(DEVICES_URL))

        self.device_info = resp
        return resp

