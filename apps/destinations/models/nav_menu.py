from django.db import models

from apps.common.models.base import TimeStampedModel


class MenuType(models.TextChoices):
    CATEGORIES = "CATEGORIES", "Trek categories"
    LINKS = "LINKS", "Links"


class NavigationMenu(TimeStampedModel):
    """
    A top-level menu in the public site header (Treks, Tours, Climbing, …).

    CATEGORIES menus list trek categories and have a catalogue page at
    /treks?kind=<slug>; LINKS menus list the plain links in `links`.
    The intro fields fill the panel on the left of the open menu.
    """

    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=60, unique=True)
    menu_type = models.CharField(max_length=12, choices=MenuType.choices, default=MenuType.CATEGORIES)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    eyebrow = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=120, blank=True)
    intro = models.CharField(max_length=300, blank=True)
    image = models.CharField(max_length=500, blank=True)
    all_label = models.CharField(max_length=80, blank=True)
    href = models.CharField(max_length=300, blank=True, help_text="“Explore all” link for link menus; trek menus use their catalogue page.")
    links = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "navigation_menus"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name
