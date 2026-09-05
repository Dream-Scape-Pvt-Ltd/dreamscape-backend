# Product Requirements Document (PRD): Backend Services
## Dreamscape Treks™ — Himalaya & Beyond (Nepal, Tibet, Bhutan, India)
**Version:** 1.0  
**Stack:** Django 5.x + Django REST Framework (DRF) | PostgreSQL 16+ | Celery + Redis  

---

## 1. Executive Summary & Objectives
Dreamscape Treks™ is an international adventure travel and expedition booking platform specializing in high-altitude Himalayan trekking, mountaineering expeditions, cultural tours, and cross-border circuits across Nepal, Tibet, Bhutan, and India.

The backend service is responsible for:
1. **Catalog & Itinerary CMS**: Serving complex multi-day trekking itineraries, peak climbing technical details, basecamp logistics, and Google Maps trail waypoints.
2. **Dynamic Split-Payment Booking Engine**: Facilitating 100% full payments or 20% advance reservations with automated 80% balance due triggers (scheduled 7 days prior to departure) and international gateway processing (Khalti / Bank API).
3. **Inquiry & CRM Pipeline**: Managing incoming leads, custom "Plan My Journey" / Tailor-Made trip requests, agent assignment, and queue workflows.
4. **B2B Agency Portal**: Onboarding international travel partners and DMCs with tiered commission pricing and white-label asset access.
5. **SEO & Search Services**: Dynamic Schema.org structured data feeds (`TouristTrip`, `Product`, `FAQPage`) and PostgreSQL-powered full-text search.

---

## 2. Core Architecture & System Components

### 2.1 Component Architecture
```
+-------------------------------------------------------------+
|               Next.js 14+ Frontend (SSR/ISR)                |
+-------------------------------------------------------------+
                              |
                     HTTPS / JSON REST API
                              |
+-------------------------------------------------------------+
|           Django 5.x REST Framework (API Gateway)           |
|  - Custom JWT Auth     - Role-Based Permissions (RBAC)      |
|  - Request Validation  - drf-spectacular OpenAPI Docs       |
+-------------------------------------------------------------+
        |                     |                     |
+---------------+     +---------------+     +-----------------+
|  PostgreSQL   |     |     Redis     |     |  Celery Workers |
|  - ACID DB    |     |  - Cache      |     |  - Split Alerts |
|  - JSONB Geo  |     |  - Broker     |     |  - Resend Email |
|  - Full-Text  |     |  - Rate Limits|     |  - WhatsApp API |
+---------------+     +---------------+     +-----------------+
```

---

## 3. Data Schema & Models (Entity Relationships)

### 3.1 `destinations` & `trips`
- **`Destination`**: `id`, `slug`, `name`, `country` (`NEPAL`, `TIBET`, `BHUTAN`, `INDIA`, `MULTI_COUNTRY`), `visa_guidelines`, `permit_details`, `hero_image_url`.
- **`Trip`**: `id`, `slug`, `title`, `destination_id` (FK), `trip_type` (`TREK`, `TOUR`, `EXPEDITION`, `ADVENTURE`), `duration_days`, `max_altitude_meters`, `difficulty_grade` (`GRADE_1` to `GRADE_5`, `ALPINE`), `starting_price_usd`, `overview`, `inclusions`, `exclusions`, `packing_list`, `is_featured`, `is_active`.
- **`PeakExpeditionDetail`** (OneToOne with `Trip`): `summit_window`, `climbing_grade`, `technical_gear`, `permit_type`, `mandatory_certifications`.
- **`ItineraryDay`**: `id`, `trip_id` (FK), `day_number`, `title`, `description`, `overnight_stay`, `elevation_meters`, `latitude`, `longitude`.
- **`TripDeparture`**: `id`, `trip_id` (FK), `start_date`, `end_date`, `price_usd`, `max_seats`, `available_seats`, `status` (`GUARANTEED`, `LIMITED`, `SOLD_OUT`).

### 3.2 `bookings` & `payments`
- **`Booking`**: `id`, `booking_reference` (e.g., `DS-2026-XXXX`, unique, indexed), `user_id` (FK, nullable for guest checkout), `departure_id` (FK), `payment_type` (`FULL_100`, `DEPOSIT_20`), `total_amount_usd`, `deposit_amount_usd`, `balance_amount_usd`, `trip_start_date`, `balance_due_date` (computed: `trip_start_date - 7 days`), `status` (`PENDING`, `DEPOSIT_PAID`, `FULLY_PAID`, `CANCELLED`, `REFUNDED`).
- **`Passenger`**: `id`, `booking_id` (FK), `full_name`, `passport_number`, `nationality`, `emergency_contact`, `medical_notes`.
- **`PaymentTransaction`**: `id`, `booking_id` (FK), `transaction_id` (unique), `gateway` (`KHALTI`, `BANK_TRANSFER`), `amount`, `currency`, `status` (`INITIATED`, `SUCCESS`, `FAILED`), `raw_webhook_payload` (JSONB), `created_at`.

### 3.3 `inquiries` & `crm`
- **`Inquiry`**: `id`, `inquiry_number`, `inquiry_type` (`GENERAL`, `JOURNEY`, `TAILOR_MADE`, `PARTNER_DMC`, `EXISTING_TRAVELLER`), `full_name`, `email`, `phone`, `whatsapp`, `message`, `status` (`NEW`, `ASSIGNED`, `IN_CONTACT`, `TRAVELLING`, `COMPLETED`, `CLOSED`), `assigned_to` (FK User, nullable).
- **`TailorMadePlan`** (OneToOne with `Inquiry`): `destinations_json` (JSONB), `duration_days`, `fitness_level`, `accommodation_level`, `custom_route_waypoints` (JSONB).

### 3.4 `b2b` (Partner Portal)
- **`B2BPartner`**: `id`, `user_id` (OneToOne), `company_name`, `country`, `registration_number`, `tier` (`BRONZE`, `SILVER`, `GOLD`, `PLATINUM`), `commission_rate`, `is_approved`.
- **`B2BAsset`**: `id`, `title`, `asset_type` (`WHITE_LABEL_ITINERARY`, `ROUTE_MAP`, `MEDIA_KIT`), `file_url`, `minimum_tier`.

---

## 4. Business Logic, Concurrency & Automation

1. **Split-Payment Workflow**:
   - Customer selects `DEPOSIT_20` at checkout.
   - Backend creates `Booking` with `status = PENDING`.
   - On successful 20% payment via Khalti webhook, status updates to `DEPOSIT_PAID`.
   - Celery Beat scheduled job runs daily at 00:00 UTC:
     - Queries `Booking.objects.filter(status='DEPOSIT_PAID', balance_due_date__lte=today + 2 days)`.
     - Generates a cryptographically signed one-click payment token.
     - Triggers transactional balance-due email via Resend and WhatsApp alert.
2. **Seat Allocation & Atomic Transactions**:
   - Booking creation and departure seat decrement MUST run in a `select_for_update()` block inside `@transaction.atomic` to prevent race conditions and overbooking.
3. **Webhook Idempotency**:
   - Webhook processing checks `PaymentTransaction.objects.filter(transaction_id=payload.id).exists()` before updating booking balances.
4. **Lead Routing & Instant SLA**:
   - Every inquiry triggers a Celery task that sends an automated customer acknowledgement email within 5 seconds and notifies internal duty officers.

---

## 5. Security, NFRs & API Contracts

- **Security**: CORS restricted to approved Next.js domains, CSRF protection, rate limiting (`django-ratelimit`) on `/api/v1/inquiries/` and `/api/v1/bookings/`.
- **API Formats**: Standardized JSON envelopes with `success`, `data`, and `error`.
- **Full Documentation**: Endpoints documented with OpenAPI 3.0 via `drf-spectacular` at `/api/v1/schema/swagger-ui/`.
