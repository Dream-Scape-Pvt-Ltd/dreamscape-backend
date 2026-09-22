from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.inquiries.models import Inquiry, Tag
from apps.inquiries.serializers import TagSerializer


class TagListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/tags/
        List all CRM tags for filter/segmentation UI.

    POST /api/v1/tags/
        Create a new tag.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class InquiryTagView(APIView):
    """
    POST /api/v1/inquiries/{inquiry_number}/tags/
        Attach a tag to an inquiry. Body: { "tag_id": "<uuid>" }.

    DELETE /api/v1/inquiries/{inquiry_number}/tags/{tag_id}/
        Detach a tag from an inquiry.

    Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]

    def post(self, request, inquiry_number, *args, **kwargs):
        inquiry = get_object_or_404(Inquiry, inquiry_number=inquiry_number)
        tag_id = request.data.get("tag_id")
        tag = get_object_or_404(Tag, id=tag_id)
        inquiry.tags.add(tag)
        return Response(TagSerializer(inquiry.tags.all(), many=True).data, status=status.HTTP_200_OK)

    def delete(self, request, inquiry_number, tag_id=None, *args, **kwargs):
        inquiry = get_object_or_404(Inquiry, inquiry_number=inquiry_number)
        tag = get_object_or_404(Tag, id=tag_id)
        inquiry.tags.remove(tag)
        return Response(TagSerializer(inquiry.tags.all(), many=True).data, status=status.HTTP_200_OK)
