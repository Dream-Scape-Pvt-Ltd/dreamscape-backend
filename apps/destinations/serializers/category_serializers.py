from rest_framework import serializers
from apps.destinations.models import ActivityCategory, MenuType, NavigationMenu


class ActivityCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for activity filter chips and category management.
    `menu` is the slug of the header menu the category is listed under.
    """

    menu = serializers.SlugRelatedField(slug_field="slug", queryset=NavigationMenu.objects.all(), allow_null=True, required=False)

    class Meta:
        model = ActivityCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "menu",
            "sort_order",
        ]
        # DRF's automatic (menu, name) check would make `menu` required; validate() does it instead.
        validators = []

    def validate_menu(self, menu):
        if menu and menu.menu_type != MenuType.CATEGORIES:
            raise serializers.ValidationError("This menu lists links, not trek categories.")
        return menu

    def validate(self, attrs):
        menu = attrs.get("menu", getattr(self.instance, "menu", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if menu and name:
            clash = ActivityCategory.objects.filter(menu=menu, name=name)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"name": f"“{name}” is already in the {menu.name} menu."})
        return attrs
