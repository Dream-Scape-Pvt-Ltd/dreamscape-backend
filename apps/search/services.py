from typing import List, Dict, Any
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Value, F

from apps.destinations.models import Destination
from apps.trips.models import Trip
from apps.content_cms.models import TravelGuide
from apps.faq.models import FAQ


def perform_global_search(query_text: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Executes PostgreSQL full-text search across Trip, Destination, TravelGuide, and FAQ models,
    applying weighted ranking (A=1.0, B=0.4, C=0.2, D=0.1) and returns a unified ranked result list.
    """
    if not query_text or not query_text.strip():
        return []

    search_query = SearchQuery(query_text.strip())
    results: List[Dict[str, Any]] = []

    # 1. Search Trips (title, slug: A; overview: B)
    trip_vector = (
        SearchVector("title", weight="A")
        + SearchVector("slug", weight="A")
        + SearchVector("overview", weight="B")
    )
    trips = (
        Trip.objects.filter(is_active=True)
        .annotate(rank=SearchRank(trip_vector, search_query))
        .filter(rank__gt=0.01)
        .order_by("-rank")[:limit]
    )
    for t in trips:
        results.append({
            "entity_type": "trip",
            "id": t.id,
            "title": t.title,
            "slug": t.slug,
            "snippet": t.overview[:160] + "..." if len(t.overview) > 160 else t.overview,
            "rank_score": round(float(t.rank), 4),
            "url": f"/trips/{t.slug}",
        })

    # 2. Search Destinations (name, region_name: A)
    dest_vector = (
        SearchVector("name", weight="A")
        + SearchVector("region_name", weight="A")
    )
    destinations = (
        Destination.objects.filter(is_active=True)
        .annotate(rank=SearchRank(dest_vector, search_query))
        .filter(rank__gt=0.01)
        .order_by("-rank")[:limit]
    )
    for d in destinations:
        snippet = f"Explore {d.name}, {d.region_name} ({d.country})"
        results.append({
            "entity_type": "destination",
            "id": d.id,
            "title": d.name,
            "slug": d.slug,
            "snippet": snippet,
            "rank_score": round(float(d.rank), 4),
            "url": f"/destinations/{d.slug}",
        })

    # 3. Search Travel Guides (title: A; markdown_content: C)
    guide_vector = (
        SearchVector("title", weight="A")
        + SearchVector("markdown_content", weight="C")
    )
    guides = (
        TravelGuide.objects.filter(is_published=True)
        .annotate(rank=SearchRank(guide_vector, search_query))
        .filter(rank__gt=0.01)
        .order_by("-rank")[:limit]
    )
    for g in guides:
        results.append({
            "entity_type": "guide",
            "id": g.id,
            "title": g.title,
            "slug": g.slug,
            "snippet": g.meta_description or (g.markdown_content[:160] + "..."),
            "rank_score": round(float(g.rank), 4),
            "url": f"/guides/{g.slug}",
        })

    # 4. Search FAQs (question: B; answer: C)
    faq_vector = (
        SearchVector("question", weight="B")
        + SearchVector("answer", weight="C")
    )
    faqs = (
        FAQ.objects.filter(is_active=True)
        .annotate(rank=SearchRank(faq_vector, search_query))
        .filter(rank__gt=0.01)
        .order_by("-rank")[:limit]
    )
    for f in faqs:
        results.append({
            "entity_type": "faq",
            "id": f.id,
            "title": f.question,
            "slug": "",
            "snippet": f.answer[:160] + "..." if len(f.answer) > 160 else f.answer,
            "rank_score": round(float(f.rank), 4),
            "url": f"/faq",
        })

    # Sort combined results by rank descending
    results.sort(key=lambda r: r["rank_score"], reverse=True)
    return results[:limit]
