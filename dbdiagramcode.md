//////////////////////////////////////////////////////
// DREAMSCAPE TREKS™ - PRODUCTION DATABASE SCHEMA
// Engine: PostgreSQL 16+ / Django 5.x + DRF
// Nepal, Tibet, Bhutan, India & Beyond
//////////////////////////////////////////////////////

// ===================================================
// ENUMS
// ===================================================

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

// ===================================================
// 1. ACCOUNTS (apps.accounts)
// ===================================================

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

// ===================================================
// 2. DESTINATIONS (apps.destinations)
// ===================================================

Table destinations {
  id uuid [pk]
  slug varchar(255) [not null, unique]
  name varchar(255) [not null]

  country destination_country [not null]
  region_name varchar(150) // e.g. "Khumbu / Everest", "Annapurna", "Mustang"

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

Table activity_categories {
  id uuid [pk]
  name varchar(150) [not null, unique]
  slug varchar(150) [not null, unique]
  description text

  is_active boolean [not null, default: true]

  created_at timestamp [not null]
  updated_at timestamp [not null]
}

// ===================================================
// 3. TRIPS & EXPEDITIONS (apps.trips)
// ===================================================

Table trips {
  id uuid [pk]

  destination_id uuid [not null, ref: > destinations.id]
  category_id uuid [not null, ref: > activity_categories.id]

  title varchar(255) [not null]
  slug varchar(255) [not null, unique]

  duration_days int [not null]
  altitude_max_meters int

  difficulty_grade difficulty_grade [not null]

  // Group capacities for departure guarantees
  min_group_size int [not null, default: 1]
  max_group_size int [not null, default: 14]

  // JSONB in PostgreSQL 16+
  best_seasons jsonb
  inclusions jsonb
  exclusions jsonb
  packing_list jsonb

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

Table peak_expedition_details {
  id uuid [pk]

  trip_id uuid [not null, unique, ref: - trips.id]

  summit_window varchar(255)
  technical_rating varchar(100)
  gear_requirements jsonb
  permit_fee_type varchar(100)
  mandatory_certifications jsonb

  created_at timestamp [not null]
  updated_at timestamp [not null]
}

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

  meals_included jsonb

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

Table trip_reviews {
  id uuid [pk]

  trip_id uuid [not null, ref: > trips.id]
  user_id uuid [ref: > users.id]
  booking_id uuid [unique, ref: - bookings.id] // Verified booking badge

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

// ===================================================
// 4. BOOKINGS (apps.bookings)
// ===================================================

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

// ===================================================
// 5. PAYMENTS (apps.payments)
// ===================================================

Table payment_transactions {
  id uuid [pk]

  booking_id uuid [not null, ref: > bookings.id]

  transaction_id varchar(255) [not null, unique]
  idempotency_key varchar(255) [unique]

  gateway payment_gateway [not null]
  payment_stage payment_stage [not null]

  amount decimal(12,2) [not null]
  currency varchar(10) [not null, default: 'USD']

  // Khalti / NPR gateway conversion reconciliation
  exchange_rate decimal(10,4)
  charged_amount decimal(14,2)
  charged_currency varchar(10) [default: 'NPR']
  gateway_fee decimal(10,2)

  status payment_status [not null, default: 'INITIATED']

  webhook_raw_payload jsonb
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

// ===================================================
// 6. INQUIRIES & CRM (apps.inquiries)
// ===================================================

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

Table tailor_made_requests {
  id uuid [pk]

  inquiry_id uuid [not null, unique, ref: - inquiries.id]

  custom_destinations jsonb
  desired_activities jsonb

  fitness_level varchar(100)
  accommodation_standard varchar(100)
  guide_language_preference varchar(50)

  custom_route_coordinates jsonb
  waypoints jsonb

  created_at timestamp [not null]
  updated_at timestamp [not null]
}

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

// ===================================================
// 7. B2B PARTNER PORTAL (apps.b2b)
// ===================================================

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

Table b2b_assets {
  id uuid [pk]

  trip_id uuid [ref: > trips.id]

  title varchar(255) [not null]
  asset_type asset_type [not null]
  file varchar(500) [not null]

  // Hierarchical minimum tier required to download
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

// ===================================================
// 8. CONTENT CMS (apps.content_cms)
// ===================================================

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

Table responsible_travel_initiatives {
  id uuid [pk]

  title varchar(255) [not null]
  slug varchar(255) [not null, unique]

  // Pillars: Community, Environment, Porter Welfare, Waste
  pillars jsonb
  content text [not null]

  is_published boolean [not null, default: false]

  created_at timestamp [not null]
  updated_at timestamp [not null]

  Indexes {
    slug
    is_published
  }
}

// ===================================================
// 9. FAQ SERVICE (apps.faq)
// ===================================================

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

// ===================================================
// 10. SYSTEM & SHARED UTILITIES
// ===================================================

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

Table notification_logs {
  id uuid [pk]

  user_id uuid [ref: > users.id]
  booking_id uuid [ref: > bookings.id]
  inquiry_id uuid [ref: > inquiries.id]

  channel varchar(50) [not null]       // e.g. "EMAIL", "WHATSAPP"
  event_type varchar(100) [not null]   // e.g. "SPLIT_PAYMENT_REMINDER", "INQUIRY_RECEIVED"

  recipient varchar(255)
  subject varchar(255)

  status varchar(50) [not null]        // "SENT", "FAILED", "DELIVERED"
  provider_message_id varchar(255)

  response_payload jsonb

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

Table audit_logs {
  id uuid [pk]

  actor_id uuid [ref: > users.id]

  action varchar(100) [not null]       // e.g. "BOOKING_MODIFIED", "DEPOSIT_REFUNDED"
  entity_type varchar(100) [not null]  // e.g. "Booking", "TripDeparture"
  entity_id uuid

  old_values jsonb
  new_values jsonb

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
