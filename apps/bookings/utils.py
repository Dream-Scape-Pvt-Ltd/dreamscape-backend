import random
import string
from django.utils.timezone import now


def generate_booking_reference() -> str:
    """
    Generate unique human-readable booking reference in format DS-{year}-{suffix}.
    Example: DS-2026-X8B9Q
    """
    year = now().year
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"DS-{year}-{suffix}"
