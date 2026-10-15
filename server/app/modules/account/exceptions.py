"""User service domain exceptions."""

from app.exceptions.base import ConflictError, ServiceUnavailableError


class UserAlreadyExistsError(ConflictError):
    """Exception raised when attempting to create a user that already exists."""

    error_code = "USER_ALREADY_EXISTS"


class UserProvisioningError(ServiceUnavailableError):
    """The request's credentials were valid, but its user could not be resolved or created."""

    error_code = "USER_PROVISIONING_FAILED"
