from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for authenticated user self-profile management.
    Role and email are strictly read-only to prevent unauthorized privilege escalation.
    """

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "whatsapp_number",
            "role",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "date_joined", "full_name"]


class UserAdminSerializer(serializers.ModelSerializer):
    """
    Admin-only serializer for viewing and updating user accounts,
    including role, staff status, and active status.
    """

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "whatsapp_number",
            "role",
            "is_active",
            "is_staff",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["id", "date_joined", "last_login", "full_name"]


class UserMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight read-only representation for nested relations (agents, authors, reviewers).
    """

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role"]
        read_only_fields = ["id", "email", "full_name", "role"]
