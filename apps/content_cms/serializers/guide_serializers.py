from rest_framework import serializers

from apps.accounts.serializers.user_serializers import UserMinimalSerializer
from apps.content_cms.models import TravelGuide
from apps.destinations.serializers.destination_serializers import DestinationListSerializer


class TravelGuideListSerializer(serializers.ModelSerializer):
    """
    Serializer for guide index and cards.
    ORM Dependencies: select_related('destination', 'author')
    """

    class Meta:
        model = TravelGuide
        fields = [
            "id",
            "title",
            "slug",
            "category",
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

    destination = DestinationListSerializer(read_only=True)
    author = UserMinimalSerializer(read_only=True)
    schema_org_article = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_schema_org_article(self, obj):
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
                    "url": "https://dreamscape-treks.com/logo.png",
                },
            },
            "mainEntityOfPage": obj.canonical_url or f"https://dreamscape-treks.com/guides/{obj.slug}",
        }
