from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.common.permissions import IsAdminRole
from apps.content_cms.models import SiteSettings


from .website_content_validation import validate_company, validate_partner, validate_gallery


class SiteSettingsSerializer(serializers.ModelSerializer):
    map_zoom = serializers.IntegerField(min_value=1, max_value=20)

    def validate_company_content(self, value):
        return validate_company(value)

    def validate_partner_content(self, value):
        return validate_partner(value)

    def validate_gallery_images(self, value):
        return validate_gallery(value) if value is not None else None

    def update(self, instance, validated_data):
        for key in ['company_content','partner_content']:
            if key in validated_data:
                validated_data[key] = {**getattr(instance,key), **validated_data[key]}
        return super().update(instance, validated_data)

    class Meta:
        model = SiteSettings
        fields = ["home_title","home_description","home_eyebrow","company_title","company_accent","gallery_title","gallery_description","company_content","partner_content","gallery_images","home_caption","home_location","nepal_title","nepal_description","nepal_image","beyond_title","beyond_description","beyond_image","home_filter_destinations","home_filter_difficulties","home_filter_budgets","admin_login_image","featured_video_title","featured_video_description","featured_video_thumbnail","city", "area", "address", "map_query", "directions_note", "map_zoom", "journal_title", "journal_description", "featured_story_slug", "home_image_url", "home_image_alt"]


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
