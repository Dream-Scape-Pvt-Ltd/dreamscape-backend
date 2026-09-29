from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.common.permissions import IsAdminRole
from apps.content_cms.models import SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    map_zoom = serializers.IntegerField(min_value=1, max_value=20)

    class Meta:
        model = SiteSettings
        fields = ["city", "area", "address", "map_query", "directions_note", "map_zoom", "journal_title", "journal_description", "featured_story_slug", "home_image_url", "home_image_alt"]


class SiteSettingsView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method in ("GET", "HEAD", "OPTIONS") else [IsAdminRole()]

    def get(self, request):
        return Response(SiteSettingsSerializer(SiteSettings.objects.first() or SiteSettings()).data)

    def patch(self, request):
        instance, _ = SiteSettings.objects.get_or_create(pk=1)
        serializer = SiteSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
