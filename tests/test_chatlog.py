"""test_chatlog.py
    tests for chatlog
    by Annika"""

from datetime import datetime
import re
import sys
import pathlib
import dummies
sys.path.append(str(pathlib.Path(__file__).joinpath("../..").resolve()) + '/')

from psclient import chatlog # pylint: disable=wrong-import-position

class TestChatlog:
    """Tests for the chatlog module
    """
    chatlogger = chatlog.Chatlogger('tests/logs/')

    def testChatlogger(self):
        """Tests the basic chatlogger functions
        """
        assert str(self.chatlogger.path.resolve().relative_to(pathlib.Path('.').resolve())) == 'tests/logs'
        today = datetime.now().date()
        assert str(pathlib.Path(self.chatlogger.getFile("testroom", "a").name).resolve()).split('/')[-1] == f"{today}.txt"

    def testFormatData(self):
        """Tests formatting data
        """
        sampleData = "annika|1591322849|chat|#Annika|hi!\n"
        assert self.chatlogger.formatData(sampleData, isHTML=False) == "[02:07:29] #Annika: hi!"
        assert self.chatlogger.formatData(sampleData, isHTML=True) == \
            "<small>[02:07:29] </small><small>#</small><b>Annika</b>: hi!"

    def testFormatMessage(self):
        """Tests formatting a message
        """
        sampleMessage = dummies.DummyMessage(
            sender=dummies.DummyUser(userid='annika'),
            time=1591322849,
            messageType='chat',
            senderName="#Annika",
            body="hi!"
        )
        assert re.match(r"annika\|15913[0-9]{3}49\|chat\|#Annika\|hi!\n", self.chatlogger.formatMessage(sampleMessage))
    # todo: figure out a way to test the rest of chatlog
