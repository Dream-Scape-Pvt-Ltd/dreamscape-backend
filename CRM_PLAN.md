# DREAMSCAPE TREKS™ — CRM EXPANSION PLAN

**Document Version:** `1.0`
**Scope:** `apps.inquiries`, `apps.bookings` (link-back), `apps.accounts` (agent roles), staff admin dashboard
**Related Docs:** [`backend/BACKEND_PRD.md`](./BACKEND_PRD.md) · [`backend/apidesign.md`](./apidesign.md) · [`backend/suggestion.md`](./suggestion.md) · [`backend_and_frontend_connection.md`](../backend_and_frontend_connection.md) (Phase 4 & 10)

---

## 1. Where the CRM Stands Today

Dreamscape already has a working lead-capture and pipeline core, built on three models in `apps.inquiries`:

| Model | File | Role |
| :--- | :--- | :--- |
| `Inquiry` | `apps/inquiries/models/inquiry.py` | The lead record: type, contact info, budget, group size, source, status, assigned agent |
| `InquiryNote` | `apps/inquiries/models/note.py` | Free-text internal log entries, one author per note |
| `TailorMadeRequest` | `apps/inquiries/models/tailor_made.py` | 1:1 bespoke-trip spec (destinations, activities, route GeoJSON) for `TAILOR_MADE` leads |

Pipeline stages (`InquiryStatus`): `NEW → ASSIGNED → IN_CONTACT → TRAVELING → COMPLETED / CLOSED`.
Lead types (`InquiryType`): `GENERAL`, `JOURNEY`, `TAILOR_MADE`, `PARTNER_DMC`, `EXISTING_TRAVELLER`.

API surface (`apps/inquiries/views/inquiry_views.py`):
- `POST /api/v1/inquiries/` — public capture (`AllowAny`)
- `GET /api/v1/inquiries/` — staff list with `status`, `inquiry_type`, `assigned_agent`, `search` filters
- `GET/PATCH /api/v1/inquiries/<inquiry_number>/` — detail + status/agent update
- `GET/POST /api/v1/inquiries/<inquiry_number>/notes/` — note thread

Frontend: `inquiries.service.ts`, `inquiry-form.tsx` / `inquiry-dialog.tsx` (public capture), and an `InquiryDrawer` component inside `admin-dashboard.tsx` (staff view).

**Verdict:** this is a solid *lead intake + status tracker*, not yet a CRM. It has no customer identity beyond a single inquiry, no scheduled follow-ups, no activity timeline beyond text notes, no conversion linkage to bookings, and no pipeline analytics. The sections below close those gaps without discarding any of the above — everything here extends `apps.inquiries`, it does not replace it.

---

## 2. Gaps vs. a Working Sales CRM

| Gap | Why it matters | Fix |
| :--- | :--- | :--- |
| No customer identity | Same traveler emailing twice creates two disconnected `Inquiry` rows; agents lose history | §3.1 `Customer` profile keyed on email, backfilled from existing inquiries |
| No follow-up scheduling | Leads go cold — nothing tells an agent "call this person Thursday" | §3.2 `Task` model + Celery beat reminders |
| No structured activity timeline | `InquiryNote` mixes calls, emails, and internal commentary as plain text | §3.3 `Activity` model with a `channel` enum |
| No booking linkage | Once a lead converts, the connection to the resulting `Booking` is lost — no true conversion tracking | §3.4 `Inquiry.converted_booking` FK |
| No lost-reason capture | `CLOSED` gives no signal on *why* — price, dates, competitor, no response | §3.5 `lost_reason` field |
| No SLA / response-time tracking | No way to know if a lead sat untouched for 3 days | §3.6 `first_response_at`, `sla_breached` + Celery check |
| No auto-assignment | Agents currently self-assign or a manager assigns manually via PATCH | §4.3 round-robin assignment task (optional, phase 4) |
| No tagging/segmentation | Can't build a marketing list of "budget > $3000, EBC interest, NEW status" | §3.7 `Tag` (M2M) |
| No pipeline analytics | Admin dashboard shows a list, not a funnel or agent scorecard | §5 |

---

## 3. Data Model Additions

All new models live in `apps.inquiries` (or `apps.accounts` where noted) and inherit `TimeStampedModel` (`apps/common/models/base.py`) for consistency with the rest of the schema.

### 3.1 `Customer` — deduplicated identity

```python
class Customer(TimeStampedModel):
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    whatsapp_number = models.CharField(max_length=50, blank=True)
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="customer_profile",
    )
    lifetime_inquiries = models.PositiveIntegerField(default=0)
    lifetime_bookings = models.PositiveIntegerField(default=0)
    lifetime_value_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "crm_customers"
```

- `Inquiry` gets `customer = models.ForeignKey("inquiries.Customer", null=True, blank=True, related_name="inquiries")`, populated in `InquiryCreateSerializer.create()` via `get_or_create(email=...)`.
- A one-off data migration backfills `Customer` rows from the existing `Inquiry.email` values (dedupe on lowercase email) and from `bookings.customer_email` if that field exists on `Booking`.
- `lifetime_*` counters are updated by a Django signal (`post_save` on `Inquiry` and `Booking`) rather than computed on every read, to keep the customer-detail endpoint cheap.

This single model is what turns "a pile of inquiries" into "a CRM" — it's the join point for the customer-360 view in §6.1.

### 3.2 `Task` — follow-ups and reminders

```python
class TaskStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    DONE = "DONE", "Done"
    CANCELLED = "CANCELLED", "Cancelled"

class Task(TimeStampedModel):
    inquiry = models.ForeignKey("inquiries.Inquiry", on_delete=models.CASCADE, related_name="tasks")
    assigned_agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_tasks")
    title = models.CharField(max_length=255)
    due_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.OPEN, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crm_tasks"
        indexes = [models.Index(fields=["assigned_agent", "status", "due_at"], name="task_agent_status_due_idx")]
```

- A Celery Beat job (pattern already established for `apps.b2b.tasks.dispatch_pending_partner_emails`) runs every 15 minutes, finds `Task.objects.filter(status=OPEN, due_at__lte=now)`, and pushes a notification (reuse `apps.common.models.notification.Notification`, already used elsewhere in the codebase) plus an email/WhatsApp nudge to `assigned_agent`.
- Frontend: a "My Tasks" panel in the admin dashboard, and a due-date field exposed inline in `InquiryDrawer` when an agent logs an activity ("follow up in 3 days" quick-action).

### 3.3 `Activity` — structured timeline (supersedes free-text-only `InquiryNote` for logged interactions)

```python
class ActivityChannel(models.TextChoices):
    CALL = "CALL", "Phone Call"
    EMAIL = "EMAIL", "Email"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    NOTE = "NOTE", "Internal Note"
    STATUS_CHANGE = "STATUS_CHANGE", "Status Change"
    SYSTEM = "SYSTEM", "System Event"

class Activity(TimeStampedModel):
    inquiry = models.ForeignKey("inquiries.Inquiry", on_delete=models.CASCADE, related_name="activities")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=20, choices=ActivityChannel.choices)
    body = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # e.g. {"from_status": "NEW", "to_status": "ASSIGNED"}

    class Meta:
        db_table = "crm_activities"
        ordering = ["-created_at"]
```

- `InquiryNote` is kept as-is for backward compatibility (existing data, existing API), but new agent-facing UI writes to `Activity` going forward; a thin serializer union merges both into one timeline view (`GET /api/v1/inquiries/<inquiry_number>/timeline/`, §4.1).
- Every `PATCH` that changes `Inquiry.status` auto-creates a `STATUS_CHANGE` activity via `InquiryUpdateSerializer.update()` — this alone gives free audit history without any UI change.

### 3.4 Conversion linkage

```python
# apps/inquiries/models/inquiry.py
converted_booking = models.OneToOneField(
    "bookings.Booking", null=True, blank=True,
    on_delete=models.SET_NULL, related_name="source_inquiry",
)
converted_at = models.DateTimeField(null=True, blank=True)
```

- Set automatically when a `Booking` is created with a `departure` that matches an `IN_CONTACT`/`ASSIGNED` inquiry for the same email — wired into `BookingListCreateView.create()` in `apps.bookings.views.booking_views` as a best-effort match (exact email + same trip), never blocking booking creation if no match is found.
- This is what makes §5's funnel and conversion-rate numbers real instead of estimated.

### 3.5 Lost-reason capture

```python
class LostReason(models.TextChoices):
    PRICE = "PRICE", "Price Too High"
    DATES = "DATES", "Dates Didn't Work"
    COMPETITOR = "COMPETITOR", "Booked With Competitor"
    NO_RESPONSE = "NO_RESPONSE", "Went Unresponsive"
    NOT_SUITABLE = "NOT_SUITABLE", "Trip Not Suitable"
    OTHER = "OTHER", "Other"

# Inquiry:
lost_reason = models.CharField(max_length=20, choices=LostReason.choices, blank=True)
```

- `InquiryUpdateSerializer` requires `lost_reason` when `status` transitions to `CLOSED` and `converted_booking` is null — a `serializers.ValidationError` if omitted. This is a one-line validation rule that pays for itself the first time someone asks "why are we losing EBC leads."

### 3.6 SLA / response-time tracking

```python
# Inquiry:
first_response_at = models.DateTimeField(null=True, blank=True)
sla_breached = models.BooleanField(default=False, db_index=True)
```

- `first_response_at` is stamped the first time an `Activity` with `channel in (CALL, EMAIL, WHATSAPP)` is logged against the inquiry, or the first time status leaves `NEW`.
- A Celery Beat job every 30 minutes flags `sla_breached = True` for any `NEW` inquiry older than a configurable threshold (default 4 business hours) and notifies the sales manager role.

### 3.7 Tags / segmentation

```python
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default="#6B7280")  # hex, for admin UI chips

# Inquiry:
tags = models.ManyToManyField("inquiries.Tag", blank=True, related_name="inquiries")
```

- Powers saved filters in the admin pipeline view and, longer-term, targeted re-engagement email lists (e.g. "everyone tagged `budget-sensitive` who closed in the last 90 days" for a seasonal discount campaign).

---

## 4. API Additions

All new endpoints sit under the existing `apps.inquiries` URL namespace (`apps/inquiries/urls.py`) and reuse `IsSalesAgentOrAdmin` from `apps.common.permissions`.

| Method & Path | Purpose |
| :--- | :--- |
| `GET /api/v1/inquiries/<inquiry_number>/timeline/` | Merged, chronological `Activity` + `InquiryNote` feed |
| `POST /api/v1/inquiries/<inquiry_number>/activities/` | Log a call/email/WhatsApp touch (auto-stamps `first_response_at`) |
| `GET/POST /api/v1/inquiries/<inquiry_number>/tasks/` | List/create follow-up tasks |
| `PATCH /api/v1/tasks/<id>/` | Mark task `DONE`/`CANCELLED` |
| `GET /api/v1/crm/customers/<email>/` | Customer-360: all inquiries, bookings, lifetime value for one traveler |
| `GET /api/v1/crm/pipeline-summary/` | Counts per status, per agent, per inquiry_type — powers the kanban + dashboard tiles |
| `GET /api/v1/crm/funnel/?date_from=&date_to=` | Conversion funnel (NEW → conversion rate, avg. days-to-close) |
| `POST /api/v1/inquiries/<inquiry_number>/tags/` | Attach/detach tags |
| `GET /api/v1/tags/` | List tags for filter UI |

Every response keeps the existing `DreamscapeJSONRenderer` envelope (`{success, data, message}`) already used across the API — no new contract shape to learn.

---

## 5. Admin Dashboard (Frontend) Changes

Extends `frontend/src/app/admin/components/admin-dashboard.tsx` and `frontend/src/services/inquiries.service.ts`. No new pages — the existing `/admin` staff portal grows a CRM tab.

1. **Pipeline (Kanban) view** — one column per `InquiryStatus`, drag-to-update-status (fires the existing `PATCH` endpoint), agent avatar + SLA-breach badge on each card. Replaces the flat filtered list as the default view; the list stays available as a "table view" toggle.
2. **Inquiry drawer upgrade** (`InquiryDrawer`, already exists) — add:
   - Timeline tab consuming `GET .../timeline/` (calls, emails, status changes, notes in one feed)
   - "Log activity" quick-action (channel dropdown + optional "follow up in N days" → creates a `Task`)
   - Lost-reason dropdown, required when dragging a card to `CLOSED`
3. **My Tasks panel** — agent's own open tasks due today/this week, with a "Done" checkbox.
4. **Customer 360 modal** — click a traveler's name anywhere in the CRM to see every inquiry + booking they've ever had, opened from `GET /api/v1/crm/customers/<email>/`.
5. **Dashboard analytics tiles** — reuse the existing `DashboardAnalyticsData` pattern already in `admin-dashboard.tsx` (it already renders `RevenueAnalyticsView`); add a CRM section: leads this week, conversion rate, avg. response time, leads by source.

---

## 6. Automation (Celery)

Following the existing pattern in `apps/b2b/tasks.py` and `apps/bookings/tasks.py` (Celery + `config/celery.py` beat schedule):

| Task | Schedule | Action |
| :--- | :--- | :--- |
| `check_sla_breaches` | Every 30 min | Flag stale `NEW` inquiries, notify sales manager |
| `send_task_reminders` | Every 15 min | Push notification/email for `Task`s due within the next hour |
| `auto_assign_new_inquiries` | On `Inquiry` post-save (signal, not beat) | Round-robin assignment across active `SALES_AGENT` users if `assigned_agent` is null — optional, ship behind a `settings.CRM_AUTO_ASSIGN` flag so manual assignment still works during rollout |
| `nightly_customer_rollup` | Daily, 02:00 | Recompute `Customer.lifetime_*` counters as a consistency check against the signal-based updates |

---

## 7. Phased Rollout

Mirrors the phase numbering style already used in [`backend_and_frontend_connection.md`](../backend_and_frontend_connection.md); this slots in as a deepening of its existing **Phase 4**.

| Phase | Scope | Ships independently? |
| :--- | :--- | :--- |
| **4a** | `Customer` model + backfill migration, `Inquiry.customer` FK, `Inquiry.converted_booking` link, `lost_reason` field | Yes — pure data layer, no UI change required |
| **4b** | `Activity` + `Task` models, timeline/activity/task endpoints, Celery reminder jobs | Yes — additive API, old `InquiryNote` flow keeps working |
| **4c** | Admin dashboard: Kanban pipeline, timeline tab, My Tasks panel | Depends on 4a + 4b |
| **4d** | `Tag` model, tagging UI, saved filters | Independent, can ship anytime after 4a |
| **4e** | Customer 360 modal, `crm/customers/<email>/` endpoint | Depends on 4a |
| **4f** | Funnel/conversion analytics tiles, `crm/funnel/` endpoint | Depends on 4a (needs `converted_booking` populated) |
| **4g** | Auto-assignment + SLA breach automation | Optional, ship last, behind a feature flag |

Each phase gets its own migration, so nothing in 4b–4g requires a backfill beyond what 4a already did.

---

## 8. Open Questions Before Implementation

1. **B2B leads**: `InquiryType.PARTNER_DMC` exists but `apps.b2b` already has its own `Partner`/`Booking` models — should `PARTNER_DMC` inquiries eventually link to `b2b.Partner` the same way §3.4 links to `bookings.Booking`? Recommend yes, as a follow-up to Phase 4a using the same pattern.
2. **Auto-assignment fairness**: round-robin by count, or weighted by open-task load? Recommend starting with simple round-robin (§6) and revisiting once agent headcount grows past 2-3.
3. **SLA threshold**: 4 business hours is a placeholder — confirm against actual staffing hours before enabling `check_sla_breaches` in production.
