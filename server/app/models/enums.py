"""Domain enumerations for the Rilevio application."""

from enum import StrEnum


class Role(StrEnum):
    """Clerk organisation roles.

    Values match the Clerk org role slugs with the 'org:' prefix stripped.
    The AuthMiddleware extracts org_role from the JWT and strips the prefix
    before storing it in request.state.org_role.

    Migration note: when switching auth providers, only AuthMiddleware changes.
    This enum and all consumers remain unchanged.
    """

    PROJECT_MANAGER = "project_manager"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    SUPPLIER = "supplier"
