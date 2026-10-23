"""Pretend AI models for tests, so no test ever calls a real LLM."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ScriptedChatModel(GenericFakeChatModel):
    """A pretend AI model that plays back a fixed script of replies."""

    def bind_tools(self, tools, **kwargs):
        return self


class BrokenChatModel(ScriptedChatModel):
    """A pretend AI model that always fails."""

    def _generate(self, *args, **kwargs):
        raise RuntimeError("the model is down")


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    """A model reply that asks for one tool to be run."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def report_call(score: int, level: str, call_id: str = "report") -> AIMessage:
    """A model reply that submits the final RiskReport."""
    return tool_call(
        "RiskReport",
        {
            "score": score,
            "level": level,
            "reasons": ["Margin is 8%, below the 15% threshold", "Deadline is in 5 days"],
            "recommendation": "Raise the price or decline.",
        },
        call_id,
    )