"""Quick check that the LLM connection works.

Run it with:  uv run python -m app.agent.ping
"""

from app.agent.llm import get_llm
from app.config import settings
from app.exceptions import LLMNotConfiguredError


def main() -> None:
    try:
        llm = get_llm()
    except LLMNotConfiguredError as exc:
        raise SystemExit(f"Not configured: {exc.message}")

    print(f"Model: {settings.llm_model}")
    try:
        reply = llm.invoke("Reply with exactly one word: pong")
    except Exception as exc:  # network, bad key, unknown model, and so on
        raise SystemExit(f"Call failed: {type(exc).__name__}: {exc}")
    print(f"Reply: {reply.content}")


if __name__ == "__main__":
    main()