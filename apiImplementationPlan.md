# DREAMSCAPE TREKS™ — API IMPLEMENTATION PLAN
**Reference:** [`apidesign.md`](./apidesign.md)  
**Database Reference:** [`databaseplan.md`](./databaseplan.md)  
**Stack:** Django 5.x · DRF · PostgreSQL 16 · Redis · Celery · `drf-spectacular`

> [!IMPORTANT]
> This plan assumes all **models and migrations are already complete** across all apps.
> Each phase builds on the previous. Do not start a phase until all items in the preceding phase are verified.

---

## Phase Overview

| Phase | Domain | Endpoints | Priority | Est. Complexity |
| :---: | :--- | :---: | :--- | :---: |
| **0** | Infrastructure & DRF Foundation | 0 | Blocker for everything | 🟡 Medium |
| **1** | Auth & Accounts | 10 | Critical path | 🟡 Medium |
| **2** | Core Catalog (Public Read) | 18 | Revenue-facing | 🔴 High |
| **3** | Booking Engine (Commerce) | 7 | Revenue-critical | 🔴 High |
| **4** | Payments & Gateways | 6 | Revenue-critical | 🔴 High |
| **5** | CRM & Inquiries | 6 | Lead pipeline | 🟡 Medium |
| **6** | B2B Partner Portal | 8 | Partner channel | 🟡 Medium |
| **7** | Content, FAQs & Search | 9 | SEO & Discoverability | 🟢 Low–Medium |

**Total Endpoints:** 64

---

## Dependency Map

```
Phase 0 (Foundation)
    └── Phase 1 (Auth)
            ├── Phase 2 (Catalog) ──────────────────────┐
            │       └── Phase 3 (Bookings) ─────────┐   │
            │               └── Phase 4 (Payments)   │   │
            └── Phase 5 (Inquiries)                  │   │
            └── Phase 6 (B2B) ──── depends on Phase 3┘   │
            └── Phase 7 (Content & Search) ───────────────┘
```

---

## Phase 0 — Infrastructure & DRF Foundation

> **Goal:** Wire up the DRF project configuration, custom response envelopes, authentication backend, throttling, and API documentation. No business logic yet — only scaffolding.

### 0.1 — DRF Settings Configuration

**File:** `config/settings/base.py`

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.StandardResultsPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/day',
        'user': '2000/day',
        'registration': '5/hour',
        'login': '10/hour',
        'password_reset': '3/hour',
        'inquiry_submit': '10/hour',
        'payment_initiate': '10/minute',
        'search': '60/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=14),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Dreamscape Treks™ API',
    'DESCRIPTION': 'Multi-Destination Trekking & Expedition Platform API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}
```

### 0.2 — Custom Response Envelope Renderer

**New File:** `apps/common/renderers.py`

- Create `DreamscapeJSONRenderer(JSONRenderer)` that wraps every response in:
  ```json
  { "success": true/false, "data": ..., "message": ... }
  ```
- Register as the global renderer in `REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']`.

### 0.3 — Custom Pagination

**New File:** `apps/common/pagination.py`

- Create `StandardResultsPagination(PageNumberPagination)`:
  - `page_size = 20`
  - `page_size_query_param = 'page_size'`
  - `max_page_size = 100`

### 0.4 — Custom Exception Handler

**New File:** `apps/common/exceptions.py`

- Create `custom_exception_handler(exc, context)` that maps DRF exceptions to the standard error envelope:
  ```json
  { "success": false, "error": { "code": "...", "message": "...", "details": {...} } }
  ```
- Register via `REST_FRAMEWORK['EXCEPTION_HANDLER']`.

### 0.5 — API Root URL Configuration

**File:** `config/urls.py`

```python
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls.auth_urls')),
    path('api/v1/users/', include('apps.accounts.urls.user_urls')),
    path('api/v1/destinations/', include('apps.destinations.urls')),
    path('api/v1/trips/', include('apps.trips.urls')),
    path('api/v1/bookings/', include('apps.bookings.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/inquiries/', include('apps.inquiries.urls')),
    path('api/v1/b2b/', include('apps.b2b.urls')),
    path('api/v1/content/', include('apps.content_cms.urls')),
    path('api/v1/faqs/', include('apps.faq.urls')),
    path('api/v1/search/', include('apps.search.urls')),
    # API Docs
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

### 0.6 — CORS Configuration

**Dependency:** `pip install django-cors-headers`  
**File:** `config/settings/base.py`

```python
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=['http://localhost:3000'])
CORS_ALLOW_CREDENTIALS = True
```

### Phase 0 Checklist

- [ ] `apps/common/renderers.py` — `DreamscapeJSONRenderer`
- [ ] `apps/common/pagination.py` — `StandardResultsPagination`
- [ ] `apps/common/exceptions.py` — `custom_exception_handler`
- [ ] `config/settings/base.py` — DRF + JWT + Spectacular settings
- [ ] `config/urls.py` — All 12 app URL includes + Swagger/ReDoc
- [ ] Install: `djangorestframework-simplejwt`, `drf-spectacular`, `django-cors-headers`
- [ ] Verify: `GET /api/v1/schema/swagger/` renders without error

---

## Phase 1 — Auth & Accounts

> **Goal:** Full JWT authentication flow — registration, login, token lifecycle, password management, and user profile management.

**Apps touched:** `apps.accounts`

### 1.1 — URL Structure

**New File:** `apps/accounts/urls/auth_urls.py`
```python
urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]
```

**New File:** `apps/accounts/urls/user_urls.py`
```python
urlpatterns = [
    path('me/', UserProfileView.as_view(), name='user-profile'),
    path('', UserListView.as_view(), name='user-list'),           # Admin only
    path('<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),  # Admin only
]
```

### 1.2 — Serializers

**File:** `apps/accounts/serializers/auth_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `UserRegistrationSerializer` | Validates email uniqueness, password strength, `password_confirm` match. Creates `CUSTOMER` role user. Returns tokens on success. |
| `LoginSerializer` | Validates `email` + `password`, returns JWT pair + user summary. |
| `TokenRefreshSerializer` | Wraps `simplejwt` token refresh. |
| `LogoutSerializer` | Accepts `refresh` token, adds to blacklist. |
| `PasswordChangeSerializer` | Validates `current_password`, sets new password. |
| `PasswordResetRequestSerializer` | Accepts `email`, triggers Celery reset email task. |
| `PasswordResetConfirmSerializer` | Validates signed reset token + new password. |

**File:** `apps/accounts/serializers/user_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `UserProfileSerializer` | Read/Write for `/users/me/`. `role`, `email` are read-only. |
| `UserAdminSerializer` | Admin-only write for `role`, `is_active`, `is_staff`. |
| `UserMinimalSerializer` | Embedded author/agent rep: `id`, `full_name`, `email`, `role`. |

### 1.3 — Views

**New File:** `apps/accounts/views/auth_views.py`

| View | Method | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `RegisterView` | POST | `/auth/register/` | `AllowAny` + `RegistrationThrottle` |
| `LoginView` | POST | `/auth/login/` | `AllowAny` + `LoginThrottle` |
| `TokenRefreshView` | POST | `/auth/token/refresh/` | `AllowAny` (simplejwt) |
| `LogoutView` | POST | `/auth/logout/` | `IsAuthenticated` |
| `PasswordChangeView` | POST | `/auth/password/change/` | `IsAuthenticated` |
| `PasswordResetRequestView` | POST | `/auth/password/reset/` | `AllowAny` + `PasswordResetThrottle` |
| `PasswordResetConfirmView` | POST | `/auth/password/reset/confirm/` | `AllowAny` |

**New File:** `apps/accounts/views/user_views.py`

| View | Method | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `UserProfileView` | GET, PATCH | `/users/me/` | `IsAuthenticated` |
| `UserListView` | GET | `/users/` | `IsAdminUser` |
| `UserDetailView` | GET, PATCH | `/users/{id}/` | `IsAdminUser` |

### 1.4 — Custom Permissions

**New File:** `apps/common/permissions.py`

```python
class IsAdminRole(BasePermission): ...        # role == ADMIN
class IsSalesAgentRole(BasePermission): ...   # role in [ADMIN, SALES_AGENT]
class IsB2BPartnerRole(BasePermission): ...   # role == B2B_PARTNER, approved == True
class IsOwnerOrAdmin(BasePermission): ...     # obj.customer_user == request.user OR ADMIN
```

### Phase 1 Checklist

- [ ] `apps/accounts/urls/__init__.py`, `auth_urls.py`, `user_urls.py`
- [ ] `apps/accounts/serializers/auth_serializers.py` — 7 serializers
- [ ] `apps/accounts/serializers/user_serializers.py` — 3 serializers
- [ ] `apps/accounts/views/auth_views.py` — 7 views
- [ ] `apps/accounts/views/user_views.py` — 3 views
- [ ] `apps/common/permissions.py` — 4 custom permission classes
- [ ] Verify: `POST /api/v1/auth/register/` returns JWT + user data
- [ ] Verify: `POST /api/v1/auth/login/` returns JWT pair
- [ ] Verify: `GET /api/v1/users/me/` returns profile for authenticated user
- [ ] Verify: Unauthenticated `GET /api/v1/users/me/` returns `401`

---

## Phase 2 — Core Catalog (Public Read Layer)

> **Goal:** The full public-facing product catalog — destinations, trips, itineraries, departures, reviews, and expedition details. This is the highest-traffic read path and must be optimized for Next.js SSR.

**Apps touched:** `apps.destinations`, `apps.trips`

### 2.1 — Destinations

**New File:** `apps/destinations/serializers/destination_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `DestinationListSerializer` | Catalog cards: `id`, `name`, `slug`, `country`, `region_name`, `hero_media`, `trips_count` (annotated). |
| `DestinationDetailSerializer` | Full detail: adds `visa_guidelines`, `permit_details`, Schema.org `TouristDestination`. |
| `DestinationWriteSerializer` | Admin create/update: full field set. |

**New File:** `apps/destinations/serializers/category_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `ActivityCategorySerializer` | Read/Write: `id`, `name`, `slug`, `description`. |

**New File:** `apps/destinations/views/destination_views.py`

| View | Methods | Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| `DestinationListCreateView` | GET, POST | `/destinations/` | GET: `AllowAny`; POST: `IsAdminRole` |
| `DestinationDetailView` | GET, PATCH, DELETE | `/destinations/{slug}/` | GET: `AllowAny`; others: `IsAdminRole` |

**New File:** `apps/destinations/views/category_views.py`

| View | Methods | Endpoint |
| :--- | :--- | :--- |
| `ActivityCategoryListCreateView` | GET, POST | `/destinations/activity-categories/` |
| `ActivityCategoryDetailView` | GET, PATCH | `/destinations/activity-categories/{slug}/` |

**File:** `apps/destinations/urls.py`

```python
urlpatterns = [
    path('', DestinationListCreateView.as_view(), name='destination-list'),
    path('activity-categories/', ActivityCategoryListCreateView.as_view(), name='category-list'),
    path('activity-categories/<slug:slug>/', ActivityCategoryDetailView.as_view(), name='category-detail'),
    path('<slug:slug>/', DestinationDetailView.as_view(), name='destination-detail'),
]
```

### 2.2 — Trips

**New File:** `apps/trips/serializers/trip_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `TripListSerializer` | Catalog cards. `select_related('destination', 'category')`. Annotates `rating_avg`. |
| `TripDetailSerializer` | Full detail. Nests `destination`, `category`, `expedition_detail`, `itinerary_days`, `departures`, `rating_summary`, `reviews`. Includes Schema.org `TouristTrip` + `AggregateRating` + `Offer`. |
| `TripWriteSerializer` | Admin create/update. |

**New File:** `apps/trips/serializers/itinerary_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `ItineraryDaySerializer` | Read/Write: day data with GPS coords for elevation chart + map. |

**New File:** `apps/trips/serializers/departure_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `TripDepartureSerializer` | Read: seat calendar data. |
| `TripDepartureWriteSerializer` | Admin create. Defaults `available_seats = max_seats`. |

**New File:** `apps/trips/serializers/review_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `TripReviewReadSerializer` | Public display: `reviewer_name`, `reviewer_country`, ratings, `is_verified`. |
| `TripReviewCreateSerializer` | Customer submit. Validates `booking_id` ownership → auto-sets `is_verified`. |

**New File:** `apps/trips/serializers/expedition_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `PeakExpeditionDetailSerializer` | Read/Write for technical mountaineering detail. |

**New File:** `apps/trips/views/trip_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `TripListCreateView` | GET, POST | `/trips/` |
| `TripDetailView` | GET, PATCH, DELETE | `/trips/{slug}/` |

**New File:** `apps/trips/views/itinerary_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `ItineraryView` | GET, POST | `/trips/{slug}/itinerary/` |
| `ItineraryDayDetailView` | PATCH, DELETE | `/trips/{slug}/itinerary/{day_number}/` |

**New File:** `apps/trips/views/departure_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `DepartureListCreateView` | GET, POST | `/trips/{slug}/departures/` |
| `DepartureDetailView` | PATCH | `/trips/{slug}/departures/{departure_id}/` |

**New File:** `apps/trips/views/review_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `ReviewListCreateView` | GET, POST | `/trips/{slug}/reviews/` |
| `ReviewModerationView` | PATCH | `/trips/{slug}/reviews/{review_id}/` |

**New File:** `apps/trips/views/expedition_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `ExpeditionDetailView` | GET, POST | `/trips/{slug}/expedition-detail/` |

**New File:** `apps/trips/urls.py`

```python
urlpatterns = [
    path('', TripListCreateView.as_view(), name='trip-list'),
    path('<slug:slug>/itinerary/', ItineraryView.as_view(), name='trip-itinerary'),
    path('<slug:slug>/itinerary/<int:day_number>/', ItineraryDayDetailView.as_view(), name='itinerary-day'),
    path('<slug:slug>/departures/', DepartureListCreateView.as_view(), name='departure-list'),
    path('<slug:slug>/departures/<uuid:departure_id>/', DepartureDetailView.as_view(), name='departure-detail'),
    path('<slug:slug>/reviews/', ReviewListCreateView.as_view(), name='review-list'),
    path('<slug:slug>/reviews/<uuid:review_id>/', ReviewModerationView.as_view(), name='review-moderation'),
    path('<slug:slug>/expedition-detail/', ExpeditionDetailView.as_view(), name='expedition-detail'),
    path('<slug:slug>/', TripDetailView.as_view(), name='trip-detail'),
]
```

> [!IMPORTANT]
> `<slug:slug>/` must be placed **last** to prevent it from swallowing sub-paths like `/itinerary/` and `/departures/`.

### 2.3 — Filters & Search for Trip List

**Dependency:** `pip install django-filter`

**New File:** `apps/trips/filters.py`

- `TripFilter(django_filters.FilterSet)` on `destination__slug`, `destination__country`, `category__slug`, `difficulty_grade`, `duration_days`, `altitude_max_meters`, `starting_price_usd`, `best_seasons` (JSON containment), `is_featured`.
- Register via `filterset_class = TripFilter` on `TripListCreateView`.

### Phase 2 Checklist

**Destinations**
- [ ] `apps/destinations/serializers/destination_serializers.py`
- [ ] `apps/destinations/serializers/category_serializers.py`
- [ ] `apps/destinations/views/destination_views.py`
- [ ] `apps/destinations/views/category_views.py`
- [ ] `apps/destinations/urls.py`

**Trips**
- [ ] `apps/trips/serializers/trip_serializers.py`
- [ ] `apps/trips/serializers/itinerary_serializers.py`
- [ ] `apps/trips/serializers/departure_serializers.py`
- [ ] `apps/trips/serializers/review_serializers.py`
- [ ] `apps/trips/serializers/expedition_serializers.py`
- [ ] `apps/trips/views/trip_views.py`
- [ ] `apps/trips/views/itinerary_views.py`
- [ ] `apps/trips/views/departure_views.py`
- [ ] `apps/trips/views/review_views.py`
- [ ] `apps/trips/views/expedition_views.py`
- [ ] `apps/trips/filters.py`
- [ ] `apps/trips/urls.py`

**Verification**
- [ ] `GET /api/v1/trips/` returns paginated list with filters
- [ ] `GET /api/v1/trips/everest-base-camp-trek/` returns full nested detail
- [ ] `GET /api/v1/trips/everest-base-camp-trek/itinerary/` returns GPS coords
- [ ] `GET /api/v1/trips/everest-base-camp-trek/departures/` returns seat calendar
- [ ] Schema.org JSON-LD present in trip detail response
- [ ] `GET /api/v1/destinations/` returns list with `trips_count` annotation

---

## Phase 3 — Booking Engine (Commerce)

> **Goal:** The atomic split-payment booking flow. Seat locking, `FULL_100`/`DEPOSIT_20` logic, passenger validation, and booking cancellation with seat release.

**Apps touched:** `apps.bookings`

> [!CAUTION]
> All booking write operations **must** use `@transaction.atomic` + `select_for_update()` on `TripDeparture`. Failure to do so will cause seat overbooking under concurrent load.

### 3.1 — Serializers

**New File:** `apps/bookings/serializers/passenger_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `PassengerDetailSerializer` | Read/Write. Validates: passport expiry ≥ 6 months from `trip_start_date`. |

**New File:** `apps/bookings/serializers/booking_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `BookingCreateSerializer` | Write. Validates departure availability with `select_for_update()`, generates `booking_reference`, computes deposit/balance/due date, creates passenger records in one atomic block. |
| `BookingDetailSerializer` | Read. Full booking with nested `departure`, `passengers`, `payments`. `select_related('departure__trip', 'customer_user')`. |
| `BookingListSerializer` | Read. Compact summary for list view. |
| `BookingCancelSerializer` | Write. Accepts `cancellation_reason`. Releases seat atomically. |

### 3.2 — Views

**New File:** `apps/bookings/views/booking_views.py`

| View | Methods | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `BookingCreateView` | POST | `/bookings/` | `AllowAny` (guest) + `IsAuthenticated` (assigns `customer_user`) |
| `BookingListView` | GET | `/bookings/` | `IsAuthenticated`. Customers filtered to own bookings. |
| `BookingDetailView` | GET | `/bookings/{booking_reference}/` | `IsOwnerOrAdmin` |
| `BookingCancelView` | PATCH | `/bookings/{booking_reference}/cancel/` | `IsOwnerOrAdmin` |

**New File:** `apps/bookings/views/passenger_views.py`

| View | Methods | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `PassengerListView` | GET | `/bookings/{booking_reference}/passengers/` | `IsOwnerOrAdmin` |
| `PassengerDetailView` | PATCH | `/bookings/{booking_reference}/passengers/{passenger_id}/` | `IsOwnerOrAdmin` |

### 3.3 — Atomic Booking Logic (core algorithm)

```python
# apps/bookings/views/booking_views.py
@transaction.atomic
def perform_create(self, serializer):
    departure = TripDeparture.objects.select_for_update().get(
        pk=serializer.validated_data['departure_id']
    )
    num_travelers = serializer.validated_data['num_travelers']

    if departure.available_seats < num_travelers:
        raise SeatsUnavailableError()

    departure.available_seats -= num_travelers
    if departure.available_seats == 0:
        departure.status = DepartureStatus.SOLD_OUT
    departure.save(update_fields=['available_seats', 'status'])

    booking = serializer.save(
        departure=departure,
        customer_user=self.request.user if self.request.user.is_authenticated else None,
        booking_reference=generate_booking_reference(),
        trip_start_date=departure.start_date,
        balance_due_date=departure.start_date - timedelta(days=7),
    )
    send_booking_confirmation_email.delay(booking.id)
```

### 3.4 — Booking Reference Generator

**New File:** `apps/bookings/utils.py`

```python
import random, string
from django.utils.timezone import now

def generate_booking_reference():
    year = now().year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"DS-{year}-{suffix}"
```

### 3.5 — URLs

**New File:** `apps/bookings/urls.py`

```python
urlpatterns = [
    path('', BookingListCreateView.as_view(), name='booking-list-create'),
    path('<str:booking_reference>/', BookingDetailView.as_view(), name='booking-detail'),
    path('<str:booking_reference>/cancel/', BookingCancelView.as_view(), name='booking-cancel'),
    path('<str:booking_reference>/passengers/', PassengerListView.as_view(), name='passenger-list'),
    path('<str:booking_reference>/passengers/<uuid:passenger_id>/', PassengerDetailView.as_view(), name='passenger-detail'),
]
```

### Phase 3 Checklist

- [x] `apps/bookings/serializers/passenger_serializers.py`
- [x] `apps/bookings/serializers/booking_serializers.py`
- [x] `apps/bookings/views/booking_views.py`
- [x] `apps/bookings/views/passenger_views.py`
- [x] `apps/bookings/utils.py` — `generate_booking_reference()`
- [x] `apps/bookings/urls.py`
- [x] Verify: `POST /api/v1/bookings/` with `DEPOSIT_20` creates booking and decrements seats
- [x] Verify: Concurrent booking attempts on a 1-seat departure — only one succeeds
- [x] Verify: Passport expiry < 6 months from trip start returns `400`
- [x] Verify: `PATCH /api/v1/bookings/{ref}/cancel/` restores seat count

---

## Phase 4 — Payments & Gateways

> **Goal:** Khalti/Stripe gateway session initiation, HMAC-validated webhooks with full idempotency, and the one-click balance payment token endpoint. All payment state transitions are atomic.

**Apps touched:** `apps.payments`

> [!CAUTION]
> Webhooks must be **idempotent**. Always check `webhook_event_id` uniqueness before processing. Use `select_for_update()` on `PaymentTransaction` to prevent double-processing on concurrent retries.

### 4.1 — Celery Setup

**File:** `config/celery.py` — Ensure Celery app is configured with Redis broker.

**New File:** `apps/payments/tasks.py`

```python
@shared_task
def send_payment_receipt_email(booking_id): ...

@shared_task
def send_payment_whatsapp_alert(booking_id): ...
```

### 4.2 — Serializers

**New File:** `apps/payments/serializers/payment_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `PaymentInitiateSerializer` | Write. Validates booking state, gateway, stage. Returns `checkout_url`. |
| `PaymentWebhookKhaltiSerializer` | Write. Validates HMAC signature. Idempotency via `webhook_event_id`. |
| `PaymentWebhookBankSerializer` | Write. Bank transfer webhook equivalent. |
| `BalancePaymentTokenSerializer` | Write. Validates `token_hash` via `PaymentActionToken`, checks expiry and `used_at`. |
| `PaymentTransactionReadSerializer` | Read. Receipt view: `transaction_id`, `gateway`, `stage`, `amount`, `status`. |

### 4.3 — Views

**New File:** `apps/payments/views/payment_views.py`

| View | Methods | Endpoint | Auth |
| :--- | :--- | :--- | :--- |
| `PaymentInitiateView` | POST | `/payments/initiate/` | `AllowAny` + `PaymentInitiateThrottle` |
| `KhaltiWebhookView` | POST | `/payments/webhook/khalti/` | None (HMAC) |
| `BankWebhookView` | POST | `/payments/webhook/bank/` | None (HMAC) |
| `BalancePayTokenView` | POST | `/payments/balance/pay/` | None (token-auth) |
| `TransactionListView` | GET | `/payments/transactions/` | `IsAuthenticated` |
| `TransactionDetailView` | GET | `/payments/transactions/{id}/` | `IsOwnerOrAdmin` |

### 4.4 — HMAC Webhook Validation Utility

**New File:** `apps/payments/utils.py`

```python
import hmac, hashlib

def validate_khalti_hmac(request, secret_key: str) -> bool:
    signature = request.headers.get('X-Khalti-Signature', '')
    payload = request.body
    expected = hmac.new(secret_key.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

### 4.5 — Idempotent Webhook Processing (core algorithm)

```python
@transaction.atomic
def process_khalti_webhook(validated_data):
    event_id = validated_data['pidx']

    # Idempotency check — reject if already processed
    txn = PaymentTransaction.objects.select_for_update().filter(
        webhook_event_id=event_id
    ).first()
    if txn and txn.status == PaymentStatus.SUCCESS:
        return  # Already processed — silently ignore

    txn.status = PaymentStatus.SUCCESS
    txn.processed_at = now()
    txn.webhook_event_id = event_id
    txn.webhook_raw_payload = validated_data
    txn.save()

    booking = Booking.objects.select_for_update().get(pk=txn.booking_id)
    booking.amount_paid_usd += txn.amount

    if txn.payment_stage == PaymentStage.DEPOSIT_20:
        booking.status = BookingStatus.DEPOSIT_PAID
    elif txn.payment_stage in [PaymentStage.BALANCE_80, PaymentStage.FULL_100]:
        booking.status = BookingStatus.FULLY_PAID
    booking.save()

    send_payment_receipt_email.delay(booking.id)
    send_payment_whatsapp_alert.delay(booking.id)
```

### 4.6 — Celery Beat: Balance Due Reminder

**File:** `config/celery.py`

```python
CELERY_BEAT_SCHEDULE = {
    'send-balance-reminders-daily': {
        'task': 'apps.payments.tasks.send_balance_due_reminders',
        'schedule': crontab(hour=8, minute=0),  # 08:00 UTC daily
    },
}
```

**File:** `apps/payments/tasks.py`

```python
@shared_task
def send_balance_due_reminders():
    threshold = now() + timedelta(hours=48)
    bookings = Booking.objects.filter(
        status=BookingStatus.DEPOSIT_PAID,
        balance_due_date__lte=threshold,
        balance_due_date__gt=now()
    ).select_related('departure__trip')

    for booking in bookings:
        token = PaymentActionToken.objects.create(
            booking=booking,
            purpose='BALANCE_PAYMENT_80',
            token_hash=generate_signed_token(),
            expires_at=now() + timedelta(hours=72)
        )
        send_balance_reminder_email.delay(booking.id, token.token_hash)
```

### 4.7 — URLs

**New File:** `apps/payments/urls.py`

```python
urlpatterns = [
    path('initiate/', PaymentInitiateView.as_view(), name='payment-initiate'),
    path('webhook/khalti/', KhaltiWebhookView.as_view(), name='webhook-khalti'),
    path('webhook/bank/', BankWebhookView.as_view(), name='webhook-bank'),
    path('balance/pay/', BalancePayTokenView.as_view(), name='balance-pay'),
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    path('transactions/<str:transaction_id>/', TransactionDetailView.as_view(), name='transaction-detail'),
]
```

### Phase 4 Checklist

- [ ] `config/celery.py` — Celery app + Beat schedule configured
- [ ] `apps/payments/serializers/payment_serializers.py` — 5 serializers
- [ ] `apps/payments/views/payment_views.py` — 6 views
- [ ] `apps/payments/utils.py` — HMAC validator + signed token generator
- [ ] `apps/payments/tasks.py` — receipt email, WhatsApp alert, balance reminder tasks
- [ ] `apps/payments/urls.py`
- [ ] Verify: `POST /api/v1/payments/initiate/` returns `checkout_url`
- [ ] Verify: Duplicate webhook with same `pidx` is silently ignored (idempotent)
- [ ] Verify: Booking status transitions to `DEPOSIT_PAID` after successful Khalti webhook
- [ ] Verify: `POST /api/v1/payments/balance/pay/` with expired token returns `410`
- [ ] Verify: Celery Beat task fires and dispatches emails for eligible bookings

---

## Phase 5 — CRM & Inquiries

> **Goal:** Public-facing lead capture for general, journey-specific, and tailor-made trip inquiries. Internal CRM pipeline for agents with lead lifecycle management, notes thread, and async email acknowledgement.

**Apps touched:** `apps.inquiries`

### 5.1 — Inquiry Number Generator

**New File:** `apps/inquiries/utils.py`

```python
def generate_inquiry_number():
    year = now().year
    suffix = random.randint(1000, 9999)
    return f"INQ-{year}-{suffix}"
```

### 5.2 — Serializers

**New File:** `apps/inquiries/serializers/inquiry_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `InquiryCreateSerializer` | Write. Accepts all inquiry types. Auto-generates `inquiry_number`. If `inquiry_type == TAILOR_MADE`, expects nested `tailor_made` block and creates `TailorMadeRequest` in same atomic operation. Triggers Celery acknowledgement task after save. |
| `InquiryDetailSerializer` | Read. Full CRM detail: nested `assigned_agent`, `trip`, `departure`, `tailor_made_detail`, `notes`. |
| `InquiryListSerializer` | Read. Compact list view for CRM dashboard. |
| `InquiryUpdateSerializer` | Write. Agent-only: update `status`, `assigned_agent`. |
| `InquiryNoteSerializer` | Read/Write. Internal note with `author` from `request.user`. |

**New File:** `apps/inquiries/serializers/tailor_made_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `TailorMadeRequestSerializer` | Nested read/write: destinations, activities, GPS coordinates, waypoints. |

### 5.3 — Celery Tasks

**New File:** `apps/inquiries/tasks.py`

```python
@shared_task
def send_inquiry_acknowledgement_email(inquiry_id): ...
    # "We have received your journey inquiry; our team is reviewing your requirements..."

@shared_task
def send_agent_whatsapp_alert(inquiry_id): ...
    # Sends lead details to internal agent WhatsApp group
```

### 5.4 — Views

**New File:** `apps/inquiries/views/inquiry_views.py`

| View | Methods | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `InquiryCreateView` | POST | `/inquiries/` | `AllowAny` + `InquiryThrottle` |
| `InquiryListView` | GET | `/inquiries/` | `IsSalesAgentRole` |
| `InquiryDetailView` | GET | `/inquiries/{inquiry_number}/` | `IsSalesAgentRole` |
| `InquiryUpdateView` | PATCH | `/inquiries/{inquiry_number}/` | `IsSalesAgentRole` |
| `InquiryNoteListCreateView` | GET, POST | `/inquiries/{inquiry_number}/notes/` | `IsSalesAgentRole` |

### 5.5 — URLs

**New File:** `apps/inquiries/urls.py`

```python
urlpatterns = [
    path('', InquiryListCreateView.as_view(), name='inquiry-list-create'),
    path('<str:inquiry_number>/', InquiryDetailUpdateView.as_view(), name='inquiry-detail'),
    path('<str:inquiry_number>/notes/', InquiryNoteListCreateView.as_view(), name='inquiry-notes'),
]
```

### Phase 5 Checklist

- [x] `apps/inquiries/serializers/inquiry_serializers.py` — 5 serializers
- [x] `apps/inquiries/serializers/tailor_made_serializers.py`
- [x] `apps/inquiries/views/inquiry_views.py` — 5 views
- [x] `apps/inquiries/tasks.py` — acknowledgement email + agent WhatsApp alert
- [x] `apps/inquiries/utils.py` — `generate_inquiry_number()`
- [x] `apps/inquiries/urls.py`
- [x] Verify: `POST /api/v1/inquiries/` (TAILOR_MADE) creates both `Inquiry` + `TailorMadeRequest`
- [x] Verify: Celery acknowledgement email task fires within 5 seconds
- [x] Verify: `GET /api/v1/inquiries/` returns `403` for `CUSTOMER` role
- [x] Verify: `PATCH /api/v1/inquiries/{num}/` updates status with valid transition

---

## Phase 6 — B2B Partner Portal

> **Goal:** Travel agency self-registration, admin approval workflow, tier-gated asset downloads, and commission ledger for attributed partner bookings.

**Apps touched:** `apps.b2b`

### 6.1 — Serializers

**New File:** `apps/b2b/serializers/partner_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `B2BRegistrationSerializer` | Write. Creates `User(role=B2B_PARTNER)` + pending `B2BPartner` profile atomically. |
| `B2BPartnerProfileSerializer` | Read. Own profile: `company_name`, `country`, `agency_tier`, `commission_rate`, `approved`. |
| `B2BPartnerAdminSerializer` | Read/Write (Admin). Includes `approved`, `agency_tier`, `commission_rate`. |
| `B2BPartnerApprovalSerializer` | Write. Admin: sets `approved`, `agency_tier`, `commission_rate`. |

**New File:** `apps/b2b/serializers/asset_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `B2BAssetSerializer` | Read. Tier-filtered. Includes `download_url` pointing to `/b2b/assets/{id}/download/`. |

**New File:** `apps/b2b/serializers/booking_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `B2BBookingSerializer` | Read. Commission ledger view: gross, commission amount, net, status. |
| `B2BCommissionUpdateSerializer` | Write (Admin). Updates `commission_status`. |

### 6.2 — Tier Filtering Logic

```python
# Asset tier hierarchy mapping (used in queryset filtering)
TIER_ORDER = {'BRONZE': 1, 'SILVER': 2, 'GOLD': 3, 'PLATINUM': 4}

def get_accessible_assets(partner: B2BPartner):
    partner_tier_value = TIER_ORDER[partner.agency_tier]
    accessible_tiers = [t for t, v in TIER_ORDER.items() if v <= partner_tier_value]
    return B2BAsset.objects.filter(
        minimum_tier__in=accessible_tiers,
        is_active=True
    ).select_related('trip')
```

### 6.3 — Views

**New File:** `apps/b2b/views/partner_views.py`

| View | Methods | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `B2BRegisterView` | POST | `/b2b/register/` | `AllowAny` |
| `B2BPartnerListView` | GET | `/b2b/partners/` | `IsAdminRole` |
| `B2BPartnerMeView` | GET, PATCH | `/b2b/partners/me/` | `IsB2BPartnerRole` |
| `B2BPartnerApproveView` | POST | `/b2b/partners/{partner_id}/approve/` | `IsAdminRole` |

**New File:** `apps/b2b/views/asset_views.py`

| View | Methods | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `B2BAssetListView` | GET | `/b2b/assets/` | `IsB2BPartnerRole` (approved) |
| `B2BAssetDownloadView` | GET | `/b2b/assets/{asset_id}/download/` | `IsB2BPartnerRole` + tier check |

**New File:** `apps/b2b/views/booking_views.py`

| View | Methods | Endpoint | Permission |
| :--- | :--- | :--- | :--- |
| `B2BBookingListView` | GET | `/b2b/bookings/` | `IsB2BPartnerRole` (own) / `IsAdminRole` (all) |
| `B2BCommissionUpdateView` | PATCH | `/b2b/bookings/{id}/commission/` | `IsAdminRole` |

### 6.4 — URLs

**New File:** `apps/b2b/urls.py`

```python
urlpatterns = [
    path('register/', B2BRegisterView.as_view(), name='b2b-register'),
    path('partners/', B2BPartnerListView.as_view(), name='partner-list'),
    path('partners/me/', B2BPartnerMeView.as_view(), name='partner-me'),
    path('partners/<uuid:partner_id>/approve/', B2BPartnerApproveView.as_view(), name='partner-approve'),
    path('assets/', B2BAssetListView.as_view(), name='asset-list'),
    path('assets/<uuid:asset_id>/download/', B2BAssetDownloadView.as_view(), name='asset-download'),
    path('bookings/', B2BBookingListView.as_view(), name='b2b-booking-list'),
    path('bookings/<uuid:b2b_booking_id>/commission/', B2BCommissionUpdateView.as_view(), name='commission-update'),
]
```

### Phase 6 Checklist

Implementation verified with API tests. Email dispatch/provider calls are mocked in tests; live delivery requires the worker, Redis and Resend configuration. Private signed API downloads are implemented; production CDN signing remains a separate integration milestone. See [setup and verification](PHASE_6_7_SETUP.md).

- [x] `apps/b2b/serializers/partner_serializers.py`
- [x] `apps/b2b/serializers/asset_serializers.py`
- [x] `apps/b2b/serializers/booking_serializers.py`
- [x] `apps/b2b/views/partner_views.py`
- [x] `apps/b2b/views/asset_views.py`
- [x] `apps/b2b/views/booking_views.py`
- [x] `apps/b2b/urls.py`
- [x] Verify: `POST /api/v1/b2b/register/` creates User + pending partner profile
- [x] Verify: Unapproved partner cannot access `/b2b/assets/` — returns `403`
- [x] Verify: BRONZE partner cannot download GOLD-tier asset — returns `403 TIER_INSUFFICIENT`
- [x] Verify: `POST /api/v1/b2b/partners/{id}/approve/` triggers approval email via Celery

---

## Phase 7 — Content, FAQs & Search

> **Goal:** Travel guide CMS with markdown + Schema.org Article, responsible travel initiatives, contextual FAQs with FAQPage JSON-LD, and multi-entity PostgreSQL full-text search.

**Apps touched:** `apps.content_cms`, `apps.faq`, `apps.search`

### 7.1 — Content CMS

**New File:** `apps/content_cms/serializers/guide_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `TravelGuideListSerializer` | Read. Catalog cards with `destination`, `category`, `hero_image_url`. |
| `TravelGuideDetailSerializer` | Read. Full markdown body + `meta_title`, `meta_description`, `canonical_url`, Schema.org `Article` + `BreadcrumbList`. |
| `TravelGuideWriteSerializer` | Write (Admin). Creates/updates guide. Auto-sets `published_at` on first `is_published=True` transition. |

**New File:** `apps/content_cms/serializers/initiative_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `ResponsibleTravelSerializer` | Read/Write. `title`, `slug`, `pillars` (JSONField), `content`. |

**New File:** `apps/content_cms/views/guide_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `TravelGuideListCreateView` | GET, POST | `/content/guides/` |
| `TravelGuideDetailView` | GET, PATCH, DELETE | `/content/guides/{slug}/` |

**New File:** `apps/content_cms/views/initiative_views.py`

| View | Methods | Endpoints |
| :--- | :--- | :--- |
| `ResponsibleTravelListCreateView` | GET, POST | `/content/responsible-travel/` |
| `ResponsibleTravelDetailView` | GET | `/content/responsible-travel/{slug}/` |

**New File:** `apps/content_cms/urls.py`

```python
urlpatterns = [
    path('guides/', TravelGuideListCreateView.as_view(), name='guide-list'),
    path('guides/<slug:slug>/', TravelGuideDetailView.as_view(), name='guide-detail'),
    path('responsible-travel/', ResponsibleTravelListCreateView.as_view(), name='initiative-list'),
    path('responsible-travel/<slug:slug>/', ResponsibleTravelDetailView.as_view(), name='initiative-detail'),
]
```

### 7.2 — FAQs

**New File:** `apps/faq/serializers/faq_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `FAQSerializer` | Read/Write. Contextual FAQ with `display_order`. |
| `FAQResponseSerializer` | Read. Wraps FAQ list + Schema.org `FAQPage` JSON-LD block. |

**New File:** `apps/faq/views/faq_views.py`

| View | Methods | Endpoint |
| :--- | :--- | :--- |
| `FAQListCreateView` | GET, POST | `/faqs/` |
| `FAQDetailView` | PATCH, DELETE | `/faqs/{id}/` |

**New File:** `apps/faq/urls.py`

```python
urlpatterns = [
    path('', FAQListCreateView.as_view(), name='faq-list'),
    path('<uuid:pk>/', FAQDetailView.as_view(), name='faq-detail'),
]
```

### 7.3 — Full-Text Search

> **Phase 1 implementation**: Query-time `SearchVector` annotation (no stored vector field). Sufficient for launch.

**New File:** `apps/search/views/search_views.py`

```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db.models import Value, F

class UnifiedSearchView(APIView):
    throttle_classes = [SearchThrottle]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            raise ValidationError({'q': 'Search query must be at least 2 characters.'})

        search_query = SearchQuery(query)
        entity_type = request.query_params.get('entity_type')

        results = []

        # Trip search (Weight A: title/slug, Weight B: overview)
        if not entity_type or entity_type == 'trip':
            trips = Trip.objects.annotate(
                search=SearchVector('title', 'slug', weight='A') + SearchVector('overview', weight='B'),
                rank=SearchRank(SearchVector('title', 'slug', weight='A') + SearchVector('overview', weight='B'), search_query)
            ).filter(search=search_query, is_active=True).order_by('-rank')[:10]
            results += [serialize_trip_result(t) for t in trips]

        # Destination search (Weight A)
        if not entity_type or entity_type == 'destination':
            destinations = Destination.objects.annotate(
                search=SearchVector('name', 'region_name', weight='A'),
                rank=SearchRank(SearchVector('name', 'region_name', weight='A'), search_query)
            ).filter(search=search_query, is_active=True).order_by('-rank')[:5]
            results += [serialize_destination_result(d) for d in destinations]

        # Guide search (Weight A: title, Weight C: content)
        if not entity_type or entity_type == 'guide':
            guides = TravelGuide.objects.annotate(
                search=SearchVector('title', weight='A') + SearchVector('markdown_content', weight='C'),
                rank=SearchRank(SearchVector('title', weight='A') + SearchVector('markdown_content', weight='C'), search_query)
            ).filter(search=search_query, is_published=True).order_by('-rank')[:5]
            results += [serialize_guide_result(g) for g in guides]

        # FAQ search (Weight B: question, Weight C: answer)
        if not entity_type or entity_type == 'faq':
            faqs = FAQ.objects.annotate(
                search=SearchVector('question', weight='B') + SearchVector('answer', weight='C'),
                rank=SearchRank(SearchVector('question', weight='B') + SearchVector('answer', weight='C'), search_query)
            ).filter(search=search_query, is_active=True).order_by('-rank')[:5]
            results += [serialize_faq_result(f) for f in faqs]

        results.sort(key=lambda x: x['rank_score'], reverse=True)
        return Response({'query': query, 'count': len(results), 'results': results})
```

**New File:** `apps/search/serializers/search_serializers.py`

| Serializer | Purpose |
| :--- | :--- |
| `SearchResultSerializer` | Read. `entity_type`, `title`, `slug`, `snippet`, `rank_score`, `meta` (type-specific fields). |

**New File:** `apps/search/urls.py`

```python
urlpatterns = [
    path('', UnifiedSearchView.as_view(), name='unified-search'),
]
```

### Phase 7 Checklist

Implemented using modular views/serializers packages. PostgreSQL tests cover publication visibility, soft deletion, FAQPage output and global search pagination.

**Content CMS**
- [x] `apps/content_cms/serializers/guide_serializers.py`
- [x] `apps/content_cms/serializers/initiative_serializers.py`
- [x] `apps/content_cms/views/guide_views.py`
- [x] `apps/content_cms/views/initiative_views.py`
- [x] `apps/content_cms/urls.py`

**FAQs**
- [x] `apps/faq/serializers/faq_serializers.py`
- [x] `apps/faq/views/faq_views.py`
- [x] `apps/faq/urls.py`

**Search**
- [x] `apps/search/views/search_views.py`
- [x] `apps/search/serializers/search_serializers.py`
- [x] `apps/search/urls.py`

**Verification**
- [x] `GET /api/v1/content/guides/` returns paginated published guides
- [x] `GET /api/v1/content/guides/{slug}/` includes Schema.org `Article` JSON-LD
- [x] `GET /api/v1/faqs/?trip=everest-base-camp-trek` returns trip-specific FAQs + `FAQPage` JSON-LD
- [x] `GET /api/v1/search/?q=everest` returns ranked results across trips, destinations, guides, FAQs
- [x] `GET /api/v1/search/?q=e` returns `400` (query too short)
- [x] Publishing a guide for the first time auto-sets `published_at`

---

## Integration Milestones

These cross-cutting items span multiple phases and must be tracked separately.

| Milestone | Phase | Status |
| :--- | :--- | :--- |
| Resend API integration (email templates) | Phase 1 (password reset) + Phase 3, 4, 5 | ⬜ Todo |
| WhatsApp Business Cloud API integration | Phase 4, 5 | ⬜ Todo |
| Khalti payment gateway integration | Phase 4 | ⬜ Todo |
| International Bank API integration | Phase 4 | ⬜ Todo |
| Google Maps / GeoJSON route rendering | Phase 2 (itinerary) | ⬜ Todo |
| Redis + Celery worker deployment | Phase 4 | ⬜ Todo |
| CORS configuration for Next.js frontend | Phase 0 | ⬜ Todo |
| Sentry error tracking setup | Phase 0 | ⬜ Todo |
| CDN signed URL generation for B2B assets | Phase 6 | ⬜ Todo |
| PostgreSQL GIN index for full-text search (Phase 2) | Phase 7 (upgrade) | ⬜ Todo |

---

## Implementation Order Summary

```
Phase 0: DRF Config · Envelope Renderer · Pagination · Exception Handler · CORS · Swagger
    ↓
Phase 1: Auth (JWT) · Registration · Password Flow · User Profile
    ↓
Phase 2: Destinations Catalog · Trips Catalog · Itinerary · Departures · Reviews
    ↓
Phase 3: Booking Engine (DEPOSIT_20 / FULL_100) · Passenger Validation · Seat Lock
    ↓
Phase 4: Payment Gateway Sessions · HMAC Webhooks · Balance Token · Celery Beat
    ↓
Phase 5: Inquiry Capture · CRM Pipeline · Tailor-Made Builder · Agent Notes
    ↓
Phase 6: B2B Registration · Approval · Tier-Gated Assets · Commission Ledger
    ↓
Phase 7: Travel Guides (Markdown+Schema.org) · FAQs (FAQPage JSON-LD) · Unified Search
```

---

*End of API Implementation Plan — Dreamscape Treks™ v1.0*
