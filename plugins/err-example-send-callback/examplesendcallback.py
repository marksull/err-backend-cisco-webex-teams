from errbot import BotPlugin, botcmd
from pathlib import Path


class ExampleSendCallback(BotPlugin):

    @botcmd
    def simple_message_with_callback(self, msg, _):
        yield "This is a Simple Teams Message which will trigger a callback"

    def callback_send_message(self, message):
        """
        Inspect a message after it has been sent

        Refer to https://webexteamssdk.readthedocs.io/en/latest/user/api.html#webexteamssdk.Message
        for the message attributes
        """
        print(f"Message ID: {message.id}")
        print(f"Message Markdown: {message.markdown}")
