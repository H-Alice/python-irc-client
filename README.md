# Python IRC Client
A simple Python IRC client with ability to reconnect after connection dropped.  
有偵測斷線功能的Python IRC客戶端.  

## 基本使用說明 Basic Usage
**Be aware of long running loops in callback function!**  
**請注意盡量避免在callback執行過長的程式或迴圈**
```python
from irc_client import IRCClient, IRCUser
# Define a callback function while receive message.
# 定義一個處理訊息的callback.
def callback(message):
    # Do something with message.
    print(message)

# Login information.
# 使用者資訊.
# <Name> <Password>
user = IRCUser("justinfan123", "blah")  # Twitch的匿名帳號.
client = IRCClient("irc.twitch.tv", 6667, user, callback=callback)
client.join("halice_art")   # Join channel. 加入頻道
client.run()    # 啟動IRC客戶端

```
**Twitch專用的簡單版**
```python
# Callback寫法與上面的範例一樣
client = TwitchIRCClient(name="justinfan123", password="blah", callback=callback)
client.join("halice_art")
client.run()
```

## IRC Message Parser
IRC訊息解析器  
本解析器實作了[RFC1459](https://datatracker.ietf.org/doc/html/rfc1459#section-2.3.1), [RFC2812](https://datatracker.ietf.org/doc/html/rfc2812#section-2.3.1)與[IRCv3](https://ircv3.net/specs/extensions/message-tags.html)對訊息的基本定義.  


irc_client.**IRCMessage**(message)

### Example
```python
if message.command == "PRIVMSG":    # Message from other user. 其他使用者的訊息
    if message.nickname == "halice_art":     # 訊息來自'halice_art'.
        client.send("PRIVMSG #test :Hi")  # 將Hi訊息傳送到#test頻道

```

### Fields

irc_client.**IRCMessage**.tags  
IRCv3 tag string.

irc_client.**IRCMessage**.prefix  

irc_client.**IRCMessage**.nickname  
Sender nickname.  
傳訊息的人.  

irc_client.**IRCMessage**.user  

irc_client.**IRCMessage**.host  

irc_client.**IRCMessage**.command  
Message command.  
指令(可以理解成訊息類別).  

irc_client.**IRCMessage**.params  

irc_client.**IRCMessage**.trailing  
Message body.  
訊息本體.  


