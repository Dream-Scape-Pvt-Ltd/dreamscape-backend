import json
from rest_framework.renderers import JSONRenderer


class DreamscapeJSONRenderer(JSONRenderer):
    """
    Custom JSON renderer that wraps all API responses in the standard
    Dreamscape Treks™ success envelope:

    Success:
        { "success": true, "data": {...}, "message": "..." }

    Error (handled by custom_exception_handler):
        { "success": false, "error": { "code": "...", "message": "...", "details": {...} } }

    The renderer detects whether the response is already an error envelope
    (produced by the custom exception handler) and passes it through unchanged,
    otherwise it wraps the data in the success envelope.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        status_code = response.status_code if response else 200

        # If the exception handler already produced the error envelope, pass it through.
        if isinstance(data, dict) and "success" in data:
            return super().render(data, accepted_media_type, renderer_context)

        # Build standard success envelope.
        # Extract an optional "message" key that serializers/views may set on the response.
        message = None
        if response is not None:
            message = getattr(response, "success_message", None)

        if message is None and isinstance(data, dict):
            message = data.pop("message", None)

        envelope = {
            "success": status_code < 400,
            "data": data,
            "message": message or self._default_message(status_code),
        }

        return super().render(envelope, accepted_media_type, renderer_context)

    @staticmethod
    def _default_message(status_code: int) -> str:
        messages = {
            200: "Request successful.",
            201: "Resource created successfully.",
            204: "Resource deleted successfully.",
        }
        return messages.get(status_code, "Request processed.")
