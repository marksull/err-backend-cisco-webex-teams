import os
import logging

BACKEND = "CiscoWebexTeams"

BOT_IDENTITY = {"TOKEN": os.environ.get("BOT_IDENTITY_TOKEN")}
BOT_DATA_DIR = "/home/errbot/data"
BOT_EXTRA_PLUGIN_DIR = "/home/errbot/backends/err-backend-cisco-webex-teams/plugins/"
BOT_EXTRA_BACKEND_DIR = f"/home/errbot/backends/err-backend-cisco-webex-teams"
BOT_PREFIX = f"{os.environ.get('BOT_PREFIX')} "
BOT_LOG_LEVEL = logging.DEBUG
BOT_PREFIX_OPTIONAL_ON_CHAT = True
BOT_ALT_PREFIX_CASEINSENSITIVE = True

AUTOINSTALL_DEPS = False

# Security

## BOT Admins needs to be of type tuple otherwise errbot will fail to init correctly
BOT_ADMINS = (os.environ.get("BOT_ADMIN"),)
ACCESS_CONTROLS = {}
PERMITTED_DOMAINS = []

# Workaround as the https version of this URL has expired certificate
BOT_PLUGIN_INDEXES = "http://repos.errbot.io/repos.json"

# LDAP SETTINGS if using err-ldap
LDAP_URL = ""
LDAP_USERNAME = ""
LDAP_PASSWORD = ""
LDAP_SEARCH_BASE = ""
