import re
from html import escape

# The only placeholders a template may use.
VARIABLES = {
    "full_name": "Customer's name",
    "trip_title": "Trip they asked about",
    "inquiry_number": "Inquiry reference",
    "departure_label": "Chosen departure date",
}
_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def unknown_placeholders(*texts):
    found = {name for text in texts for name in _PLACEHOLDER.findall(text or "")}
    return sorted(found - set(VARIABLES))


def render(text, context, *, html):
    """Substitute placeholders; values are HTML-escaped for HTML bodies. Missing values become empty."""
    def sub(match):
        value = str(context.get(match.group(1), "") or "")
        return escape(value) if html else value
    return _PLACEHOLDER.sub(sub, text or "")


def inquiry_context(inquiry):
    departure = inquiry.departure
    return {
        "full_name": inquiry.full_name,
        "trip_title": inquiry.trip.title if inquiry.trip else "",
        "inquiry_number": inquiry.inquiry_number,
        "departure_label": departure.start_date.strftime("%d %b %Y") if departure else "",
    }
