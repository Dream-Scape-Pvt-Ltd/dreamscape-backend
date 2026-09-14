from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import UserRole
from apps.b2b.models import B2BPartner, AgencyTier
from apps.b2b.tasks import queue_partner_email

User = get_user_model()


class B2BRegistrationSerializer(serializers.Serializer):
    """
    Onboarding serializer for travel agencies and corporate tour operators.
    Creates User (role=B2B_PARTNER) and linked pending B2BPartner profile atomically.
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    whatsapp_number = serializers.CharField(max_length=50, required=False, allow_blank=True)

    company_name = serializers.CharField(max_length=255)
    country = serializers.CharField(max_length=100)
    registration_number = serializers.CharField(max_length=150, required=False, allow_blank=True)
    website = serializers.URLField(max_length=255, required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        validate_password(attrs['password'], user=User(
            email=attrs['email'], first_name=attrs['first_name'], last_name=attrs['last_name']))
        return attrs

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
            queue_partner_email(user.email, 'Dreamscape agency registration received',
                                f'Your application for {partner.company_name} is pending admin approval.')
            if settings.B2B_ADMIN_EMAIL:
                queue_partner_email(settings.B2B_ADMIN_EMAIL, 'New Dreamscape agency application',
                                    f'{partner.company_name} ({partner.country}) has applied. Review partner {partner.pk} in the portal.')
        return partner


class B2BPartnerProfileSerializer(serializers.ModelSerializer):
    """
    B2B Partner profile serializer.
    """

    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True, max_length=50)

    class Meta:
        model = B2BPartner
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
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

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        if 'phone' in user_data:
            User.objects.filter(pk=instance.user_id).update(phone=user_data['phone'])
            instance.user.phone = user_data['phone']
        return super().update(instance, validated_data)


class B2BPartnerAdminSerializer(B2BPartnerProfileSerializer):
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    class Meta(B2BPartnerProfileSerializer.Meta):
        read_only_fields = ['id', 'email', 'created_at']


class B2BPartnerApprovalSerializer(serializers.ModelSerializer):
    approved = serializers.BooleanField(default=True)
    agency_tier = serializers.ChoiceField(choices=AgencyTier.choices, required=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)

    class Meta:
        model = B2BPartner
        fields = ['approved', 'agency_tier', 'commission_rate']


class B2BRegistrationResponseSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    partner_id = serializers.UUIDField()
    company_name = serializers.CharField()
    agency_tier = serializers.CharField()
    approved = serializers.BooleanField()
