# DREAMSCAPE TREKS™ — API DESIGN SPECIFICATION
**Version:** `v1.0`  
**Base URL:** `/api/v1/`  
**Auth Mechanism:** JWT (`Authorization: Bearer <access_token>`)  
**API Docs (Auto-generated):** `/api/v1/schema/swagger/` · `/api/v1/schema/redoc/`  
**Framework:** Django 5.x + Django REST Framework + `drf-spectacular`

---

## Table of Contents

1. [Global Standards & Conventions](#1-global-standards--conventions)
2. [Auth — `/api/v1/auth/`](#2-auth--apiv1auth)
3. [Accounts — `/api/v1/users/`](#3-accounts--apiv1users)
4. [Destinations — `/api/v1/destinations/`](#4-destinations--apiv1destinations)
5. [Trips — `/api/v1/trips/`](#5-trips--apiv1trips)
6. [Bookings — `/api/v1/bookings/`](#6-bookings--apiv1bookings)
7. [Payments — `/api/v1/payments/`](#7-payments--apiv1payments)
8. [Inquiries — `/api/v1/inquiries/`](#8-inquiries--apiv1inquiries)
9. [B2B Partner Portal — `/api/v1/b2b/`](#9-b2b-partner-portal--apiv1b2b)
10. [Content CMS — `/api/v1/content/`](#10-content-cms--apiv1content)
11. [FAQs — `/api/v1/faqs/`](#11-faqs--apiv1faqs)
12. [Search — `/api/v1/search/`](#12-search--apiv1search)
13. [Permission Matrix](#13-permission-matrix)
14. [Error Code Reference](#14-error-code-reference)
15. [Rate Limiting & Throttling](#15-rate-limiting--throttling)
16. [Celery Async Task Triggers](#16-celery-async-task-triggers)

---

## 1. Global Standards & Conventions

### 1.1 URL & Versioning

All endpoints are prefixed with `/api/v1/`. Resource identifiers for publicly-accessible resources use **slug** (human-readable), while internal or ownership-sensitive resources use **UUID** (`pk`).

### 1.2 Response Envelopes

**Success (2xx)**
```json
{
  "success": true,
  "data": { ... },
  "message": "Resource retrieved successfully."
}
```

**Paginated Success**
```json
{
  "success": true,
  "data": {
    "count": 120,
    "next": "https://api.dreamscapetreks.com/api/v1/trips/?page=3",
    "previous": "https://api.dreamscapetreks.com/api/v1/trips/?page=1",
    "results": [ ... ]
  },
  "message": "Trips retrieved successfully."
}
```

**Error (4xx / 5xx)**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description of the error.",
    "details": {
      "field_name": ["Error detail string."]
    }
  }
}
```

### 1.3 Standard Error Codes

| Code | HTTP Status | Description |
| :--- | :--- | :--- |
| `VALIDATION_ERROR` | 400 | Input validation failed (field-level errors in `details`) |
| `UNAUTHORIZED` | 401 | Missing or invalid JWT token |
| `FORBIDDEN` | 403 | Authenticated but insufficient role/permission |
| `NOT_FOUND` | 404 | Resource does not exist or is inactive |
| `SEATS_UNAVAILABLE` | 409 | Departure is full; concurrent booking conflict |
| `TOKEN_EXPIRED` | 410 | Secure payment action token has expired or was already used |
| `PAYMENT_FAILED` | 402 | Gateway declined the transaction |
| `IDEMPOTENCY_CONFLICT` | 409 | Duplicate payment attempt detected |
| `INTERNAL_ERROR` | 500 | Unhandled server error (logged to Sentry) |

### 1.4 Pagination

Default cursor/page-based pagination. Default page size: **20**. Max page size: **100**.
- `?page=<N>` — Page number
- `?page_size=<N>` — Override page size (max 100)

### 1.5 Authentication Roles

| Role | Identifier | Description |
| :--- | :--- | :--- |
| Anonymous | *(no token)* | Can browse, search, submit inquiries, view public content |
| Customer | `CUSTOMER` | Can book, view own bookings, submit reviews |
| Sales Agent | `SALES_AGENT` | All Customer permissions + CRM inquiry management |
| B2B Partner | `B2B_PARTNER` | Partner portal: B2B bookings, asset downloads, commissions |
| Superadmin | `ADMIN` | Full access, admin CRUD on all resources |

---

## 2. Auth — `/api/v1/auth/`

Handles JWT token issuance, refresh, verification, user registration, and password flows. Powered by `djangorestframework-simplejwt`.

---

### `POST /api/v1/auth/register/`

Register a new customer account.

**Auth:** Anonymous  
**Throttle:** `5/hour` per IP

**Request Body**
```json
{
  "email": "john@example.com",
  "password": "SecurePass@2024",
  "password_confirm": "SecurePass@2024",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+9779841000000",
  "whatsapp_number": "+9779841000000"
}
```

**Validation Rules**
- `email`: Must be unique, valid format.
- `password`: Min 8 chars, at least 1 uppercase, 1 digit, 1 special character.
- `password_confirm`: Must match `password`.
- `role` is always set to `CUSTOMER`; cannot be set by client.

**Response `201 Created`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "CUSTOMER",
    "access": "<jwt_access_token>",
    "refresh": "<jwt_refresh_token>"
  },
  "message": "Account created successfully. Welcome to Dreamscape Treks!"
}
```

---

### `POST /api/v1/auth/login/`

Obtain JWT token pair for an existing user.

**Auth:** Anonymous

**Request Body**
```json
{
  "email": "john@example.com",
  "password": "SecurePass@2024"
}
```

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "access": "<jwt_access_token>",
    "refresh": "<jwt_refresh_token>",
    "user": {
      "id": "uuid-string",
      "email": "john@example.com",
      "full_name": "John Doe",
      "role": "CUSTOMER"
    }
  },
  "message": "Login successful."
}
```

**Error `401`** → `UNAUTHORIZED` — Invalid credentials.

---

### `POST /api/v1/auth/token/refresh/`

Obtain a new access token using a valid refresh token.

**Auth:** Anonymous

**Request Body**
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Response `200 OK`**
```json
{
  "success": true,
  "data": { "access": "<new_jwt_access_token>" },
  "message": "Token refreshed successfully."
}
```

---

### `POST /api/v1/auth/logout/`

Blacklist the provided refresh token (requires `simplejwt` token blacklisting enabled).

**Auth:** Authenticated

**Request Body**
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Response `200 OK`**
```json
{
  "success": true,
  "data": null,
  "message": "Logged out successfully."
}
```

---

### `POST /api/v1/auth/password/change/`

Change password for the authenticated user.

**Auth:** Authenticated (any role)

**Request Body**
```json
{
  "current_password": "OldPass@123",
  "new_password": "NewSecurePass@456",
  "new_password_confirm": "NewSecurePass@456"
}
```

**Response `200 OK`**
```json
{
  "success": true,
  "data": null,
  "message": "Password changed successfully."
}
```

---

### `POST /api/v1/auth/password/reset/`

Request a password reset email (token-based link).

**Auth:** Anonymous  
**Throttle:** `3/hour` per email

**Request Body**
```json
{ "email": "john@example.com" }
```

**Response `200 OK`** *(always returns 200 to prevent user enumeration)*
```json
{
  "success": true,
  "data": null,
  "message": "If this email exists, a password reset link has been sent."
}
```

---

### `POST /api/v1/auth/password/reset/confirm/`

Confirm password reset with token received via email.

**Auth:** Anonymous

**Request Body**
```json
{
  "token": "<reset_token_from_email>",
  "new_password": "BrandNewPass@789",
  "new_password_confirm": "BrandNewPass@789"
}
```

**Response `200 OK`**
```json
{
  "success": true,
  "data": null,
  "message": "Password reset successfully. You can now log in."
}
```

---

## 3. Accounts — `/api/v1/users/`

Manage user profile data. Admin-only listing and management.

---

### `GET /api/v1/users/me/`

Retrieve the authenticated user's own profile.

**Auth:** Authenticated (any role)

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+9779841000000",
    "whatsapp_number": "+9779841000000",
    "role": "CUSTOMER",
    "date_joined": "2026-01-15T09:30:00Z",
    "is_active": true
  },
  "message": "Profile retrieved successfully."
}
```

---

### `PATCH /api/v1/users/me/`

Update the authenticated user's own profile. `email` and `role` are read-only.

**Auth:** Authenticated (any role)

**Request Body** *(all fields optional)*
```json
{
  "first_name": "Jonathan",
  "phone": "+9779841111111",
  "whatsapp_number": "+9779841111111"
}
```

**Response `200 OK`** → Updated profile object.

---

### `GET /api/v1/users/` *(Admin Only)*

List all users with filtering.

**Auth:** `ADMIN`  
**Query Params:** `?role=CUSTOMER&is_active=true&search=john`

**Response `200 OK`** → Paginated list of user profile objects.

---

### `GET /api/v1/users/{id}/` *(Admin Only)*

Retrieve a specific user profile by UUID.

**Auth:** `ADMIN`

---

### `PATCH /api/v1/users/{id}/` *(Admin Only)*

Update a user's role, active status, or staff flag.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "role": "SALES_AGENT",
  "is_active": true,
  "is_staff": true
}
```

---

## 4. Destinations — `/api/v1/destinations/`

Public catalog of countries, regions, and activity categories.

---

### `GET /api/v1/destinations/`

List all active destinations.

**Auth:** Anonymous  
**Query Params:** `?country=NEPAL&is_active=true`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "count": 12,
    "results": [
      {
        "id": "uuid-string",
        "name": "Khumbu / Everest Region",
        "slug": "khumbu-everest-region",
        "country": "NEPAL",
        "region_name": "Khumbu / Everest",
        "hero_media": "https://cdn.dreamscapetreks.com/destinations/khumbu.jpg",
        "trips_count": 18
      }
    ]
  },
  "message": "Destinations retrieved successfully."
}
```

---

### `GET /api/v1/destinations/{slug}/`

Full destination detail with visa guidelines, permit info, and Schema.org metadata for Next.js SSR.

**Auth:** Anonymous  
**ORM:** `prefetch_related('trips', 'guides', 'faqs')`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "name": "Khumbu / Everest Region",
    "slug": "khumbu-everest-region",
    "country": "NEPAL",
    "region_name": "Khumbu / Everest",
    "hero_media": "https://cdn.dreamscapetreks.com/destinations/khumbu.jpg",
    "visa_guidelines": "Tourists require a tourist visa on arrival...",
    "permit_details": "TIMS card and Sagarmatha National Park permit required...",
    "trips_count": 18,
    "schema_org": {
      "@type": "TouristDestination",
      "name": "Khumbu / Everest Region",
      "description": "..."
    }
  },
  "message": "Destination retrieved successfully."
}
```

---

### `POST /api/v1/destinations/` *(Admin Only)*

Create a new destination.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "name": "Manaslu Circuit",
  "slug": "manaslu-circuit",
  "country": "NEPAL",
  "region_name": "Manaslu / Gorkha",
  "visa_guidelines": "...",
  "permit_details": "Manaslu Conservation Area permit required...",
  "hero_media": "https://cdn.dreamscapetreks.com/...",
  "is_active": true
}
```

**Response `201 Created`** → Full destination object.

---

### `PATCH /api/v1/destinations/{slug}/` *(Admin Only)*

Partially update a destination.

**Auth:** `ADMIN`

---

### `DELETE /api/v1/destinations/{slug}/` *(Admin Only)*

Soft-delete: sets `is_active=False`.

**Auth:** `ADMIN`

---

### `GET /api/v1/destinations/activity-categories/`

List all active activity categories (used as filter chips on the frontend).

**Auth:** Anonymous

**Response `200 OK`**
```json
{
  "success": true,
  "data": [
    { "id": "uuid-string", "name": "Classic Trekking", "slug": "classic-trekking", "description": "..." },
    { "id": "uuid-string", "name": "Mountaineering Expeditions", "slug": "mountaineering-expeditions", "description": "..." }
  ],
  "message": "Activity categories retrieved successfully."
}
```

---

### `POST /api/v1/destinations/activity-categories/` *(Admin Only)*

Create a new activity category.

**Auth:** `ADMIN`

---

### `PATCH /api/v1/destinations/activity-categories/{slug}/` *(Admin Only)*

Update an activity category.

**Auth:** `ADMIN`

---

## 5. Trips — `/api/v1/trips/`

The core product catalog: treks, expeditions, itineraries, departures, and reviews.

---

### `GET /api/v1/trips/`

Filterable, searchable, paginated trip catalog.

**Auth:** Anonymous  
**ORM:** `select_related('destination', 'category')`  
**Query Params:**

| Param | Type | Description |
| :--- | :--- | :--- |
| `destination` | `slug` | Filter by destination slug |
| `country` | `string` | `NEPAL`, `TIBET`, `BHUTAN`, `INDIA`, `MULTI_COUNTRY` |
| `category` | `slug` | Filter by activity category slug |
| `difficulty` | `string` | `GRADE_1` through `GRADE_5`, `ALPINE` |
| `duration_min` | `int` | Minimum duration in days |
| `duration_max` | `int` | Maximum duration in days |
| `altitude_max` | `int` | Max altitude filter in meters |
| `price_min` | `decimal` | Minimum price in USD |
| `price_max` | `decimal` | Maximum price in USD |
| `season` | `string` | `SPRING`, `SUMMER`, `AUTUMN`, `WINTER` |
| `is_featured` | `bool` | Featured trips only |
| `ordering` | `string` | `starting_price_usd`, `-starting_price_usd`, `duration_days`, `altitude_max_meters` |
| `search` | `string` | Full-text keyword search |

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "count": 48,
    "next": "...",
    "previous": null,
    "results": [
      {
        "id": "uuid-string",
        "title": "Everest Base Camp Trek",
        "slug": "everest-base-camp-trek",
        "destination_name": "Khumbu / Everest Region",
        "destination_slug": "khumbu-everest-region",
        "category_name": "Classic Trekking",
        "duration_days": 14,
        "altitude_max_meters": 5364,
        "difficulty_grade": "GRADE_3",
        "starting_price_usd": "1350.00",
        "is_featured": true,
        "best_seasons": ["SPRING", "AUTUMN"],
        "hero_media_url": "https://cdn.dreamscapetreks.com/..."
      }
    ]
  },
  "message": "Trips retrieved successfully."
}
```

---

### `GET /api/v1/trips/{slug}/`

Full trip detail for the Next.js trip detail page (SSR). Returns all nested data in a single request.

**Auth:** Anonymous  
**ORM:** `select_related('destination', 'category', 'expedition_detail')` + `prefetch_related('itinerary_days', 'departures', 'reviews', 'faqs')`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "title": "Everest Base Camp Trek",
    "slug": "everest-base-camp-trek",
    "overview": "The most iconic trek in the Himalayas...",
    "duration_days": 14,
    "altitude_max_meters": 5364,
    "difficulty_grade": "GRADE_3",
    "min_group_size": 1,
    "max_group_size": 14,
    "best_seasons": ["SPRING", "AUTUMN"],
    "starting_price_usd": "1350.00",
    "single_supplement_usd": "250.00",
    "inclusions": ["Airport transfers", "TIMS & park permits", "Teahouse accommodation", "All meals on trail"],
    "exclusions": ["International flights", "Travel insurance", "Personal gear"],
    "packing_list": ["Down jacket", "Trekking poles", "Sleeping bag (-20 deg C)"],
    "destination": {
      "id": "uuid-string",
      "name": "Khumbu / Everest Region",
      "slug": "khumbu-everest-region",
      "country": "NEPAL"
    },
    "category": {
      "id": "uuid-string",
      "name": "Classic Trekking",
      "slug": "classic-trekking"
    },
    "expedition_detail": null,
    "itinerary_days": [
      {
        "day_number": 1,
        "title": "Arrival in Kathmandu",
        "description": "Transfer to hotel, trek briefing...",
        "overnight_stay": "Kathmandu",
        "elevation_meters": 1400,
        "accommodation_type": "HOTEL",
        "is_acclimatization_day": false,
        "meals_included": ["D"],
        "latitude": 27.7172,
        "longitude": 85.3240
      }
    ],
    "departures": [
      {
        "id": "uuid-string",
        "start_date": "2026-03-15",
        "end_date": "2026-03-29",
        "price_usd": "1350.00",
        "available_seats": 8,
        "max_seats": 14,
        "status": "LIMITED",
        "is_guaranteed": true
      }
    ],
    "rating_summary": {
      "average_overall": 4.7,
      "total_reviews": 42,
      "rating_guide": 4.8,
      "rating_itinerary": 4.6,
      "rating_safety": 4.9
    },
    "reviews": [
      {
        "id": "uuid-string",
        "reviewer_name": "Sarah M.",
        "reviewer_country": "Australia",
        "rating_overall": 5,
        "title": "Life-changing experience!",
        "content": "...",
        "travel_date": "2025-10-01",
        "is_verified": true,
        "created_at": "2025-11-15T08:00:00Z"
      }
    ],
    "schema_org": {
      "@context": "https://schema.org",
      "@type": "TouristTrip",
      "name": "Everest Base Camp Trek",
      "description": "...",
      "offers": {
        "@type": "Offer",
        "price": "1350.00",
        "priceCurrency": "USD"
      },
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": 4.7,
        "reviewCount": 42
      }
    }
  },
  "message": "Trip retrieved successfully."
}
```

---

### `POST /api/v1/trips/` *(Admin Only)*

Create a new trip.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "destination": "uuid-destination-id",
  "category": "uuid-category-id",
  "title": "Annapurna Circuit Trek",
  "slug": "annapurna-circuit-trek",
  "duration_days": 16,
  "altitude_max_meters": 5416,
  "difficulty_grade": "GRADE_3",
  "min_group_size": 1,
  "max_group_size": 12,
  "best_seasons": ["SPRING", "AUTUMN"],
  "starting_price_usd": "1200.00",
  "single_supplement_usd": "200.00",
  "overview": "...",
  "inclusions": ["..."],
  "exclusions": ["..."],
  "packing_list": ["..."],
  "is_featured": false,
  "is_active": true
}
```

**Response `201 Created`** → Full trip detail object.

---

### `PATCH /api/v1/trips/{slug}/` *(Admin Only)*

Partially update a trip.

**Auth:** `ADMIN`

---

### `DELETE /api/v1/trips/{slug}/` *(Admin Only)*

Soft-delete: sets `is_active=False`.

**Auth:** `ADMIN`

---

### `GET /api/v1/trips/{slug}/itinerary/`

Day-by-day itinerary with GPS coordinates for map rendering.

**Auth:** Anonymous

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "trip_slug": "everest-base-camp-trek",
    "total_days": 14,
    "itinerary": [
      {
        "day_number": 1,
        "title": "Arrival in Kathmandu",
        "description": "...",
        "overnight_stay": "Kathmandu",
        "elevation_meters": 1400,
        "accommodation_type": "HOTEL",
        "is_acclimatization_day": false,
        "meals_included": ["D"],
        "latitude": 27.7172,
        "longitude": 85.3240
      }
    ]
  },
  "message": "Itinerary retrieved successfully."
}
```

---

### `POST /api/v1/trips/{slug}/itinerary/` *(Admin Only)*

Add a new itinerary day to a trip.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "day_number": 2,
  "title": "Fly to Lukla, Trek to Phakding",
  "description": "...",
  "overnight_stay": "Phakding",
  "elevation_meters": 2610,
  "accommodation_type": "TEAHOUSE",
  "is_acclimatization_day": false,
  "meals_included": ["B", "L", "D"],
  "latitude": 27.7457,
  "longitude": 86.7145
}
```

**Response `201 Created`** → Created itinerary day object.

---

### `PATCH /api/v1/trips/{slug}/itinerary/{day_number}/` *(Admin Only)*

Update a specific itinerary day by its day number.

**Auth:** `ADMIN`

---

### `DELETE /api/v1/trips/{slug}/itinerary/{day_number}/` *(Admin Only)*

Delete a specific itinerary day.

**Auth:** `ADMIN`

---

### `GET /api/v1/trips/{slug}/departures/`

List all upcoming departures for a trip.

**Auth:** Anonymous  
**Query Params:** `?status=LIMITED&from_date=2026-01-01&to_date=2026-12-31`

**Response `200 OK`**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-string",
      "start_date": "2026-03-15",
      "end_date": "2026-03-29",
      "price_usd": "1350.00",
      "available_seats": 8,
      "max_seats": 14,
      "status": "LIMITED",
      "is_guaranteed": true
    }
  ],
  "message": "Departures retrieved successfully."
}
```

---

### `POST /api/v1/trips/{slug}/departures/` *(Admin Only)*

Create a new departure for a trip. `available_seats` defaults to `max_seats`.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "start_date": "2026-10-01",
  "end_date": "2026-10-15",
  "price_usd": "1450.00",
  "max_seats": 14,
  "is_guaranteed": false
}
```

**Response `201 Created`**

---

### `PATCH /api/v1/trips/{slug}/departures/{departure_id}/` *(Admin Only)*

Update departure status, pricing, or seat count.

**Auth:** `ADMIN`

---

### `GET /api/v1/trips/{slug}/reviews/`

List published, approved reviews for a trip.

**Auth:** Anonymous  
**Query Params:** `?ordering=-created_at&is_verified=true`

**Response `200 OK`** → Paginated list of review objects.

---

### `POST /api/v1/trips/{slug}/reviews/`

Submit a review. If `booking_id` belongs to the authenticated user, `is_verified` is auto-set `True`. Reviews require admin approval before publishing.

**Auth:** `CUSTOMER`

**Request Body**
```json
{
  "booking_id": "uuid-booking-id",
  "reviewer_name": "John Doe",
  "reviewer_country": "Australia",
  "rating_overall": 5,
  "rating_guide": 5,
  "rating_itinerary": 4,
  "rating_safety": 5,
  "title": "Absolutely incredible experience!",
  "content": "The guides were incredible...",
  "travel_date": "2026-03-15"
}
```

**Response `201 Created`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "is_verified": true,
    "is_published": false
  },
  "message": "Review submitted and is pending admin approval."
}
```

---

### `PATCH /api/v1/trips/{slug}/reviews/{review_id}/` *(Admin Only)*

Publish or unpublish a review.

**Auth:** `ADMIN`

**Request Body**
```json
{ "is_published": true }
```

---

### `GET /api/v1/trips/{slug}/expedition-detail/`

Expedition-specific details for a technical mountaineering trip. Returns `404` if no expedition detail exists.

**Auth:** Anonymous

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "trip_slug": "island-peak-expedition",
    "summit_window": "April - May",
    "technical_rating": "PD (Peu Difficile)",
    "gear_requirements": ["Crampons", "Ice axe", "Jumar", "Harness", "Fixed rope experience"],
    "permit_fee_type": "Nepal Mountaineering Association (NMA) Permit",
    "mandatory_certifications": ["Basic mountaineering course", "Medical fitness certificate"]
  },
  "message": "Expedition details retrieved successfully."
}
```

---

### `POST /api/v1/trips/{slug}/expedition-detail/` *(Admin Only)*

Attach expedition detail to a technical trip.

**Auth:** `ADMIN`

---

## 6. Bookings — `/api/v1/bookings/`

The split-payment booking engine. Atomically locks departure seats and supports `FULL_100` and `DEPOSIT_20` payment modalities.

---

### `POST /api/v1/bookings/`

Initiate a new booking. Atomically locks a departure seat and creates passenger records.

**Auth:** `CUSTOMER` or Anonymous (guest booking)  
**Transaction:** `@transaction.atomic` with `select_for_update()` on `TripDeparture`

**Request Body**
```json
{
  "departure_id": "uuid-departure-id",
  "payment_type": "DEPOSIT_20",
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "customer_phone": "+9779841000000",
  "num_travelers": 2,
  "passengers": [
    {
      "full_name": "John Doe",
      "gender": "MALE",
      "date_of_birth": "1990-06-15",
      "passport_number": "A12345678",
      "passport_expiry_date": "2029-06-15",
      "nationality": "Australian",
      "insurance_provider": "World Nomads",
      "insurance_policy_number": "WN-8876543",
      "insurance_emergency_phone": "+61291234567",
      "emergency_contact_name": "Jane Doe",
      "emergency_contact_phone": "+61491234567",
      "dietary_requirements": "Vegetarian",
      "medical_conditions": "None"
    }
  ]
}
```

**Validation Rules**
- `departure.available_seats >= num_travelers` — enforced with `select_for_update()`.
- `passengers` array length must equal `num_travelers`.
- Passport expiry must be ≥ 6 months from `trip_start_date`.
- Departure `status` must not be `SOLD_OUT`.

**Business Logic on Create**
- Generate `booking_reference`: `DS-{YEAR}-{RANDOM5}` (e.g. `DS-2026-X8B9Q`).
- Compute `deposit_amount_usd = total_amount_usd * 0.20`.
- Compute `balance_amount_usd = total_amount_usd * 0.80`.
- Compute `balance_due_date = trip_start_date - 7 days`.
- Atomically decrement `departure.available_seats`.
- Set `departure.status = SOLD_OUT` if `available_seats` reaches `0`.
- Trigger Celery: send booking confirmation email via Resend.

**Response `201 Created`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "booking_reference": "DS-2026-X8B9Q",
    "status": "PENDING",
    "payment_type": "DEPOSIT_20",
    "departure": {
      "id": "uuid-string",
      "start_date": "2026-03-15",
      "end_date": "2026-03-29",
      "trip_title": "Everest Base Camp Trek"
    },
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "num_travelers": 2,
    "total_amount_usd": "2700.00",
    "deposit_amount_usd": "540.00",
    "balance_amount_usd": "2160.00",
    "amount_paid_usd": "0.00",
    "balance_due_date": "2026-03-08",
    "passengers": [ { "full_name": "John Doe" } ]
  },
  "message": "Booking created. Please proceed to payment to confirm your reservation."
}
```

**Error `409`** → `SEATS_UNAVAILABLE`

---

### `GET /api/v1/bookings/{booking_reference}/`

Retrieve full booking detail including payment history.

**Auth:** `CUSTOMER` (own bookings only), `SALES_AGENT`, `ADMIN`  
**ORM:** `select_related('departure__trip', 'customer_user')` + `prefetch_related('passengers', 'payments')`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "booking_reference": "DS-2026-X8B9Q",
    "status": "DEPOSIT_PAID",
    "payment_type": "DEPOSIT_20",
    "departure": { "start_date": "2026-03-15", "end_date": "2026-03-29", "trip_title": "Everest Base Camp Trek" },
    "total_amount_usd": "2700.00",
    "deposit_amount_usd": "540.00",
    "balance_amount_usd": "2160.00",
    "amount_paid_usd": "540.00",
    "balance_due_date": "2026-03-08",
    "passengers": [ { ... } ],
    "payments": [
      {
        "transaction_id": "khalti_txn_abc123",
        "gateway": "KHALTI",
        "payment_stage": "DEPOSIT_20",
        "amount": "540.00",
        "status": "SUCCESS",
        "created_at": "2026-01-20T10:30:00Z"
      }
    ]
  },
  "message": "Booking retrieved successfully."
}
```

---

### `GET /api/v1/bookings/`

List bookings. Customers see only their own. Agents and admins see all.

**Auth:** `CUSTOMER`, `SALES_AGENT`, `ADMIN`  
**Query Params:** `?status=DEPOSIT_PAID&customer_email=john@example.com`

**Response `200 OK`** → Paginated booking list.

---

### `PATCH /api/v1/bookings/{booking_reference}/cancel/`

Cancel a booking. Releases the locked seats atomically.

**Auth:** `CUSTOMER` (own booking, status `PENDING` or `DEPOSIT_PAID`), `ADMIN`

**Request Body**
```json
{ "cancellation_reason": "Change of plans due to health reasons." }
```

**Response `200 OK`**
```json
{
  "success": true,
  "data": { "booking_reference": "DS-2026-X8B9Q", "status": "CANCELLED" },
  "message": "Booking cancelled. Refunds will be processed within 5-7 business days."
}
```

---

### `GET /api/v1/bookings/{booking_reference}/passengers/`

List all passengers attached to a booking.

**Auth:** `CUSTOMER` (own booking), `SALES_AGENT`, `ADMIN`

---

### `PATCH /api/v1/bookings/{booking_reference}/passengers/{passenger_id}/`

Update a specific passenger's details (e.g. corrected passport number).

**Auth:** `CUSTOMER` (own booking, pre-departure), `ADMIN`

---

## 7. Payments — `/api/v1/payments/`

Gateway session initiation, HMAC webhook processing, and one-click balance payment via signed tokens.

---

### `POST /api/v1/payments/initiate/`

Initiate a payment session. Returns a gateway checkout URL.

**Auth:** `CUSTOMER` or Anonymous (with booking reference)  
**Throttle:** `10/minute` per user

**Request Body**
```json
{
  "booking_reference": "DS-2026-X8B9Q",
  "gateway": "KHALTI",
  "payment_stage": "DEPOSIT_20",
  "return_url": "https://dreamscapetreks.com/booking/DS-2026-X8B9Q/confirm",
  "website_url": "https://dreamscapetreks.com"
}
```

**Business Logic**
- Validates booking status is `PENDING` for `DEPOSIT_20`/`FULL_100` stages.
- Validates booking status is `DEPOSIT_PAID` for `BALANCE_80` stage.
- Locks USD→NPR exchange rate at initiation time.
- Creates `PaymentTransaction` record (`status=INITIATED`) with unique `idempotency_key`.
- Calls Khalti/Stripe API to create checkout session.

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "transaction_id": "txn_uuid_string",
    "gateway": "KHALTI",
    "payment_stage": "DEPOSIT_20",
    "amount_usd": "540.00",
    "charged_amount_npr": "72900.00",
    "exchange_rate": "135.00",
    "checkout_url": "https://test-pay.khalti.com/?pidx=abc123xyz",
    "expires_in_seconds": 3600
  },
  "message": "Payment session initiated. Redirecting to gateway..."
}
```

---

### `POST /api/v1/payments/webhook/khalti/`

Khalti payment webhook. Validates HMAC signature and processes transaction result idempotently.

**Auth:** None (server-to-server; validated by HMAC in headers)  
**Transaction:** `@transaction.atomic` with `select_for_update()` on `PaymentTransaction`

**Request Headers**
```
X-Khalti-Signature: <hmac_sha256_signature>
Content-Type: application/json
```

**Request Body**
```json
{
  "event": "payment.completed",
  "pidx": "abc123xyz",
  "transaction_id": "khalti_txn_success_ref",
  "amount": 72900,
  "status": "Completed"
}
```

**Business Logic on Success**
1. Validate HMAC signature — reject `400` if invalid.
2. Fetch `PaymentTransaction` with `select_for_update()`.
3. Reject duplicate `webhook_event_id` with `409 IDEMPOTENCY_CONFLICT`.
4. Set `PaymentTransaction.status = SUCCESS`, `processed_at = now()`.
5. Update `Booking.amount_paid_usd += payment.amount`.
6. Transition `Booking.status`:
   - `DEPOSIT_20` stage → `DEPOSIT_PAID`
   - `BALANCE_80` or `FULL_100` stage → `FULLY_PAID`
7. Trigger Celery: send payment receipt email via Resend.
8. Trigger Celery: send WhatsApp alert to internal agent.

**Response `200 OK`**
```json
{ "received": true }
```

---

### `POST /api/v1/payments/webhook/bank/`

International bank transfer webhook handler. Same idempotency and transition logic as Khalti.

**Auth:** None (server-to-server, HMAC validated)

---

### `POST /api/v1/payments/balance/pay/`

One-click 80% balance payment via a signed `PaymentActionToken` (delivered in the Celery email reminder). Stateless — the token is the auth.

**Auth:** None (token-authenticated)

**Request Body**
```json
{
  "token": "<signed_token_from_email_link>",
  "gateway": "KHALTI",
  "return_url": "https://dreamscapetreks.com/booking/DS-2026-X8B9Q/paid"
}
```

**Business Logic**
- Validate `token_hash` exists in `PaymentActionToken`.
- Check `expires_at > now()` and `used_at IS NULL`.
- Atomically set `used_at = now()` to prevent double-use.
- Initiate `BALANCE_80` checkout with selected gateway.

**Response `200 OK`** → Same schema as `/payments/initiate/`.

**Error `410`** → `TOKEN_EXPIRED`

---

### `GET /api/v1/payments/transactions/`

List all payment transactions for authenticated user's bookings.

**Auth:** `CUSTOMER`, `SALES_AGENT`, `ADMIN`  
**Query Params:** `?booking_reference=DS-2026-X8B9Q&status=SUCCESS&gateway=KHALTI`

**Response `200 OK`** → Paginated transaction list.

---

### `GET /api/v1/payments/transactions/{transaction_id}/`

Retrieve a single payment transaction (receipt view).

**Auth:** `CUSTOMER` (own booking), `ADMIN`

---

## 8. Inquiries — `/api/v1/inquiries/`

Lead capture, CRM pipeline management, and tailor-made trip builder.

---

### `POST /api/v1/inquiries/`

Submit a general, trip-specific, or tailor-made inquiry. Always public.

**Auth:** Anonymous  
**Throttle:** `10/hour` per IP  
**Celery:** Dispatches acknowledgement email to client within 5 seconds.

**Request Body (General)**
```json
{
  "inquiry_type": "GENERAL",
  "full_name": "Sarah Mitchell",
  "email": "sarah@example.com",
  "phone": "+61491234567",
  "whatsapp_number": "+61491234567",
  "message": "I'm interested in trekking in Nepal next spring.",
  "group_size": 3,
  "preferred_dates": "March - April 2027",
  "estimated_budget": "5000.00",
  "lead_source": "WEBSITE"
}
```

**Request Body (Journey — trip-specific)**
```json
{
  "inquiry_type": "JOURNEY",
  "trip_id": "uuid-trip-id",
  "departure_id": "uuid-departure-id",
  "full_name": "Sarah Mitchell",
  "email": "sarah@example.com",
  "phone": "+61491234567",
  "message": "Is the October departure still available?",
  "group_size": 2,
  "preferred_dates": "October 2026"
}
```

**Request Body (Tailor-Made)**
```json
{
  "inquiry_type": "TAILOR_MADE",
  "full_name": "James Harper",
  "email": "james@example.com",
  "phone": "+44791234567",
  "message": "Looking for a combined Nepal + Bhutan itinerary.",
  "group_size": 4,
  "preferred_dates": "April 2027",
  "estimated_budget": "8000.00",
  "tailor_made": {
    "custom_destinations": ["NEPAL", "BHUTAN"],
    "desired_activities": ["Trekking", "Cultural Tours"],
    "fitness_level": "Moderate",
    "accommodation_standard": "Luxury Lodges",
    "guide_language_preference": "English",
    "custom_route_coordinates": [
      { "name": "Kathmandu", "lat": 27.7172, "lng": 85.3240 },
      { "name": "Paro", "lat": 27.4285, "lng": 89.4129 }
    ],
    "waypoints": ["Namche Bazaar", "Tengboche", "Paro Taktsang"]
  }
}
```

**Response `201 Created`**
```json
{
  "success": true,
  "data": {
    "inquiry_number": "INQ-2026-9082",
    "inquiry_type": "TAILOR_MADE",
    "status": "NEW",
    "full_name": "James Harper",
    "email": "james@example.com"
  },
  "message": "We have received your journey inquiry. Our team will respond within 24 hours."
}
```

---

### `GET /api/v1/inquiries/` *(Agent/Admin Only)*

List all inquiries with CRM filtering.

**Auth:** `SALES_AGENT`, `ADMIN`  
**ORM:** `select_related('trip', 'departure', 'assigned_agent')` + `prefetch_related('tailor_made_detail', 'notes__author')`  
**Query Params:** `?status=NEW&inquiry_type=TAILOR_MADE&assigned_agent=uuid&search=sarah`

**Response `200 OK`** → Paginated inquiry list.

---

### `GET /api/v1/inquiries/{inquiry_number}/` *(Agent/Admin Only)*

Retrieve a single inquiry with full CRM data: tailor-made plan, notes thread, assigned agent.

**Auth:** `SALES_AGENT`, `ADMIN`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "inquiry_number": "INQ-2026-9082",
    "inquiry_type": "TAILOR_MADE",
    "status": "ASSIGNED",
    "full_name": "James Harper",
    "email": "james@example.com",
    "phone": "+44791234567",
    "group_size": 4,
    "preferred_dates": "April 2027",
    "estimated_budget": "8000.00",
    "lead_source": "WEBSITE",
    "assigned_agent": {
      "id": "uuid-string",
      "full_name": "Pemba Sherpa",
      "email": "pemba@dreamscapetreks.com"
    },
    "tailor_made_detail": {
      "custom_destinations": ["NEPAL", "BHUTAN"],
      "desired_activities": ["Trekking", "Cultural Tours"],
      "fitness_level": "Moderate",
      "accommodation_standard": "Luxury Lodges",
      "guide_language_preference": "English",
      "custom_route_coordinates": [ { "name": "Kathmandu", "lat": 27.7172, "lng": 85.3240 } ],
      "waypoints": ["Namche Bazaar", "Tengboche", "Paro Taktsang"]
    },
    "notes": [
      {
        "id": "uuid-string",
        "author": { "full_name": "Pemba Sherpa" },
        "note_text": "Called client. Flexible on dates but firm on luxury lodges.",
        "created_at": "2026-01-21T11:00:00Z"
      }
    ],
    "created_at": "2026-01-20T14:22:00Z"
  },
  "message": "Inquiry retrieved successfully."
}
```

---

### `PATCH /api/v1/inquiries/{inquiry_number}/` *(Agent/Admin Only)*

Update inquiry status, assign an agent, or update lead details.

**Auth:** `SALES_AGENT`, `ADMIN`

**Request Body**
```json
{
  "status": "IN_CONTACT",
  "assigned_agent": "uuid-agent-user-id"
}
```

**Valid Status Transitions:** `NEW` → `ASSIGNED` → `IN_CONTACT` → `TRAVELING` → `COMPLETED` → `CLOSED`

---

### `POST /api/v1/inquiries/{inquiry_number}/notes/` *(Agent/Admin Only)*

Add an internal CRM note to an inquiry.

**Auth:** `SALES_AGENT`, `ADMIN`

**Request Body**
```json
{ "note_text": "Sent customized itinerary PDF. Awaiting client feedback." }
```

**Response `201 Created`**

---

### `GET /api/v1/inquiries/{inquiry_number}/notes/` *(Agent/Admin Only)*

List all internal notes for an inquiry.

**Auth:** `SALES_AGENT`, `ADMIN`

---

## 9. B2B Partner Portal — `/api/v1/b2b/`

Travel agency registration, management, tier-filtered asset downloads, and commission ledger.

---

### `POST /api/v1/b2b/register/`

Register a new travel agency. Creates a `User` (role=`B2B_PARTNER`) and pending `B2BPartner` profile.

**Auth:** Anonymous  
**Celery:** Sends agency confirmation email + internal admin alert.

**Request Body**
```json
{
  "email": "reservations@mountaintrekkers.com",
  "password": "AgencyPass@2024",
  "password_confirm": "AgencyPass@2024",
  "first_name": "Marco",
  "last_name": "Rossi",
  "phone": "+390612345678",
  "company_name": "Mountain Trekkers Italy",
  "country": "Italy",
  "registration_number": "IT-REG-12345",
  "website": "https://mountaintrekkers.it"
}
```

**Response `201 Created`**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid-string",
    "partner_id": "uuid-string",
    "company_name": "Mountain Trekkers Italy",
    "agency_tier": "BRONZE",
    "approved": false
  },
  "message": "Registration received. Your agency account is pending admin approval."
}
```

---

### `POST /api/v1/b2b/partners/{partner_id}/approve/` *(Admin Only)*

Approve a B2B partner application and set tier/commission.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "approved": true,
  "agency_tier": "SILVER",
  "commission_rate": "12.50"
}
```

**Response `200 OK`** → Triggers Celery approval email to partner.

---

### `GET /api/v1/b2b/partners/` *(Admin Only)*

List all B2B partners.

**Auth:** `ADMIN`  
**Query Params:** `?approved=true&agency_tier=GOLD&country=Italy`

---

### `GET /api/v1/b2b/partners/me/`

Retrieve own partner profile.

**Auth:** `B2B_PARTNER`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "company_name": "Mountain Trekkers Italy",
    "country": "Italy",
    "agency_tier": "SILVER",
    "commission_rate": "12.50",
    "approved": true,
    "website": "https://mountaintrekkers.it"
  },
  "message": "Partner profile retrieved successfully."
}
```

---

### `PATCH /api/v1/b2b/partners/me/`

Update own partner profile (company info, website, phone).

**Auth:** `B2B_PARTNER`  
**Note:** `agency_tier`, `commission_rate`, and `approved` are admin-only fields.

---

### `GET /api/v1/b2b/assets/`

List marketing assets available for the partner's tier (BRONZE < SILVER < GOLD < PLATINUM).

**Auth:** `B2B_PARTNER` (approved only)  
**ORM:** `select_related('trip')`  
**Query Params:** `?asset_type=WHITE_LABEL_ITINERARY&trip_slug=everest-base-camp-trek`

**Response `200 OK`**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-string",
      "title": "Everest Base Camp Trek — White Label Itinerary",
      "asset_type": "WHITE_LABEL_ITINERARY",
      "trip": { "title": "Everest Base Camp Trek", "slug": "everest-base-camp-trek" },
      "minimum_tier": "BRONZE",
      "download_url": "/api/v1/b2b/assets/uuid-string/download/"
    }
  ],
  "message": "Assets retrieved successfully."
}
```

---

### `GET /api/v1/b2b/assets/{asset_id}/download/`

Authenticated, tier-gated asset download. Returns a signed, time-limited CDN URL.

**Auth:** `B2B_PARTNER` (approved, tier >= asset.minimum_tier)

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "download_url": "https://cdn.dreamscapetreks.com/b2b_assets/signed-url?expires=...",
    "expires_in_seconds": 300
  },
  "message": "Download URL generated."
}
```

**Error `403`** → `TIER_INSUFFICIENT`

---

### `GET /api/v1/b2b/bookings/`

List all bookings attributed to the partner, showing commission ledger.

**Auth:** `B2B_PARTNER` (own), `ADMIN` (all)  
**Query Params:** `?commission_status=PENDING&from_date=2026-01-01`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "count": 5,
    "results": [
      {
        "id": "uuid-string",
        "booking_reference": "DS-2026-M1T2P",
        "trip_title": "Everest Base Camp Trek",
        "gross_amount_usd": "2700.00",
        "commission_rate": "12.50",
        "commission_amount_usd": "337.50",
        "net_amount_usd": "2362.50",
        "commission_status": "PENDING",
        "commission_invoiced_at": null,
        "commission_paid_at": null
      }
    ]
  },
  "message": "Partner bookings retrieved successfully."
}
```

---

### `PATCH /api/v1/b2b/bookings/{b2b_booking_id}/commission/` *(Admin Only)*

Update commission payment status.

**Auth:** `ADMIN`

**Request Body**
```json
{ "commission_status": "INVOICED" }
```

---

## 10. Content CMS — `/api/v1/content/`

Travel guides and responsible travel initiatives for Next.js SSR/ISR pages with Schema.org metadata.

---

### `GET /api/v1/content/guides/`

List published travel guides.

**Auth:** Anonymous  
**ORM:** `select_related('destination', 'author')`  
**Query Params:** `?country=NEPAL&category=PERMITS&destination=khumbu-everest-region&search=altitude`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "count": 24,
    "results": [
      {
        "id": "uuid-string",
        "title": "Nepal Trekking Permits Guide 2026",
        "slug": "nepal-trekking-permits-guide-2026",
        "category": "PERMITS",
        "country": "Nepal",
        "destination": { "name": "Khumbu / Everest Region", "slug": "khumbu-everest-region" },
        "hero_image_url": "https://cdn.dreamscapetreks.com/guides/permits.jpg",
        "published_at": "2026-01-10T00:00:00Z"
      }
    ]
  },
  "message": "Travel guides retrieved successfully."
}
```

---

### `GET /api/v1/content/guides/{slug}/`

Full guide detail with markdown content and Schema.org `Article` + `BreadcrumbList` for Next.js SSR.

**Auth:** Anonymous

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "title": "Nepal Trekking Permits Guide 2026",
    "slug": "nepal-trekking-permits-guide-2026",
    "category": "PERMITS",
    "country": "Nepal",
    "region": "Khumbu",
    "destination": { "name": "Khumbu / Everest Region", "slug": "khumbu-everest-region" },
    "markdown_content": "## TIMS Card\nAll trekkers in Nepal require...",
    "hero_image_url": "https://cdn.dreamscapetreks.com/guides/permits.jpg",
    "meta_title": "Nepal Trekking Permits Guide 2026 — Dreamscape Treks",
    "meta_description": "Complete guide to TIMS cards, Sagarmatha National Park permits...",
    "canonical_url": "https://dreamscapetreks.com/guides/nepal-trekking-permits-guide-2026",
    "published_at": "2026-01-10T00:00:00Z",
    "author": { "full_name": "Ang Dorji Sherpa" },
    "schema_org": {
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Nepal Trekking Permits Guide 2026",
      "author": { "@type": "Person", "name": "Ang Dorji Sherpa" },
      "datePublished": "2026-01-10",
      "breadcrumb": {
        "@type": "BreadcrumbList",
        "itemListElement": [ { "@type": "ListItem", "position": 1, "name": "Guides", "item": "https://dreamscapetreks.com/guides" } ]
      }
    }
  },
  "message": "Travel guide retrieved successfully."
}
```

---

### `POST /api/v1/content/guides/` *(Admin Only)*

Create a new travel guide.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "destination": "uuid-destination-id",
  "title": "Bhutan Cultural Etiquette Guide",
  "slug": "bhutan-cultural-etiquette-guide",
  "country": "Bhutan",
  "region": "Paro Valley",
  "category": "CULTURE",
  "markdown_content": "## Dress Code\n...",
  "hero_image_url": "https://cdn.dreamscapetreks.com/guides/bhutan.jpg",
  "meta_title": "Bhutan Cultural Etiquette — Dreamscape Treks",
  "meta_description": "...",
  "canonical_url": "https://dreamscapetreks.com/guides/bhutan-cultural-etiquette-guide",
  "is_published": false
}
```

**Response `201 Created`**

---

### `PATCH /api/v1/content/guides/{slug}/` *(Admin Only)*

Update a guide. Publishing for the first time auto-sets `published_at`.

**Auth:** `ADMIN`

---

### `DELETE /api/v1/content/guides/{slug}/` *(Admin Only)*

Soft-delete by setting `is_published=False`.

**Auth:** `ADMIN`

---

### `GET /api/v1/content/responsible-travel/`

List all published responsible travel initiatives.

**Auth:** Anonymous

**Response `200 OK`**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-string",
      "title": "Porter Welfare Standards",
      "slug": "porter-welfare-standards",
      "pillars": ["Porter Welfare", "Community"],
      "content": "At Dreamscape Treks, we are committed to..."
    }
  ],
  "message": "Responsible travel initiatives retrieved successfully."
}
```

---

### `GET /api/v1/content/responsible-travel/{slug}/`

Retrieve a single responsible travel initiative.

**Auth:** Anonymous

---

### `POST /api/v1/content/responsible-travel/` *(Admin Only)*

Create a responsible travel initiative.

**Auth:** `ADMIN`

---

## 11. FAQs — `/api/v1/faqs/`

Contextual FAQs scoped to global, trip-specific, or destination-specific contexts. Includes Schema.org `FAQPage` JSON-LD.

---

### `GET /api/v1/faqs/`

Retrieve FAQs, optionally filtered by trip or destination.

**Auth:** Anonymous  
**ORM:** `select_related('trip', 'destination')`  
**Query Params:** `?trip={trip_slug}&destination={destination_slug}&category=TREKKING`

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "faqs": [
      {
        "id": "uuid-string",
        "question": "What fitness level is required for Everest Base Camp Trek?",
        "answer": "You should be able to walk 5-6 hours per day on hilly terrain...",
        "category": "TREKKING",
        "display_order": 1
      }
    ],
    "schema_org": {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What fitness level is required for Everest Base Camp Trek?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "You should be able to walk 5-6 hours per day..."
          }
        }
      ]
    }
  },
  "message": "FAQs retrieved successfully."
}
```

---

### `POST /api/v1/faqs/` *(Admin Only)*

Create a new FAQ.

**Auth:** `ADMIN`

**Request Body**
```json
{
  "trip": "uuid-trip-id",
  "destination": null,
  "question": "Do I need travel insurance for trekking in Nepal?",
  "answer": "Yes, comprehensive travel insurance with helicopter evacuation coverage is mandatory...",
  "category": "TREKKING",
  "display_order": 2,
  "is_active": true
}
```

---

### `PATCH /api/v1/faqs/{id}/` *(Admin Only)*

Update an FAQ content, display order, or active status.

**Auth:** `ADMIN`

---

### `DELETE /api/v1/faqs/{id}/` *(Admin Only)*

Soft-delete by setting `is_active=False`.

**Auth:** `ADMIN`

---

## 12. Search — `/api/v1/search/`

Multi-entity PostgreSQL full-text search returning ranked, unified results.

---

### `GET /api/v1/search/`

Cross-entity full-text search.

**Auth:** Anonymous  
**Throttle:** `60/minute` per IP

**Query Params:**

| Param | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `q` | `string` | Yes | Search query (min 2 characters) |
| `entity_type` | `string` | No | Filter by `trip`, `destination`, `guide`, `faq` |
| `page` | `int` | No | Page number |

**PostgreSQL SearchVector Weights**

| Source Model | Searched Fields | Weight |
| :--- | :--- | :---: |
| `Trip` | `title`, `slug` | A (highest) |
| `Trip` | `overview` | B |
| `Destination` | `name`, `region_name` | A |
| `TravelGuide` | `title` | A |
| `TravelGuide` | `markdown_content` | C |
| `FAQ` | `question` | B |
| `FAQ` | `answer` | C |

**Response `200 OK`**
```json
{
  "success": true,
  "data": {
    "query": "everest",
    "count": 12,
    "results": [
      {
        "entity_type": "trip",
        "title": "Everest Base Camp Trek",
        "slug": "everest-base-camp-trek",
        "snippet": "The most iconic trek in the Himalayas, reaching the base of the world's highest mountain...",
        "rank_score": 0.9847,
        "meta": {
          "duration_days": 14,
          "starting_price_usd": "1350.00",
          "difficulty_grade": "GRADE_3"
        }
      },
      {
        "entity_type": "destination",
        "title": "Khumbu / Everest Region",
        "slug": "khumbu-everest-region",
        "snippet": "Home to the world's highest peak...",
        "rank_score": 0.9215,
        "meta": { "country": "NEPAL" }
      },
      {
        "entity_type": "guide",
        "title": "Everest Base Camp Packing List 2026",
        "slug": "everest-base-camp-packing-list-2026",
        "snippet": "Essential gear for your Everest Base Camp adventure...",
        "rank_score": 0.7340,
        "meta": { "category": "BEST_TIME" }
      }
    ]
  },
  "message": "Search results retrieved successfully."
}
```

**Error `400`** → `VALIDATION_ERROR` — Query less than 2 characters.

---

## 13. Permission Matrix

| Endpoint Group | Anonymous | Customer | Sales Agent | B2B Partner | Admin |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `POST /auth/register/` | ✅ | — | — | — | — |
| `POST /auth/login/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /users/me/` | ❌ | ✅ | ✅ | ✅ | ✅ |
| `PATCH /users/me/` | ❌ | ✅ | ✅ | ✅ | ✅ |
| `GET /users/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `GET /destinations/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /destinations/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `GET /trips/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /trips/{slug}/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /trips/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `POST /trips/{slug}/departures/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `POST /trips/{slug}/reviews/` | ❌ | ✅ | ❌ | ❌ | ✅ |
| `PATCH /trips/{slug}/reviews/{id}/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `POST /bookings/` | ✅* | ✅ | ✅ | ✅ | ✅ |
| `GET /bookings/` | ❌ | ✅ (own) | ✅ | ❌ | ✅ |
| `GET /bookings/{ref}/` | ❌ | ✅ (own) | ✅ | ❌ | ✅ |
| `PATCH /bookings/{ref}/cancel/` | ❌ | ✅ (own) | ✅ | ❌ | ✅ |
| `POST /payments/initiate/` | ✅* | ✅ | ✅ | ✅ | ✅ |
| `POST /payments/webhook/khalti/` | server-to-server | — | — | — | — |
| `POST /payments/balance/pay/` | ✅ (token-auth) | — | — | — | — |
| `POST /inquiries/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /inquiries/` | ❌ | ❌ | ✅ | ❌ | ✅ |
| `PATCH /inquiries/{num}/` | ❌ | ❌ | ✅ | ❌ | ✅ |
| `POST /inquiries/{num}/notes/` | ❌ | ❌ | ✅ | ❌ | ✅ |
| `POST /b2b/register/` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `POST /b2b/partners/{id}/approve/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `GET /b2b/assets/` | ❌ | ❌ | ❌ | ✅ (approved) | ✅ |
| `GET /b2b/assets/{id}/download/` | ❌ | ❌ | ❌ | ✅ (tier-gated) | ✅ |
| `GET /b2b/bookings/` | ❌ | ❌ | ❌ | ✅ (own) | ✅ |
| `GET /content/guides/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /content/guides/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `GET /content/responsible-travel/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /faqs/` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `POST /faqs/` | ❌ | ❌ | ❌ | ❌ | ✅ |
| `GET /search/` | ✅ | ✅ | ✅ | ✅ | ✅ |

> *Anonymous users can guest-book and initiate payment using only a booking reference.

---

## 14. Error Code Reference

| Code | HTTP | Trigger Scenario |
| :--- | :--- | :--- |
| `VALIDATION_ERROR` | 400 | DRF serializer / field-level validation failure |
| `UNAUTHORIZED` | 401 | No JWT token, expired token, or wrong credentials |
| `FORBIDDEN` | 403 | Role insufficient for the requested action |
| `NOT_FOUND` | 404 | `Model.DoesNotExist`, `is_active=False`, or `is_published=False` |
| `PAYMENT_FAILED` | 402 | Gateway declined the transaction |
| `SEATS_UNAVAILABLE` | 409 | Concurrent booking exhausted available seats |
| `IDEMPOTENCY_CONFLICT` | 409 | Duplicate `webhook_event_id` received from gateway |
| `TOKEN_EXPIRED` | 410 | `PaymentActionToken.used_at` is set or `expires_at` is past |
| `PARTNER_UNAPPROVED` | 403 | `B2BPartner.approved = False` on portal access |
| `TIER_INSUFFICIENT` | 403 | Asset's `minimum_tier` exceeds partner's `agency_tier` |
| `INTERNAL_ERROR` | 500 | Unhandled exception (auto-logged to Sentry) |

---

## 15. Rate Limiting & Throttling

Configure via `DEFAULT_THROTTLE_CLASSES` in `config/settings/base.py`.

| Scope | Rate | Applied To |
| :--- | :--- | :--- |
| Anonymous — global | `200/day` | All unauthenticated requests |
| Authenticated — global | `2000/day` | All authenticated requests |
| Registration | `5/hour` per IP | `POST /auth/register/` |
| Login | `10/hour` per IP | `POST /auth/login/` |
| Password Reset | `3/hour` per email | `POST /auth/password/reset/` |
| Inquiry Submit | `10/hour` per IP | `POST /inquiries/` |
| Payment Initiate | `10/minute` per user | `POST /payments/initiate/` |
| Search | `60/minute` per IP | `GET /search/` |
| Webhooks | Unlimited (IP-allowlisted) | `POST /payments/webhook/*` |

---

## 16. Celery Async Task Triggers

All slow external I/O (email, WhatsApp, PDF generation) is dispatched to Celery workers. No synchronous HTTP handler blocks on I/O.

| Trigger Event | Celery Task | Channel | Target Latency |
| :--- | :--- | :--- | :--- |
| `POST /inquiries/` submitted | `send_inquiry_acknowledgement_email` | Resend Email | < 5 sec |
| `POST /inquiries/` submitted | `send_agent_whatsapp_alert` | WhatsApp Business API | < 5 sec |
| `POST /bookings/` created | `send_booking_confirmation_email` | Resend Email | < 30 sec |
| Payment webhook success | `send_payment_receipt_email` | Resend Email | Immediate |
| Payment webhook success | `send_payment_whatsapp_alert` | WhatsApp Business API | Immediate |
| `POST /b2b/register/` submitted | `send_b2b_registration_confirmation_email` | Resend Email | < 30 sec |
| `POST /b2b/partners/{id}/approve/` | `send_b2b_approval_notification_email` | Resend Email | Immediate |
| **Celery Beat — daily cron** | `send_balance_due_reminders` | Resend Email | Runs daily 08:00 UTC |

### Balance Due Reminder Cron Logic

```python
# Celery Beat task: runs every day at 08:00 UTC
# Target: all DEPOSIT_PAID bookings with balance_due_date within the next 48 hours

bookings = Booking.objects.filter(
    status=BookingStatus.DEPOSIT_PAID,
    balance_due_date__lte=now() + timedelta(hours=48),
    balance_due_date__gt=now()
).select_related('departure__trip')

for booking in bookings:
    # 1. Create or reuse a valid PaymentActionToken
    token = PaymentActionToken.objects.create(
        booking=booking,
        purpose='BALANCE_PAYMENT_80',
        expires_at=now() + timedelta(hours=72)
    )
    # 2. Hash the token and dispatch via Resend
    send_balance_reminder_email.delay(
        booking_reference=booking.booking_reference,
        token_hash=token.token_hash,
        balance_due_date=booking.balance_due_date,
        balance_amount_usd=str(booking.balance_amount_usd)
    )
```

---

*End of API Design Specification — Dreamscape Treks™ v1.0*
