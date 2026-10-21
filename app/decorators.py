import functools
import logging

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