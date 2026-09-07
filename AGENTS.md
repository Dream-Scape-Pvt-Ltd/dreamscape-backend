# AGENTS.md — Dreamscape Treks™ Backend Architecture & Engineering Guidelines

This document serves as the single source of truth for all AI agents and engineers working within the `backend/` directory of **Dreamscape Treks™** (Nepal & Beyond: Nepal, Tibet, Bhutan, India). It codifies the project requirements, architecture, data schemas, API contracts, and non-negotiable coding standards synthesized from the project agreements and Product Requirements Documents.

---

## 1. Project Identity & Architecture Overview

- **Product**: Dreamscape Treks™ Multi-Destination Travel, Trekking & Mountaineering Expedition Platform.
- **Regions Served**: Nepal (Everest, Annapurna, Langtang, Manaslu, Mustang, Dolpo, Kanchenjunga, Makalu, Rolwaling), Tibet, Bhutan, India, and Cross-Border Combined Circuits.
- **Frontend**: Next.js 14+ (App Router, SSR/ISR, React, Tailwind CSS)
- **Backend Stack**: Python 3.12+ / Django 5.x + Django REST Framework (DRF)
- **Database**: PostgreSQL 16+ (ACID transactions, JSONB for dynamic metadata & waypoints, PostGIS-compatible coordinates)
- **Cache & Message Broker**: Redis
- **Task Queue & Scheduler**: Celery + Celery Beat (balance due scheduling, automated transactional emails)
- **Authentication**: JWT (`djangorestframework-simplejwt`) + role-based permissions (Anonymous, Customer, B2B Agency Partner, Sales Agent, Superadmin)
- **API Documentation**: OpenAPI 3.0 / Swagger via `drf-spectacular`
- **Integrations**:
  - Payment Gateways: Khalti (Stripe International Bridge) & International Commercial Bank API
  - Email: Resend API (transactional booking receipts, 80% balance due reminders, inquiry confirmations)
  - Messaging: WhatsApp Business Cloud API (lead alerts & customer inquiries)
  - Maps: Google Maps integration with GeoJSON route point coordinates and elevation profiles

---

## 2. Directory & Application Layout

The Django backend MUST be structured into focused domain apps under `backend/`:

```text
backend/
├── manage.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── config/                  # Django project root
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   ├── celery.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── development.py
│       └── production.py
└── apps/
    ├── accounts/           # Custom User, JWT auth, Role permissions, Profile management
    ├── destinations/        # Countries, Regions, Activities & Multi-Country circuits
    ├── trips/               # Treks, Expeditions, Itineraries, Departures & Elevation maps
    ├── bookings/            # Split payment engine (20% deposit / 80% balance), travelers
    ├── payments/            # Khalti / Bank Gateways, Webhook handlers, Idempotent ledger
    ├── inquiries/           # Leads, Tailor-Made trip builder, CRM & agent queues
    ├── b2b/                 # Partner portal, B2B tiers, net rates, asset downloads
    ├── content_cms/         # Travel Guides, FAQs, Responsible Travel, SEO Schema.org
    └── search/              # PostgreSQL Full-Text Search (vector/rank across content)
```

### 2.1. App Structure & Modular Layout
Each domain app under `apps/` uses a modular package structure for `models/` and `views/` (instead of monolithic `models.py` and `views.py` files):

```text
apps/<app_name>/
├── __init__.py
├── admin.py
├── apps.py
├── migrations/
│   └── __init__.py
├── models/
│   └── __init__.py      # Re-exports all sub-models for Django ORM & migrations
├── views/
│   └── __init__.py      # Re-exports viewsets / API views
├── serializers/         # DRF serializers (as needed)
├── urls.py              # App-level routing
└── tests.py
```

### 2.2. Creating New Apps in the `apps/` Folder
When creating a new domain app within `apps/`, follow this exact sequence:
1. **Create target directory**: `mkdir apps/<app_name>` (Django requires the target folder to exist when providing a custom path).
2. **Generate app template**: `python manage.py startapp <app_name> apps/<app_name>`
3. **Configure AppConfig name**: In `apps/<app_name>/apps.py`, update `name` to include the namespace:
   ```python
   class <AppName>Config(AppConfig):
       default_auto_field = 'django.db.models.BigAutoField'
       name = 'apps.<app_name>'
   ```
4. **Register in settings**: In `config/settings.py`, register `'apps.<app_name>'` in `INSTALLED_APPS`.
5. **Modularize models & views**:
   - Replace `models.py` with `models/` folder containing `__init__.py`. Re-export any model defined in submodules in `__init__.py` so Django automatically detects it for migrations.
   - Replace `views.py` with `views/` folder containing `__init__.py`.

---

## 3. Core Domain Specifications & Business Rules

### 3.1. Trips & Expeditions (`apps.trips` & `apps.destinations`)
- **Trip Types**: Classic Treks, Remote Treks, High Pass Treks, Cultural Tours, Day Hikes, Adventure Activities, and Technical Mountain Expeditions.
- **Peak & Expedition Details**: Technical grades, summit windows, base camp logistics, gear requirements, and mandatory certifications.
- **Day-by-Day Itineraries**: Each day must capture day number, title, description, overnight stay, altitude (m), meals, and optional geo-coordinates (latitude/longitude) for Google Maps trail plotting.
- **Departures**: Fixed departure dates with `max_seats`, `available_seats`, status (`guaranteed`, `limited`, `sold_out`), and seasonal pricing.

### 3.2. Split-Payment Booking Engine (`apps.bookings` & `apps.payments`)
- **Two Payment Modalities**:
  1. `FULL_100`: 100% upfront payment upon booking.
  2. `DEPOSIT_20`: 20% advance reservation deposit due immediately.
- **Automated 80% Balance Due Calculation**:
  - `balance_due_date = trip_start_date - 7 days`
  - A Celery Beat worker runs daily to find all bookings with status `DEPOSIT_PAID` where `balance_due_date` is 48 hours away.
  - Automatically dispatches an email via Resend with a secure, signed one-click payment URL for the remaining 80% balance.
- **Concurrency & Idempotency**:
  - All payment webhook callbacks from Khalti / Banking APIs must be validated with HMAC signature checking.
  - Webhooks MUST be idempotent; store `transaction_id` in a unique constraint and wrap status transitions in `select_for_update()` and `transaction.atomic()`.
  - Seats on departures must be deducted atomically to prevent overbooking.

### 3.3. Inquiries & CRM Pipeline (`apps.inquiries`)
- **Inquiry Categories**:
  - `GENERAL`: General info
  - `JOURNEY`: Inquiries tied to a specific trek or expedition
  - `TAILOR_MADE`: Custom itinerary requests with destination combos, dates, fitness, and custom coordinates
  - `PARTNER_DMC`: B2B partner inquiries
  - `EXISTING_TRAVELLER`: Assistance for travelers currently on the trail
- **Lead Lifecycle States**:
  `NEW` → `ASSIGNED` → `IN_CONTACT` → `TRAVELLING` → `COMPLETED` → `CLOSED`
- **Instant Response SLA**:
  - On submission, an asynchronous Celery task immediately sends an acknowledgement email to the client confirming receipt ("*We have received your journey inquiry; our team is reviewing your requirements...*").
  - An alert notification is dispatched to internal agents with lead details.

### 3.4. B2B Partner Portal (`apps.b2b`)
- Dedicated registration and validation for international tour agencies and DMCs.
- Tiered commission structures (`BRONZE`, `SILVER`, `GOLD`, `PLATINUM`).
- Authenticated endpoints to download white-label high-resolution itineraries, route maps, and marketing media.

### 3.5. SEO & Schema.org Structured Data (`apps.content_cms`)
- DRF endpoints must return rich Schema.org metadata for Next.js SSR consumption:
  - `TouristTrip` & `Product` schemas for treks and tours (name, description, itinerary, offers, aggregateRating).
  - `FAQPage` schema for travel guides and destination advisories.
  - `BreadcrumbList` schema for deep hierarchical navigation.

---

## 4. API Standards & Error Envelope

All API endpoints must be prefixed with `/api/v1/` and adhere strictly to consistent JSON envelopes:

### Standard Success Response
```json
{
  "success": true,
  "data": { ... },
  "message": "Resource retrieved successfully"
}
```

### Standard Error Response
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR | SEATS_UNAVAILABLE | PAYMENT_FAILED | UNAUTHORIZED",
    "message": "Human-readable explanation of error.",
    "details": { ... }
  }
}
```

### Key Endpoint Contracts
- `GET /api/v1/trips/` — Filterable trip list (destination, activity, difficulty, max_altitude, duration, season, price).
- `GET /api/v1/trips/{slug}/` — Full trip details including day-by-day itineraries, coordinates, packing lists, departures, and SEO schema.
- `POST /api/v1/bookings/` — Initiate a booking (`FULL_100` or `DEPOSIT_20`).
- `POST /api/v1/payments/webhook/khalti/` — Secure, signature-verified webhook handler for Khalti/Stripe events.
- `POST /api/v1/inquiries/` — Submit general, trip-specific, or tailor-made journey inquiries.
- `GET /api/v1/search/?q={query}` — Full-text multi-entity search across trips, guides, and FAQs.
- `POST /api/v1/b2b/register/` — Agency registration and partner portal access.

---

## 5. Non-Negotiable Engineering Rules for Agents

1. **Always use atomic transactions** (`@transaction.atomic`) when modifying bookings, departures, payments, or inquiries.
2. **Never expose secrets or API keys** in source files. Always use `django-environ` reading from `.env`.
3. **Database Constraints**: Use explicit `db_index=True`, `unique=True`, foreign key `on_delete` behaviors (`PROTECT` for financial/booking references, `CASCADE` where ownership is strict).
4. **Performance**: Prevent N+1 queries by mandating `select_related()` on ForeignKeys/OneToOnes and `prefetch_related()` on ManyToMany/reverse relationships in all DRF serializers and views.
5. **Asynchronous Dispatch**: Any slow external I/O (Resend email delivery, WhatsApp webhooks, PDF itinerary generation) MUST be offloaded to Celery tasks; NEVER block synchronous HTTP request-response cycles.
