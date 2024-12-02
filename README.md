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

## Quick Start

The quickest way to get started is to use Docker to build the image and run the preconfigured container.

1) Create a new bot here (if required) and note the token : https://developer.webex.com/my-apps/new/bot 
2) Clone this repo: `git clone https://github.com/marksull/err-backend-cisco-webex-teams.git`
3) From the cloned repo directory, copy the `.env` file to `.env.local` and update the environment variables in `.env.local`
4) From the cloned repo directory, build and run the Docker image: `make build_run`

This will start the container and run the bot. Start a 1:1 chat with the bot using the bot's email 
address created during the teams bot registration process.

Use the command `help` to see the available commands.

There are six example plugins included in the container. The see the list of plugins use the command `status plugins`.

To see the examples in action, use the following commands:
1) `simple message` - get a simple message in response
2) `example card` - get a card, selected an option from the dropdown, and receive a response
3) `example upload` - get a message and multiple example files uploaded
4) `simple message with callback` - get a simple message in response with a callback (check the logs for the callback response)
5) `remember this` - remember a message and recall it later
6) `recall` - recall the message remembered in the previous command
7) `args remember blue green` - remember a message with multiple args and recall it later
8) `args recall` - recall the message remembered in the previous command with multiple args
9) `example large response` - see how to manually paginate a large response when using fenced code blocks
10) `template this is my message` - see how to use errbot templates to build your replies
11) `this is a bad message` - see how to custom handle a message that is not a valid command (only required if you want to do something special - i.e. ask OpenAI?)

To stop the container, issue a `Control-c`.

### Quick Command

Using the Quick Start method, here is how you would introduce your own simple command and test it out:

1) Within this repo, open the file [plugins/err-example-simple/examplesimple.py](plugins/err-example-simple/examplesimple.py)
2) Add a new command of your choosing, for example:
```python
    @botcmd
    def my_new_command(self, msg, _):
        yield f"Hello, {msg.frm.email}! This is your new command."
```
3) Build and run Docker image using the LOCAL repo that you just modified: `make test_build_run`
4) Issue the command `my new command` in a 1:1 chat with the bot


## Installation

If you want to set up your own custom bot, you can follow the instructions below.

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
be found here: https://developer.webex.com/my-apps/new/bot.

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

To restrict the bot to only respond to commands to users from specific domains only, define PERMITTED_DOMAINS:

```python
PERMITTED_DOMAINS = ["mydomain.com"]
```


## Cards

A custom card callback handler has now been implemented to make it easier to work with cards. Refer to the
example plugin [err-example-card](plugins/err-example-cards)

## Uploads

While Webex Teams does not support the creation of a Message with both text and file(s) for upload, this backend 
will now automatically split the message and the file upload into multiple messages. Refer to the example  [err-example-upload](plugins/err-example-upload)

## Credit

I unrestrainedly plagiarized from most of the already existing err backends and cgascoig's ciscospark-websocket implementation 
(https://github.com/cgascoig/ciscospark-websocket).

## Contributing

Happy to accept Pull Requests
