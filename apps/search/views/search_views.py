from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.search.querysets import global_search_queryset
from apps.search.serializers.search_serializers import SearchQuerySerializer, SearchResultSerializer, SearchResponseSerializer


class SearchIPThrottle(SimpleRateThrottle):
    scope = 'search'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class UnifiedSearchView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [SearchIPThrottle]
    serializer_class = SearchResultSerializer

    @extend_schema(parameters=[SearchQuerySerializer], responses=SearchResponseSerializer)
    def get(self, request):
        params = SearchQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        query = params.validated_data['q']
        queryset = global_search_queryset(query, params.validated_data.get('entity_type'))
        page = self.paginate_queryset(queryset)
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data['query'] = query
        return response
