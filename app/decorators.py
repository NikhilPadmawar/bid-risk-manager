import functools
import logging
import time

from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def handle_db_errors(func):
    """Turn any database failure inside an endpoint into a clean DatabaseError."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as exc:
            db = kwargs.get("db")
            if db is not None:
                db.rollback()
            logger.error("Database error in %s: %s", func.__name__, exc, exc_info=True)
            raise DatabaseError("The database could not complete the request") from exc

    return wrapper


def log_tool_call(func):
    """Log every call to an agent tool: its arguments, how long it took and what came back."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info("Tool %s called with %s", func.__name__, kwargs)
        started = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception:
            logger.error("Tool %s crashed", func.__name__, exc_info=True)
            raise
        millis = (time.perf_counter() - started) * 1000
        # Tools report problems as {"error": ...} instead of raising, so check for that
        if isinstance(result, dict) and "error" in result:
            logger.warning("Tool %s returned an error in %.0f ms: %s", func.__name__, millis, result["error"])
        else:
            logger.info("Tool %s finished in %.0f ms: %s", func.__name__, millis, str(result)[:200])
        return result

    return wrapper