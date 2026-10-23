import logging

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class StepLogger(BaseCallbackHandler):
    """Logs each turn of the agent loop: every time the model is asked, and what it answered.

    LangChain calls these methods by itself while the agent runs. We only pass an
    instance in, we never call them ourselves.
    """

    def __init__(self, bid_id: int):
        self.bid_id = bid_id
        self.step = 0

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.step += 1
        logger.info("Bid %s, step %s: asking the model (%s messages so far)", self.bid_id, self.step, len(messages[0]))

    def on_llm_end(self, response, **kwargs):
        message = response.generations[0][0].message
        if message.tool_calls:
            names = ", ".join(call["name"] for call in message.tool_calls)
            logger.info("Bid %s, step %s: the model wants to call %s", self.bid_id, self.step, names)
        else:
            logger.info("Bid %s, step %s: the model replied with text, no tool call", self.bid_id, self.step)