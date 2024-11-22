from errbot import BotPlugin, botcmd


class ExampleSimple(BotPlugin):
    @botcmd
    def simple_message(self, msg, _):
        yield "This is a Simple Teams Message"


