"""
Stable public URLs for uploaded media.

The B2 bucket is private, so storage URLs are signed and expire. Anything that
gets saved (trek/guide image fields) must use media_url(), which points at the
backend's /media/<key> route; media_redirect() then sends the browser to a
freshly signed B2 URL.
"""
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseRedirect

ALLOWED_PREFIXES = ("media/", "site/")


def media_url(request, name):
    return request.build_absolute_uri(settings.MEDIA_URL + name)


def media_redirect(request, path):
    if ".." in path.split("/") or not path.startswith(ALLOWED_PREFIXES):
        raise Http404
    response = HttpResponseRedirect(default_storage.url(path))
    # Shorter than the signed URL lifetime so a cached redirect never points at an expired link.
    response["Cache-Control"] = f"public, max-age={max(settings.B2_URL_EXPIRE - 600, 60)}"
    return response
