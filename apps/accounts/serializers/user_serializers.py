from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for public customer account creation.
    Enforces password complexity through Django validators.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone",
            "whatsapp_number",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for authenticated user self-profile management.
    Role is strictly read-only to prevent unauthorized privilege escalation.
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


class UserMinimalSerializer(serializers.ModelSerializer):
    """
    Lightweight read-only representation for nested relations (agents, authors, reviewers).
    """

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role"]
        read_only_fields = ["id", "email", "full_name", "role"]
