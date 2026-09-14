from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTTokenRefreshView

from apps.accounts.serializers.auth_serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TokenRefreshSerializer,
    UserRegistrationSerializer,
)
from apps.accounts.serializers.user_serializers import UserProfileSerializer
from apps.common.throttling import (
    LoginThrottle,
    PasswordResetThrottle,
    RegistrationThrottle,
)


class RegisterView(APIView):
    """
    Public customer account registration.
    Creates a new user with CUSTOMER role and returns an access/refresh JWT token pair.
    """

    permission_classes = [AllowAny]
    throttle_classes = [RegistrationThrottle]

    @extend_schema(
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(description="Registration successful. Returns user profile and JWT pair."),
            400: OpenApiResponse(description="Validation error (mismatched password or email in use)."),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["full_name"] = user.full_name

        data = {
            "user": UserProfileSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
        response = Response(data, status=status.HTTP_201_CREATED)
        response.success_message = "Registration successful."
        return response


class LoginView(APIView):
    """
    Authenticates user with email and password, returning JWT access/refresh tokens.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="Login successful. Returns user profile and JWT pair."),
            400: OpenApiResponse(description="Invalid credentials or inactive account."),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        response.success_message = "Login successful."
        return response


class TokenRefreshView(SimpleJWTTokenRefreshView):
    """
    Refreshes an expired access token using a valid refresh token.
    """

    serializer_class = TokenRefreshSerializer

    @extend_schema(
        tags=["Auth"],
        responses={
            200: OpenApiResponse(description="Token refreshed successfully."),
            401: OpenApiResponse(description="Token is invalid or expired."),
        },
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            response.success_message = "Token refreshed successfully."
        return response


class LogoutView(APIView):
    """
    Logs out the authenticated user by blacklisting their refresh token.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutSerializer,
        responses={
            200: OpenApiResponse(description="Logged out successfully."),
            400: OpenApiResponse(description="Invalid or expired refresh token."),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response = Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )
        response.success_message = "Logged out successfully."
        return response


class PasswordChangeView(APIView):
    """
    Changes the authenticated user's password after verifying their current password.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully."),
            400: OpenApiResponse(description="Validation error or incorrect current password."),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response = Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )
        response.success_message = "Password changed successfully."
        return response


class PasswordResetRequestView(APIView):
    """
    Initiates a password reset flow by sending a reset email if the account exists.
    Always returns HTTP 200 to prevent user enumeration.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Reset instructions dispatched if the account exists.",
            ),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response = Response(
            {"message": "If an account exists with this email, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )
        response.success_message = "If an account exists with this email, a password reset link has been sent."
        return response


class PasswordResetConfirmView(APIView):
    """
    Confirms password reset using uid and token, setting a new password.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successful."),
            400: OpenApiResponse(description="Invalid or expired reset token."),
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response = Response(
            {"message": "Password reset successful. You can now log in with your new password."},
            status=status.HTTP_200_OK,
        )
        response.success_message = "Password reset successful. You can now log in with your new password."
        return response
