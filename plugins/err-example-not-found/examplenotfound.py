from errbot import BotPlugin
from errbot import cmdfilter


class ExampleNotFound(BotPlugin):
    @cmdfilter(catch_unprocessed=True)
    def cnf_filter(self, msg, cmd, args, dry_run, emptycmd=False):
        """

        To avoid the core plugin CommandNotFoundFilter from generating a response
        when a command is not found, the core plugin needs to be disabled. Refer
        to the .env.local CUSTOM_CORE setting that creates a custom core plugin
        list that excludes the CommandNotFoundFilter plugin.

        *****

        This base code comes from:
         https://github.com/errbotio/errbot/blob/master/errbot/core_plugins/cnf_filter.py

        Check if command exists.  If not, signal plugins.  This plugin
        will be called twice: once as a command filter and then again
        as a "command not found" filter. See the emptycmd parameter.

        :param msg: Original chat message.
        :param cmd: Parsed command.
        :param args: Command arguments.
        :param dry_run: True when this is a dry-run.
        :param emptycmd: False when this command has been parsed and is valid.
                         True if the command was not found.
        """

        if not emptycmd:
            return msg, cmd, args

        return f"BAD command `{msg.body.strip()}` - this message comes from err-example-not-found plugin."
