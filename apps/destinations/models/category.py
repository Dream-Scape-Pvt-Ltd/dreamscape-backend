from django.db import models
from apps.common.models.base import TimeStampedModel


class ActivityCategory(TimeStampedModel):
    """
    A trip's category. Categories with a `menu` are the sub-items of that
    header menu on the public site; `description` is their subtitle there.
    """

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    menu = models.ForeignKey("destinations.NavigationMenu", null=True, blank=True, on_delete=models.PROTECT, related_name="categories")
    sort_order = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        db_table = "activity_categories"
        ordering = ["menu__sort_order", "sort_order", "name"]
        # The same label may appear under two menus (e.g. "Everest Region" in Treks and Climbing).
        constraints = [models.UniqueConstraint(fields=["menu", "name"], name="category_menu_name_unique")]
        verbose_name_plural = "Activity Categories"

    def __str__(self):
        return self.name
