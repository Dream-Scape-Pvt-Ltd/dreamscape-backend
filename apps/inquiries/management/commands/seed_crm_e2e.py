"""
Creates the two staff accounts the Playwright CRM suite logs in with.

    python manage.py seed_crm_e2e --password "<something long>"

Idempotent: re-running resets the passwords and roles. Refuses to run unless
DEBUG is on, so it can never plant known-password staff on production.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserRole

E2E_USERS = (
    ("e2e-admin@dreamscape.test", UserRole.ADMIN, "E2E", "Admin"),
    ("e2e-agent@dreamscape.test", UserRole.SALES_AGENT, "E2E", "Agent"),
)


class Command(BaseCommand):
    help = "Create or reset the staff accounts used by the Playwright CRM tests (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Password for both e2e accounts (min 12 chars).")

    def handle(self, *args, password, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to seed e2e staff accounts with DEBUG off.")
        if len(password) < 12:
            raise CommandError("Use a password of at least 12 characters.")

        User = get_user_model()
        for email, role, first_name, last_name in E2E_USERS:
            user, created = User.objects.get_or_create(email=email, defaults={"role": role})
            user.role = role
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.is_staff = role == UserRole.ADMIN
            user.set_password(password)
            user.save()
            self.stdout.write(f"{'Created' if created else 'Reset'} {role} {email}")
