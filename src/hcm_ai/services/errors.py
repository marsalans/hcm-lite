class PermissionDenied(Exception):
    """Caller's role/scope does not allow this data. Maps to HTTP 403 in the REST layer."""


class NotFound(Exception):
    """Requested record does not exist."""
