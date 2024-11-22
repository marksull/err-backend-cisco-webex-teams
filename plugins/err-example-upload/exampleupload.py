from errbot import BotPlugin, botcmd
from pathlib import Path

MY_TEXT = "This is my text message"
FILE_1 = "/tmp/file1.txt"
FILE_2 = "/tmp/file2.txt"


class ExampleUpload(BotPlugin):
    @botcmd
    def example_upload(self, msg, _):

        # Add your file(s) into the message.files attribute
        #
        # A couple of Webex Teams Message + Files idiosyncrasies:
        #
        # 1) By default Webex Teams expects a list of a single file. If you provide a str with
        #    just the filename, this backend will convert it to a list
        #
        # 2) By default Webex Teams does not support a Message body and an attachment in the same
        #    message. If a message with with both is detected, this backend will split it into
        #    two messages, one for the body and one for the attachment(s)
        #
        # 3) By default Webex teams does not support a Message with multiple attachments. If you
        #    provide a list of more than one filename, this backend will create a separate
        #    message for each attachment.

        new_msg = self._bot.build_reply(msg)

        Path(FILE_1).write_text(MY_TEXT + "File1")
        Path(FILE_2).write_text(MY_TEXT + "File2")

        new_msg.body = MY_TEXT
        new_msg.files = [FILE_1, FILE_2]

        # As this message contains a body and two files, each will be split into a separate messages:
        # First message will be the body
        # Second message will be FILE_1
        # Third message will be FILE_2

        self._bot.send_message(new_msg)
