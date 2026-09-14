from apps.search.querysets import global_search_queryset


def perform_global_search(query_text: str, limit: int = 20, entity_type: str | None = None) -> list[dict]:
    """Bounded helper for internal callers; the API paginates the same ranked queryset."""
    if not query_text or not query_text.strip() or limit <= 0:
        return []
    return list(global_search_queryset(query_text, entity_type)[:limit])
