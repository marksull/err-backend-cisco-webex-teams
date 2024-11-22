from errbot import BotPlugin, botcmd


class ExampleCards(BotPlugin):
    @botcmd
    def example_card(self, msg, _):

        # Add your card definition into the message.card attribute
        #
        # Use https://adaptivecards.io/designer/ to build your card
        #
        # Ensure to include a "data" key in the actions definition with at least
        # a single key (in the example below called "callback") that can be used
        # to route multiple cardAction requests (see callback_card below)

        msg.card = {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.2",
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "Submit",
                        "data": {"callback": "my_callback_name"},
                    }
                ],
                "body": [
                    {
                        "type": "TextBlock",
                        "wrap": True,
                        "height": "stretch",
                        "fontType": "Monospace",
                        "size": "Medium",
                        "weight": "Bolder",
                        "text": "Example Card",
                    },
                    {
                        "type": "Input.ChoiceSet",
                        "choices": [
                            {"title": "Say Hello World", "value": "say_hello"},
                            {"title": "Say Goodbye World", "value": "say_goodbye"},
                        ],
                        "placeholder": "Placeholder text",
                        "id": "card_id",
                        "value": "say_hello",
                    },
                ],
            },
        }
        self._bot.send_card(msg)

    def say_something(self, msg, response):
        """
        Say something
        :param msg:
        :param response:
        :return:
        """

        # As the cardAction is outside to normal message handling, we need to manually
        # build the reply (swap the to and from addresses) and then manually send the message

        new_msg = self._bot.build_reply(msg, text=response)
        self._bot.send_message(new_msg)

    def callback_card(self, msg):
        """
        This is a custom callback handler that will be called if we receive a cardAction over
        the websocket. Inspect the input attribute to retrieve the cardAction data
        :param msg:
        :return:
        """

        # In the Card -> actions -> data  we manually defined the key called "callback" (you can name
        # this anything) and we use the value assigned to it to determine how we route incoming
        # cardAction requests

        if msg.card_action.inputs.get("callback") == "my_callback_name":
            self.say_something(msg, msg.card_action.inputs["card_id"])
