from rest_framework import serializers


class SearchResultSerializer(serializers.Serializer):
    """
    Unified search result representation across trips, destinations, guides, and FAQs.
    """

    entity_type = serializers.ChoiceField(
        choices=["trip", "destination", "guide", "faq"]
    )
    id = serializers.UUIDField()
    title = serializers.CharField()
    slug = serializers.CharField(allow_blank=True, required=False)
    snippet = serializers.CharField(allow_blank=True, required=False)
    rank_score = serializers.FloatField(default=0.0)
    url = serializers.CharField(allow_blank=True, required=False)
