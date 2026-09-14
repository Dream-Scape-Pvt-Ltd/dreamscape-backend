from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


# ---------------------------------------------------------------------------
# Standard error code mapping
# ---------------------------------------------------------------------------

STATUS_CODE_MAP = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    410: "TOKEN_EXPIRED",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR",
}


def custom_exception_handler(exc, context):
    """
    Global DRF exception handler.

    Converts all exceptions into the standard Dreamscape error envelope:

        {
            "success": false,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Human-readable explanation.",
                "details": { "field": ["Error message."] }
            }
        }

    Registration:
        REST_FRAMEWORK = { 'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler' }
    """
    # Convert Django's core ValidationError to DRF's ValidationError
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(detail=exc.messages)

    # Handle Django ProtectedError (e.g. attempting to delete a trip with active departures)
    if isinstance(exc, ProtectedError):
        return Response(
            _build_error_envelope(
                code="PROTECTED_ERROR",
                message="Cannot delete this resource because it is referenced by other active records (such as departures or bookings).",
                details=None,
            ),
            status=status.HTTP_409_CONFLICT,
        )

    # Let DRF do its default handling first to get a Response object.
    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception — return generic 500
        return Response(
            _build_error_envelope(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred. Please try again later.",
                details=None,
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    http_status = response.status_code
    error_code = _resolve_error_code(exc, http_status)
    message = _resolve_message(exc, http_status)
    details = _resolve_details(exc, response.data)

    response.data = _build_error_envelope(
        code=error_code,
        message=message,
        details=details,
    )
    return response


# ---------------------------------------------------------------------------
# Custom application-level exception classes
# ---------------------------------------------------------------------------

class SeatsUnavailableError(APIException):
    """Raised when a departure has no available seats for the requested count."""
    status_code = status.HTTP_409_CONFLICT
    default_code = "SEATS_UNAVAILABLE"
    default_detail = "The selected departure does not have enough available seats."


class PaymentTokenExpiredError(APIException):
    """Raised when a PaymentActionToken is expired or already used."""
    status_code = status.HTTP_410_GONE
    default_code = "TOKEN_EXPIRED"
    default_detail = "This payment link has expired or has already been used."


class IdempotencyConflictError(APIException):
    """Raised when a duplicate webhook event_id is received."""
    status_code = status.HTTP_409_CONFLICT
    default_code = "IDEMPOTENCY_CONFLICT"
    default_detail = "This payment event has already been processed."


class PartnerUnapprovedError(APIException):
    """Raised when an unapproved B2B partner attempts to access the partner portal."""
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "PARTNER_UNAPPROVED"
    default_detail = "Your agency account is pending admin approval."


class TierInsufficientError(APIException):
    """Raised when a partner's tier is below the asset's minimum required tier."""
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "TIER_INSUFFICIENT"
    default_detail = "Your agency tier does not have access to this asset."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_error_envelope(code: str, message: str, details) -> dict:
    envelope = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        envelope["error"]["details"] = details
    return envelope


def _resolve_error_code(exc: Exception, http_status: int) -> str:
    # Use the exception's own code if it's a custom APIException
    if isinstance(exc, APIException) and hasattr(exc, "default_code"):
        custom_code = exc.default_code
        if custom_code and custom_code not in ("error", "invalid", "authentication_failed", "not_found", "permission_denied"):
            return custom_code.upper()
    return STATUS_CODE_MAP.get(http_status, "ERROR")


def _resolve_message(exc: Exception, http_status: int) -> str:
    if isinstance(exc, NotAuthenticated):
        return "Authentication credentials were not provided."
    if isinstance(exc, AuthenticationFailed):
        return "Invalid authentication credentials."
    if isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this action."
    if isinstance(exc, NotFound):
        return "The requested resource was not found."
    if isinstance(exc, ValidationError):
        return "Input validation failed. Please check the details below."
    if isinstance(exc, APIException) and exc.detail:
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and len(detail) > 0:
            first = detail[0]
            return str(first) if hasattr(first, "__str__") else "Request failed."
    return "An error occurred. Please try again."


def _resolve_details(exc: Exception, response_data) -> dict | list | None:
    """Extract field-level validation details from DRF ValidationError."""
    if not isinstance(exc, ValidationError):
        return None

    if isinstance(response_data, dict):
        # Convert ErrorDetail objects to plain strings
        return {
            field: [str(e) for e in errors] if isinstance(errors, list) else str(errors)
            for field, errors in response_data.items()
            if field not in ("detail",)
        }
    if isinstance(response_data, list):
        return [str(e) for e in response_data]

    return None
