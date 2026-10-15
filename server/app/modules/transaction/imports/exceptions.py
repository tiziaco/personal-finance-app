"""The import's exceptions. A 422's context carries `reason`, a code the web words itself."""

from app.exceptions.base import NotFoundError, ServiceError, ValidationError


class InvalidImportFileError(ValidationError):
    """The upload is not a CSV this app can read."""

    error_code = "INVALID_IMPORT_FILE"


class InvalidImportMappingError(ValidationError):
    """The confirmed mapping cannot be used with the held file."""

    error_code = "INVALID_IMPORT_MAPPING"


class ImportUploadNotFoundError(NotFoundError):
    """No held upload with this id: never uploaded, expired, confirmed, replaced, or another user's."""

    error_code = "IMPORT_UPLOAD_NOT_FOUND"


class CategorisationUnavailableError(ServiceError):
    """Every labelling call failed; nothing was saved and the upload is still held."""

    status_code = 503
    error_code = "CATEGORISATION_UNAVAILABLE"
