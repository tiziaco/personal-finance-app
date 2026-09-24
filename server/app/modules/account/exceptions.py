"""User service domain exceptions."""

from app.exceptions.base import ConflictError


class UserAlreadyExistsError(ConflictError):
    """Exception raised when attempting to create a user that already exists."""

    error_code = "USER_ALREADY_EXISTS"
