from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer as SimpleJWTTokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole
from apps.accounts.serializers.user_serializers import UserProfileSerializer

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    JWT token serializer that enriches token payload with user role and full name.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": str(self.user.id),
            "email": self.user.email,
            "role": self.user.role,
            "full_name": self.user.full_name,
        }
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for public customer account creation.
    Enforces password validation, auto-assigns CUSTOMER role,
    and returns JWT tokens upon creation.
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
            "id",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone",
            "whatsapp_number",
        ]
        read_only_fields = ["id"]

    def validate_email(self, value):
        normalized = value.lower().strip()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return normalized

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
            role=UserRole.CUSTOMER,
            **validated_data,
        )
        return user


class LoginSerializer(serializers.Serializer):
    """
    Validates email + password credentials and returns JWT tokens with user profile.
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        email = attrs.get("email", "").lower().strip()
        password = attrs.get("password", "")

        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            # Fallback check in case backend authentication class wasn't explicitly invoked
            try:
                user_obj = User.objects.get(email__iexact=email)
                if user_obj.check_password(password):
                    user = user_obj
            except User.DoesNotExist:
                user = None

        if not user:
            raise serializers.ValidationError({"detail": "Invalid email or password credentials."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "This user account is inactive."})

        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["full_name"] = user.full_name

        return {
            "user": UserProfileSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class TokenRefreshSerializer(SimpleJWTTokenRefreshSerializer):
    """
    Wraps SimpleJWT TokenRefreshSerializer for consistent validation.
    """
    pass


class LogoutSerializer(serializers.Serializer):
    """
    Accepts a refresh token and adds it to the token blacklist.
    """

    refresh = serializers.CharField(required=True)

    def validate(self, attrs):
        self.token = attrs["refresh"]
        return attrs

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.token)
            token.blacklist()
        except Exception as exc:
            raise serializers.ValidationError({"refresh": f"Invalid or expired refresh token: {exc}"})


class PasswordChangeSerializer(serializers.Serializer):
    """
    Allows an authenticated user to change their password by verifying current password.
    """

    current_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "New passwords do not match."})
        user = self.context["request"].user
        validate_password(attrs["new_password"], user=user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Accepts an email address and initiates a password reset flow.
    Always returns success to prevent user enumeration.
    """

    email = serializers.EmailField(required=True)

    def save(self, **kwargs):
        email = self.validated_data["email"].lower().strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # In development/test or until Celery mail worker is wired:
            # We send via Django's standard send_mail
            reset_subject = "Dreamscape Treks — Password Reset Request"
            reset_message = (
                f"Hello {user.full_name},\n\n"
                f"We received a request to reset your password for your Dreamscape Treks account.\n"
                f"Use the following token details to reset your password:\n"
                f"UID: {uid}\n"
                f"Token: {token}\n\n"
                f"If you did not make this request, you can safely ignore this email."
            )
            try:
                send_mail(
                    subject=reset_subject,
                    message=reset_message,
                    from_email="no-reply@dreamscapetreks.com",
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Validates uid + token and resets user password to new_password.
    """

    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "New passwords do not match."})

        try:
            uid_decoded = force_str(urlsafe_base64_decode(attrs["uid"]))
            self.user = User.objects.get(pk=uid_decoded)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uid": "Invalid reset link or user does not exist."})

        if not default_token_generator.check_token(self.user, attrs["token"]):
            raise serializers.ValidationError({"token": "Password reset token is invalid or has expired."})

        validate_password(attrs["new_password"], user=self.user)
        return attrs

    def save(self, **kwargs):
        self.user.set_password(self.validated_data["new_password"])
        self.user.save(update_fields=["password"])
        return self.user
