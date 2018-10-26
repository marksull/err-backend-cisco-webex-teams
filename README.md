err-backend-cisco-webex-teams
======

This is an err (http://errbot.io) backend for Cisco Webex Teams (https://www.webex.com/products/teams/index.html) 
(formally Cisco Spark).

This repo is based off my previous Cisco Spark repo (https://github.com/marksull/err-backend-cisco-spark) but with one 
big difference: this uses websockets and not webhooks to communicate with Webex Teams. This makes a big difference when 
it comes to deploying your bot behind a firewall or NAT device as the connection is initiated outbound and held open so
there are no need for webhooks, firewall/nat changes, or tunnels (like NGROK) to provide access to your bot.

The websocket implementation comes from: https://github.com/cgascoig/ciscospark-websocket

## Status

This backend is currently under development.


## Installation

```
git clone https://github.com/marksull/err-backend-cisco-webex-teams.git
```

To your errbot config.py file add the following:

```
BACKEND = 'CiscoWebexTeams'
BOT_EXTRA_BACKEND_DIR = '/path_to/err-backend-cisco-webex-teams'
```

## Bot Configuration


To configure the bot you will need a Bot TOKEN. If you don't already have a bot setup on Cisco Webex Teams  details can
be found here: https://developer.webex.com/bots.html.

```python
BOT_IDENTITY = {
    'TOKEN': '<insert your token in here>',
}
```

In a Webex Teams GROUP room (more than two people), to direct a command to the bot you need to prefix it with the name of the
bot as you would any other person in the room (for example, type @ and select the bot name). 
As Webex Teams will prefix the command with this name it is important that it is stripped from the 
incoming command for it to be processed correctly. To achieve this add your bot name 
(exactly as configured in Webex Teams) to the BOT_PREFIX:

```python
BOT_PREFIX = 'my-webex-teams-bot-name '
```

In a Webex Teams DIRECT room chat with the bot the bot prefix is not sent with the command. Ensure
to enable BOT_PREFIX_OPTIONAL_ON_CHAT so that the prefix is not required for direct communication:

```python
BOT_PREFIX_OPTIONAL_ON_CHAT = True
```

## Credit

I unrestrainedly plagiarized from most of the already existing err backends and cgascoig's ciscospark-websocket implementation 
(https://github.com/cgascoig/ciscospark-websocket).

## Contributing

Happy to accept Pull Requests
