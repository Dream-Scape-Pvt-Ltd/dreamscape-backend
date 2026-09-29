from unittest import mock

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.common.media import media_redirect, media_url


@override_settings(B2_URL_EXPIRE=3600)
class MediaRedirectTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    @mock.patch("apps.common.media.default_storage")
    def test_redirects_to_signed_storage_url(self, storage):
        storage.url.return_value = "https://b2.example/site/blog/a.jpg?X-Amz-Signature=abc"
        response = media_redirect(self.request, "site/blog/a.jpg")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], storage.url.return_value)
        self.assertEqual(response["Cache-Control"], "public, max-age=3000")
        storage.url.assert_called_once_with("site/blog/a.jpg")

    @mock.patch("apps.common.media.default_storage")
    def test_rejects_unknown_prefix_and_traversal(self, storage):
        for path in ("b2b_assets/contract.pdf", "media/../b2b_assets/x.pdf", "site/../../etc/passwd"):
            with self.subTest(path=path), self.assertRaises(Http404):
                media_redirect(self.request, path)
        storage.url.assert_not_called()

    def test_media_url_is_stable_and_unsigned(self):
        self.assertEqual(media_url(self.request, "media/a.jpg"), "http://testserver/media/media/a.jpg")
