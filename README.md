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

```
BOT_IDENTITY = {
    'TOKEN': '<insert your token in here>',
}
```

## Credit

I unrestrainedly plagiarized from most of the already existing err backends and cgascoig's ciscospark-websocket implementation 
(https://github.com/cgascoig/ciscospark-websocket).

## Contributing

Happy to accept Pull Requests
