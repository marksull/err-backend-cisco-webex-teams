from errbot import botflow
from errbot import BotFlow


class ExampleFlowFlow(BotFlow):
    @botflow
    def details_flow(self, flow):
        start = flow.connect("details", auto_trigger=True)
        eye_step = start.connect("eyes")
        hair_step = eye_step.connect("hair")
        hair_step.connect("finished")
