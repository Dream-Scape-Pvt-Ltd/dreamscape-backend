import re

from django.utils.text import slugify
from rest_framework import serializers

from apps.destinations.models import MenuType, NavigationMenu

HREF = re.compile(r"^(/\S*|https://\S+)$")
IMAGE = re.compile(r"^(/images/\S+|/svg/\S+|https://\S+|[\w-]+)$")
MAX_LINKS = 30


class NavigationMenuSerializer(serializers.ModelSerializer):
    """
    A header menu with its items: trek categories for CATEGORIES menus, or the
    stored links for LINKS menus. `slug` and `menu_type` are fixed once created.
    """

    slug = serializers.SlugField(max_length=60, required=False)
    items = serializers.SerializerMethodField()

    class Meta:
        model = NavigationMenu
        fields = ["id", "name", "slug", "menu_type", "sort_order", "is_active", "eyebrow", "title", "intro", "image", "all_label", "href", "links", "items"]

    def get_items(self, menu):
        if menu.menu_type != MenuType.CATEGORIES:
            return []
        categories = menu.categories.all()
        if not self.context.get("include_hidden"):
            categories = [category for category in categories if category.is_active]
        return [{"slug": c.slug, "name": c.name, "description": c.description, "sort_order": c.sort_order, "is_active": c.is_active}
                for c in sorted(categories, key=lambda c: (c.sort_order, c.name))]

    def validate_image(self, value):
        if value and not IMAGE.match(value.strip()):
            raise serializers.ValidationError("Use an /images/ path or an https:// link.")
        return value.strip()

    def validate_href(self, value):
        if value and not HREF.match(value.strip()):
            raise serializers.ValidationError("Links must start with / or https://.")
        return value.strip()

    def validate_links(self, links):
        if not isinstance(links, list) or len(links) > MAX_LINKS:
            raise serializers.ValidationError(f"Provide up to {MAX_LINKS} links.")
        cleaned = []
        for link in links:
            if not isinstance(link, dict):
                raise serializers.ValidationError("Each link needs a title and a link.")
            label, href = str(link.get("label", "")).strip(), str(link.get("href", "")).strip()
            description = str(link.get("description", "")).strip()
            if not label or len(label) > 150 or len(description) > 300 or not HREF.match(href):
                raise serializers.ValidationError("Each link needs a title (up to 150 characters) and a link starting with / or https://.")
            cleaned.append({"label": label, "description": description, "href": href})
        return cleaned

    def validate(self, attrs):
        if self.instance is not None:
            # A menu's address and kind can't change: catalogue links and trek categories depend on them.
            attrs.pop("slug", None)
            attrs.pop("menu_type", None)
            return attrs
        base = slugify(attrs.get("slug") or attrs.get("name", ""))[:50] or "menu"
        slug, n = base, 2
        while NavigationMenu.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        attrs["slug"] = slug
        return attrs
