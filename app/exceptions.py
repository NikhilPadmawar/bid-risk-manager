class AppError(Exception):
    """Base class for errors we raise on purpose."""

    status_code = 500
    error = "app_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    error = "not_found"


class ConflictError(AppError):
    status_code = 409
    error = "conflict"


class ImportFileError(AppError):
    status_code = 500
    error = "import_file_error"


class DatabaseError(AppError):
    status_code = 500
    error = "database_error"
    

class LLMNotConfiguredError(AppError):
    status_code = 503
    error = "llm_not_configured"


class LLMError(AppError):
    status_code = 502
    error = "llm_error"