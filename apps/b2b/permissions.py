from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole
from apps.common.exceptions import PartnerUnapprovedError


class IsPartner(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role == UserRole.B2B_PARTNER
                    and hasattr(request.user, "b2b_profile"))


class IsApprovedPartnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role == UserRole.ADMIN:
            return True
        if not IsPartner().has_permission(request, view):
            return False
        if not request.user.b2b_profile.approved:
            raise PartnerUnapprovedError()
        return True
