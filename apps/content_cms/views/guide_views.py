from django.db import transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.models import MediaAsset
from apps.common.permissions import IsAdminRole
from apps.content_cms.models import BlogComment, TravelGuide
from apps.content_cms.serializers.guide_serializers import (
    BlogCommentCreateSerializer, BlogCommentSerializer, GuideImageUploadSerializer, TravelGuideListSerializer,
    TravelGuideDetailSerializer, TravelGuideWriteSerializer,
)
from .permissions import IsAdminOrReadOnly, is_editor
from apps.common.lookups import SlugOrIdLookupMixin, ref_filter


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


class TravelGuideDetailView(SlugOrIdLookupMixin, GuideQuerysetMixin, generics.RetrieveUpdateDestroyAPIView):
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
        # ?permanent=true removes the post and its comments; plain DELETE only unpublishes it.
        if self.request.query_params.get("permanent", "").lower() in ("1", "true"):
            instance.delete()
            return
        TravelGuide.objects.filter(pk=instance.pk).update(is_published=False, updated_at=timezone.now())


class GuideViewCountView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        updated = TravelGuide.objects.filter(**ref_filter(slug), is_published=True).update(view_count=F("view_count") + 1)
        if not updated:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        view_count = TravelGuide.objects.values_list("view_count", flat=True).get(**ref_filter(slug))
        return Response({"view_count": view_count})


class GuideImageUploadView(APIView):
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        files = request.FILES.getlist("files")
        if not files:
            return Response({"files": ["Select at least one image."]}, status=status.HTTP_400_BAD_REQUEST)
        if len(files) > 12:
            return Response({"files": ["Upload no more than 12 images at once."]}, status=status.HTTP_400_BAD_REQUEST)

        uploaded = []
        for image in files:
            serializer = GuideImageUploadSerializer(data={"file": image})
            serializer.is_valid(raise_exception=True)
            valid_image = serializer.validated_data["file"]
            asset = MediaAsset.objects.create(
                file=valid_image,
                original_name=valid_image.name[:255],
                mime_type=valid_image.content_type,
                file_size_bytes=valid_image.size,
                uploaded_by=request.user,
            )
            uploaded.append({
                "id": str(asset.id),
                "url": request.build_absolute_uri(asset.file.url),
                "name": asset.original_name,
                "size": asset.file_size_bytes,
            })
        return Response({"files": uploaded}, status=status.HTTP_201_CREATED)


class GuideCommentListCreateView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_guide(self, slug):
        return generics.get_object_or_404(TravelGuide, **ref_filter(slug), is_published=True)

    def get(self, request, slug):
        comments = self.get_guide(slug).comments.filter(is_active=True)
        return Response(BlogCommentSerializer(comments, many=True).data)

    def post(self, request, slug):
        guide = self.get_guide(slug)
        serializer = BlogCommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = BlogComment.objects.create(
            guide=guide,
            user=request.user,
            author_name=request.user.full_name or request.user.email,
            body=serializer.validated_data["body"],
        )
        return Response(BlogCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class GuideCommentDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ["delete", "options"]

    def delete(self, request, slug, comment_id):
        if not is_editor(request.user):
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        updated = BlogComment.objects.filter(id=comment_id, **ref_filter(slug, "guide__"), is_active=True).update(
            is_active=False, updated_at=timezone.now()
        )
        if not updated:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
