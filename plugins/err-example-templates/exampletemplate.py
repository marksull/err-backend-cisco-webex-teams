from errbot import botcmd
from errbot import BotPlugin


class ExampleTemplate(BotPlugin):
    @botcmd(template="my_template")
    def template(self, msg, message=None):
        """
        This is an example of using a template to reply to a message

        The template is defined in the templates/my_example.md file
        """
        return {"user": msg.frm.email, "message": message}
