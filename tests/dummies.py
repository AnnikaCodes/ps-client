"""dummies.py
    helper classes for testing without a connection to Pokemon Showdown
    by Annika"""
import psclient

# pylint: disable=super-init-not-called

class DummyConnection(psclient.PSConnection):
    """A modified version of PSConnection to be used for offline testing
    """
    def __init__(self):
        super().__init__('', '')
        self.roomList = {
            psclient.Room("testroom", self), psclient.Room("testroom2", self),
            psclient.Room("testroom3", self), psclient.Room("lobby", self)
        }

    def send(self, message):
        """The send() method is disabled in DummyConnection
        """

class DummyMessage(psclient.Message):
    """A modified version of Message to be used for offline testing
    """
    def __init__(
        self, sender=None, arguments=None, room=None, body=None, time=None,
        messageType=None, challstr=None, senderName=None, connection=DummyConnection()
    ):
        self.sender = sender
        self.arguments = arguments
        self.room = room
        self.body = body
        self.time = time
        self.type = messageType
        self.challstr = challstr
        self.senderName = senderName
        self.connection = connection
        self.response = None
        #                          (because HTML is an acronym)
        self.HTMLResponse = None # pylint: disable=invalid-name

    def respond(self, response):
        """Captures the response to a message

        Args:
            response (string): the response
        """
        self.response = response

    def respondHTML(self, html):
        """Captures the HTML response to a message

        Args:
            html (string): the HTML
        """
        self.HTMLResponse = html

class DummyUser(psclient.User):
    """A modified version of User to be used for offline testing
    """
    def __init__(self, userid=None, isAdmin=False):
        self.id = userid
        self.isAdmin = isAdmin
