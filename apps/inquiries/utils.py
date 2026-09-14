import random
from django.utils.timezone import now


def generate_inquiry_number() -> str:
    """
    Generate unique human-readable inquiry lead number in format INQ-{year}-{suffix}.
    Example: INQ-2026-4821
    """
    year = now().year
    suffix = random.randint(1000, 9999)
    return f"INQ-{year}-{suffix}"
