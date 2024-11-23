from errbot import botcmd
from errbot import BotPlugin


class ExampleSimple(BotPlugin):
    @botcmd
    def simple_message(self, msg, _):
        yield "This is a Simple Teams Message"


