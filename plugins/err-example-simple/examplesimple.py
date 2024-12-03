from errbot import botcmd
from errbot import BotPlugin


class ExampleSimple(BotPlugin):
    @botcmd
    def simple_message(self, msg, message):
        return f"This is a simple teams message from `{msg.frm.email}` and the message is: `{message}`"
