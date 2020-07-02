"""psclient
    connects to Pokémon Showdown
    by Annika, originally for Expecto Botronum"""

import threading
import re
import json
import time
import sys
import requests
import websocket

from psclient import chatlog

ranksInOrder = list("+%☆@★*#&~")
LOGLEVEL = 1

def log(message):
    """Logs a message to the console according to `loglevel`

    Arguments:
        message {string} -- the message to be logged, beginning with E:, W:, I:, or DEBUG:
    """
    # Errors are always logged and warnings if logged go to stderr
    if message[:2] == 'E:' or message[:2] == 'W:' and LOGLEVEL >= 1: return sys.stderr.write(f"{message}\n")
    if message[:2] == 'I:' and LOGLEVEL >= 2: return print(message)
    if LOGLEVEL >= 3: return print(message)

def toID(string):
    """Converts a string into an ID

    Arguments:
        string {string} -- the string to be converted

    Returns:
        [string] -- the ID
    """
    return re.sub('[^0-9a-zA-Z]+', '', string).lower()


class Room():
    """Represents a room on Pokemon Showdown
    """
    def __init__(self, name, connection):
        """Creates a new Room object

        Arguments:
            name {string} -- the name of the room that the Room object represents (can include spaces/caps)
            connection {PSConnection} -- the PSConnection object to use to connect to the room
        """
        self.connection = connection
        self.id = toID(name)
        self.auth = {}
        self.join()

    def updateAuth(self, authDict):
        """Updates the auth list for the room based on the given auth dictionary

        Arguments:
            authDict {dictionary} -- dictionary of the changes to the auth list
        """
        for key in authDict.keys():
            if key in self.auth:
                for user in authDict[key]:
                    if user not in self.auth[key]: self.auth[key].add(user)
            else:
                self.auth[key] = set(authDict[key])

    def say(self, message):
        """Sends a message to the room

        Arguments:
            message {string} -- the message to send
        """
        self.connection.send(f"{self.id}|{message}")

    def leave(self):
        """Leaves the room
        """
        self.say("/part")

    def join(self):
        """Joins the room
        """
        self.connection.send(f'|/j {self.id}')
        self.connection.roomList.add(self)
        self.say(f'/cmd roominfo {self.id}')

    def usersWithRankGEQ(self, rank):
        """Gets a set of userids of the roomauth whose room rank is greater than or equal to a certain rank

        Arguments:
            rank {string} -- the minimum rank

        Returns:
            set --  a set of userids for the roomauth whose room rank is greater than or equal to the given rank
        """
        userIDList = set()
        for roomRank in ranksInOrder[ranksInOrder.index(rank):]:
            if roomRank in self.auth:
                userIDList = userIDList.union(self.auth[roomRank])
        return userIDList


    def __str__(self):
        """String representation of the Room

        Returns:
            string -- representation
        """
        return f"Room: {self.id}; auth: {self.auth}"

class User():
    """Represents a user on Pokemon Showdown
    """
    def __init__(self, name, connection):
        """User()

        Arguments:
            name {string} -- the username
            connection {PSConnection} -- the connection to access PS with
        """
        self.name = name
        self.connection = connection
        self.id = toID(name)

    def can(self, action, room):
        """Checks if the user may perform an action

        Arguments:
            action {string} -- the action
                (one of `wall` or `html`)
            room {Room} -- the room where the action is taking place

        Returns:
            [bool] -- True if the user can do the action and False otherwise
        """
        if not room: return False
        if action not in ['wall', 'html']: log(f"E: User.can(): {action} isn't a valid action")
        return (
            (action == 'wall' and self.id in room.usersWithRankGEQ('%')) or
            (action == 'html' and self.id in room.usersWithRankGEQ('*'))
        )

    #                       (reason: acronym)
    def PM(self, message): # pylint: disable=invalid-name
        """PMs the user the given message

        Arguments:
            message {string} -- the message to PM the user
        """
        self.connection.whisper(self.id, message)

    def __str__(self):
        """String representation of the User

        Returns:
            string -- representation
        """
        return f"User: {self.name}; id: {self.id}"

class Message():
    """Represents a message sent on Pokemon Showdown
    """
    def __init__(self, raw, connection):
        """Creates a new Message object

        Arguments:
            raw {string} -- the raw data of the message
            connection {PSConnection} -- the connection the message was recieved on
        """
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
        else: log(f"DEBUG: Message() of unknown type {self.type}: {self.raw}")

    def respondHTML(self, html):
        """Responds to the message with a HTML box, in a room or in PMs

        If the user cannot broadcast and the command wasn't in PMs or it's not a message that can be responded to, does nothing

        Arguments:
            html {string} -- the html to be sent
        """
        if self.room and self.connection.this.can("html", self.room):
            return self.room.say(f"/adduhtml {self.connection.this.userid},{html}")
        if self.sender and not self.room:
            possibleRoomIDs = [r for r in self.connection.getUserRooms(self.sender) \
                if r in self.connection.getUserRooms(self.connection.this)]
            for possibleRoom in possibleRoomIDs:
                possibleRoom = self.connection.getRoom(possibleRoom)
                if possibleRoom and self.connection.this.can("html", possibleRoom):
                    return possibleRoom.say(f"/pminfobox {self.sender.id}," + html.replace('\n', ''))

    def _handleChat(self, split):
        """Handles messages of type chat

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
        """Handles messages of type join and leave

        Args:
            split (list): the split raw message
            isJoin (bool, optional): whether the message describes a join. Defaults to False.
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
        """String representation of the Message

        Returns:
            string -- representation
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

class PSConnection():
    """Represents a connection to Pokemon Showdown
    """
    def __init__(
        self,
        username,
        password,
        onParsedMessage=None,
        onOpenThread=None,
        url="ws://sim.smogon.com:8000/showdown/websocket",
        chatlogger=None,
        loglevel=1,
    ):
        """Creates a new PSConnection object

        Args:
            username (string): the username to log in with
            password (string): the password to log in with
            onParsedMessage (function): a function that will be called each time a message is recieved from the PS! server
                the only argument passed in is the parsed Message object
            onOpenThread (function): a function that will run in its own thread once the socket is open,
                with the PSConnection as an argument. Defaults to None.
            url (str, optional): the URL of the websocket of the server to connect to.
                Defaults to "ws://sim.smogon.com:8000/showdown/websocket".
            chatlogger (object, optional): a chatlogger, whose .handleMessage() method will be called on each message.
                Defaults to None.
            loglevel (int, optional): the level of logging (to stdout / stderr). Defaults to 1. Higher means more verbose.
        """
        self.websocket = websocket.WebSocketApp(
            url,
            on_message=self.onMessage,
            on_open=self.onOpen,
            on_error=self.onError,
            on_close=self.onClose
        )
        self.roomList = set()
        self.userList = {}
        self.password = password
        self.loglevel = loglevel
        self.lastSentTime = 0
        self.this = User(username, self)
        self.chatlogger = chatlogger
        self.onParsedMessage = onParsedMessage
        self.onOpenThread = onOpenThread
        self.isLoggedIn = False

    def login(self, challstr):
        """Logs into Pokemon Showdown

        Arguments:
            challstr {string} -- the challstr to use to log in
        """
        log("I: PSConnection.login(): logging in...")
        loginInfo = {'act': 'login', 'name': self.this.name, 'pass': self.password, 'challstr': challstr}
        loginResponse = requests.post('http://play.pokemonshowdown.com/action.php', data=loginInfo).content
        assertion = json.loads(loginResponse[1:].decode('utf-8'))['assertion']
        self.send(f"|/trn {self.this.name},0,{assertion}")
        self.isLoggedIn = True
        return log("I: PSConnection.login(): logged in successfully")

    def send(self, message):
        """Sends a message

        Arguments:
            message {string} -- the message to send
        """
        timeDiff = ((time.time() * 1000.0) - self.lastSentTime) - 600.0 # throttle = 600
        if timeDiff < 0:
            time.sleep((-1 * timeDiff) / 1000.0)
        self.websocket.send(message)
        self.lastSentTime = time.time() * 1000.0

    def getRoom(self, name):
        """Gets the Room object corresponding to an ID

        Arguments:
            id {string in ID format} -- the room ID (in ID format from toID())

        Returns:
            Room -- a Room object with the given ID
        """
        roomid = toID(name)
        objects = [room for room in self.roomList if room.id == roomid]
        if len(objects) == 0: return None
        if len(objects) > 1:
            log(f"W: PSConnection.getRoom(): more than 1 Room object for room {roomid}")
        return objects[0]

    def getUser(self, userid):
        """Gets the User object for a given ID

        Arguments:
            userid {string that is an ID} -- the ID of the user to search for

        Returns:
            User || None -- the user, or None if the user isn't in the records
        """
        if userid == self.this.id: return self.this
        for user in self.userList:
            if user and user.id == userid:
                return user
        return None

    def getUserRooms(self, user):
        """Gets a set of the IDs (not objects) of the rooms that the user is in.

        Arguments:
            user {User} -- the user

        Returns:
            set -- the roomids for the user's rooms, or None if the user isn't found
        """
        for possibleUser in self.userList:
            if possibleUser and possibleUser.id == user.id:
                return self.userList[possibleUser]
        return None

    def userJoinedRoom(self, user, room):
        """Handles a user joining a room

        Arguments:
            user {User} -- the user who joined
            room {Room} -- the room they joined
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
            user {User} -- the user who joined
            room {Room} -- the room they joined
        """
        userRooms = self.getUserRooms(user)
        if not isinstance(userRooms, set) or room.id not in userRooms:
            # Do nothing if there's no room set for the user or the user wasn't marked as being in the room
            return
        userRooms.remove(room.id)
        self.userList[self.getUser(user.id)] = userRooms

    def sayIn(self, room, message):
        """Sends a message to a room.

        Arguments:
            room {Room} -- the room to send the message to
            message {string} -- the message to send
        """
        self.websocket.send(f"{room}|{message}")

    def whisper(self, userid, message):
        """PMs a message to a user

        Arguments:
            userid {string in ID format} -- the user to PM
            message {string} -- the message to PM
        """
        self.websocket.send(f"|/pm {userid}, {message}")

    def onError(self, error):
        """Handles errors on the websocket
        Arguments:
            error {string? probably} -- the error
        """
        log(f"E: PSConnection.onError(): websocket error: {error}")

    def onClose(self):
        """Logs when the connection closes
        """
        log("I: PSConnection.onClose(): websocket closed")

    def onOpen(self):
        """Logs when the websocket is opened
        """
        log("I: PSConnection.onOpen(): websocket successfully opened")
        if self.onOpenThread:
            thread = threading.Thread(target=self.onOpenThread, args=tuple([self]))
            thread.start()

    def onMessage(self, rawMessage):
        """Handles new messages from the websocket, creating a Message object
        Arguments:
            rawMessage {string} -- the raw message data
        """
        message = Message(rawMessage, self)
        if self.chatlogger: self.chatlogger.handleMessage(message)
        if message.challstr:
            self.login(message.challstr)
        if self.onParsedMessage: self.onParsedMessage(self, message)

    def __str__(self):
        """String representation of the PSConnection

        Returns:
            string -- representation
        """
        return f"Connection to {self.websocket.url} in these rooms: {', '.join([str(room.id) for room in self.roomList])}"

class PSClient():
    """A Pokemon Showdown client
    """
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        """Runs the client, logging in and connecting.
        Note that this function is blocking -- statements after this function is called will not be executed.
        However, your program will keep running in the form of the PSConnection.onParsedMessage and .onOpenThread attributes.
        """
        self.connection.websocket.run_forever()
