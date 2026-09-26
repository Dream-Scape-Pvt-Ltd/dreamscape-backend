"""
Look content up by its UUID or its slug through the same URL.

Public pages address treks, destinations, journal posts and guides by id
(`/treks?id=<uuid>`), while older links and admin tools still use slugs. The
`<slug:…>` URL converter already accepts UUID strings, so views only need to
decide which field to filter on.
"""
import uuid

from django.shortcuts import get_object_or_404


def ref_filter(value, prefix=""):
    """Filter kwargs for a URL reference: `{prefix}pk` for a UUID, otherwise `{prefix}slug`."""
    try:
        return {f"{prefix}pk": uuid.UUID(str(value))}
    except ValueError:
        return {f"{prefix}slug": value}


class SlugOrIdLookupMixin:
    """For views whose URL captures `slug`: the value may also be the object's UUID."""

    lookup_url_kwarg = "slug"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, **ref_filter(self.kwargs[self.lookup_url_kwarg]))
        self.check_object_permissions(self.request, obj)
        return obj
