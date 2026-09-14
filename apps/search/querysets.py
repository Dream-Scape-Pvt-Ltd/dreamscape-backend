from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import CharField, F, Q, Value
from django.db.models.functions import Cast, Coalesce, Concat, JSONObject, Substr

from apps.content_cms.models import TravelGuide
from apps.destinations.models import Destination
from apps.faq.models import FAQ
from apps.trips.models import Trip


def global_search_queryset(query_text, entity_type=None):
    """One UNION query: global ranking/pagination without loading all results into Python."""
    query = SearchQuery(query_text.strip())
    sources = [
        ('trip', Trip.objects.filter(is_active=True),
         SearchVector('title', 'slug', weight='A') + SearchVector('overview', weight='B'),
         F('title'), F('slug'), F('overview'), '/trips/',
         JSONObject(duration_days=F('duration_days'),
                    starting_price_usd=Cast('starting_price_usd', CharField()),
                    difficulty_grade=F('difficulty_grade'))),
        ('destination', Destination.objects.filter(is_active=True),
         SearchVector('name', 'region_name', weight='A'),
         F('name'), F('slug'), F('region_name'), '/destinations/', JSONObject(country=F('country'))),
        ('guide', TravelGuide.objects.filter(is_published=True),
         SearchVector('title', weight='A') + SearchVector('markdown_content', weight='C'),
         F('title'), F('slug'), F('markdown_content'), '/guides/', JSONObject(category=F('category'))),
        ('faq', FAQ.objects.filter(is_active=True).filter(
            Q(trip__isnull=True) | Q(trip__is_active=True)).filter(
            Q(destination__isnull=True) | Q(destination__is_active=True)),
         SearchVector('question', weight='B') + SearchVector('answer', weight='C'),
         F('question'), Value(''), F('answer'), '/faq', JSONObject(category=F('category'))),
    ]
    queries = []
    for kind, qs, vector, title, slug, snippet, prefix, meta in sources:
        if entity_type and kind != entity_type:
            continue
        qs = qs.annotate(search_vector=vector, search_rank=SearchRank(vector, query)).filter(search_vector=query)
        # Fixed projection gives all UNION arms identical SQL types and column order.
        queries.append(qs.order_by().values('id').annotate(
            entity_type=Value(kind, output_field=CharField()), title=title, slug=slug,
            snippet=Substr(Coalesce(snippet, Value(''), output_field=CharField()), 1, 160),
            rank_score=F('search_rank'), url=Concat(Value(prefix), slug, output_field=CharField()), meta=meta,
        ))
    if not queries:
        raise ValueError('Unknown search entity type.')
    return queries[0].union(*queries[1:], all=True).order_by('-rank_score', 'entity_type', 'id')
