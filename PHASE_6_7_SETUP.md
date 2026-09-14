# Phases 6 and 7: partner portal, content and search

The APIs are implemented and covered by PostgreSQL tests. External services are not started by migrations or test runs.

## Database and configuration

Run `python manage.py migrate` before serving the new B2B endpoints. Migration `b2b.0003` adds the durable partner email outbox and switches assets to private storage.

Configure the values documented in `.env.example`:

- `CELERY_BROKER_URL`: Redis broker, shared by web, worker and Beat.
- `RESEND_API_KEY` and `DEFAULT_FROM_EMAIL`: Resend credentials and a sender on a verified domain.
- `B2B_ADMIN_EMAIL`: optional recipient for new agency application alerts.
- `B2B_PRIVATE_ROOT`: private filesystem root; defaults to `backend/private_media`.
- `B2B_DOWNLOAD_TTL`: signed download lifetime, default 300 seconds.
- `PUBLIC_SITE_URL`: frontend origin used in guide structured data.

Use a private storage volume shared by web instances. Do not map this directory to a public media URL. Existing asset records retain their relative file names, but the migration does **not** move existing files: copy any existing `b2b_assets/` directory from the old media root into `B2B_PRIVATE_ROOT` before enabling downloads, verify the private copies, and remove public access to the old files. Keep backups during the storage transition.

## Background emails

Run Redis and these processes separately:

```text
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

For local Windows development, use `celery -A config worker --pool=solo --loglevel=info`.

Registration and approval create immutable email payloads in an outbox inside the database transaction. Publishing to Celery happens after commit. Beat scans pending messages every five seconds, providing recovery when broker publishing fails. Failed provider requests back off up to one hour. Successful messages are skipped on redelivery; Resend requests also carry a stable idempotency key. Resend's provider-side idempotency window is 24 hours, so an ambiguous delivery retried after that window can still duplicate an email. Monitor worker logs and unsent `PartnerEmail` records.

The provider integration follows [Resend's send-email API](https://resend.com/docs/api-reference/emails/send-email) and [idempotency rules](https://resend.com/docs/dashboard/emails/idempotency-keys). Automated tests mock Resend and broker publishing; no real email is sent during verification.

## Partner portal behavior

- Registration requires `password_confirm`, normalizes email, creates a B2B user and a pending BRONZE profile atomically.
- Pending partners can GET/PATCH their own `/api/v1/b2b/partners/me/` profile. They cannot change approval, commission or tier.
- Only admins list applications, approve accounts, or update commission status.
- Approved partners see their own attributed booking ledger; admins see all ledgers. Commission changes lock the ledger row and maintain invoice/payment timestamps.
- Asset listings include only active assets available to the current tier, with no raw storage URL. Admins can access all active tiers.
- `/assets/{id}/download/` returns an expiring URL for `/assets/{id}/file/?token=...`. Fetch that URL with the same JWT Authorization header. The token is bound to the user, asset and file name; approval, tier and active status are checked again when serving bytes. The binary response is an attachment with `Cache-Control: private, no-store`.

The default is an authenticated signed **API download**, not a production CDN link. CDN hosting/signing remains the separate integration milestone in the plan. The frontend can fetch the file with its JWT and download the resulting blob. Do not expose the private filesystem to implement a CDN shortcut.

## Content, FAQs and search

- Public guide and initiative reads exclude drafts. Admins can preview drafts and create content.
- Guide create/update returns full detail, including Article and BreadcrumbList JSON-LD. First publication sets `published_at`; unpublishing and republishing preserve it. Guide DELETE unpublishes rather than deleting the row.
- FAQ GET accepts `trip` and `destination` slugs and `category`. Its response contains `faqs` and `schema_org` (FAQPage). Inactive FAQs and FAQs belonging to inactive trips/destinations are hidden publicly. FAQ DELETE sets `is_active=False`.
- `/api/v1/search/?q=everest` searches active trips/destinations, published guides and public FAQs, even for admin callers. It supports `entity_type`, `page`, and `page_size` (maximum 100), returns type-specific `meta`, and rejects queries shorter than two characters.
- Search uses query-time weighted PostgreSQL full-text vectors and a database UNION for global ranking and pagination. It does not load all matches into Python. GIN indexing remains the separately planned search scaling milestone.
- List endpoints use the existing pagination/envelope format; FAQ GET uses its documented FAQPage collection format. File bytes are the intentional exception to JSON envelopes.

## Verification

```text
python manage.py test apps.b2b apps.content_cms apps.faq apps.search --noinput
python manage.py test --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --file schema.yaml
```

The new tests cover access control, registration rollback, tier checks, token expiry/tampering, ledger isolation, publication lifecycle, search ranking/pagination, and email retry behavior. Existing debug endpoint schema errors and the undiscovered/broken `apps.common.tests.test_databaseplan` module predate this work; neither is claimed fixed by phases 6–7. Earlier booking/payment issues are also outside this implementation.
