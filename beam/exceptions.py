from typing import Optional


class AdministratorRequiredError(PermissionError):
    """Raised when an administrator is required to perform an action."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or 'Administrator privileges are required to perform this action.')
