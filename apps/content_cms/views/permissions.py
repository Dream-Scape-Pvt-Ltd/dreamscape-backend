from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.accounts.models import UserRole


def is_editor(user):
    return user.is_authenticated and user.role == UserRole.ADMIN


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_editor(request.user)
