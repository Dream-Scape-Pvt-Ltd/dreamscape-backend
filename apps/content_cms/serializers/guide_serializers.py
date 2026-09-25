from rest_framework import serializers
from django.conf import settings
from django.utils.text import slugify

from apps.content_cms.models import BlogComment, TravelGuide
from apps.destinations.models import Destination


class GuideDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ['id', 'name', 'slug']
        read_only_fields = fields


class GuideAuthorSerializer(serializers.Serializer):
    full_name = serializers.CharField(read_only=True)


class BlogCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogComment
        fields = ["id", "author_name", "body", "created_at"]
        read_only_fields = fields


class BlogCommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=2000, trim_whitespace=True)

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Please enter a comment.")
        return value.strip()


class GuideImageUploadSerializer(serializers.Serializer):
    file = serializers.ImageField()

    def validate_file(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Each image must be 10 MB or smaller.")
        if value.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise serializers.ValidationError("Upload a JPG, PNG, or WebP image.")
        return value


class TravelGuideListSerializer(serializers.ModelSerializer):
    """
    Serializer for guide index and cards.
    ORM Dependencies: select_related('destination', 'author')
    """

    destination = GuideDestinationSerializer(read_only=True)
    comment_count = serializers.SerializerMethodField()

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
            "gallery_images",
            "is_published",
            "published_at",
            "updated_at",
            "view_count",
            "comment_count",
        ]
        read_only_fields = fields

    def get_comment_count(self, obj) -> int:
        return obj.comments.filter(is_active=True).count()


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
    comments = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

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
            "sections",
            "hero_image_url",
            "gallery_images",
            "meta_title",
            "meta_description",
            "canonical_url",
            "is_published",
            "published_at",
            "view_count",
            "comment_count",
            "comments",
            "schema_org_article",
            "schema_org_breadcrumb",
            "schema_org",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_comments(self, obj):
        return BlogCommentSerializer(obj.comments.filter(is_active=True), many=True).data

    def get_comment_count(self, obj) -> int:
        return obj.comments.filter(is_active=True).count()

    def get_schema_org_article(self, obj) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": obj.title,
            "description": obj.meta_description or obj.markdown_content[:200],
            "image": ([obj.hero_image_url] if obj.hero_image_url else [])
            + [s["image_url"] for s in obj.sections or [] if s.get("image_url")]
            + list(obj.gallery_images or []),
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


SECTION_LIMITS = {"heading": 200, "body": 20000, "image_url": 500, "image_caption": 300}
MAX_SECTIONS = 30


def sections_to_markdown(sections):
    """The Markdown mirror of a sectioned article: `## heading` then the section's text."""
    blocks = []
    for section in sections:
        if section["heading"]:
            blocks.append(f"## {section['heading']}")
        if section["body"]:
            blocks.append(section["body"])
    return "\n\n".join(blocks)


class TravelGuideWriteSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True, max_length=255)
    # Optional on the wire: a sectioned article rebuilds it from its sections.
    markdown_content = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = TravelGuide
        fields = ['id', 'destination', 'author', 'title', 'slug', 'country', 'region', 'category',
                  'markdown_content', 'sections', 'hero_image_url', 'gallery_images', 'meta_title',
                  'meta_description', 'canonical_url', 'is_published', 'published_at']
        read_only_fields = ['id', 'author', 'published_at']

    def validate_sections(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Sections must be a list.")
        if len(value) > MAX_SECTIONS:
            raise serializers.ValidationError(f"An article can have at most {MAX_SECTIONS} sections.")
        cleaned = []
        for index, raw in enumerate(value, start=1):
            if not isinstance(raw, dict):
                raise serializers.ValidationError(f"Section {index} is not valid.")
            section = {}
            for key, limit in SECTION_LIMITS.items():
                text = raw.get(key) or ""
                if not isinstance(text, str):
                    raise serializers.ValidationError(f"Section {index}: {key.replace('_', ' ')} must be text.")
                text = text.strip()
                if len(text) > limit:
                    raise serializers.ValidationError(
                        f"Section {index}: {key.replace('_', ' ')} is longer than {limit} characters."
                    )
                section[key] = text
            url = section["image_url"]
            if url and not (url.startswith(("https://", "http://")) or (url.startswith("/") and not url.startswith("//"))):
                raise serializers.ValidationError(f"Section {index}: the photo link is not valid.")
            if not (section["heading"] or section["body"] or url):
                continue  # A completely empty card is dropped, not an error.
            cleaned.append(section)
        return cleaned

    def validate(self, attrs):
        if "sections" in attrs and attrs["sections"]:
            attrs["markdown_content"] = sections_to_markdown(attrs["sections"])
        elif self.instance is None and not (attrs.get("markdown_content") or "").strip():
            raise serializers.ValidationError({"sections": "Add at least one section to the article."})
        elif "markdown_content" in attrs and not attrs["markdown_content"].strip() and not attrs.get("sections"):
            raise serializers.ValidationError({"sections": "Add at least one section to the article."})
        return attrs

    def create(self, validated_data):
        if not validated_data.get("slug"):
            base = slugify(validated_data["title"])[:240] or "blog-post"
            candidate = base
            suffix = 2
            while TravelGuide.objects.filter(slug=candidate).exists():
                candidate = f"{base[:240 - len(str(suffix))]}-{suffix}"
                suffix += 1
            validated_data["slug"] = candidate
        return super().create(validated_data)
