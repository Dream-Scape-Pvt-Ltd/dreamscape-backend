from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


class IsAdminRole(BasePermission):
    """
    Grants access only to users with role == ADMIN (superadmin).
    Use for all admin-only CRUD operations (create trips, manage departures, etc.)
    """

    message = "You must be an admin to perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )


class IsSalesAgentOrAdmin(BasePermission):
    """
    Grants access to SALES_AGENT and ADMIN roles.
    Used for CRM inquiry management, viewing all bookings, etc.
    """

    message = "You must be a sales agent or admin to perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.ADMIN, UserRole.SALES_AGENT)
        )


class IsApprovedB2BPartner(BasePermission):
    """
    Grants access only to approved B2B partner accounts.
    Used for partner portal, asset downloads, and commission ledger.
    """

    message = "Your agency account is pending admin approval or you are not a B2B partner."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role != UserRole.B2B_PARTNER:
            return False
        # Check that the partner profile exists and is approved
        return hasattr(request.user, "b2b_profile") and request.user.b2b_profile.approved


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: grants access if the requesting user owns
    the object (obj.customer_user == request.user) or is an ADMIN.

    Usage:
        permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
        # Then call self.check_object_permissions(request, obj) in the view.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role in (UserRole.ADMIN, UserRole.SALES_AGENT):
            return True
        # Direct booking ownership
        if hasattr(obj, "customer_user") and obj.customer_user == request.user:
            return True
        if hasattr(obj, "customer_email") and request.user.email and obj.customer_email.lower() == request.user.email.lower():
            return True
        # Passenger detail ownership via parent booking
        if hasattr(obj, "booking"):
            if obj.booking.customer_user == request.user:
                return True
            if request.user.email and obj.booking.customer_email and obj.booking.customer_email.lower() == request.user.email.lower():
                return True
        if hasattr(obj, "user") and obj.user == request.user:
            return True
        return False


class IsOwnerAgentOrAdmin(BasePermission):
    """
    Grants access to the assigned sales agent, the object owner, or an ADMIN.
    Used for inquiry detail views where the assigned agent should have access.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if request.user.role == UserRole.ADMIN:
            return True
        if request.user.role == UserRole.SALES_AGENT:
            # Assigned agent always has access; other agents can also view leads
            return True
        if hasattr(obj, "customer_user"):
            return obj.customer_user == request.user
        return False
