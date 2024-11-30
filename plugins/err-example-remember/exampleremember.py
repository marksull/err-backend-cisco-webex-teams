from errbot import arg_botcmd
from errbot import botcmd
from errbot import BotPlugin


class ExampleRemember(BotPlugin):
    """
    This plugin is an example of how to use the remember and recall methods implemented
    in the CiscoWebexTeams backend.

    While Errbot does implement its owns remember and recall methods, they include
    some idiosyncratic behaviors that would trip up new users. The CiscoWebexTeams
    backend implements a more straightforward version of these methods.
    """

    @botcmd
    def remember(self, msg, message=None):
        """
        Remember a value for a specific user
        """

        yield f"For the user: {msg.frm.email}"
        yield f"I will remember this message: `{message}`"

        self._bot.remember(id=msg.frm.email, key="message", value=message)

        yield "Done. Remember, if the bot is restarted, the value will be lost."

    @botcmd
    def recall(self, msg, _):
        """
        Recall a value for a specific user
        """

        yield f"For the user: {msg.frm.email}"
        yield f"I will recall the value saved under the key `message`"

        message = self._bot.recall_key(id=msg.frm.email, key="message")

        yield f"If I recall correctly, the message was: `{message}`"

    @arg_botcmd("arg_2", type=str)
    @arg_botcmd("arg_1", type=str)
    def args_remember(self, msg, arg_1=None, arg_2=None):
        """
        Perform a remember operation with arguments
        """

        yield f"For the user: {msg.frm.email}"
        yield "I will remember this these two args:"
        yield f"- `{arg_1}`"
        yield f"- `{arg_2}`"

        self._bot.remember(id=msg.frm.email, key="args", value=[arg_1, arg_2])

        yield "Done. Remember, if the bot is restarted, the value will be lost."

    @botcmd
    def args_recall(self, msg, _):
        """
        Recall the values for the args key for a specific user
        """

        yield f"For the user: {msg.frm.email}"
        yield f"I will recall the value saved under the key `args`"

        args = self._bot.recall_key(id=msg.frm.email, key="args")

        yield "If I recall correctly, the values were:"
        yield f"- `{args[0]}`"
        yield f"- `{args[1]}`"
