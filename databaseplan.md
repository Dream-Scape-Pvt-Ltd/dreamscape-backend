# DREAMSCAPE TREKS™ — DATABASE & SERIALIZATION ARCHITECTURE PLAN
**File:** `databaseplan.md`  
**Engine:** PostgreSQL 16+ | Django 5.x | Django REST Framework (DRF)  
**Target Environment:** Python 3.12+, Celery, Redis  
**Reference Schema:** `dbdiagramcode.md`

---

## Table of Contents
1. [Architecture Foundations & Standards](#1-architecture-foundations--standards)
2. [Shared Base Models & Utilities (`apps.common`)](#2-shared-base-models--utilities-appscommon)
3. [App 1: `apps.accounts` (Auth & RBAC)](#3-app-1-appsaccounts-auth--rbac)
4. [App 2: `apps.destinations` (Destinations & Activities)](#4-app-2-appsdestinations-destinations--activities)
5. [App 3: `apps.trips` (Trips, Itineraries, Departures & Reviews)](#5-app-3-appstrips-trips-itineraries-departures--reviews)
6. [App 4: `apps.bookings` (Split Bookings & Passengers)](#6-app-4-appsbookings-split-bookings--passengers)
7. [App 5: `apps.payments` (Transactions, Tokens & Gateways)](#7-app-5-appspayments-transactions-tokens--gateways)
8. [App 6: `apps.inquiries` (CRM, Leads & Tailor-Made Requests)](#8-app-6-appsinquiries-crm-leads--tailor-made-requests)
9. [App 7: `apps.b2b` (Partner Portal & Asset Access)](#9-app-7-appsb2b-partner-portal--asset-access)
10. [App 8: `apps.content_cms` (Guides & Responsible Travel)](#10-app-8-appscontent_cms-guides--responsible-travel)
11. [App 9: `apps.faq` (Contextual FAQs)](#11-app-9-appsfaq-contextual-faqs)
12. [Cross-App Query Optimization & N+1 Prevention Matrix](#12-cross-app-query-optimization--n1-prevention-matrix)

---

## 1. Architecture Foundations & Standards

### 1.1 Model Design Standards
- **Primary Keys**: UUIDv4 (`models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`).
- **JSON Fields**: Always use `models.JSONField(default=dict/list, blank=True)` which PostgreSQL 16 stores natively as binary `JSONB`.
- **Foreign Key Integrity**:
  - `on_delete=models.PROTECT`: Used on all financial, booking, and departure associations to prevent accidental cascading deletion.
  - `on_delete=models.CASCADE`: Used only where children have strict lifecycle dependency on parents (e.g. `ItineraryDay` $\rightarrow$ `Trip`, `PassengerDetail` $\rightarrow$ `Booking`).
  - `on_delete=models.SET_NULL`: Used on optional audit references (e.g. `customer_user_id` on guest bookings, `assigned_agent_id` on inquiries).
- **Audit Timestamps**: All models inherit `created_at` and `updated_at`.
- **Database Constraints**: Explicit `CheckConstraint` and `UniqueConstraint` on the model `Meta`.

### 1.2 Serialization Standards
- **Separation of Read & Write**: High-traffic entities implement dedicated `ReadSerializer` (rich nested objects, computed badges) and `WriteSerializer` (strict input validation, atomic transactions).
- **Envelope Compliance**: Serializer outputs plug into standard API envelopes (`success`, `data`, `message`, `error`).
- **N+1 Prevention**: Every serializer defines its required ORM `select_related` and `prefetch_related` dependencies in docstrings.

---

## 2. Shared Base Models & Utilities (`apps.common`)

To maintain DRY principles, create `apps/common/` to provide common abstract base classes and logging models:

```text
apps/common/
├── models/
│   ├── base.py             # TimeStampedModel, UUIDModel
│   ├── media.py            # MediaAsset
│   ├── notification.py     # NotificationLog
│   ├── audit.py            # AuditLog
│   └── __init__.py
└── serializers/
    ├── media_serializers.py
    └── __init__.py
```

### 2.1 Abstract Models
- **`UUIDModel`**: `id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`
- **`TimeStampedModel(UUIDModel)`**: `created_at` (auto_now_add), `updated_at` (auto_now).

### 2.2 System Utility Models
- **`MediaAsset`**: `file`, `original_name`, `mime_type`, `file_size_bytes`, `alt_text`, `uploaded_by` (FK User).
- **`NotificationLog`**: `user` (FK User, null), `booking` (FK Booking, null), `inquiry` (FK Inquiry, null), `channel` (EMAIL/WHATSAPP), `event_type`, `recipient`, `subject`, `status` (SENT/FAILED), `provider_message_id`, `response_payload` (JSONB).
- **`AuditLog`**: `actor` (FK User, null), `action`, `entity_type`, `entity_id`, `old_values` (JSONB), `new_values` (JSONB), `ip_address`, `user_agent`.

> [!IMPORTANT]
> **Circular Import Prevention**: `NotificationLog` and `AuditLog` reference models across `apps.bookings` and `apps.inquiries`. Always use **lazy string FK references** (e.g. `ForeignKey('bookings.Booking', ...)` and `ForeignKey('inquiries.Inquiry', ...)`) — never direct class imports — to prevent circular import chains at Django startup.

---

## 3. App 1: `apps.accounts` (Auth & RBAC)

### 3.1 Directory Structure
```text
apps/accounts/
├── models/
│   ├── user.py
│   └── __init__.py
├── serializers/
│   ├── user_serializers.py
│   ├── auth_serializers.py
│   └── __init__.py
```

### 3.2 Models

#### `User(AbstractUser, UUIDModel)`
- **Table**: `users`
- **Required class-level Auth Config**:
  ```python
  USERNAME_FIELD = 'email'
  REQUIRED_FIELDS = []         # Removes 'username' from createsuperuser prompt
  username = None              # Removes AbstractUser.username field entirely
  ```
- **Fields**:
  - `email`: `EmailField(unique=True, db_index=True)`
  - `username`: `None` — removed; authentication is email-based
  - `first_name`: `CharField(max_length=100)`
  - `last_name`: `CharField(max_length=100)`
  - `phone`: `CharField(max_length=50, blank=True)`
  - `whatsapp_number`: `CharField(max_length=50, blank=True)`
  - `role`: `CharField(max_length=20, choices=UserRole.choices, default=UserRole.CUSTOMER, db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `is_staff`: `BooleanField(default=False)`
  - `is_superuser`: `BooleanField(default=False)`
- **Required `settings.py` Declaration**:
  ```python
  AUTH_USER_MODEL = 'accounts.User'  # Must be set BEFORE first migration
  ```
- **Enums**:
  - `UserRole`: `ADMIN`, `SALES_AGENT`, `B2B_PARTNER`, `CUSTOMER`
- **Indexes**: `[email]`, `[role, is_active]`

### 3.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `UserRegistrationSerializer` | Write | Customer account creation | `email`, `password`, `first_name`, `last_name`, `phone`, `whatsapp_number`. Enforces password strength. |
| `UserProfileSerializer` | Read/Write | Authenticated user profile | `id`, `email`, `first_name`, `last_name`, `phone`, `whatsapp_number`, `role`, `created_at`. `role` is read-only. |
| `UserMinimalSerializer` | Read | Embedded author/agent reps | `id`, `full_name`, `email`, `role`. |

---

## 4. App 2: `apps.destinations` (Destinations & Activities)

### 4.1 Directory Structure
```text
apps/destinations/
├── models/
│   ├── destination.py
│   ├── category.py
│   └── __init__.py
├── serializers/
│   ├── destination_serializers.py
│   ├── category_serializers.py
│   └── __init__.py
```

### 4.2 Models

#### `Destination(TimeStampedModel)`
- **Table**: `destinations`
- **Fields**:
  - `name`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255, unique=True, db_index=True)`
  - `country`: `CharField(max_length=30, choices=DestinationCountry.choices, db_index=True)`
  - `region_name`: `CharField(max_length=150, blank=True)` (e.g. "Khumbu / Everest")
  - `visa_guidelines`: `TextField(blank=True)`
  - `permit_details`: `TextField(blank=True)`
  - `hero_media`: `URLField(max_length=500, blank=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
- **Enums**:
  - `DestinationCountry`: `NEPAL`, `TIBET`, `BHUTAN`, `INDIA`, `MULTI_COUNTRY`

#### `ActivityCategory(TimeStampedModel)`
- **Table**: `activity_categories`
- **Fields**:
  - `name`: `CharField(max_length=150, unique=True)`
  - `slug`: `SlugField(max_length=150, unique=True)`
  - `description`: `TextField(blank=True)`
  - `is_active`: `BooleanField(default=True)`

### 4.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `DestinationListSerializer` | Read | Catalog cards & filters | `id`, `name`, `slug`, `country`, `region_name`, `hero_media`. |
| `DestinationDetailSerializer` | Read | Full destination landing | Includes `visa_guidelines`, `permit_details`, `trips_count`, plus SEO metadata. |
| `ActivityCategorySerializer` | Read/Write | Activity filter chips | `id`, `name`, `slug`, `description`. |

---

## 5. App 3: `apps.trips` (Trips, Itineraries, Departures & Reviews)

### 5.1 Directory Structure
```text
apps/trips/
├── models/
│   ├── trip.py
│   ├── expedition.py
│   ├── itinerary.py
│   ├── departure.py
│   ├── review.py
│   └── __init__.py
├── serializers/
│   ├── trip_serializers.py
│   ├── itinerary_serializers.py
│   ├── departure_serializers.py
│   ├── review_serializers.py
│   └── __init__.py
```

### 5.2 Models

#### `Trip(TimeStampedModel)`
- **Table**: `trips`
- **Fields**:
  - `destination`: `ForeignKey('destinations.Destination', on_delete=models.PROTECT, related_name='trips')`
  - `category`: `ForeignKey('destinations.ActivityCategory', on_delete=models.PROTECT, related_name='trips')`
  - `title`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255, unique=True, db_index=True)`
  - `duration_days`: `PositiveIntegerField(db_index=True)`
  - `altitude_max_meters`: `PositiveIntegerField(null=True, blank=True, db_index=True)`
  - `difficulty_grade`: `CharField(max_length=20, choices=DifficultyGrade.choices, db_index=True)`
  - `min_group_size`: `PositiveIntegerField(default=1)`
  - `max_group_size`: `PositiveIntegerField(default=14)`
  - `best_seasons`: `JSONField(default=list)` (e.g. `["SPRING", "AUTUMN"]`)
  - `inclusions`: `JSONField(default=list)`
  - `exclusions`: `JSONField(default=list)`
  - `packing_list`: `JSONField(default=list)`
  - `starting_price_usd`: `DecimalField(max_digits=12, decimal_places=2, db_index=True)`
  - `single_supplement_usd`: `DecimalField(max_digits=12, decimal_places=2, default=0)`
  - `overview`: `TextField()`
  - `is_featured`: `BooleanField(default=False, db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
- **Enums**:
  - `DifficultyGrade`: `GRADE_1`, `GRADE_2`, `GRADE_3`, `GRADE_4`, `GRADE_5`, `ALPINE`

#### `PeakExpeditionDetail(TimeStampedModel)`
- **Table**: `peak_expedition_details`
- **Fields**:
  - `trip`: `OneToOneField(Trip, on_delete=models.CASCADE, related_name='expedition_detail')`
  - `summit_window`: `CharField(max_length=255, blank=True)`
  - `technical_rating`: `CharField(max_length=100, blank=True)`
  - `gear_requirements`: `JSONField(default=list)`
  - `permit_fee_type`: `CharField(max_length=100, blank=True)`
  - `mandatory_certifications`: `JSONField(default=list)`

#### `ItineraryDay(TimeStampedModel)`
- **Table**: `itinerary_days`
- **Fields**:
  - `trip`: `ForeignKey(Trip, on_delete=models.CASCADE, related_name='itinerary_days')`
  - `day_number`: `PositiveIntegerField()`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField()`
  - `overnight_stay`: `CharField(max_length=255, blank=True)`
  - `elevation_meters`: `IntegerField(null=True, blank=True)`
  - `accommodation_type`: `CharField(max_length=30, choices=AccommodationType.choices, default='TEAHOUSE')`
  - `is_acclimatization_day`: `BooleanField(default=False)`
  - `meals_included`: `JSONField(default=list)` (e.g. `["B", "L", "D"]`)
  - `latitude`: `DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)`
  - `longitude`: `DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)`
- **Constraints**: `UniqueConstraint(fields=['trip', 'day_number'], name='unique_trip_day_number')`

#### `TripDeparture(TimeStampedModel)`
- **Table**: `trip_departures`
- **Fields**:
  - `trip`: `ForeignKey(Trip, on_delete=models.PROTECT, related_name='departures')`
  - `start_date`: `DateField(db_index=True)`
  - `end_date`: `DateField(db_index=True)`
  - `price_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `max_seats`: `PositiveIntegerField()`
  - `available_seats`: `PositiveIntegerField()`
  - `status`: `CharField(max_length=20, choices=DepartureStatus.choices, default='LIMITED', db_index=True)`
  - `is_guaranteed`: `BooleanField(default=False)`
- **Constraints**:
  - `CheckConstraint(check=Q(available_seats__gte=0) & Q(available_seats__lte=F('max_seats')), name='valid_departure_seats')`
  - `CheckConstraint(check=Q(end_date__gte=F('start_date')), name='valid_departure_dates')`

#### `TripReview(TimeStampedModel)`
- **Table**: `trip_reviews`
- **Fields**:
  - `trip`: `ForeignKey(Trip, on_delete=models.CASCADE, related_name='reviews')`
  - `user`: `ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')`
  - `booking`: `OneToOneField('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True, related_name='review')`
  - `reviewer_name`: `CharField(max_length=255)`
  - `reviewer_country`: `CharField(max_length=100, blank=True)`
  - `rating_overall`: `PositiveSmallIntegerField()` (1 to 5)
  - `rating_guide`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `rating_itinerary`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `rating_safety`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `title`: `CharField(max_length=255, blank=True)`
  - `content`: `TextField()`
  - `travel_date`: `DateField(null=True, blank=True)`
  - `is_verified`: `BooleanField(default=False)`
  - `is_published`: `BooleanField(default=False, db_index=True)`
- **Constraints**:
  - `CheckConstraint(check=Q(rating_overall__range=(1, 5)), name='valid_review_overall_rating')`
- **Verified Badge Integrity Signal**:
  When `booking` is set to `NULL` (e.g. on booking cancellation/refund), `is_verified` must be reset to `False` atomically. Implement via a `post_save` signal or override `save()`:
  ```python
  # In review.py
  @receiver(pre_save, sender=TripReview)
  def revoke_verified_badge_on_booking_loss(sender, instance, **kwargs):
      if instance.pk:
          original = TripReview.objects.filter(pk=instance.pk).first()
          if original and original.booking_id and not instance.booking_id:
              instance.is_verified = False
  ```

### 5.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `TripListSerializer` | Read | Search catalog & filter cards | Minimal fields: `id`, `title`, `slug`, `destination_name`, `duration_days`, `starting_price_usd`, `altitude_max_meters`, `difficulty_grade`, `is_featured`. |
| `TripDetailSerializer` | Read | Complete trip detail view | Nested: `destination`, `category`, `expedition_detail`, `itinerary_days` (ordered by day), upcoming `departures`, `rating_summary`, and Schema.org metadata. |
| `ItineraryDaySerializer` | Read/Write | Day-by-day trail data | Includes altitude graph coords (`elevation_meters`, `latitude`, `longitude`, `is_acclimatization_day`). |
| `TripDepartureSerializer` | Read | Calendar departure seats | `id`, `start_date`, `end_date`, `price_usd`, `available_seats`, `status`, `is_guaranteed`. |
| `TripReviewReadSerializer` | Read | Public customer reviews | `id`, `reviewer_name`, `reviewer_country`, `rating_overall`, `title`, `content`, `travel_date`, `is_verified`, `created_at`. |
| `TripReviewCreateSerializer` | Write | Customer review creation | Validates `rating_overall` (1-5), checks `booking_id` belongs to `request.user` to auto-set `is_verified=True`. |

---

## 6. App 4: `apps.bookings` (Split Bookings & Passengers)

### 6.1 Directory Structure
```text
apps/bookings/
├── models/
│   ├── booking.py
│   ├── passenger.py
│   └── __init__.py
├── serializers/
│   ├── booking_serializers.py
│   ├── passenger_serializers.py
│   └── __init__.py
```

### 6.2 Models

#### `Booking(TimeStampedModel)`
- **Table**: `bookings`
- **Fields**:
  - `booking_reference`: `CharField(max_length=30, unique=True, db_index=True)` (e.g. `DS-2026-X8B9Q`)
  - `customer_user`: `ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')`
  - `departure`: `ForeignKey('trips.TripDeparture', on_delete=models.PROTECT, null=True, blank=True, related_name='bookings')`
  - `custom_trip`: `ForeignKey('trips.Trip', on_delete=models.PROTECT, null=True, blank=True, related_name='custom_bookings')`
  - `customer_name`: `CharField(max_length=255)`
  - `customer_email`: `EmailField(db_index=True)`
  - `customer_phone`: `CharField(max_length=50, blank=True)`
  - `num_travelers`: `PositiveIntegerField(default=1)`
  - `total_amount_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `currency`: `CharField(max_length=10, default='USD')`
  - `payment_type`: `CharField(max_length=20, choices=PaymentType.choices, default='DEPOSIT_20')`
  - `deposit_amount_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `balance_amount_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `amount_paid_usd`: `DecimalField(max_digits=12, decimal_places=2, default=0)`
  - `status`: `CharField(max_length=20, choices=BookingStatus.choices, default='PENDING', db_index=True)`
  - `trip_start_date`: `DateField(db_index=True)`
  - `balance_due_date`: `DateField(null=True, blank=True, db_index=True)`
- **Enums**:
  - `PaymentType`: `FULL_100`, `DEPOSIT_20`
  - `BookingStatus`: `PENDING`, `DEPOSIT_PAID`, `FULLY_PAID`, `CANCELLED`, `REFUNDED`
- **Constraints** (Database-Level Financial Guards):
  - `CheckConstraint(check=Q(total_amount_usd__gt=0), name='positive_total_amount')`
  - `CheckConstraint(check=Q(amount_paid_usd__gte=0), name='non_negative_amount_paid')`
  - `CheckConstraint(check=Q(deposit_amount_usd__gte=0), name='non_negative_deposit')`
  - `CheckConstraint(check=Q(balance_amount_usd__gte=0), name='non_negative_balance')`
  - `CheckConstraint(check=Q(num_travelers__gte=1), name='minimum_one_traveler')`

#### `PassengerDetail(TimeStampedModel)`
- **Table**: `passenger_details`
- **Fields**:
  - `booking`: `ForeignKey(Booking, on_delete=models.CASCADE, related_name='passengers')`
  - `full_name`: `CharField(max_length=255)`
  - `gender`: `CharField(max_length=20, blank=True)`
  - `date_of_birth`: `DateField()`
  - `passport_number`: `CharField(max_length=100, db_index=True)`
  - `passport_expiry_date`: `DateField()`
  - `nationality`: `CharField(max_length=100)`
  - `insurance_provider`: `CharField(max_length=150)`
  - `insurance_policy_number`: `CharField(max_length=100)`
  - `insurance_emergency_phone`: `CharField(max_length=50)`
  - `emergency_contact_name`: `CharField(max_length=255, blank=True)`
  - `emergency_contact_phone`: `CharField(max_length=50, blank=True)`
  - `dietary_requirements`: `TextField(blank=True)`
  - `medical_conditions`: `TextField(blank=True)`

### 6.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `BookingCreateSerializer` | Write | Checkout & seat lock | Validates departure availability with `select_for_update()`, generates `booking_reference`, computes `deposit_amount_usd` (20%) and `balance_due_date` (`start_date - 7 days`), creates passenger records atomically. |
| `BookingDetailSerializer` | Read | Traveler booking confirmation | `booking_reference`, `status`, `payment_type`, breakdown of `total_amount_usd`, `amount_paid_usd`, `balance_amount_usd`, `balance_due_date`, nested `passengers`, departure info. |
| `PassengerDetailSerializer` | Read/Write | Passenger permit & rescue manifest | Enforces passport expiry $\ge$ 6 months from `trip_start_date`. |

---

## 7. App 5: `apps.payments` (Transactions, Tokens & Gateways)

### 7.1 Directory Structure
```text
apps/payments/
├── models/
│   ├── transaction.py
│   ├── action_token.py
│   └── __init__.py
├── serializers/
│   ├── payment_serializers.py
│   └── __init__.py
```

### 7.2 Models

#### `PaymentTransaction(TimeStampedModel)`
- **Table**: `payment_transactions`
- **Fields**:
  - `booking`: `ForeignKey('bookings.Booking', on_delete=models.PROTECT, related_name='payments')`
  - `transaction_id`: `CharField(max_length=255, unique=True, db_index=True)`
  - `idempotency_key`: `CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)`
  - `gateway`: `CharField(max_length=20, choices=PaymentGateway.choices, db_index=True)`
  - `payment_stage`: `CharField(max_length=20, choices=PaymentStage.choices, db_index=True)`
  - `amount`: `DecimalField(max_digits=12, decimal_places=2)`
  - `currency`: `CharField(max_length=10, default='USD')`
  - `exchange_rate`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)`
  - `charged_amount`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `charged_currency`: `CharField(max_length=10, default='NPR')`
  - `gateway_fee`: `DecimalField(max_digits=10, decimal_places=2, default=0)`
  - `status`: `CharField(max_length=20, choices=PaymentStatus.choices, default='INITIATED', db_index=True)`
  - `webhook_raw_payload`: `JSONField(default=dict, blank=True)`
  - `webhook_event_id`: `CharField(max_length=255, blank=True, db_index=True)`
  - `processed_at`: `DateTimeField(null=True, blank=True)`
- **Enums**:
  - `PaymentGateway`: `KHALTI`, `STRIPE`, `BANK`
  - `PaymentStage`: `DEPOSIT_20`, `BALANCE_80`, `FULL_100`, `CUSTOM_ADJUSTMENT`, `REFUND`
  - `PaymentStatus`: `INITIATED`, `SUCCESS`, `FAILED`, `REFUNDED`

#### `PaymentActionToken(TimeStampedModel)`
- **Table**: `payment_action_tokens`
- **Fields**:
  - `booking`: `ForeignKey('bookings.Booking', on_delete=models.CASCADE, related_name='action_tokens')`
  - `token_hash`: `CharField(max_length=255, unique=True, db_index=True)`
  - `purpose`: `CharField(max_length=50)` (e.g. `BALANCE_PAYMENT_80`)
  - `expires_at`: `DateTimeField(db_index=True)`
  - `used_at`: `DateTimeField(null=True, blank=True)`

### 7.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `PaymentInitiateSerializer` | Write | Initiates Khalti/Stripe session | Validates booking balance, locks `exchange_rate` (USD to NPR), returns checkout gateway URL and transaction reference. |
| `PaymentWebhookSerializer` | Write | Khalti HMAC callback | Validates digital signature, checks `idempotency_key`, marks transaction `SUCCESS`, updates `booking.amount_paid_usd` and transitions status to `DEPOSIT_PAID` or `FULLY_PAID`. |
| `PaymentTransactionReadSerializer`| Read | Receipt & transaction history | `transaction_id`, `gateway`, `payment_stage`, `amount`, `currency`, `status`, `created_at`. |

---

## 8. App 6: `apps.inquiries` (CRM, Leads & Tailor-Made Requests)

### 8.1 Directory Structure
```text
apps/inquiries/
├── models/
│   ├── inquiry.py
│   ├── tailor_made.py
│   ├── note.py
│   └── __init__.py
├── serializers/
│   ├── inquiry_serializers.py
│   ├── tailor_made_serializers.py
│   └── __init__.py
```

### 8.2 Models

#### `Inquiry(TimeStampedModel)`
- **Table**: `inquiries`
- **Fields**:
  - `inquiry_number`: `CharField(max_length=30, unique=True, db_index=True)` (e.g. `INQ-2026-9082`)
  - `inquiry_type`: `CharField(max_length=30, choices=InquiryType.choices, db_index=True)`
  - `trip`: `ForeignKey('trips.Trip', on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries')`
  - `departure`: `ForeignKey('trips.TripDeparture', on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries')`
  - `full_name`: `CharField(max_length=255)`
  - `email`: `EmailField(db_index=True)`
  - `phone`: `CharField(max_length=50, blank=True)`
  - `whatsapp_number`: `CharField(max_length=50, blank=True)`
  - `message`: `TextField(blank=True)`
  - `preferred_dates`: `CharField(max_length=255, blank=True)`
  - `estimated_budget`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `group_size`: `PositiveIntegerField(null=True, blank=True)`
  - `lead_source`: `CharField(max_length=50, default='WEBSITE')`
  - `status`: `CharField(max_length=20, choices=InquiryStatus.choices, default='NEW', db_index=True)`
  - `assigned_agent`: `ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_inquiries')`
- **Enums**:
  - `InquiryType`: `GENERAL`, `JOURNEY`, `TAILOR_MADE`, `PARTNER_DMC`, `EXISTING_TRAVELLER`
  - `InquiryStatus`: `NEW`, `ASSIGNED`, `IN_CONTACT`, `TRAVELING`, `COMPLETED`, `CLOSED`

#### `TailorMadeRequest(TimeStampedModel)`
- **Table**: `tailor_made_requests`
- **Fields**:
  - `inquiry`: `OneToOneField(Inquiry, on_delete=models.CASCADE, related_name='tailor_made_detail')`
  - `custom_destinations`: `JSONField(default=list)`
  - `desired_activities`: `JSONField(default=list)`
  - `fitness_level`: `CharField(max_length=100, blank=True)`
  - `accommodation_standard`: `CharField(max_length=100, blank=True)`
  - `guide_language_preference`: `CharField(max_length=50, blank=True)`
  - `custom_route_coordinates`: `JSONField(default=list)`
  - `waypoints`: `JSONField(default=list)`

#### `InquiryNote(TimeStampedModel)`
- **Table**: `inquiry_notes`
- **Fields**:
  - `inquiry`: `ForeignKey(Inquiry, on_delete=models.CASCADE, related_name='notes')`
  - `author`: `ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='inquiry_notes')`
  - `note_text`: `TextField()`

### 8.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `InquiryCreateSerializer` | Write | Public lead form | Auto-generates `inquiry_number`, triggers Celery 5-sec acknowledgement email task. |
| `TailorMadeRequestCreateSerializer` | Write | Custom trip planner | Captures interactive map GeoJSON waypoints, destination selections, and fitness ratings. |
| `InquiryDetailSerializer` | Read | Internal CRM lead dashboard | Full lead history, assigned agent, notes thread, and attached tailor-made plan. |

---

## 9. App 7: `apps.b2b` (Partner Portal & Asset Access)

### 9.1 Directory Structure
```text
apps/b2b/
├── models/
│   ├── partner.py
│   ├── asset.py
│   ├── booking.py
│   └── __init__.py
├── serializers/
│   ├── partner_serializers.py
│   ├── asset_serializers.py
│   └── __init__.py
```

### 9.2 Models

#### `B2BPartner(TimeStampedModel)`
- **Table**: `b2b_partners`
- **Fields**:
  - `user`: `OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='b2b_profile')`
  - `company_name`: `CharField(max_length=255, db_index=True)`
  - `country`: `CharField(max_length=100, db_index=True)`
  - `registration_number`: `CharField(max_length=150, blank=True)`
  - `website`: `URLField(max_length=255, blank=True)`
  - `agency_tier`: `CharField(max_length=20, choices=AgencyTier.choices, default='BRONZE', db_index=True)`
  - `commission_rate`: `DecimalField(max_digits=5, decimal_places=2, default=0)` (e.g. 15.00%)
  - `approved`: `BooleanField(default=False, db_index=True)`
- **Enums**:
  - `AgencyTier`: `BRONZE`, `SILVER`, `GOLD`, `PLATINUM`

#### `B2BAsset(TimeStampedModel)`
- **Table**: `b2b_assets`
- **Fields**:
  - `trip`: `ForeignKey('trips.Trip', on_delete=models.SET_NULL, null=True, blank=True, related_name='b2b_assets')`
  - `title`: `CharField(max_length=255)`
  - `asset_type`: `CharField(max_length=30, choices=AssetType.choices, db_index=True)`
  - `file`: `FileField(upload_to='b2b_assets/')`
  - `minimum_tier`: `CharField(max_length=20, choices=AgencyTier.choices, default='BRONZE', db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
- **Enums**:
  - `AssetType`: `WHITE_LABEL_ITINERARY`, `ROUTE_MAP`, `MARKETING_MEDIA`

#### `B2BBooking(TimeStampedModel)`
- **Table**: `b2b_bookings`
- **Fields**:
  - `partner`: `ForeignKey(B2BPartner, on_delete=models.PROTECT, related_name='partner_bookings')`
  - `booking`: `OneToOneField('bookings.Booking', on_delete=models.PROTECT, related_name='b2b_attribution')`
  - `commission_rate`: `DecimalField(max_digits=5, decimal_places=2)`
  - `gross_amount_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `commission_amount_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `net_amount_usd`: `DecimalField(max_digits=12, decimal_places=2)`
  - `commission_status`: `CharField(max_length=20, choices=CommissionStatus.choices, default='PENDING', db_index=True)`
  - `commission_invoiced_at`: `DateTimeField(null=True, blank=True)` — Set when invoice is issued to the partner.
  - `commission_paid_at`: `DateTimeField(null=True, blank=True)` — Set when payout is confirmed.
- **Enums**:
  - `CommissionStatus`: `PENDING`, `INVOICED`, `PAID`, `DISPUTED`

### 9.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `B2BRegistrationSerializer` | Write | Travel agency onboarding | Creates `User` (`role=B2B_PARTNER`) and pending `B2BPartner` profile. |
| `B2BAssetSerializer` | Read | Marketing download assets | Filters assets where `partner.agency_tier >= asset.minimum_tier`. |
| `B2BBookingSerializer` | Read | Partner net ledger | Shows gross vs commission vs net payable for agency group departures. |

---

## 10. App 8: `apps.content_cms` (Guides & Responsible Travel)

### 10.1 Directory Structure
```text
apps/content_cms/
├── models/
│   ├── guide.py
│   ├── initiative.py
│   └── __init__.py
├── serializers/
│   ├── guide_serializers.py
│   ├── initiative_serializers.py
│   └── __init__.py
```

### 10.2 Models

#### `TravelGuide(TimeStampedModel)`
- **Table**: `travel_guides`
- **Fields**:
  - `destination`: `ForeignKey('destinations.Destination', on_delete=models.SET_NULL, null=True, blank=True, related_name='guides')`
  - `author`: `ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='authored_guides')` — Records the Staff/Admin who created the guide for content auditing.
  - `title`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255, unique=True, db_index=True)`
  - `country`: `CharField(max_length=100, db_index=True)`
  - `region`: `CharField(max_length=150, blank=True)`
  - `category`: `CharField(max_length=30, choices=GuideCategory.choices, db_index=True)`
  - `markdown_content`: `TextField()`
  - `hero_image_url`: `URLField(max_length=500, blank=True)`
  - `meta_title`: `CharField(max_length=255, blank=True)`
  - `meta_description`: `CharField(max_length=500, blank=True)`
  - `canonical_url`: `URLField(max_length=500, blank=True)`
  - `is_published`: `BooleanField(default=False, db_index=True)`
  - `published_at`: `DateTimeField(null=True, blank=True)` — Auto-set on first publish transition.
- **Enums**:
  - `GuideCategory`: `VISAS`, `PERMITS`, `ALTITUDE`, `CULTURE`, `BEST_TIME`

#### `ResponsibleTravelInitiative(TimeStampedModel)`
- **Table**: `responsible_travel_initiatives`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `slug`: `SlugField(max_length=255, unique=True)`
  - `pillars`: `JSONField(default=list)` (Community, Environment, Porter Welfare, Waste)
  - `content`: `TextField()`
  - `is_published`: `BooleanField(default=False, db_index=True)`

### 10.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `TravelGuideListSerializer` | Read | Guide index & cards | `title`, `slug`, `category`, `country`, `hero_image_url`. |
| `TravelGuideDetailSerializer` | Read | Next.js Markdown SSR | Full markdown body, canonical URL, and Schema.org `Article` / `BreadcrumbList`. |
| `ResponsibleTravelSerializer`| Read | Porter welfare & eco pledges | `title`, `slug`, `pillars`, `content`. |

---

## 11. App 9: `apps.faq` (Contextual FAQs)

### 11.1 Directory Structure
```text
apps/faq/
├── models/
│   ├── faq.py
│   └── __init__.py
├── serializers/
│   ├── faq_serializers.py
│   └── __init__.py
```

### 11.2 Models

#### `FAQ(TimeStampedModel)`
- **Table**: `faqs`
- **Fields**:
  - `trip`: `ForeignKey('trips.Trip', on_delete=models.CASCADE, null=True, blank=True, related_name='faqs')`
  - `destination`: `ForeignKey('destinations.Destination', on_delete=models.CASCADE, null=True, blank=True, related_name='faqs')`
  - `question`: `CharField(max_length=500)`
  - `answer`: `TextField()`
  - `category`: `CharField(max_length=30, choices=FAQCategory.choices, db_index=True)`
  - `display_order`: `IntegerField(default=0, db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
- **Enums**:
  - `FAQCategory`: `GENERAL`, `BOOKING`, `TREKKING`, `EXPEDITION`, `PAYMENTS`
- **Ordering**: `['display_order', 'id']`

### 11.3 Serializers

| Serializer | Type | Description | Key Fields & Logic |
| :--- | :--- | :--- | :--- |
| `FAQSerializer` | Read | Contextual FAQ accordion | `id`, `question`, `answer`, `category`, `display_order`. Computes Schema.org `FAQPage` JSON-LD format. |

---

## 12. Cross-App Query Optimization & N+1 Prevention Matrix

To guarantee sub-100ms API response times on Next.js SSR requests, views must mandate explicit query prefetching:

| Endpoint | Target Serializer | Required `select_related()` | Required `prefetch_related()` |
| :--- | :--- | :--- | :--- |
| `GET /api/v1/trips/` | `TripListSerializer` | `destination`, `category` | None |
| `GET /api/v1/trips/{slug}/` | `TripDetailSerializer` | `destination`, `category`, `expedition_detail` | `itinerary_days`, `departures`, `reviews` |
| `GET /api/v1/bookings/{ref}/` | `BookingDetailSerializer` | `departure__trip`, `customer_user` | `passengers`, `payments` |
| `GET /api/v1/inquiries/` | `InquiryDetailSerializer` | `trip`, `departure`, `assigned_agent` | `tailor_made_detail`, `notes__author` |
| `GET /api/v1/b2b/assets/` | `B2BAssetSerializer` | `trip` | None |
| `GET /api/v1/faqs/?trip={id}` | `FAQSerializer` | `trip`, `destination` | None |
| `GET /api/v1/search/?q={query}` | `SearchResultSerializer` | None | None (raw SQL SearchVector) |
| `GET /api/v1/content/guides/` | `TravelGuideListSerializer` | `destination`, `author` | None |

---

## 13. `apps.search` — Full-Text Search Strategy

`apps.search` does not define its own models. It operates as a **query orchestration layer** using PostgreSQL 16+ native full-text search capabilities.

### 13.1 Search Vector Strategy
Use `django.contrib.postgres.search.SearchVector` across the following source fields:

| Source Model | Searched Fields | Weight |
| :--- | :--- | :---: |
| `Trip` | `title`, `slug` | `A` (highest) |
| `Trip` | `overview` | `B` |
| `Destination` | `name`, `region_name` | `A` |
| `TravelGuide` | `title` | `A` |
| `TravelGuide` | `markdown_content` | `C` |
| `FAQ` | `question` | `B` |
| `FAQ` | `answer` | `C` |

### 13.2 Implementation Approach
- Use **annotated query-time vectors** (no stored `SearchVectorField`) for simplicity in Phase 1.
- Upgrade to **stored materialized `SearchVectorField`** + GIN index on `trips` and `travel_guides` in Phase 2 when search volume justifies it:
  ```python
  # Phase 2 upgrade: apps/trips/models/trip.py
  search_vector = SearchVectorField(null=True, blank=True)  # Updated by Celery signal

  class Meta:
      indexes = [GinIndex(fields=['search_vector'], name='trips_search_gin_idx')]
  ```
- The `apps.search` view runs a **combined union query** across Trip, Destination, TravelGuide, and FAQ querysets, returning a unified ranked result list.

### 13.3 Serializer
| Serializer | Type | Description |
| :--- | :--- | :--- |
| `SearchResultSerializer` | Read | Returns `entity_type` (`trip`, `destination`, `guide`, `faq`), `title`, `slug`, `snippet`, `rank_score`. |

---

## 14. Next Execution Sequence

1. **Step 1**: Scaffold `apps.common` for shared `UUIDModel` and `TimeStampedModel`.
2. **Step 2**: Implement `apps.accounts` (Custom User model + `AUTH_USER_MODEL` setting) and run **initial migration first** before any other app.
3. **Step 3**: Implement catalog models (`apps.destinations` & `apps.trips`).
4. **Step 4**: Implement financial models (`apps.bookings` & `apps.payments`).
5. **Step 5**: Implement remaining domains (`apps.inquiries`, `apps.b2b`, `apps.content_cms`, `apps.faq`).
6. **Step 6**: Implement `apps.search` query layer after all source models are migrated.
