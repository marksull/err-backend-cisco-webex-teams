from errbot import BotPlugin, botcmd
from pathlib import Path


class ExampleSendCallback(BotPlugin):

    def callback_send_message(self, message):
        """
        Inspect a message after it has been sent

        Refer to https://webexteamssdk.readthedocs.io/en/latest/user/api.html#webexteamssdk.Message
        for the message attributes
        """
        print(f"Message ID: {message.id}")
        print(f"Message Markdown: {message.markdown}")
