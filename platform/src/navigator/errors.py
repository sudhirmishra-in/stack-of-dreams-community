"""Typed API errors with a consistent JSON shape."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.headers = headers or {}

    def body(self, correlation_id: str) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message, "correlationId": correlation_id}
        if self.details:
            err["details"] = self.details
        return {"error": err}


class BadRequest(ApiError):
    status, code = 400, "bad_request"


class Unauthorized(ApiError):
    status, code = 401, "unauthorized"


class Forbidden(ApiError):
    status, code = 403, "forbidden"


class PendingApproval(ApiError):
    """A verified identity that an administrator has not approved for the pilot yet (e.g. a new Google sign-in)."""

    status, code = 403, "pending_approval"


class NotFound(ApiError):
    status, code = 404, "not_found"


class Conflict(ApiError):
    status, code = 409, "request_in_progress"


class OutOfScope(ApiError):
    status, code = 422, "out_of_scope"


class QuotaExceeded(ApiError):
    status, code = 429, "quota_exceeded"


class ServiceUnavailable(ApiError):
    status, code = 503, "service_unavailable"
