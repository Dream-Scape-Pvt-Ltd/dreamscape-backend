from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.common.throttling import INTERNAL_READ, InternalRequestMiddleware


@override_settings(INTERNAL_API_TOKEN="secret-token")
class InternalRequestMiddlewareTests(SimpleTestCase):
    def run_middleware(self, method="get", **headers):
        request = getattr(RequestFactory(), method)("/api/v1/trips/", REMOTE_ADDR="10.0.0.9", **headers)
        InternalRequestMiddleware(lambda r: r)(request)
        return request

    def test_page_reads_from_frontend_skip_throttling(self):
        request = self.run_middleware(HTTP_X_INTERNAL_TOKEN="secret-token")
        self.assertTrue(request.META.get(INTERNAL_READ))

    def test_forwarded_client_ip_is_used_for_throttling(self):
        request = self.run_middleware("post", HTTP_X_INTERNAL_TOKEN="secret-token", HTTP_X_CLIENT_IP="203.0.113.7")
        self.assertEqual(request.META["REMOTE_ADDR"], "203.0.113.7")
        self.assertEqual(request.META["HTTP_X_FORWARDED_FOR"], "203.0.113.7")
        self.assertNotIn(INTERNAL_READ, request.META)

    def test_writes_without_client_ip_stay_throttled(self):
        request = self.run_middleware("post", HTTP_X_INTERNAL_TOKEN="secret-token")
        self.assertNotIn(INTERNAL_READ, request.META)
        self.assertEqual(request.META["REMOTE_ADDR"], "10.0.0.9")

    def test_wrong_token_changes_nothing(self):
        request = self.run_middleware("post", HTTP_X_INTERNAL_TOKEN="guess", HTTP_X_CLIENT_IP="203.0.113.7")
        self.assertEqual(request.META["REMOTE_ADDR"], "10.0.0.9")
        self.assertNotIn(INTERNAL_READ, self.run_middleware(HTTP_X_INTERNAL_TOKEN="guess").META)

    @override_settings(INTERNAL_API_TOKEN="")
    def test_disabled_when_no_token_configured(self):
        self.assertNotIn(INTERNAL_READ, self.run_middleware(HTTP_X_INTERNAL_TOKEN="").META)
