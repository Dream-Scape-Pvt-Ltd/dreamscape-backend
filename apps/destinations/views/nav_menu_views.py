from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.exceptions import _build_error_envelope
from apps.common.permissions import IsAdminRole
from apps.destinations.models import ActivityCategory, NavigationMenu
from apps.destinations.serializers.nav_menu_serializers import NavigationMenuSerializer


def _is_admin(request):
    return request.user.is_authenticated and getattr(request.user, "role", None) == "ADMIN"


class _NavigationMenuMixin:
    serializer_class = NavigationMenuSerializer
    pagination_class = None

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAdminRole()]

    def get_throttles(self):
        # Every page render reads the menus (cached by the frontend); only writes count against the rate limit.
        return [] if self.request.method == "GET" else super().get_throttles()

    def get_queryset(self):
        queryset = NavigationMenu.objects.prefetch_related(Prefetch("categories", queryset=ActivityCategory.objects.order_by("sort_order", "name")))
        return queryset if _is_admin(self.request) else queryset.filter(is_active=True)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "include_hidden": _is_admin(self.request)}


class NavigationMenuListCreateView(_NavigationMenuMixin, generics.ListCreateAPIView):
    """The site header's menus in order. Admins also see hidden menus and items, and can add menus."""

    @extend_schema(tags=["Navigation"], responses={200: NavigationMenuSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.success_message = "Navigation menus retrieved successfully."
        return response

    @extend_schema(tags=["Navigation"], request=NavigationMenuSerializer, responses={201: NavigationMenuSerializer})
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.success_message = "Menu created."
        return response


class NavigationMenuDetailView(_NavigationMenuMixin, generics.RetrieveUpdateDestroyAPIView):
    lookup_field = "slug"

    @extend_schema(tags=["Navigation"], responses={200: NavigationMenuSerializer})
    def patch(self, request, *args, **kwargs):
        response = super().patch(request, *args, **kwargs)
        response.success_message = "Menu saved."
        return response

    @extend_schema(tags=["Navigation"], responses={204: OpenApiResponse(description="Menu deleted."), 409: OpenApiResponse(description="Menu still has items.")})
    def delete(self, request, *args, **kwargs):
        menu = self.get_object()
        count = menu.categories.count()
        if count:
            return Response(
                _build_error_envelope(
                    code="MENU_IN_USE",
                    message=f"“{menu.name}” still has {count} item{'s' if count != 1 else ''}. Move or remove them first, or hide the menu instead.",
                    details=None,
                ),
                status=status.HTTP_409_CONFLICT,
            )
        menu.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.success_message = "Menu deleted."
        return response
