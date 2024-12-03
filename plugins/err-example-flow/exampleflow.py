from errbot import arg_botcmd
from errbot import botcmd
from errbot import BotPlugin


class ExampleFlow(BotPlugin):
    @botcmd
    def details(self, msg, _):
        yield "Lets collect some details..."

    @arg_botcmd("colour", type=str, flow_only=True)
    def eyes(self, msg, colour=None):
        msg.ctx["eyes"] = colour
        return f"Your eyes are {colour}"

    @arg_botcmd("colour", type=str, flow_only=True)
    def hair(self, msg, colour=None):
        msg.ctx["hair"] = colour
        return f"Your hair is {colour}"

    @botcmd(flow_only=True)
    def finished(self, msg, _):
        return f"Your details are:\n- eyes:{msg.ctx['eyes']}\n- eyes:{msg.ctx['hair']}"
