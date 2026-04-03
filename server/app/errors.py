class BexLogixError(Exception):
    """Base application error for domain/service failures."""


class ValidationError(BexLogixError):
    """Raised when input values fail validation."""


class DomainError(BexLogixError):
    """Raised when a business/domain rule is violated."""


class PermissionError(BexLogixError):
    """Raised when the actor is not authorized to perform an action."""

