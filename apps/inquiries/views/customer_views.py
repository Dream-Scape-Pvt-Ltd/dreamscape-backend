from django.shortcuts import get_object_or_404
from rest_framework import generics

from apps.common.permissions import IsSalesAgentOrAdmin
from apps.inquiries.models import Customer
from apps.inquiries.serializers import CustomerSerializer


class CustomerDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/crm/customers/{email}/
        Customer-360: identity, lifetime stats, and every inquiry + booking
        made under this email address.
        Permissions: IsSalesAgentOrAdmin.
    """

    permission_classes = [IsSalesAgentOrAdmin]
    serializer_class = CustomerSerializer

    def get_object(self):
        email = self.kwargs.get("email", "").strip().lower()
        return get_object_or_404(Customer, email=email)
