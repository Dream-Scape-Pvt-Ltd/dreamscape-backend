from .category_views import (
    ActivityCategoryDetailView,
    ActivityCategoryListCreateView,
)
from .nav_menu_views import NavigationMenuDetailView, NavigationMenuListCreateView
from .destination_views import (
    DestinationDetailView,
    DestinationListCreateView,
)

__all__ = [
    "DestinationListCreateView",
    "DestinationDetailView",
    "ActivityCategoryListCreateView",
    "ActivityCategoryDetailView",
    "NavigationMenuListCreateView",
    "NavigationMenuDetailView",
]
