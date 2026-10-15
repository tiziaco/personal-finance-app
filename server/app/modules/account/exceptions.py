"""User service domain exceptions."""

from app.exceptions.base import ConflictError, ServiceError


class UserAlreadyExistsError(ConflictError):
    """Exception raised when attempting to create a user that already exists."""

    error_code = "USER_ALREADY_EXISTS"


class UserProvisioningError(ServiceError):
    """The request's credentials were valid, but its user could not be resolved or created.

    503, not 401: the web treats a persistent 401 as an ended session and signs out,
    and a database or Clerk outage during provisioning is not that.
    """

    status_code = 503
    error_code = "USER_PROVISIONING_FAILED"
