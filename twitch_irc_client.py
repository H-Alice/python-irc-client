import sys
from irc_client import IRCClient, IRCUser, IRCMessage

class TwitchIRCClient(IRCClient):

    def __init__(self, name="justinfan123", password="blah", /, callback=None, loop=None, **kwargs):
        user = IRCUser(name, password)
        super().__init__("irc.twitch.tv", 6667, user, callback=callback, loop=loop, on_connect=self.on_connect, **kwargs)

    def on_connect(self):
        """
        Send capability requests.
        """
        self.writer.write("CAP REQ :twitch.tv/membership\r\n".encode("UTF-8"))
        self.writer.write("CAP REQ :twitch.tv/tags\r\n".encode("UTF-8"))
        self.writer.write("CAP REQ :twitch.tv/commands\r\n".encode("UTF-8"))


if __name__ == "__main__":

    # Simple twitch listener.
    # Usage: irc_client.py <channel 1> [<channel 2>...]
    import sys

    def callback(message):
        message = IRCMessage(message)
        if message["command"] == "PRIVMSG":
            print(f'{message["nickname"]} >> {message["trailing"]}')

    client = TwitchIRCClient(callback=callback)

    for _ch in sys.argv[1:]:
        client.join(_ch)
    client.run()