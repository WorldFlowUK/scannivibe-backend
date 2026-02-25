"""
Request ID middleware for tracking and correlating requests.

Assigns a unique request ID to each request/response cycle:
- Uses client-provided X-Request-ID header if present
- Generates a new UUID if not provided
- Attaches to request for use in views and logging
- Returns in response header for client-side correlation
"""

import uuid
from typing import Callable, Any
from django.http import HttpRequest, HttpResponse


class RequestIDMiddleware:
    """
    Middleware that attaches a stable request ID to each request/response cycle.

    The request ID is used for:
    - Telemetry correlation across frontend and backend
    - Request tracing in logs
    - Error response identification

    X-Request-ID header format: Any string that uniquely identifies a request
    (typically a UUID, but can be any string)
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """
        Initialize middleware.

        Args:
            get_response: The next middleware or view callable
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request and attach request ID.

        Args:
            request: The HTTP request

        Returns:
            The HTTP response with X-Request-ID header
        """
        # Extract or generate request ID
        request_id: str = (
            request.headers.get("X-Request-ID") or uuid.uuid4().hex
        )

        # Store on request object for access in views/serializers
        request.request_id = request_id  # type: ignore

        # Process request through application
        response: HttpResponse = self.get_response(request)

        # Attach request ID to response header for client correlation
        response["X-Request-ID"] = request_id

        return response

