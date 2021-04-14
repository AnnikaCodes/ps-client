"""test_core.py
    tests for the main portion of psclient
    by Annika"""

# pylint: disable=line-too-long

import sys
import pathlib
sys.path.append(str(pathlib.Path('.').resolve()))

from dummies import DummyConnection # pylint: disable=wrong-import-position
import psclient # pylint: disable=wrong-import-position

def testToID():
    """Tests the toID() function
    """
    assert psclient.toID("hi") == "hi"
    assert psclient.toID("HI") == "hi"
    assert psclient.toID("$&@*%$HI   ^4åå") == "hi4"

def testLog(capsys):
    """Tests the log() function
    """
    psclient.LOGLEVEL = 0
    psclient.log("E: this shows")
    psclient.log("W: this doesn't show")
    psclient.log("I: this doesn't show")
    psclient.log("DEBUG: this doesn't show")
    psclient.log("this doesn't show")
    capture = capsys.readouterr()
    assert capture.out == ""
    assert capture.err == "E: this shows\n"

    psclient.LOGLEVEL = 1
    psclient.log("E: this shows")
    psclient.log("W: this shows")
    psclient.log("I: this doesn't show")
    psclient.log("DEBUG: this doesn't show")
    psclient.log("this doesn't show")
    capture = capsys.readouterr()
    assert capture.out == ""
    assert capture.err == "E: this shows\nW: this shows\n"

    psclient.LOGLEVEL = 2
    psclient.log("E: this shows")
    psclient.log("W: this shows")
    psclient.log("I: this shows")
    psclient.log("DEBUG: this doesn't show")
    psclient.log("this doesn't show")
    capture = capsys.readouterr()
    assert capture.out == "I: this shows\n"
    assert capture.err == "E: this shows\nW: this shows\n"

    psclient.LOGLEVEL = 3
    psclient.log("E: this shows")
    psclient.log("W: this shows")
    psclient.log("I: this shows")
    psclient.log("DEBUG: this shows")
    psclient.log("this shows")
    capture = capsys.readouterr()
    assert capture.out == "I: this shows\nDEBUG: this shows\nthis shows\n"
    assert capture.err == "E: this shows\nW: this shows\n"

## Tests for Message objects ##
def testMessageChallstr():
    """Tests the ability of Message objects to handle challstrs
    """
    message = psclient.Message(
        "|challstr|4|314159265358979323846264338327950288419716939937510582097494459230781640628620899862803482534211706798214808651328230664709384460955058223172535940812848111745028410270193852110555964462294895493038196442881097566593344612847564823",
        DummyConnection()
    )
    assert message.challstr == "4|314159265358979323846264338327950288419716939937510582097494459230781640628620899862803482534211706798214808651328230664709384460955058223172535940812848111745028410270193852110555964462294895493038196442881097566593344612847564823"

def testMessageChat():
    """Tests the ability of Message objects to parse chat messages including strange characters, from the Lobby
    """
    message = psclient.Message(
        "|c|#Ann/ika ^_^|Hi, I wrote a Python test|Isn't it cool?it,contains,odd characters och konstigt bokstaver från andra språk.",
        DummyConnection()
    )
    assert message.senderName == "#Ann/ika ^_^"
    assert message.sender.id == "annika"
    assert message.room.id == "lobby"
    assert message.body == "Hi, I wrote a Python test|Isn't it cool?it,contains,odd characters och konstigt bokstaver från andra språk."
    assert message.time is None
    assert message.type == 'chat'
    assert message.challstr is None
    assert isinstance(str(message), str)

def testMessageChatCommand():
    """Tests the ability of Message objects to handle commands sent to rooms, with arguments
    """
    message = psclient.Message(
        """>testroom
|c:|1593475694|#Ann/ika ^_^|~somecommand argument1,argumENT2||withpipes, argumént3""",
        DummyConnection()
    )
    assert message.senderName == "#Ann/ika ^_^"
    assert message.sender.id == "annika"
    assert message.room.id == "testroom"
    assert message.body == "~somecommand argument1,argumENT2||withpipes, argumént3"
    assert message.time == "1593475694"
    assert message.type == 'chat'
    assert message.challstr is None


def testMessageJoin():
    """Tests the ability of Message objects to handle join messages
    """
    connection = DummyConnection()
    message = psclient.Message(
        """>testroom
|J|#Ann(ik)a ^_^""",
        connection
    )
    assert message.type == "join"
    assert 'testroom' in connection.getUserRooms(connection.getUser('annika'))

    message = psclient.Message(
        """>testroom2
|j|#Ann(ik)a ^_^""",
        connection
    )
    assert message.type == "join"
    assert 'testroom2' in connection.getUserRooms(connection.getUser('annika'))

    message = psclient.Message(
        """>testroom3
|join|#Ann(ik)a ^_^""",
        connection
    )
    assert message.type == "join"
    assert 'testroom3' in connection.getUserRooms(connection.getUser('annika'))

def testMessageLeave():
    """Tests the ability of Message objects to handle leave messages
    """
    connection = DummyConnection()
    joinMessage = """>testroom
|J|#Ann(ik)a ^_^"""

    psclient.Message(joinMessage, connection)
    assert 'testroom' in connection.getUserRooms(connection.getUser('annika'))
    message = psclient.Message(
        """>testroom
|L|#Ann(ik)a ^_^""",
        connection
    )
    assert message.type == "leave"
    assert 'testroom' not in connection.getUserRooms(connection.getUser('annika'))

    psclient.Message(joinMessage, connection)
    assert 'testroom' in connection.getUserRooms(connection.getUser('annika'))
    message = psclient.Message(
        """>testroom
|l|#Ann(ik)a ^_^""",
        connection
    )
    assert message.type == "leave"
    assert 'testroom' not in connection.getUserRooms(connection.getUser('annika'))

    psclient.Message(joinMessage, connection)
    assert 'testroom' in connection.getUserRooms(connection.getUser('annika'))
    message = psclient.Message(
        """>testroom
|leave|#Ann(ik)a ^_^""",
        connection
    )
    assert message.type == "leave"
    assert 'testroom' not in connection.getUserRooms(connection.getUser('annika'))

def testMessagePM():
    """Tests the ability of Message objects to handle PM messages and commands
    """
    message = psclient.Message(
        "|pm|+aNNika ^_^|Expecto Botronum|~somecommand argument1,argumENT2||withpipes, argumént3",
        DummyConnection()
    )
    assert message.senderName == "+aNNika ^_^"
    assert message.sender.id == "annika"
    assert message.room is None
    assert message.body == "~somecommand argument1,argumENT2||withpipes, argumént3"
    assert message.time is None
    assert message.type == 'pm'
    assert message.challstr is None

def testMessageQueryResponse():
    """Tests the ability of Message objects to handle query responses
    """
    connection = DummyConnection()
    message = psclient.Message(
        """|queryresponse|roominfo|{"id":"testroom","roomid":"testroom","title":"Magic & Mayhem","type":"chat","visibility":"hidden","modchat":null,"auth":{"#":["annika","awa","cleo","meicoo"],"%":["dawnofares","instruct","ratisweep","pirateprincess","watfor","oaklynnthylacine"],"@":["gwynt","darth","profsapling","ravioliqueen","miapi"],"+":["madmonty","birdy","captanpasta","iwouldprefernotto","xprienzo","nui","toxtricityamped"],"*":["expectobotronum","kida"]}, "users":["user1","user2"]}""",
        connection
    )
    assert message.type == "queryresponse"
    assert "testroom" in connection.userList[connection.getUser('user1')]
    assert "testroom" in connection.userList[connection.getUser('user2')]

    allUserIDs = [user.id for user in connection.userList.keys()]
    assert 'user1' in allUserIDs
    assert 'user2' in allUserIDs

    auth = connection.getRoom("testroom").auth
    assert auth['#'] == {"annika", "awa", "cleo", "meicoo"}
    assert auth['*'] == {"expectobotronum", "kida"}
    assert auth['@'] == {"gwynt", "darth", "profsapling", "ravioliqueen", "miapi"}
    assert auth['%'] == {"dawnofares", "instruct", "ratisweep", "pirateprincess", "watfor", "oaklynnthylacine"}
    assert auth['+'] == {"madmonty", "birdy", "captanpasta", "iwouldprefernotto", "xprienzo", "nui", "toxtricityamped"}

## Room Object Tests ##
class TestRoom:
    """Tests for Room objects
    """
    connection = DummyConnection()
    room = psclient.Room("testroom", connection)

    def testRoomAuth(self):
        """Tests the ability of Room objects to handle updating and checking auth
        """
        assert self.room.auth == {}
        self.room.updateAuth({'#': {'owner1', 'owner2'}, '*': {'bot1', 'bot2'}, '@': {'mod1', 'mod2'}})
        assert self.room.auth == {'#': {'owner1', 'owner2'}, '*': {'bot1', 'bot2'}, '@': {'mod1', 'mod2'}}
        self.room.updateAuth({'%': {'driver1', 'driver2'}, '+': {'voice1', 'voice2'}})
        assert self.room.auth == {'#': {'owner1', 'owner2'}, '*': {'bot1', 'bot2'}, '@': {'mod1', 'mod2'}, '%': {'driver1', 'driver2'}, '+': {'voice1', 'voice2'}}

        assert self.room.usersWithRankGEQ('#') == {'owner1', 'owner2'}
        assert self.room.usersWithRankGEQ('*') == {'owner1', 'owner2', 'bot1', 'bot2'}
        assert self.room.usersWithRankGEQ('@') == {'owner1', 'owner2', 'bot1', 'bot2', 'mod1', 'mod2'}
        assert self.room.usersWithRankGEQ('%') == {'owner1', 'owner2', 'bot1', 'bot2', 'mod1', 'mod2', 'driver1', 'driver2'}
        assert self.room.usersWithRankGEQ('+') == {'owner1', 'owner2', 'bot1', 'bot2', 'mod1', 'mod2', 'driver1', 'driver2', 'voice1', 'voice2'}

        assert isinstance(str(self.room), str)

## User Object Tests ##
def testUser():
    """Tests the User object
    """
    connection = DummyConnection()
    user = psclient.User("&tEsT uSeR ~o///o~", connection)
    room = psclient.Room("testroom", connection)

    assert user.name == "&tEsT uSeR ~o///o~"
    assert user.id == "testuseroo"

    room.auth = {}
    assert not user.can("html", room)
    assert not user.can("wall", room)

    room.auth = {'%': {'testuseroo'}}
    assert not user.can("html", room)
    assert user.can("wall", room)

    room.auth = {'*': {'testuseroo'}}
    assert user.can("html", room)
    assert user.can("wall", room)

    assert isinstance(str(user), str)

## Connection Object Tests
def testConnection():
    """tests the Connection object
    """
    connection = DummyConnection()

    connection.userJoinedRoom(psclient.User("user1", connection), connection.getRoom("tE ST r]OOm"))
    assert connection.userList[connection.getUser("user1")] == {"testroom"}
    assert connection.getUserRooms(connection.getUser("user1")) == {"testroom"}

    connection.userLeftRoom(connection.getUser("user1"), connection.getRoom("testroom"))
    assert connection.userList[connection.getUser("user1")] == set()
    assert connection.getUserRooms(connection.getUser("user1")) == set()

    assert connection.getRoom("testroom").id == "testroom"
    assert connection.getRoom("T e s tROO  &%# m").id == "testroom"

    assert isinstance(str(connection), str)
