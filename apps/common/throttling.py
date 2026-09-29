import hmac

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

INTERNAL_READ = "dreamscape.internal_read"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


class InternalRequestMiddleware:
    """
    Requests from the Next.js server all arrive from one IP, which would make every
    visitor share one rate limit. The frontend proves itself with X-Internal-Token:
    - with X-Client-IP (forwarded for form posts, logins…), throttles key on that IP;
    - without it (server-rendered page reads), safe-method requests skip throttling.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = settings.INTERNAL_API_TOKEN
        sent = request.META.get("HTTP_X_INTERNAL_TOKEN", "")
        if token and sent and hmac.compare_digest(sent, token):
            client_ip = request.META.get("HTTP_X_CLIENT_IP", "").strip()
            if client_ip:
                request.META["REMOTE_ADDR"] = client_ip
                request.META["HTTP_X_FORWARDED_FOR"] = client_ip
            elif request.method in SAFE_METHODS:
                request.META[INTERNAL_READ] = True
        return self.get_response(request)


class InternalReadExemptMixin:
    def allow_request(self, request, view):
        if request.META.get(INTERNAL_READ):
            return True
        return super().allow_request(request, view)


class DreamscapeAnonThrottle(InternalReadExemptMixin, AnonRateThrottle):
    pass


class DreamscapeUserThrottle(InternalReadExemptMixin, UserRateThrottle):
    pass


class DreamscapeIPThrottle(InternalReadExemptMixin, SimpleRateThrottle):
    """Keys on client IP for every caller, signed in or not."""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class RegistrationThrottle(DreamscapeAnonThrottle):
    """Throttle rate limiting for account registration (5/hour)."""
    scope = "registration"


class LoginThrottle(DreamscapeAnonThrottle):
    """Throttle rate limiting for login attempts (10/hour)."""
    scope = "login"


class PasswordResetThrottle(DreamscapeAnonThrottle):
    """Throttle rate limiting for password reset requests (3/hour)."""
    scope = "password_reset"


class InquiryThrottle(DreamscapeAnonThrottle):
    """Throttle rate limiting for public inquiry submissions (10/hour)."""
    scope = "inquiry_submit"


class PaymentInitiateThrottle(DreamscapeAnonThrottle):
    """Throttle rate limiting for payment initiations (10/minute)."""
    scope = "payment_initiate"


class SearchThrottle(DreamscapeAnonThrottle):
    """Throttle rate limiting for full-text searches (60/minute)."""
    scope = "search"
