import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppError

logger = logging.getLogger(__name__)


def error_response(
    status_code: int, error: str, message: str, details: list | None = None
) -> JSONResponse:
    body: dict = {"error": error, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
        logger.log(level, "%s %s -> %s: %s", request.method, request.url.path, exc.error, exc.message)
        return error_response(exc.status_code, exc.error, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(part) for part in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        logger.warning("%s %s -> validation_error: %s", request.method, request.url.path, details)
        return error_response(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return error_response(500, "internal_error", "Something went wrong on our side")