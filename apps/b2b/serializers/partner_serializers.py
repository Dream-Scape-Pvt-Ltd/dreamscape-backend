from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import UserRole
from apps.b2b.models import B2BPartner, AgencyTier

User = get_user_model()


class B2BRegistrationSerializer(serializers.Serializer):
    """
    Onboarding serializer for travel agencies and corporate tour operators.
    Creates User (role=B2B_PARTNER) and linked pending B2BPartner profile atomically.
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    whatsapp_number = serializers.CharField(max_length=50, required=False, allow_blank=True)

    company_name = serializers.CharField(max_length=255)
    country = serializers.CharField(max_length=100)
    registration_number = serializers.CharField(max_length=150, required=False, allow_blank=True)
    website = serializers.URLField(max_length=255, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
                first_name=validated_data["first_name"],
                last_name=validated_data["last_name"],
                phone=validated_data.get("phone", ""),
                whatsapp_number=validated_data.get("whatsapp_number", ""),
                role=UserRole.B2B_PARTNER,
                is_active=True,
            )

            partner = B2BPartner.objects.create(
                user=user,
                company_name=validated_data["company_name"],
                country=validated_data["country"],
                registration_number=validated_data.get("registration_number", ""),
                website=validated_data.get("website", ""),
                agency_tier=AgencyTier.BRONZE,
                commission_rate=0,
                approved=False,
            )
        return partner


class B2BPartnerProfileSerializer(serializers.ModelSerializer):
    """
    B2B Partner profile serializer.
    """

    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = B2BPartner
        fields = [
            "id",
            "email",
            "full_name",
            "company_name",
            "country",
            "registration_number",
            "website",
            "agency_tier",
            "commission_rate",
            "approved",
            "created_at",
        ]
        read_only_fields = ["id", "email", "agency_tier", "commission_rate", "approved", "created_at"]
