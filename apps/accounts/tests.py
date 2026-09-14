from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole

User = get_user_model()


class AuthEndpointTests(APITestCase):
    """
    Test suite for Phase 1 Authentication endpoints:
    Register, Login, Token Refresh, Logout, Password Change, and Password Reset.
    Validates both HTTP status codes and the standard Dreamscape response envelope.
    """

    def setUp(self):
        self.password = "StrongP@ssw0rd123!"
        self.customer = User.objects.create_user(
            email="trekker@example.com",
            password=self.password,
            first_name="Tenzing",
            last_name="Norgay",
            phone="+9779800000001",
            role=UserRole.CUSTOMER,
        )

        self.admin = User.objects.create_superuser(
            email="admin@dreamscapetreks.com",
            password=self.password,
            first_name="Admin",
            last_name="Superuser",
        )

    def test_register_success(self):
        url = reverse("auth:auth-register")
        payload = {
            "email": "edmund@example.com",
            "password": "SecurePassword123!",
            "password_confirm": "SecurePassword123!",
            "first_name": "Edmund",
            "last_name": "Hillary",
            "phone": "+6491234567",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertIn("access", res["data"])
        self.assertIn("refresh", res["data"])
        self.assertEqual(res["data"]["user"]["email"], "edmund@example.com")
        self.assertEqual(res["data"]["user"]["role"], UserRole.CUSTOMER)
        self.assertEqual(res["message"], "Registration successful.")

    def test_register_password_mismatch(self):
        url = reverse("auth:auth-register")
        payload = {
            "email": "mismatch@example.com",
            "password": "SecurePassword123!",
            "password_confirm": "DifferentPassword123!",
            "first_name": "Mismatch",
            "last_name": "User",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res = response.json()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("password_confirm", res["error"]["details"])

    def test_register_duplicate_email(self):
        url = reverse("auth:auth-register")
        payload = {
            "email": "trekker@example.com",  # Already exists in setUp
            "password": "SecurePassword123!",
            "password_confirm": "SecurePassword123!",
            "first_name": "Duplicate",
            "last_name": "User",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res = response.json()
        self.assertFalse(res["success"])

    def test_login_success(self):
        url = reverse("auth:auth-login")
        payload = {
            "email": "trekker@example.com",
            "password": self.password,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertIn("access", res["data"])
        self.assertIn("refresh", res["data"])
        self.assertEqual(res["data"]["user"]["email"], "trekker@example.com")
        self.assertEqual(res["message"], "Login successful.")

    def test_login_invalid_password(self):
        url = reverse("auth:auth-login")
        payload = {
            "email": "trekker@example.com",
            "password": "WrongPassword123!",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res = response.json()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["code"], "VALIDATION_ERROR")

    def test_login_inactive_user(self):
        self.customer.is_active = False
        self.customer.save()

        url = reverse("auth:auth-login")
        payload = {
            "email": "trekker@example.com",
            "password": self.password,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res = response.json()
        self.assertFalse(res["success"])

    def test_token_refresh(self):
        refresh = RefreshToken.for_user(self.customer)
        url = reverse("auth:token-refresh")
        response = self.client.post(url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertIn("access", res["data"])
        self.assertEqual(res["message"], "Token refreshed successfully.")

    def test_logout_blacklists_token(self):
        refresh = RefreshToken.for_user(self.customer)
        self.client.force_authenticate(user=self.customer)

        logout_url = reverse("auth:auth-logout")
        response = self.client.post(logout_url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["message"], "Logged out successfully.")

        # Attempt to refresh using the blacklisted token should fail
        self.client.logout()
        refresh_url = reverse("auth:token-refresh")
        refresh_response = self.client.post(refresh_url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_change_success(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("auth:password-change")
        new_password = "NewSuperPassword987#"
        payload = {
            "current_password": self.password,
            "new_password": new_password,
            "new_password_confirm": new_password,
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["message"], "Password changed successfully.")

        # Verify new password allows login
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(new_password))

    def test_password_change_wrong_current(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("auth:password-change")
        payload = {
            "current_password": "IncorrectPassword!",
            "new_password": "NewSuperPassword987#",
            "new_password_confirm": "NewSuperPassword987#",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        res = response.json()
        self.assertFalse(res["success"])

    def test_password_reset_flow(self):
        # 1. Request reset
        request_url = reverse("auth:password-reset")
        req_response = self.client.post(request_url, {"email": self.customer.email}, format="json")
        self.assertEqual(req_response.status_code, status.HTTP_200_OK)
        res_req = req_response.json()
        self.assertTrue(res_req["success"])
        self.assertEqual(len(mail.outbox), 1)

        # 2. Confirm reset with token
        uid = urlsafe_base64_encode(force_bytes(self.customer.pk))
        token = default_token_generator.make_token(self.customer)

        confirm_url = reverse("auth:password-reset-confirm")
        new_pass = "BrandNewPassword123!"
        confirm_payload = {
            "uid": uid,
            "token": token,
            "new_password": new_pass,
            "new_password_confirm": new_pass,
        }
        confirm_response = self.client.post(confirm_url, confirm_payload, format="json")
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        res_confirm = confirm_response.json()
        self.assertTrue(res_confirm["success"])

        # Verify user can log in with new password
        login_url = reverse("auth:auth-login")
        login_response = self.client.post(login_url, {"email": self.customer.email, "password": new_pass}, format="json")
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)


class UserEndpointTests(APITestCase):
    """
    Test suite for User Profile and Admin User endpoints:
    /api/v1/users/me/ and /api/v1/users/
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            first_name="Sherpa",
            last_name="Guide",
            phone="+9779811111111",
            role=UserRole.CUSTOMER,
        )

        self.admin = User.objects.create_superuser(
            email="admin@dreamscapetreks.com",
            password="Password123!",
            first_name="Admin",
            last_name="Chief",
        )

    def test_get_user_profile_authenticated(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("users:user-profile")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["email"], self.customer.email)
        self.assertEqual(res["data"]["full_name"], "Sherpa Guide")

    def test_get_user_profile_unauthenticated(self):
        url = reverse("users:user-profile")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        res = response.json()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["code"], "NOT_AUTHENTICATED")

    def test_patch_user_profile_self(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("users:user-profile")
        payload = {
            "first_name": "UpdatedSherpa",
            "phone": "+9779899999999",
            "role": UserRole.ADMIN,  # Should be ignored (read-only)
        }
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["first_name"], "UpdatedSherpa")
        self.assertEqual(res["data"]["phone"], "+9779899999999")

        # Confirm role was not escalated
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, UserRole.CUSTOMER)

    def test_admin_list_users_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("users:user-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["data"]["count"], 2)

    def test_admin_list_users_as_customer_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        url = reverse("users:user-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        res = response.json()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"]["code"], "FORBIDDEN")

    def test_admin_get_and_patch_user_detail(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse("users:user-detail", kwargs={"pk": self.customer.pk})

        # GET detail
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res = response.json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["email"], self.customer.email)

        # PATCH role to SALES_AGENT
        patch_response = self.client.patch(url, {"role": UserRole.SALES_AGENT}, format="json")
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        res_patch = patch_response.json()
        self.assertTrue(res_patch["success"])
        self.assertEqual(res_patch["data"]["role"], UserRole.SALES_AGENT)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, UserRole.SALES_AGENT)
