"""
Custom exception handler for DRF to enforce standardized error responses.

All errors are transformed to the standard error envelope:
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {...}
  },
  "request_id": "uuid-or-provided"
}
"""

from typing import Any, Dict, Optional
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .error_types import (
    ErrorCode,
    get_error_code_for_status,
    get_error_message,
    APIError,
)


def _request_id_from_context(context: Dict[str, Any]) -> Optional[str]:
    """Extract request ID from DRF exception context."""
    request = context.get("request")
    if not request:
        return None
    return getattr(request, "request_id", None) or request.headers.get("X-Request-ID")


def _extract_message_from_data(data: Any) -> str:
    """
    Extract a human-readable message from DRF error data.

    Handles various formats:
    - dict with 'detail' key
    - list of errors
    - string error message
    """
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
        return "Invalid request."

    if isinstance(data, list):
        if data:
            first = data[0]
            return str(first) if first else "Invalid request."
        return "Invalid request."

    if isinstance(data, str) and data.strip():
        return data

    return "Request failed."


def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Response:
    """
    Custom exception handler that transforms all DRF exceptions to standardized error envelope.

    Args:
        exc: The exception being handled
        context: DRF exception handler context

    Returns:
        Response with standardized error envelope
    """
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)
    request_id = _request_id_from_context(context)

    # If DRF returns None, it's an unhandled server error
    if response is None:
        return Response(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": get_error_message("INTERNAL_ERROR"),
                    "details": {},
                },
                "request_id": request_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Transform DRF response to standardized format
    error_code: ErrorCode = get_error_code_for_status(response.status_code)
    message = _extract_message_from_data(response.data)

    response.data: APIError = {
        "error": {
            "code": error_code,
            "message": message,
            "details": response.data or {},
        },
        "request_id": request_id,
    }

    return response

