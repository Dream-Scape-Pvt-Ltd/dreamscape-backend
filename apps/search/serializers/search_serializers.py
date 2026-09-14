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
    meta = serializers.JSONField(required=False)


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=200)
    entity_type = serializers.ChoiceField(choices=['trip', 'destination', 'guide', 'faq'], required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SearchResultSerializer(many=True)
