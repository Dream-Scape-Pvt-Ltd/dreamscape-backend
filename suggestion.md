# Database Architecture Review & Engineering Suggestions
**Project:** Dreamscape Treks™ (Nepal & Beyond: Nepal, Tibet, Bhutan, India)  
**Target Engine:** PostgreSQL 16+ / Django 5.x + DRF  
**Document Version:** 1.0  

---

## 1. Executive Summary & Verdict

Your DBML schema draft provides a solid foundation. The separation into domain boundaries (`accounts`, `destinations`, `trips`, `bookings`, `payments`, `inquiries`, `b2b`, `content_cms`) matches enterprise travel platforms.

However, Himalayan mountaineering and multi-country expedition logistics (Nepal, Tibet, Bhutan, India) introduce strict legal, medical, regulatory, and multi-currency constraints that are currently missing or underspecified.

### Overall Architecture Scorecard

| Area | Current Rating | Primary Recommendation |
| :--- | :--- | :--- |
| **Domain Boundaries** | 🟢 **9/10 (Excellent)** | Clean decoupling across apps and domain tables. |
| **Himalayan Expedition Logistics** | 🟡 **6/10 (Needs Work)** | Missing mandatory high-altitude helicopter rescue insurance, passport expiry, and DOB for permits. |
| **Financial & Payment Ledger** | 🟡 **7/10 (Good)** | Missing payment milestone distinction (`DEPOSIT` vs `BALANCE`), NPR conversion for Khalti, and idempotency keys. |
| **Inquiries & CRM Linking** | 🟡 **7/10 (Good)** | Missing direct `trip_id` foreign key for journey inquiries and lead attribution sources. |
| **SEO & Social Proof** | 🔴 **4/10 (Critical Gap)** | Missing `reviews` / `ratings` model, which is mandatory for Schema.org `aggregateRating` and conversion. |
| **PostgreSQL 16+ Constraints** | 🟡 **6/10 (Basic)** | Missing database-level `CheckConstraint` rules for seat counts, date ranges, and positive amounts. |

---

## 2. Critical High-Altitude & Himalayan Operational Improvements

### 2.1. Passenger Details: Mandatory High-Altitude Rescue Insurance & Permits
In Nepal, Tibet, and Bhutan, travel operators are legally forbidden from issuing TIMS cards, national park permits (Sagarmatha, Annapurna, Manaslu), or booking domestic mountain flights (e.g., Lukla, Jomsom) without passenger passport validity and emergency medical evacuation insurance up to 6,000 meters.

- **Add to `passenger_details`**:
  - `date_of_birth date [not null]`: Required for child/senior discounts, mountain permit forms, and flight tickets.
  - `passport_expiry_date date [not null]`: Visas for Nepal, Tibet, and Bhutan require at least **6 months** of remaining validity from trip start date.
  - `gender varchar(20)`: Required on flight manifests and government permit manifests.
  - `insurance_policy_number varchar(100) [not null]`: Emergency policy number.
  - `insurance_provider varchar(150) [not null]`: e.g., Ripcord, World Nomads, Global Rescue.
  - `insurance_emergency_phone varchar(50) [not null]`: 24/7 emergency dispatch line for helicopter rescue evacuation.

### 2.2. Itinerary Days: Acclimatization & Mountain Lodging Standards
On routes like Everest Base Camp (Namche Bazaar, Dingboche) or Annapurna Circuit (Manang), acclimatization rest days are safety milestones.
- **Add to `itinerary_days`**:
  - `is_acclimatization_day boolean [not null, default: false]`: Powers visual elevation graphs, medical safety badges, and rest day highlights on Next.js.
  - `accommodation_type enum` (`TEAHOUSE`, `CAMPING`, `ECO_LODGE`, `HOTEL_3STAR`, `HOTEL_5STAR`): Sets traveler expectations on trail amenities.

---

## 3. Financial, Split-Payment & Booking Integrity

### 3.1. Payment Milestone Tracking in `payment_transactions`
Currently, `payment_transactions` records `amount` and `status`, but does not differentiate whether a transaction paid the initial **20% deposit**, the **80% remaining balance**, or was an **ancillary adjustment / refund**.
- **Add `payment_stage` enum**:
  ```sql
  Enum payment_stage {
    DEPOSIT_20
    BALANCE_80
    FULL_100
    CUSTOM_ADJUSTMENT
    REFUND
  }
  ```
- Add `payment_stage payment_stage [not null]` to `payment_transactions`.

### 3.2. Multi-Currency & Khalti NPR Gateway Reconciliation
Dreamscape prices trips in `USD`, but Khalti is a Nepalese payment gateway whose primary clearing currency is **NPR (Nepalese Rupees)**.
- **Add to `payment_transactions`**:
  - `exchange_rate decimal(10,4)`: The USD to NPR rate locked at the moment of payment initiation.
  - `charged_amount decimal(14,2)`: The actual amount charged at the gateway (e.g., NPR 270,000 for a $2,000 trek).
  - `charged_currency varchar(10) [default: 'NPR']`: Currency sent to the payment provider.
  - `gateway_fee decimal(10,2)`: Transaction fee charged by Khalti/Stripe for net ledger accounting.
  - `idempotency_key varchar(255) [unique]`: Prevents accidental double charges on webhook retries or customer multi-clicks.

### 3.3. Bookings Table Enhancements
- **Add `num_travelers int [not null, default: 1]`**: Storing the party size directly on `bookings` prevents costly joins on `passenger_details` every time departure seat capacities are updated.
- **Foreign Key Delete Behavior (Django ORM)**:
  - `customer_user_id`: Set `on_delete=models.SET_NULL, null=True` (supports guest checkouts).
  - `departure_id`: Set `on_delete=models.PROTECT` (prevents deleting a departure schedule if paid bookings exist).

---

## 4. Missing Core Entity: `trip_reviews` (Social Proof & Schema.org)

For high-ticket adventure travel ($1,500 – $15,000+ USD), verified customer reviews are the highest-converting asset. Furthermore, Google's rich snippets (`Product` & `TouristTrip`) require `aggregateRating` and `review` objects.

```sql
//////////////////////////////////////////////////////
// REVIEWS & TESTIMONIALS
//////////////////////////////////////////////////////

Table trip_reviews {
  id uuid [pk]
  trip_id uuid [not null, ref: > trips.id]
  user_id uuid [ref: > users.id]
  booking_id uuid [unique, ref: - bookings.id] // Verified booking badge

  reviewer_name varchar(255) [not null]
  reviewer_country varchar(100)

  rating_overall int [not null] // 1 to 5
  rating_guide int             // 1 to 5
  rating_itinerary int         // 1 to 5
  rating_safety int            // 1 to 5

  title varchar(255)
  content text [not null]

  travel_date date
  is_verified boolean [not null, default: false]
  is_published boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    trip_id
    rating_overall
    is_published
    travel_date
  }
}
```

---

## 5. Inquiries & CRM Improvements

1. **Link Journey Leads to Trips**:
   - `inquiry_type` has a `JOURNEY` choice, but `Table inquiries` has no `trip_id` column.
   - Add `trip_id uuid [ref: > trips.id]` (nullable) to `inquiries`.
2. **Attribution & Channel Tracking**:
   - Add `lead_source varchar(50) [default: 'WEBSITE']` (`WEBSITE`, `WHATSAPP_WIDGET`, `B2B_PARTNER`, `ORGANIC_SEARCH`, `INSTAGRAM_CAMPAIGN`).
3. **Trip Departure Interest**:
   - Add `departure_id uuid [ref: > trip_departures.id]` (nullable) to `inquiries` so sales agents know which specific date the customer is interested in.

---

## 6. B2B Partner Portal Enhancements

1. **Hierarchical Tier Access for Assets**:
   - Instead of storing JSON arrays like `restricted_tiers: ["BRONZE", "SILVER"]`, use a hierarchical enum `minimum_tier agency_tier [not null, default: 'BRONZE']`.
   - Any agency with a tier $\ge$ `minimum_tier` automatically inherits access (`PLATINUM` $\ge$ `GOLD` $\ge$ `SILVER` $\ge$ `BRONZE`). This makes Django ORM queries simple:
     ```python
     B2BAsset.objects.filter(minimum_tier__lte=partner.agency_tier)
     ```
2. **Associate Assets with Trips**:
   - Add `trip_id uuid [ref: > trips.id]` (nullable) to `b2b_assets` so agencies can download trip-specific white-label marketing collateral.

---

## 7. PostgreSQL 16+ & Django 5.x Constraints

Add explicit database-level check constraints to guarantee ACID integrity:

```python
# Django 5.x Model Meta Check Constraints:

# 1. TripDepartures: Available seats cannot exceed max seats or fall below 0
models.CheckConstraint(
    condition=models.Q(available_seats__gte=0) & models.Q(available_seats__lte=models.F('max_seats')),
    name='valid_departure_seats'
)

# 2. TripDepartures: Departure end date must be on or after start date
models.CheckConstraint(
    condition=models.Q(end_date__gte=models.F('start_date')),
    name='valid_departure_dates'
)

# 3. Bookings: Amount paid cannot be negative
models.CheckConstraint(
    condition=models.Q(amount_paid_usd__gte=0),
    name='positive_amount_paid'
)

# 4. ItineraryDays: Day numbers must be positive
models.CheckConstraint(
    condition=models.Q(day_number__gte=1),
    name='positive_day_number'
)

# 5. Reviews: Ratings must be between 1 and 5
models.CheckConstraint(
    condition=models.Q(rating_overall__range=(1, 5)),
    name='valid_rating_range'
)
```

---

## 8. Complete Refined & Production-Ready DBML Code

Below is the complete, upgraded DBML diagram incorporating all corrections:

```dbml
//////////////////////////////////////////////////////
// DREAMSCAPE TREKS™ - PRODUCTION DATABASE SCHEMA
// PostgreSQL 16+ / Django 5.x
//////////////////////////////////////////////////////

Enum user_role {
  ADMIN
  SALES_AGENT
  B2B_PARTNER
  CUSTOMER
}

Enum destination_country {
  NEPAL
  TIBET
  BHUTAN
  INDIA
  MULTI_COUNTRY
}

Enum difficulty_grade {
  GRADE_1
  GRADE_2
  GRADE_3
  GRADE_4
  GRADE_5
  ALPINE
}

Enum departure_status {
  GUARANTEED
  LIMITED
  SOLD_OUT
  CANCELLED
}

Enum payment_type {
  FULL_100
  DEPOSIT_20
}

Enum payment_stage {
  DEPOSIT_20
  BALANCE_80
  FULL_100
  CUSTOM_ADJUSTMENT
  REFUND
}

Enum booking_status {
  PENDING
  DEPOSIT_PAID
  FULLY_PAID
  CANCELLED
  REFUNDED
}

Enum payment_gateway {
  KHALTI
  STRIPE
  BANK
}

Enum payment_status {
  INITIATED
  SUCCESS
  FAILED
  REFUNDED
}

Enum inquiry_type {
  GENERAL
  JOURNEY
  TAILOR_MADE
  PARTNER_DMC
  EXISTING_TRAVELLER
}

Enum inquiry_status {
  NEW
  ASSIGNED
  IN_CONTACT
  TRAVELING
  COMPLETED
  CLOSED
}

Enum agency_tier {
  BRONZE
  SILVER
  GOLD
  PLATINUM
}

Enum asset_type {
  WHITE_LABEL_ITINERARY
  ROUTE_MAP
  MARKETING_MEDIA
}

Enum guide_category {
  VISAS
  PERMITS
  ALTITUDE
  CULTURE
  BEST_TIME
}

Enum faq_category {
  GENERAL
  BOOKING
  TREKKING
  EXPEDITION
  PAYMENTS
}

Enum accommodation_type {
  TEAHOUSE
  CAMPING
  ECO_LODGE
  HOTEL_3STAR
  HOTEL_5STAR
}

//////////////////////////////////////////////////////
// ACCOUNTS
//////////////////////////////////////////////////////

Table users {
  id uuid [pk]
  email varchar(255) [not null, unique]
  password varchar(255) [not null]

  first_name varchar(100)
  last_name varchar(100)

  phone varchar(50)
  whatsapp_number varchar(50)

  role user_role [not null, default: 'CUSTOMER']

  is_active boolean [not null, default: true]
  is_staff boolean [not null, default: false]
  is_superuser boolean [not null, default: false]

  last_login timestamp
  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    email
    role
    is_active
  }
}

//////////////////////////////////////////////////////
// DESTINATIONS
//////////////////////////////////////////////////////

Table destinations {
  id uuid [pk]
  slug varchar(255) [not null, unique]
  name varchar(255) [not null]

  country destination_country [not null]
  region_name varchar(150) // e.g. "Khumbu / Everest Region"

  visa_guidelines text
  permit_details text
  hero_media varchar(500)

  is_active boolean [not null, default: true]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    country
    is_active
    slug
  }
}

//////////////////////////////////////////////////////
// ACTIVITY CATEGORIES
//////////////////////////////////////////////////////

Table activity_categories {
  id uuid [pk]
  name varchar(150) [not null, unique]
  slug varchar(150) [not null, unique]
  description text

  is_active boolean [not null, default: true]

  created_at timestamp [not null]
  updated_at timestamp [not null]
}

//////////////////////////////////////////////////////
// TRIPS / TREKS / TOURS / EXPEDITIONS
//////////////////////////////////////////////////////

Table trips {
  id uuid [pk]

  destination_id uuid [not null, ref: > destinations.id]
  category_id uuid [not null, ref: > activity_categories.id]

  title varchar(255) [not null]
  slug varchar(255) [not null, unique]

  duration_days int [not null]
  altitude_max_meters int

  difficulty_grade difficulty_grade [not null]

  // Min/Max group size for departure guarantees
  min_group_size int [not null, default: 1]
  max_group_size int [not null, default: 14]

  // PostgreSQL JSONB in Django
  best_seasons json
  inclusions json
  exclusions json
  packing_list json

  starting_price_usd decimal(12,2) [not null]
  single_supplement_usd decimal(12,2) [default: 0]

  overview text

  is_featured boolean [not null, default: false]
  is_active boolean [not null, default: true]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    destination_id
    category_id
    difficulty_grade
    duration_days
    altitude_max_meters
    starting_price_usd
    is_featured
    is_active
  }
}

//////////////////////////////////////////////////////
// PEAK EXPEDITION DETAILS
//////////////////////////////////////////////////////

Table peak_expedition_details {
  id uuid [pk]

  trip_id uuid [not null, unique, ref: - trips.id]

  summit_window varchar(255)
  technical_rating varchar(100)
  gear_requirements json
  permit_fee_type varchar(100)
  mandatory_certifications json

  created_at timestamp [not null]
  updated_at timestamp [not null]
}

//////////////////////////////////////////////////////
// ITINERARY
//////////////////////////////////////////////////////

Table itinerary_days {
  id uuid [pk]

  trip_id uuid [not null, ref: > trips.id]

  day_number int [not null]
  title varchar(255) [not null]
  description text

  overnight_stay varchar(255)
  elevation_meters int
  accommodation_type accommodation_type [not null, default: 'TEAHOUSE']

  // Himalayan acclimatization milestone flag
  is_acclimatization_day boolean [not null, default: false]

  meals_included json

  latitude decimal(10,7)
  longitude decimal(10,7)

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    trip_id
    day_number
    (trip_id, day_number) [unique]
  }
}

//////////////////////////////////////////////////////
// TRIP DEPARTURES
//////////////////////////////////////////////////////

Table trip_departures {
  id uuid [pk]

  trip_id uuid [not null, ref: > trips.id]

  start_date date [not null]
  end_date date [not null]

  price_usd decimal(12,2) [not null]

  max_seats int [not null]
  available_seats int [not null]

  status departure_status [not null, default: 'LIMITED']
  is_guaranteed boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    trip_id
    start_date
    end_date
    status
    (trip_id, start_date)
  }
}

//////////////////////////////////////////////////////
// BOOKINGS
//////////////////////////////////////////////////////

Table bookings {
  id uuid [pk]

  booking_reference varchar(30) [not null, unique]

  customer_user_id uuid [ref: > users.id]
  departure_id uuid [ref: > trip_departures.id]
  custom_trip_id uuid [ref: > trips.id]

  customer_name varchar(255) [not null]
  customer_email varchar(255) [not null]
  customer_phone varchar(50)

  // Direct party size tracking
  num_travelers int [not null, default: 1]

  total_amount_usd decimal(12,2) [not null]
  currency varchar(10) [not null, default: 'USD']

  payment_type payment_type [not null, default: 'DEPOSIT_20']

  deposit_amount_usd decimal(12,2) [not null]
  balance_amount_usd decimal(12,2) [not null]
  amount_paid_usd decimal(12,2) [not null, default: 0]

  status booking_status [not null, default: 'PENDING']

  trip_start_date date [not null]
  balance_due_date date

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    booking_reference
    customer_user_id
    departure_id
    status
    trip_start_date
    balance_due_date
    customer_email
  }
}

//////////////////////////////////////////////////////
// PASSENGERS (GOVERNMENT PERMITS & RESCUE INSURANCE)
//////////////////////////////////////////////////////

Table passenger_details {
  id uuid [pk]

  booking_id uuid [not null, ref: > bookings.id]

  full_name varchar(255) [not null]
  gender varchar(20)
  date_of_birth date [not null]

  passport_number varchar(100) [not null]
  passport_expiry_date date [not null]
  nationality varchar(100) [not null]

  // Mandatory 6,000m high-altitude rescue insurance
  insurance_provider varchar(150) [not null]
  insurance_policy_number varchar(100) [not null]
  insurance_emergency_phone varchar(50) [not null]

  emergency_contact_name varchar(255)
  emergency_contact_phone varchar(50)

  dietary_requirements text
  medical_conditions text

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    booking_id
    passport_number
  }
}

//////////////////////////////////////////////////////
// PAYMENTS & GATEWAY RECONCILIATION
//////////////////////////////////////////////////////

Table payment_transactions {
  id uuid [pk]

  booking_id uuid [not null, ref: > bookings.id]

  transaction_id varchar(255) [not null, unique]
  idempotency_key varchar(255) [unique]

  gateway payment_gateway [not null]
  payment_stage payment_stage [not null]

  amount decimal(12,2) [not null]
  currency varchar(10) [not null, default: 'USD']

  // Khalti / Local currency reconciliation
  exchange_rate decimal(10,4)
  charged_amount decimal(14,2)
  charged_currency varchar(10) [default: 'NPR']
  gateway_fee decimal(10,2)

  status payment_status [not null, default: 'INITIATED']

  webhook_raw_payload json
  webhook_event_id varchar(255)

  created_at timestamp [not null]
  processed_at timestamp

  Indexes {
    booking_id
    transaction_id
    idempotency_key
    webhook_event_id
    status
    gateway
    payment_stage
  }
}

//////////////////////////////////////////////////////
// PAYMENT TOKENS / SECURE BALANCE LINKS
//////////////////////////////////////////////////////

Table payment_action_tokens {
  id uuid [pk]

  booking_id uuid [not null, ref: > bookings.id]

  token_hash varchar(255) [not null, unique]

  purpose varchar(50) [not null] // e.g. "BALANCE_PAYMENT_80"
  expires_at timestamp [not null]
  used_at timestamp

  created_at timestamp [not null]

  Indexes {
    booking_id
    expires_at
    purpose
  }
}

//////////////////////////////////////////////////////
// REVIEWS & TESTIMONIALS (SCHEMA.ORG RICH SNIPPETS)
//////////////////////////////////////////////////////

Table trip_reviews {
  id uuid [pk]

  trip_id uuid [not null, ref: > trips.id]
  user_id uuid [ref: > users.id]
  booking_id uuid [unique, ref: - bookings.id]

  reviewer_name varchar(255) [not null]
  reviewer_country varchar(100)

  rating_overall int [not null] // 1 to 5
  rating_guide int
  rating_itinerary int
  rating_safety int

  title varchar(255)
  content text [not null]

  travel_date date
  is_verified boolean [not null, default: false]
  is_published boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    trip_id
    rating_overall
    is_published
    travel_date
  }
}

//////////////////////////////////////////////////////
// INQUIRIES / CRM
//////////////////////////////////////////////////////

Table inquiries {
  id uuid [pk]

  inquiry_number varchar(30) [not null, unique]
  inquiry_type inquiry_type [not null]

  trip_id uuid [ref: > trips.id]
  departure_id uuid [ref: > trip_departures.id]

  full_name varchar(255) [not null]
  email varchar(255) [not null]
  phone varchar(50)
  whatsapp_number varchar(50)

  message text

  preferred_dates varchar(255)
  estimated_budget decimal(12,2)
  group_size int

  lead_source varchar(50) [not null, default: 'WEBSITE']

  status inquiry_status [not null, default: 'NEW']
  assigned_agent_id uuid [ref: > users.id]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    inquiry_number
    email
    trip_id
    status
    assigned_agent_id
    inquiry_type
    created_at
  }
}

//////////////////////////////////////////////////////
// TAILOR MADE REQUEST
//////////////////////////////////////////////////////

Table tailor_made_requests {
  id uuid [pk]

  inquiry_id uuid [not null, unique, ref: - inquiries.id]

  custom_destinations json
  desired_activities json

  fitness_level varchar(100)
  accommodation_standard varchar(100)
  guide_language_preference varchar(50)

  custom_route_coordinates json
  waypoints json

  created_at timestamp [not null]
  updated_at timestamp [not null]
}

//////////////////////////////////////////////////////
// INQUIRY NOTES
//////////////////////////////////////////////////////

Table inquiry_notes {
  id uuid [pk]

  inquiry_id uuid [not null, ref: > inquiries.id]
  author_id uuid [not null, ref: > users.id]

  note_text text [not null]

  created_at timestamp [not null]

  Indexes {
    inquiry_id
    author_id
    created_at
  }
}

//////////////////////////////////////////////////////
// B2B PARTNERS
//////////////////////////////////////////////////////

Table b2b_partners {
  id uuid [pk]

  user_id uuid [not null, unique, ref: - users.id]

  company_name varchar(255) [not null]
  country varchar(100) [not null]
  registration_number varchar(150)
  website varchar(255)

  agency_tier agency_tier [not null, default: 'BRONZE']
  commission_rate decimal(5,2) [not null, default: 0]

  approved boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    company_name
    country
    agency_tier
    approved
  }
}

//////////////////////////////////////////////////////
// B2B ASSETS
//////////////////////////////////////////////////////

Table b2b_assets {
  id uuid [pk]

  trip_id uuid [ref: > trips.id]

  title varchar(255) [not null]
  asset_type asset_type [not null]
  file varchar(500) [not null]

  // Hierarchical minimum required tier
  minimum_tier agency_tier [not null, default: 'BRONZE']

  is_active boolean [not null, default: true]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    trip_id
    asset_type
    minimum_tier
    is_active
  }
}

//////////////////////////////////////////////////////
// B2B BOOKINGS
//////////////////////////////////////////////////////

Table b2b_bookings {
  id uuid [pk]

  partner_id uuid [not null, ref: > b2b_partners.id]
  booking_id uuid [not null, unique, ref: - bookings.id]

  commission_rate decimal(5,2) [not null]
  gross_amount_usd decimal(12,2) [not null]
  commission_amount_usd decimal(12,2) [not null]
  net_amount_usd decimal(12,2) [not null]

  created_at timestamp [not null]

  Indexes {
    partner_id
    booking_id
  }
}

//////////////////////////////////////////////////////
// TRAVEL GUIDES
//////////////////////////////////////////////////////

Table travel_guides {
  id uuid [pk]

  destination_id uuid [ref: > destinations.id]

  title varchar(255) [not null]
  slug varchar(255) [not null, unique]

  country varchar(100)
  region varchar(150)

  category guide_category [not null]

  markdown_content text [not null]
  hero_image_url varchar(500)

  meta_title varchar(255)
  meta_description varchar(500)
  canonical_url varchar(500)

  is_published boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    destination_id
    slug
    country
    region
    category
    is_published
  }
}

//////////////////////////////////////////////////////
// RESPONSIBLE TRAVEL
//////////////////////////////////////////////////////

Table responsible_travel_initiatives {
  id uuid [pk]

  title varchar(255) [not null]
  slug varchar(255) [not null, unique]

  pillars json
  content text [not null]

  is_published boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    slug
    is_published
  }
}

//////////////////////////////////////////////////////
// FAQ
//////////////////////////////////////////////////////

Table faqs {
  id uuid [pk]

  trip_id uuid [ref: > trips.id]
  destination_id uuid [ref: > destinations.id]

  question varchar(500) [not null]
  answer text [not null]

  category faq_category [not null]

  display_order int [not null, default: 0]
  is_active boolean [not null, default: true]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    trip_id
    destination_id
    category
    display_order
    is_active
  }
}

//////////////////////////////////////////////////////
// MEDIA
//////////////////////////////////////////////////////

Table media_assets {
  id uuid [pk]

  uploaded_by_id uuid [ref: > users.id]

  file varchar(500) [not null]
  original_name varchar(255)

  mime_type varchar(100)
  file_size_bytes bigint

  alt_text varchar(255)

  created_at timestamp [not null]

  Indexes {
    uploaded_by_id
    mime_type
  }
}

//////////////////////////////////////////////////////
// NOTIFICATION LOG
//////////////////////////////////////////////////////

Table notification_logs {
  id uuid [pk]

  user_id uuid [ref: > users.id]
  booking_id uuid [ref: > bookings.id]
  inquiry_id uuid [ref: > inquiries.id]

  channel varchar(50) [not null]
  event_type varchar(100) [not null]

  recipient varchar(255)
  subject varchar(255)

  status varchar(50) [not null]
  provider_message_id varchar(255)

  response_payload json

  created_at timestamp [not null]
  sent_at timestamp

  Indexes {
    user_id
    booking_id
    inquiry_id
    channel
    event_type
    status
    created_at
  }
}

//////////////////////////////////////////////////////
// AUDIT LOG
//////////////////////////////////////////////////////

Table audit_logs {
  id uuid [pk]

  actor_id uuid [ref: > users.id]

  action varchar(100) [not null]
  entity_type varchar(100) [not null]
  entity_id uuid

  old_values json
  new_values json

  ip_address varchar(45)
  user_agent text

  created_at timestamp [not null]

  Indexes {
    actor_id
    entity_type
    entity_id
    action
    created_at
  }
}
```
