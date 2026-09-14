"""
Temporary test views for Phase 0 verification only.
These views are NOT part of the production API and will be removed after Phase 0 testing.

URLs registered in config/urls.py under /api/v1/_test/ prefix, guarded by DEBUG mode.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status


class TestPublicView(APIView):
    """Returns a success envelope. Used to verify DreamscapeJSONRenderer."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"key": "value", "number": 42})


class TestProtectedView(APIView):
    """Requires authentication. Used to verify 401 error envelope from JWT."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": str(request.user)})


class TestValidationView(APIView):
    """Raises a DRF ValidationError. Used to verify 400 error envelope."""
    permission_classes = [AllowAny]

    def post(self, request):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({
            "email": ["This field is required."],
            "password": ["This field may not be blank."],
        })
