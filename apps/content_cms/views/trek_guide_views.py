from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response

from apps.content_cms.models import TrekGuide
from apps.content_cms.serializers.trek_guide_serializers import (
    TrekGuideDetailSerializer,
    TrekGuideListSerializer,
    TrekGuideWriteSerializer,
)
from .permissions import IsAdminOrReadOnly, is_editor
from apps.common.lookups import SlugOrIdLookupMixin


class TrekGuideQuerysetMixin:
    """Admins see drafts too; everyone else sees published guides only."""

    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = TrekGuide.objects.prefetch_related("regions", "treks_led__destination", "treks_led__category")
        return qs if is_editor(self.request.user) else qs.filter(is_published=True)


class TrekGuideListCreateView(TrekGuideQuerysetMixin, generics.ListCreateAPIView):
    search_fields = ["name", "role", "bio"]

    def get_serializer_class(self):
        return TrekGuideWriteSerializer if self.request.method == "POST" else TrekGuideListSerializer

    @extend_schema(request=TrekGuideWriteSerializer, responses=TrekGuideDetailSerializer)
    def post(self, request, *args, **kwargs):
        serializer = TrekGuideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guide = serializer.save()
        return Response(TrekGuideDetailSerializer(guide).data, status=status.HTTP_201_CREATED)


class TrekGuideDetailView(SlugOrIdLookupMixin, TrekGuideQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = "slug"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        return TrekGuideWriteSerializer if self.request.method == "PATCH" else TrekGuideDetailSerializer

    @extend_schema(request=TrekGuideWriteSerializer, responses=TrekGuideDetailSerializer)
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        guide = TrekGuide.objects.select_for_update().get(pk=self.get_object().pk)
        serializer = TrekGuideWriteSerializer(guide, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(TrekGuideDetailSerializer(serializer.save()).data)

    def perform_destroy(self, instance):
        # ?permanent=true removes the profile; plain DELETE only unpublishes it.
        if self.request.query_params.get("permanent", "").lower() in ("1", "true"):
            instance.delete()
            return
        TrekGuide.objects.filter(pk=instance.pk).update(is_published=False, updated_at=timezone.now())
