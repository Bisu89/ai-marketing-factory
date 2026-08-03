class LibraryError(Exception):
    """Base for service-layer errors. main.py registers a handler per subclass
    below so API endpoints never need their own try/except -- raise the right
    typed error from the service and the client gets a consistent, friendly
    JSON response.
    """


class NotFoundError(LibraryError):
    def __init__(self, resource: str, resource_id: object):
        super().__init__(f"{resource} {resource_id!r} not found")


class ValidationError(LibraryError):
    def __init__(self, message: str):
        super().__init__(message)


class FileOperationError(LibraryError):
    """Missing file, permission error, invalid folder, corrupted metadata --
    anything filesystem-related that shouldn't surface as a raw stack trace.
    """

    def __init__(self, message: str):
        super().__init__(message)


class ExternalServiceError(LibraryError):
    """A third-party API call failed or returned something unusable (LLM
    refusal/timeout/rate limit, malformed structured output, etc.) -- distinct
    from FileOperationError so the client can tell "your disk/files" apart
    from "an external network dependency."
    """

    def __init__(self, message: str):
        super().__init__(message)
