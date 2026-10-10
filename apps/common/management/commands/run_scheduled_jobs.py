import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.b2b.tasks import dispatch_pending_partner_emails
from apps.bookings.tasks import expire_waitlist_offers
from apps.inquiries.tasks import (
    advance_travel_statuses,
    check_sla_breaches,
    nightly_customer_rollup,
    send_task_reminders,
)

logger = logging.getLogger(__name__)

# Production has no Celery Beat; a Render cron job runs this every 15 minutes
# instead (see render.yaml). Every job is a sweep that only picks up rows still
# needing work, so running one more often than its Beat schedule is harmless.
FREQUENT_JOBS = [
    dispatch_pending_partner_emails,
    expire_waitlist_offers,
    send_task_reminders,
    check_sla_breaches,
    advance_travel_statuses,
]
DAILY_JOBS = [nightly_customer_rollup]
DAILY_HOUR_UTC = 2


class Command(BaseCommand):
    help = "Runs the Celery Beat jobs once, for hosts without a Beat process."

    def add_arguments(self, parser):
        parser.add_argument("--daily", action="store_true",
                            help=f"Also run the daily jobs (automatic during {DAILY_HOUR_UTC:02d}:00-{DAILY_HOUR_UTC:02d}:14 UTC).")

    def handle(self, *args, **options):
        now = timezone.now()
        jobs = list(FREQUENT_JOBS)
        if options["daily"] or (now.hour == DAILY_HOUR_UTC and now.minute < 15):
            jobs += DAILY_JOBS

        failed = []
        for job in jobs:
            try:
                result = job()
            except Exception:
                # Keep going so one broken job doesn't block the others.
                logger.exception("Scheduled job %s failed", job.name)
                failed.append(job.name)
                continue
            self.stdout.write(f"{job.name}: {result}")

        if failed:
            raise CommandError(f"{len(failed)} job(s) failed: {', '.join(failed)}")
