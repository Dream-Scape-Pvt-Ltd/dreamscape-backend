"""
Dreamscape Treks™ — Root URL Configuration
All API endpoints are versioned under /api/v1/
API Docs: /api/v1/schema/swagger/ | /api/v1/schema/redoc/
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # -----------------------------------------------------------------------
    # API v1 — Auth & Accounts
    # -----------------------------------------------------------------------
    path("api/v1/auth/", include("apps.accounts.urls.auth_urls")),
    path("api/v1/users/", include("apps.accounts.urls.user_urls")),

    # -----------------------------------------------------------------------
    # API v1 — Core Catalog (Phase 2)
    # -----------------------------------------------------------------------
    path("api/v1/destinations/", include("apps.destinations.urls")),
    path("api/v1/trips/", include("apps.trips.urls")),

    # -----------------------------------------------------------------------
    # API v1 — Commerce (Phase 3 & 4)
    # -----------------------------------------------------------------------
    path("api/v1/bookings/", include("apps.bookings.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),

    # -----------------------------------------------------------------------
    # API v1 — CRM & Inquiries (Phase 5)
    # -----------------------------------------------------------------------
    path("api/v1/inquiries/", include("apps.inquiries.urls")),

    # -----------------------------------------------------------------------
    # API v1 — B2B Partner Portal (Phase 6)
    # -----------------------------------------------------------------------
    path("api/v1/b2b/", include("apps.b2b.urls")),

    # -----------------------------------------------------------------------
    # API v1 — Content, FAQs & Search (Phase 7)
    # -----------------------------------------------------------------------
    path("api/v1/content/", include("apps.content_cms.urls")),
    path("api/v1/faqs/", include("apps.faq.urls")),
    path("api/v1/search/", include("apps.search.urls")),

    # -----------------------------------------------------------------------
    # API Documentation (drf-spectacular)
    # -----------------------------------------------------------------------
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/v1/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# ---------------------------------------------------------------------------
# DEBUG-only: Phase 0 verification endpoints
# Remove after Phase 0 testing is complete.
# ---------------------------------------------------------------------------
if settings.DEBUG:
    from apps.common.test_views import TestPublicView, TestProtectedView, TestValidationView
    urlpatterns += [
        path("api/v1/_test/public/", TestPublicView.as_view(), name="test-public"),
        path("api/v1/_test/protected/", TestProtectedView.as_view(), name="test-protected"),
        path("api/v1/_test/validation/", TestValidationView.as_view(), name="test-validation"),
    ]
