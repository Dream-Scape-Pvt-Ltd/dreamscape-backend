from rest_framework import serializers
from django.conf import settings

from apps.content_cms.models import TravelGuide
from apps.destinations.models import Destination


class GuideDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ['id', 'name', 'slug']
        read_only_fields = fields


class GuideAuthorSerializer(serializers.Serializer):
    full_name = serializers.CharField(read_only=True)


class TravelGuideListSerializer(serializers.ModelSerializer):
    """
    Serializer for guide index and cards.
    ORM Dependencies: select_related('destination', 'author')
    """

    destination = GuideDestinationSerializer(read_only=True)

    class Meta:
        model = TravelGuide
        fields = [
            "id",
            "title",
            "slug",
            "category",
            "destination",
            "country",
            "region",
            "hero_image_url",
            "is_published",
            "published_at",
        ]
        read_only_fields = fields


class TravelGuideDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Next.js SSR markdown guides with canonical URL and Schema.org Article JSON-LD.
    ORM Dependencies: select_related('destination', 'author')
    """

    destination = GuideDestinationSerializer(read_only=True)
    author = GuideAuthorSerializer(read_only=True)
    schema_org_article = serializers.SerializerMethodField()
    schema_org_breadcrumb = serializers.SerializerMethodField()
    schema_org = serializers.SerializerMethodField()

    class Meta:
        model = TravelGuide
        fields = [
            "id",
            "title",
            "slug",
            "destination",
            "author",
            "country",
            "region",
            "category",
            "markdown_content",
            "hero_image_url",
            "meta_title",
            "meta_description",
            "canonical_url",
            "is_published",
            "published_at",
            "schema_org_article",
            "schema_org_breadcrumb",
            "schema_org",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_schema_org_article(self, obj) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": obj.title,
            "description": obj.meta_description or obj.markdown_content[:200],
            "image": [obj.hero_image_url] if obj.hero_image_url else [],
            "datePublished": obj.published_at.isoformat() if obj.published_at else None,
            "dateModified": obj.updated_at.isoformat(),
            "author": {
                "@type": "Person",
                "name": obj.author.full_name if obj.author else "Dreamscape Editorial Team",
            },
            "publisher": {
                "@type": "Organization",
                "name": "Dreamscape Treks",
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{settings.PUBLIC_SITE_URL}/logo.png",
                },
            },
            "mainEntityOfPage": obj.canonical_url or f"{settings.PUBLIC_SITE_URL}/guides/{obj.slug}",
        }

    def get_schema_org_breadcrumb(self, obj) -> dict:
        return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Guides', 'item': f'{settings.PUBLIC_SITE_URL}/guides'},
            {'@type': 'ListItem', 'position': 2, 'name': obj.title,
             'item': obj.canonical_url or f'{settings.PUBLIC_SITE_URL}/guides/{obj.slug}'},
        ]}

    def get_schema_org(self, obj) -> dict:
        return {'@context': 'https://schema.org', '@graph': [
            self.get_schema_org_article(obj), self.get_schema_org_breadcrumb(obj)]}


class TravelGuideWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelGuide
        fields = ['id', 'destination', 'author', 'title', 'slug', 'country', 'region', 'category',
                  'markdown_content', 'hero_image_url', 'meta_title', 'meta_description',
                  'canonical_url', 'is_published', 'published_at']
        read_only_fields = ['id', 'author', 'published_at']
