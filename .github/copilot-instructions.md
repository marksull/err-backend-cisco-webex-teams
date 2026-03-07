# Copilot Instructions for err-backend-cisco-webex-teams

## Repository Overview

This is a Python-based [errbot](http://errbot.io) backend for [Cisco Webex Teams](https://www.webex.com/products/teams/index.html). It enables errbot to communicate with Cisco Webex Teams using **WebSockets** (not webhooks), which means no inbound firewall rules, NAT traversal, or tunnels (e.g., NGROK) are required. The connection is initiated outbound and held open.

- **Language:** Python 3.6+
- **Framework:** errbot (chatbot framework)
- **Key dependencies:** `webexpythonsdk`, `websockets`, `errbot`, `markdown`, `requests`
- **Runtime:** Docker (primary); direct Python also supported
- **Version:** 2.0.0 (uses WebexPythonSDK; versions prior to 2.0.0 used WebexTeamsSDK)

---

## Repository Layout

```
.
├── CiscoWebexTeams.py        # Main backend implementation (core file)
├── CiscoWebexTeams.plug      # errbot plugin descriptor for the backend
├── config.py                 # errbot configuration (reads from environment variables)
├── requirements.txt          # Python dependencies
├── Makefile                  # Docker build/run targets
├── Dockerfile                # Production Docker image (pulls from errbotio/errbot:latest)
├── Dockerfile.test           # Test Docker image (layered on top of the production image)
├── .env                      # Template for environment variables (copy to .env.local)
├── plugins/                  # Example errbot plugins
│   ├── README.md
│   ├── err-example-simple/   # Minimal botcmd example
│   ├── err-example-cards/    # Adaptive card example
│   ├── err-example-upload/   # File upload example
│   ├── err-example-send-callback/
│   ├── err-example-remember/
│   ├── err-example-large/    # Pagination example for large responses
│   ├── err-example-templates/
│   ├── err-example-not-found/
│   └── err-example-flow/     # Multi-step conversation flow example
└── .github/
    └── copilot-instructions.md
```

### Key source file: `CiscoWebexTeams.py`

- `CiscoWebexTeamsMessage` – extends errbot `Message`; adds `.card`, `.card_action`, `.files`, `.is_direct`, `.is_group`
- `CiscoWebexTeamsPerson` – extends errbot `Person`; wraps `webexpythonsdk.Person`
- `CiscoWebexTeamsRoomOccupant` – extends both `CiscoWebexTeamsPerson` and `RoomOccupant`
- `CiscoWebexTeamsRoom` – extends errbot `Room`; can be looked up by ID or title
- `CiscoWebexTeamsBackend` – main backend class extending `ErrBot`; handles WebSocket connection, message dispatch, card actions, and file uploads
- `HydraTypes` enum – Webex Hydra entity type constants

---

## Environment Setup

Before building or running, copy `.env` to `.env.local` and fill in required values:

```
BOT_PREFIX=<your-bot-name>
BOT_ADMINS=<admin@example.com>
BOT_IDENTITY_TOKEN=<webex-bot-token>
# Optional:
# PERMITTED_DOMAINS=domain1.com,domain2.com
# CUSTOM_CORE=ACLs,Backup,ChatRoom,Flows,Health,Help,Plugins,Utils,VersionChecker
```

A Webex Bot token can be created at: https://developer.webex.com/my-apps (create a new Bot app)

---

## Build, Run, and Test

All operations are performed via **Docker** using the `Makefile`.

### Build production image
```bash
make build
```

### Run production image (requires `.env.local`)
```bash
make run
```

### Build and run in one step
```bash
make build_run
```

### Build test image (includes local source code via `Dockerfile.test`)
```bash
make test_build
```
> Note: This uses `DOCKER_BUILDKIT=0` due to a known Docker Compose issue with `--pull=false` when BuildKit is enabled (see https://github.com/docker/compose/issues/8449).

### Run test image
```bash
make test_run
```

### Build and run test image (most common for local development)
```bash
make test_build_run
```

### Open a shell in the container
```bash
make sh          # production image
make test_sh     # test image
```

**Always use `make test_build_run` when testing local code changes**, as `Dockerfile.test` copies the local repo into the image with `COPY . .`.

There are no standalone Python unit tests; validation is done by running the bot in Docker and issuing commands interactively via Webex Teams.

---

## Writing errbot Plugins

Each plugin lives in `plugins/<plugin-name>/` and contains:
- A `.plug` file (plugin descriptor with `[Core]`, `[Documentation]`, `[Python]` sections)
- A `.py` file implementing a class that extends `BotPlugin`

Minimal plugin example:
```python
from errbot import botcmd, BotPlugin

class MyPlugin(BotPlugin):
    @botcmd
    def my_command(self, msg, args):
        return f"Hello {msg.frm.email}!"
```

Commands map to methods: `my_command` → user types `my command`.

---

## Important Notes

- `config.py` reads all configuration from environment variables (set in `.env.local`).
- `BOT_PREFIX_OPTIONAL_ON_CHAT = True` so prefix is not required for 1:1 direct chat.
- `AUTOINSTALL_DEPS = False` — dependencies must be pre-installed via `pip install -r requirements.txt`.
- `BOT_PLUGIN_INDEXES` uses `http://` (not `https://`) due to an expired certificate on `repos.errbot.io`.
- `PERMITTED_DOMAINS` defaults to the domain of the first admin in `BOT_ADMINS`.
- The Webex device registration URL is `https://wdm-a.wbx2.com/wdm/api/v1/devices` (US cluster only; see `TODO` in `CiscoWebexTeams.py`).
- `CISCO_WEBEX_TEAMS_MESSAGE_SIZE_LIMIT = 7439` bytes — messages exceeding this are automatically split.
- File uploads are automatically split into separate messages from text (Webex API limitation).
