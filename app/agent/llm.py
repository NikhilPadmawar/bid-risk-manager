from langchain_openai import ChatOpenAI

from app.config import settings
from app.exceptions import LLMNotConfiguredError


def get_llm() -> ChatOpenAI:
    """Build the chat model the agent will use.

    OpenRouter speaks the same language as OpenAI, so we use LangChain's OpenAI
    client and point it at OpenRouter's address. The model name is a setting,
    so switching models never needs a code change.
    """
    api_key = settings.openrouter_api_key.get_secret_value()
    if not api_key:
        raise LLMNotConfiguredError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file and restart."
        )
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=api_key,
        base_url=settings.openrouter_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )