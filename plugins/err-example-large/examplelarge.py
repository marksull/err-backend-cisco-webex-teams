from pathlib import Path

from errbot import botcmd
from errbot import BotPlugin


class ExampleLarge(BotPlugin):
    @staticmethod
    def fenced_code_block(message):
        """
        Wrap a message in a Fenced Code Block
        """
        return f"```\n{message}\n```\n"

    @botcmd
    def example_large_response(self, msg, _):
        # While the Webex backend will automatically page long responses
        # if you have a large response that is wrapped in Fenced Code Block
        # unless you preemptively page the response and wrap each page in its own
        # Fenced Code Block, you will end up with page 2 onwards not being
        # displayed as expected. Here is an example of how to deal with this.

        # Use this code as the message and make sure it results in 2 pages
        data = Path(__file__).read_text().replace("`", "'")
        data = data * int((self._bot.bot_config.MESSAGE_SIZE_LIMIT / len(data)) + 2)

        message = ""
        for line in data.splitlines():
            if len(message) + len(line) + 9 >= self._bot.bot_config.MESSAGE_SIZE_LIMIT:
                yield self.fenced_code_block(message)
                message = ""

            message += line + "\n"

        yield self.fenced_code_block(message)
