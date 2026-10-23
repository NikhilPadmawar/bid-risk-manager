import logging

from app.config import settings


class HideSecrets(logging.Filter):
    """Safety net: if the API key ever ends up in a log message, replace it with ***."""

    def filter(self, record: logging.LogRecord) -> bool:
        secret = settings.openrouter_api_key.get_secret_value()
        if secret:
            record.msg = str(record.getMessage()).replace(secret, "***")
            record.args = None
        return True


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.log_file),
        ],
    )
    # Filters on a handler run for every message that handler writes
    for handler in logging.getLogger().handlers:
        handler.addFilter(HideSecrets())