import re
import asyncio
from datetime import datetime

class IRCUser:
    """
    IRC user credential.
    """

    def __init__(self, name, password=None, /, nick=None) -> None:
        self.name = name
        self.password = password or "none"
        self.nick = nick or name

class IRCMessage:
    """
    IRC message parser.
    """
    # This parser implemented basic parts in RFC1459, RFC2812 and IRCv3.
    # Compatible with IRCv3 tags.
    GRAM = r'(@(?P<tags>[^\s]*) )?(:(?P<prefix>[^\s]*) )?(?P<command>[a-zA-Z0-9]*)(?P<params>( [^ :\r\n][^ \r\n]*)*)( :(?P<trailing>[^\r\n]*))?(\r\n)?'
    GRAM_PREFIX = r'(?P<nickname>[^!@]*)((!(?P<user>[^!@]*))?@(?P<host>[^!@]*))?'

    def __init__(self, message:str) -> None:
        matches = re.match(IRCMessage.GRAM, message)
        self.tags = matches.group("tags")
        self.prefix = matches.group("prefix")
        self.command = matches.group("command")
        self.params = matches.group("params").split() if matches.group("params") else None
        self.trailing = matches.group("trailing")

        if self.prefix:
            prefix = re.match(IRCMessage.GRAM_PREFIX, self.prefix)
            self.nickname = prefix.group("nickname")
            self.user = prefix.group("user")
            self.host = prefix.group("host")

    def __getitem__(self, key):
        return self.__dict__.get(key, None)

class IRCClient:

    def __init__(self, server, port, user:IRCUser, /, callback=None, loop=None, **kwargs):
        

        # Server information.
        self.server = server
        self.port = port
        self.ssl = kwargs.get("ssl", False)

        # User credential.
        self.user = user
        self.host = kwargs.get("host", server)

        # Watchdog settings.
        self.ping_interval = kwargs.get('ping_interval', 30)
        self.max_awaiting_ping = kwargs.get('max_awaiting_ping', 3)
        self.awaiting_ping = 0

        # Message callback.
        self.message_callback = callback or (lambda x: None)

        # On connect callback function.
        # NOTE: This function will be called before joining channels.
        self.connected_callback = kwargs.get("on_connect", lambda: None)

        # Asyncio event loop.
        self.loop = loop or asyncio.get_event_loop()

        # Connection object.
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

        # Reader/Writer tasks.
        self.writer_loop_task: asyncio.Task = None
        self.reader_loop_task: asyncio.Task = None
        self.watchdog_task: asyncio.Task = None
        self.watchdog_ping_task: asyncio.Task = None

        # Reader/Writer locks.
        self.reader_start = asyncio.Event()
        self.is_connected = asyncio.Event()

        # Channels to attach.
        self.channels = set()

        # Message Queue.
        self.message_queue = asyncio.Queue()

        # Ping conter lock.
        self.ping_lock = asyncio.Lock()

    async def init_connection(self):
        """ 
        Setup IRC server connection. 
        """

        self.is_connected.clear()   # Reset connection event.
        self.reader_start.clear()

        async def _connnect():
            """
            Init connection.
            """
            print('Connecting to IRC server.')
            try:
                if self.writer:
                    self.writer.close()
                    await self.writer.wait_closed()

                self.reader, self.writer = await asyncio.open_connection(self.server, self.port, ssl=self.ssl)

                # Send login credential.
                self.writer.write(f"PASS {self.user.password}\r\n".encode("UTF-8"))
                self.writer.write(f"USER {self.user.name} * * {self.user.name}\r\n".encode("UTF-8"))
                self.writer.write(f"NICK {self.user.nick}\r\n".encode("UTF-8"))

                return True

            except Exception as ex:

                print(f'Exception occurred while connecting: {type(ex)}')
                # TODO: Error handling
                return False

        while True:
            try:
                if await asyncio.wait_for(_connnect(), timeout=5):
                    break
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)
                continue

        # Clear all tasks.
        if self.reader_loop_task:
            self.reader_loop_task.cancel()

        if self.writer_loop_task:
            self.writer_loop_task.cancel()

        if self.watchdog_ping_task:
            self.watchdog_ping_task.cancel()

        # Reset counter.
        self.awaiting_ping = 0

        # Create new reader, writer, watchdog tasks.
        self.reader_loop_task = self.loop.create_task(self.reader_loop())
        self.writer_loop_task = self.loop.create_task(self.writer_loop())
        self.watchdog_ping_task = self.loop.create_task(self.watchdog_ping_writer())

        # Call on_connect callback.
        self.connected_callback()

        # Rejoin channel.
        for _ch in self.channels:
            self.join(_ch)

        await asyncio.sleep(1)

        # Start reader loop.
        self.reader_start.set()

    async def watchdog(self):
        """
        Reconnect if connection lost.
        """
        while True:
            await self.is_connected.wait()
            if self.awaiting_ping >= self.max_awaiting_ping:

                self.is_connected.clear()   # Reset connection event.
                await self.init_connection()

            await asyncio.sleep(1)

    async def watchdog_ping_writer(self):
        """ Ping sender. """
        while True:

            await self.is_connected.wait()
            self.writer.write(f'PING :{self.host}\r\n'.encode("UTF-8"))
            await self.writer.drain()

            async with self.ping_lock:
                self.awaiting_ping = self.awaiting_ping + 1

            await asyncio.sleep(self.ping_interval)

    async def reader_loop(self):
        """ 
        Receive message from IRC server. 
        """
        while True:

            await self.reader_start.wait()  # Wait until connected.

            # Get message and decode.
            line = await self.reader.readline()

            if line:    # Message parser
                line = line.decode("utf-8")

                message = IRCMessage(line)

                # PING and PONG.
                if message['command'] == "PING":    # On received PING
                    self.writer.write(f'PONG {message["trailing"]}\r\n'.encode("UTF-8"))

                elif message['command'] == "PONG":  # On received PING
                    async with self.ping_lock:
                        self.awaiting_ping = 0

                # Server responses.
                elif message['command'] == "001":   # Get welcome message.
                    # NOTE: 
                    #  RFC2812 5.1 Command responses
                    #    - The server sends Replies 001 to 004 to a user upon
                    #      successful registration.
                    self.is_connected.set()
    
                elif message['command'][0] in ['4', '5']:   # On Error.
                    # TODO: Error handler.
                    self.loop.create_task(self.init_connection())
                    return 

                else:
                    # General message.
                    try:
                        if self.message_callback:
                            if asyncio.iscoroutinefunction(self.message_callback):
                                await self.message_callback(line)
                            else:
                                self.message_callback(line)
                    except Exception as ex:
                        print(f"Ignored exception in reader loop callback: {ex}")

            else:
                await asyncio.sleep(1)  # Wait 1 second if received empty string.

    async def writer_loop(self):
        """ Message writer task. """
        while True:
            await self.is_connected.wait()          # Wait until connected.

            msg = await self.message_queue.get()    # Get message from queue.
            self.writer.write(f"{msg}\r\n".encode("UTF-8"))
            await self.writer.drain()
            await asyncio.sleep(0.5)
            self.message_queue.task_done()          # Notify the queue that task is done.

    def send(self, message):
        """ Put message into sender queue. """
        self.message_queue.put_nowait(message)

    def join(self, channel):
        """ Join channel. """
        self.send(f'JOIN #{channel}')
        self.channels = self.channels.union({channel})

    def part(self, channel):
        """ Leave channel. """
        self.send(f'PART #{channel}')
        self.channels = self.channels - {channel}

    def run(self):
        """ Start the client instance. """
        self.loop.run_until_complete(self.init_connection())
        self.loop.run_until_complete(self.watchdog())
        self.loop.run_forever()

if __name__ == "__main__":

    # Simple chat listener.
    # Usage: irc_client.py <server> <port> <name> <pass> <channel 1> [<channel 2>...]
    import sys

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    # Login credential.
    user = IRCUser(sys.argv[3], sys.argv[4])

    client = IRCClient(sys.argv[1], int(sys.argv[2]), user, callback=lambda x: print(f"->> {x}"), loop=loop)

    for _ch in sys.argv[5:]:
        client.join(_ch)
    client.run()
