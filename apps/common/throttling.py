from rest_framework.throttling import AnonRateThrottle


class RegistrationThrottle(AnonRateThrottle):
    """Throttle rate limiting for account registration (5/hour)."""
    scope = "registration"


class LoginThrottle(AnonRateThrottle):
    """Throttle rate limiting for login attempts (10/hour)."""
    scope = "login"


class PasswordResetThrottle(AnonRateThrottle):
    """Throttle rate limiting for password reset requests (3/hour)."""
    scope = "password_reset"


class InquiryThrottle(AnonRateThrottle):
    """Throttle rate limiting for public inquiry submissions (10/hour)."""
    scope = "inquiry_submit"


class PaymentInitiateThrottle(AnonRateThrottle):
    """Throttle rate limiting for payment initiations (10/minute)."""
    scope = "payment_initiate"


class SearchThrottle(AnonRateThrottle):
    """Throttle rate limiting for full-text searches (60/minute)."""
    scope = "search"
