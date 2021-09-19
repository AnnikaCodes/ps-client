"""connects to Pokémon Showdown"""

import asyncio
import threading
import re
import json
import time
import sys
from typing import Union, AsyncGenerator
import requests
import websockets

from psclient import chatlog

ranksInOrder = list("+%☆@★*#&~")
"""A list of PS! ranks, in order"""

def toID(string):
    """Converts a string into an ID

    Arguments:
        string (string): the string to be converted

    Returns:
        string: the ID
    """
    return re.sub('[^0-9a-zA-Z]+', '', string).lower()


class Room():
    """Represents a room on Pokemon Showdown

        Arguments:
            name (string): the name of the room that the :any:`Room` object represents (can include spaces/caps)
            connection (Connection): the :any:`Connection` object to use to connect to the room

        Attributes:
            connection (Connection): the :any:`Connection` object to use to connect to the room
            id (string that is an ID): the room's ID
            auth (dictionary): a dictionary containing the room's auth
    """
    def __init__(self, name, connection):
        """Creates a new Room object"""
        self.connection = connection
        self.id = toID(name)
        self.auth = {}

    def updateAuth(self, authDict):
        """Updates the auth list for the room based on the given auth dictionary

        Arguments:
            authDict (dictionary): dictionary of the changes to the auth list
        """
        for key in authDict.keys():
            if key in self.auth:
                for user in authDict[key]:
                    if user not in self.auth[key]: self.auth[key].add(user)
            else:
                self.auth[key] = set(authDict[key])

    async def say(self, message):
        """Sends a message to the room

        Arguments:
            message (string): the message to send
        """
        await self.connection.send(f"{self.id}|{message}")

    async def leave(self):
        """Leaves the room
        """
        await self.say("/part")

    async def join(self):
        """Joins the room
        """
        await self.connection.send(f'|/join {self.id}')
        self.connection.roomList.add(self)
        await self.say(f'/cmd roominfo {self.id}')

    def usersWithRankGEQ(self, rank):
        """Gets a set of userids of the roomauth whose room rank is greater than or equal to a certain rank

        Arguments:
            rank (string): the minimum rank

        Returns:
            set:  a set of userids for the roomauth whose room rank is greater than or equal to the given rank
        """
        userIDList = set()
        for roomRank in ranksInOrder[ranksInOrder.index(rank):]:
            if roomRank in self.auth:
                userIDList = userIDList.union(self.auth[roomRank])
        return userIDList


    def __str__(self):
        """String representation of the :any:`Room`

        Returns:
            string: representation
        """
        return f"Room: {self.id}; auth: {self.auth}"

class User():
    """Represents a user on Pokemon Showdown

        Arguments:
            name (string): the username
            connection (Connection): the connection to access PS with

        Attributes:
            name (string): the username
            connection (Connection): the connection to access PS with
            id (string that is an ID): the user's ID
    """
    def __init__(self, name, connection):
        self.name = name
        self.connection = connection
        self.id = toID(name)

    def canUseHTML(self, room):
        """Checks if the user can use HTML

        Arguments:
            room (Room): the room where the action is taking place

        Returns:
            bool: :any:`True` if the user can use HTML and :any:`False` otherwise
        """
        if not room:
            return False
        return self.id in room.usersWithRankGEQ('*')

    #                       (reason: acronym)
    async def PM(self, message): # pylint: disable=invalid-name
        """PMs the user the given message

        Arguments:
            message (string): the message to PM the user
        """
        await self.connection.whisper(self.id, message)

    def __str__(self):
        """String representation of the :any:`User`

        Returns:
            string: representation
        """
        return f"User: {self.name}; id: {self.id}"

class Message():
    """Represents a message sent on Pokemon Showdown

    Arguments:
        raw (string): the raw data of the message
        connection (Connection): the connection the message was recieved on

    Attributes:
        sender (User or None): the user who sent the message
        room (Room or None): the room the message was sent in
        body (string or None): the body of the message
        time (string or None): the UNIX timestamp of the message
        type (string or None): the type of the message (``chat``, ``pm``, etc)
        challstr (string or None): the challstr, if the message contains one
        senderName (string or None): the username of the user who sent the message
        raw (string): the raw message
        connection (Connection): the connection the message was recieved on
    """
    def __init__(self, raw, connection):
        """Creates a new Message object"""
        self.sender = None
        self.room = None
        self.body = None
        self.time = None
        self.type = None
        self.challstr = None
        self.senderName = None
        self.raw = raw
        self.connection = connection

        split = self.raw.split("|")
        self.type = split[1]

        if self.type == 'challstr': self.challstr = "|".join(split[2:])
        elif self.type in ['c:', 'c', 'chat']: self._handleChat(split)
        elif self.type in ['J', 'j', 'join']: self._handleJoinLeave(split, isJoin=True)
        elif self.type in ['L', 'l', 'leave']: self._handleJoinLeave(split, isJoin=False)
        elif self.type == 'pm': self._handlePM(split)
        elif self.type == 'queryresponse': self._handleQuery(split)
        elif self.type == 'init': pass
        else: self.connection.log(f"DEBUG: Message() of unknown type {self.type}: {self.raw}")

    async def respondHTML(self, html):
        """Responds to the message with a HTML box, in a room or in PMs

        If the user cannot broadcast and the command wasn't in PMs or it's not a message that can be responded to, does nothing

        Arguments:
            html (string): the html to be sent
        """
        if self.room and self.connection.this.canUseHTML(self.room):
            return await self.room.say(f"/adduhtml {self.connection.this.id},{html}")
        if self.sender and not self.room:
            possibleRoomIDs = [r for r in self.connection.getUserRooms(self.sender) \
                if r in self.connection.getUserRooms(self.connection.this)]
            for possibleRoom in possibleRoomIDs:
                possibleRoom = self.connection.getRoom(possibleRoom)
                if possibleRoom and self.connection.this.canUseHTML("html", possibleRoom):
                    return await possibleRoom.say(f"/pminfobox {self.sender.id}," + html.replace('\n', ''))

    def _handleChat(self, split):
        """Handles messages of type ``chat``

        Args:
            split (list): the split raw message
        """
        hasTimestamp = (self.type == 'c:')
        self.type = 'chat'
        self._setRoom(split)

        currentSlice = 2
        if hasTimestamp:
            self.time = split[currentSlice]
            currentSlice += 1

        username = split[currentSlice]
        currentSlice += 1
        userid = username.strip()
        if userid[0] in ranksInOrder:
            rank = userid[0]
            userid = toID("".join(userid[1:]))
            self.room.updateAuth({rank: [userid]})

        self._setSender([None, None, username])
        self.body = "|".join(split[currentSlice:]).strip('\n')

    def _handleJoinLeave(self, split, isJoin=False):
        """Handles messages of types ``join`` and ``leave``

        Args:
            split (list): the split raw message
            isJoin (bool, optional): whether the message describes a join. Defaults to :any:`False`.
        """
        self.type = 'join' if isJoin else 'leave'
        self._setRoom(split)
        self._setSender(split)
        if isJoin: return self.connection.userJoinedRoom(self.sender, self.room)
        return self.connection.userLeftRoom(self.sender, self.room)

    def _handlePM(self, split):
        """Handles messages of type PM

        Args:
            split (list): the split raw message
        """
        self.body = "|".join(split[4:]).strip('\n')
        self._setSender(split)

    def _handleQuery(self, split):
        """Handles query responses

        Args:
            split (list): the split raw message
        """
        query = split[2]
        if query == 'roominfo':
            roomData = json.loads(split[3])
            room = self.connection.getRoom(roomData['id']) if 'id' in roomData.keys() else None
            if room and 'auth' in roomData.keys(): room.updateAuth(roomData['auth'])
            if room and 'users' in roomData.keys():
                for user in roomData['users']:
                    userObject = self.connection.getUser(toID(user))
                    if not userObject: userObject = User(toID(user), self.connection)
                    self.connection.userJoinedRoom(userObject, room)

    def _setSender(self, split):
        """Sets the .sender attribute based on split[2]

        Args:
            split (list): the split raw message
        """
        self.senderName = split[2]
        self.sender = self.connection.getUser(toID(split[2]))
        if not self.sender: self.sender = User(split[2], self.connection)

    def _setRoom(self, split):
        """Sets the .room attribute based on split[0]

        Args:
            split (list): the split raw message
        """
        roomid = split[0].strip('>').strip('\n')
        self.room = self.connection.getRoom(roomid if roomid else 'lobby')

    def __str__(self):
        """String representation of the :any:`Message`

        Returns:
            string: representation
        """
        buf = "Message"
        if self.body: buf += f" with content {self.body}"
        if self.sender: buf += f" from User({str(self.sender)})"
        if self.senderName: buf += f" sent by {self.senderName}"
        if self.room: buf += f" in Room({str(self.room)})"
        if self.time: buf += f" at {str(self.time)}"
        if self.type: buf += f" of type {self.type}"
        if self.challstr: buf += f" with challstr {self.challstr}"
        return buf

class Connection():
    """Represents a connection to Pokemon Showdown

    **You should NOT be constructing this class yourself.** Instead, use :any:`psclient.connect()`.

    Arguments:
        username (string): the username to log in to PS! with
        password (string): the password for the PS! username provided
        websocket (object): the websocket of the server to connect to.
        chatlogger (object): a chatlogger, whose :any:`handleMessage()` method will be called on each message.
        loglevel (int): the level of logging (to stdout / stderr). Higher means more verbose.

    Attributes:
        roomList (set): a set of all the known :any:`Room` objects
        userList (dictionary): a dictionary mapping all known :any:`User` objects to lists of room IDs
        password (string): the password to use to log into PS
        loglevel (int): the level of logging
        lastSentTime (int): the timestamp at which the most recent message was sent
        this (User): an :any:`User` object referring to the user who's logged in
        isLoggedIn (bool): :any:`True` if the connection represents a logged-in user and :any:`False` otherwise
    """
    def __init__(
        self,
        username,
        password,
        websocket,
        chatlogger,
        loglevel,
    ):
        """Creates a new Connection object"""
        self.websocket = websocket
        self.roomList = set()
        self.userList = {}
        self.password = password
        self.loglevel = loglevel
        self.chatlogger = chatlogger
        self.lastSentTime = 0
        self.this = User(username, self)
        self.isLoggedIn = False

    def log(self, message):
        """Logs a message to the console according to `LOGLEVEL`

        Arguments:
            message (string): the message to be logged, beginning with E:, W:, I:, or DEBUG:
        """
        # Errors are always logged and warnings if logged go to stderr
        if message[:2] == 'E:' or message[:2] == 'W:' and self.loglevel >= 1: return sys.stderr.write(f"{message}\n")
        if message[:2] == 'I:' and self.loglevel >= 2: return print(message)
        if self.loglevel >= 3: return print(message)

    async def login(self, challstr):
        """Logs into Pokemon Showdown

        Arguments:
            challstr (string): the challstr to use to log in
        """
        self.log("I: Connection.login(): logging in...")
        loginInfo = {'act': 'login', 'name': self.this.name, 'pass': self.password, 'challstr': challstr}
        loginResponse = requests.post('http://play.pokemonshowdown.com/action.php', data=loginInfo).content
        assertion = json.loads(loginResponse[1:].decode('utf-8'))['assertion']
        await self.send(f"|/trn {self.this.name},0,{assertion}")
        self.isLoggedIn = True
        return self.log("I: Connection.login(): logged in successfully")

    async def waitForLogin(self):
        """Waits for a challstr and then logs in.

        May block infinitely if the server never sends a |challstr|, so using asyncio.wait_for() is advised.
        """
        self.log("I: Connection.waitForLogin(): Initiating wait for |challstr| message")
        messages = 0
        while self.isLoggedIn:
            await self.getMessage()
            messages += 1
            self.log(f"DEBUG: Connection.waitForLogin(): {messages} messages received")


    async def send(self, message):
        """Sends a message

        Arguments:
            message (string): the message to send
        """
        timeDiff = ((time.time() * 1000.0) - self.lastSentTime) - 600.0 # throttle = 600
        if timeDiff < 0:
            time.sleep((-1 * timeDiff) / 1000.0)
        await self.websocket.send(message)
        self.lastSentTime = time.time() * 1000.0

    def getRoom(self, name):
        """Gets the :any:`Room` object corresponding to an ID

        Arguments:
            id (string in ID format): the room ID (in ID format from :any:`toID()`)

        Returns:
            Room: a :any:`Room` object with the given ID
        """
        roomid = toID(name)
        objects = [room for room in self.roomList if room.id == roomid]
        if len(objects) == 0: return None
        if len(objects) > 1:
            self.log(f"W: Connection.getRoom(): more than 1 Room object for room {roomid}")
        return objects[0]

    def getUser(self, userid):
        """Gets the :any:`User` object for a given ID

        Arguments:
            userid (string that is an ID): the ID of the user to search for

        Returns:
            User or None: the user with the given ID
        """
        if userid == self.this.id: return self.this
        for user in self.userList:
            if user and user.id == userid:
                return user
        return None

    def getUserRooms(self, user):
        """Gets a set of the IDs (not objects) of the rooms that the user is in.

        Arguments:
            user (User): the user

        Returns:
            set or None:
        """
        for possibleUser in self.userList:
            if possibleUser and possibleUser.id == user.id:
                return self.userList[possibleUser]
        return None

    def userJoinedRoom(self, user, room):
        """Handles a user joining a room

        Arguments:
            user (User): the user who joined
            room (Room): the room they joined
        """
        if not isinstance(self.getUserRooms(user), set):
            self.userList[user] = {room.id}
            return
        for i in self.userList:
            if i.id == user.id:
                self.userList[i].add(room.id)
                return

    def userLeftRoom(self, user, room):
        """Handles a user leaving a room

        Arguments:
            user (User): the user who joined
            room (Room): the room they joined
        """
        userRooms = self.getUserRooms(user)
        if not isinstance(userRooms, set) or room.id not in userRooms:
            # Do nothing if there's no room set for the user or the user wasn't marked as being in the room
            return
        userRooms.remove(room.id)
        self.userList[self.getUser(user.id)] = userRooms

    async def sayIn(self, room, message):
        """Sends a message to a room.

        Arguments:
            room (Room): the room to send the message to
            message (string): the message to send
        """
        await self.send(f"{room}|{message}")

    async def whisper(self, userid, message):
        """PMs a message to a user

        Arguments:
            userid (string in ID format): the user to PM
            message (string): the message to PM
        """
        await self.send(f"|/pm {userid}, {message}")

    async def getMessage(self) -> Message:
        """Gets a message from the websocket and parses it as needed

        This is a blocking method if awaited, but you can use asyncio.wait_for() safely.

        Returns:
            Message or None: the message, or None if no message was received
        """
        rawMessage = await self.websocket.recv()
        return await self.handleMessage(rawMessage)

    async def handleMessage(self, rawMessage: Union[str, bytes]) -> Message:
        """Handles incoming raw messages

        Args:
            rawMessage (Union[str, bytes]): the raw message from the websocket

        Returns:
            Message: the parsed message
        """
        if isinstance(rawMessage, bytes):
            rawMessage = rawMessage.decode('utf-8')

        message = Message(rawMessage, self)
        if self.chatlogger:
            self.chatlogger.handleMessage(message)
        if message.challstr:
            await self.login(message.challstr)

        return Message(message, self)

    async def messages(self) -> AsyncGenerator[Message, None]:
        """An async generator yielding messages from the websocket

        Yields:
            Message: a processed messages
        """
        async for rawMessage in self.websocket:
            yield await self.handleMessage(rawMessage)

    def __str__(self):
        """String representation of the :any:`Connection`

        Returns:
            string: representation
        """
        host = self.websocket.host
        return f"Connection to {host} in these rooms: {', '.join([str(room.id) for room in self.roomList])}"


async def connect(
    username: str,
    password: str,
    url="wss://sim3.psim.us/showdown/websocket",
    chatlogger=None,
    loglevel=2
) -> Connection:
    """Creates a new connection to a PS server, and logs in

    Args:
        username (str): the username to use for the connection
        password (str): the password for the username
        url (str, optional): the URL of the server to connect to. Defaults to "wss://sim3.psim.us/showdown/websocket".
        chatlogger (Chatlogger, optional): a ps-client compatible chatlogger to use. Defaults to None.
        loglevel (int, optional): the level of logging; higher is more verbose. Defaults to 2.

    Returns:
        Connection: an object representing the connection
    """
    ws = await websockets.connect(url)
    connection = Connection(username, password, ws, chatlogger, loglevel)
    await connection.waitForLogin()
    return connection
