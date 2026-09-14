from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, status
from rest_framework.response import Response

from apps.content_cms.models import TravelGuide
from apps.content_cms.serializers.guide_serializers import (
    TravelGuideListSerializer, TravelGuideDetailSerializer, TravelGuideWriteSerializer,
)
from .permissions import IsAdminOrReadOnly, is_editor


class GuideQuerysetMixin:
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = TravelGuide.objects.select_related('author', 'destination').order_by('-published_at', '-created_at', 'id')
        return qs if is_editor(self.request.user) else qs.filter(is_published=True)


@extend_schema(parameters=[OpenApiParameter('destination', str)])
class TravelGuideListCreateView(GuideQuerysetMixin, generics.ListCreateAPIView):
    filterset_fields = ['country', 'category']
    search_fields = ['title', 'markdown_content', 'meta_description']

    def get_serializer_class(self):
        return TravelGuideWriteSerializer if self.request.method == 'POST' else TravelGuideListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        destination = self.request.query_params.get('destination')
        return qs.filter(destination__slug=destination) if destination else qs

    @extend_schema(request=TravelGuideWriteSerializer, responses={201: TravelGuideDetailSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guide = serializer.save(author=request.user)
        return Response(TravelGuideDetailSerializer(guide).data, status=status.HTTP_201_CREATED)


class TravelGuideDetailView(GuideQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = 'slug'
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        return TravelGuideWriteSerializer if self.request.method == 'PATCH' else TravelGuideDetailSerializer

    @extend_schema(request=TravelGuideWriteSerializer, responses=TravelGuideDetailSerializer)
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        guide = self.get_queryset().select_for_update(of=('self',)).get(pk=self.get_object().pk)
        serializer = self.get_serializer(guide, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(TravelGuideDetailSerializer(serializer.save()).data)

    def perform_destroy(self, instance):
        TravelGuide.objects.filter(pk=instance.pk).update(is_published=False, updated_at=timezone.now())
