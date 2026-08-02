from typing import Any


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class ServiceUnavailableError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code="service_unavailable",
            message=message,
            status_code=503,
            details=details,
        )


class AuthenticationError(AppError):
    def __init__(self, message: str = "Invalid email or password.") -> None:
        super().__init__(
            code="authentication_failed",
            message=message,
            status_code=401,
            details=None,
        )


class AuthorizationError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(
            code="forbidden",
            message=message,
            status_code=403,
            details=None,
        )


class InactiveUserError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="inactive_user",
            message="User account is disabled.",
            status_code=403,
            details=None,
        )


class DuplicateEmailError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="email_already_registered",
            message="Email already registered.",
            status_code=409,
            details=None,
        )


class RateLimitExceededError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="rate_limit_exceeded",
            message="Too many login attempts. Try again later.",
            status_code=429,
            details=None,
        )


class ConflictError(AppError):
    def __init__(self, message: str = "The request conflicts with existing state.") -> None:
        super().__init__(
            code="conflict",
            message=message,
            status_code=409,
            details=None,
        )


class NotFoundError(AppError):
    def __init__(self, *, resource_name: str) -> None:
        super().__init__(
            code="not_found",
            message=f"{resource_name} not found.",
            status_code=404,
            details={"resource": resource_name},
        )
