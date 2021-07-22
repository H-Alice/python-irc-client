import sys
from irc_client import IRCClient, IRCUser, IRCMessage

class TwitchIRCClient(IRCClient):
    def __init__(self, name="justinfan123", password="blah", /, callback=None, loop=None, **kwargs):
        user = IRCUser(name, password)
        super().__init__("irc.twitch.tv", 6667, user, callback=callback, loop=loop, **kwargs)

if __name__ == "__main__":

    # Simple twitch listener.
    # Usage: irc_client.py <channel 1> [<channel 2>...]
    import sys

    def callback(message):
        print(f'{message}')

    client = TwitchIRCClient(callback=callback)

    for _ch in sys.argv[1:]:
        client.join(_ch)
    client.run()