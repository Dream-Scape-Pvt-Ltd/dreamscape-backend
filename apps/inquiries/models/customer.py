from django.conf import settings
from django.db import models
from apps.common.models.base import TimeStampedModel


class Customer(TimeStampedModel):
    """
    Deduplicated traveler identity, keyed on email, joining every inquiry and
    booking made by the same person. Backs the CRM customer-360 view and
    lifetime-value tracking.
    """

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    whatsapp_number = models.CharField(max_length=50, blank=True)
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_profile",
    )
    lifetime_inquiries = models.PositiveIntegerField(default=0)
    lifetime_bookings = models.PositiveIntegerField(default=0)
    lifetime_value_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "crm_customers"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name or self.email} ({self.email})"

    @classmethod
    def get_or_create_from_contact(cls, *, email, full_name="", phone="", whatsapp_number=""):
        """
        Looks up (or creates) the Customer for an inbound email address,
        backfilling any contact fields that were still blank. Email is
        normalized to lowercase so 'Foo@x.com' and 'foo@x.com' dedupe to
        the same record.
        """
        normalized_email = email.strip().lower()
        customer, created = cls.objects.get_or_create(
            email=normalized_email,
            defaults={
                "full_name": full_name,
                "phone": phone,
                "whatsapp_number": whatsapp_number,
            },
        )
        if not created:
            update_fields = []
            if full_name and not customer.full_name:
                customer.full_name = full_name
                update_fields.append("full_name")
            if phone and not customer.phone:
                customer.phone = phone
                update_fields.append("phone")
            if whatsapp_number and not customer.whatsapp_number:
                customer.whatsapp_number = whatsapp_number
                update_fields.append("whatsapp_number")
            if update_fields:
                customer.save(update_fields=update_fields + ["updated_at"])
        return customer
