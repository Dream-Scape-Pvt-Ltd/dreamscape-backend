from uuid import UUID


def trip_lookup(reference):
    """Keep CMS slug URLs compatible with public UUID links."""
    try:
        return {"id": UUID(str(reference))}
    except (ValueError, TypeError, AttributeError):
        return {"slug": reference}
