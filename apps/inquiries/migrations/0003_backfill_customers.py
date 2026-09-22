from django.db import migrations


def backfill_customers(apps, schema_editor):
    """
    Deduplicates existing Inquiry.email (and, where available, Booking
    customer_email) values into Customer rows, links each Inquiry to its
    Customer, and seeds lifetime_inquiries/lifetime_bookings counters.
    """
    Inquiry = apps.get_model("inquiries", "Inquiry")
    Customer = apps.get_model("inquiries", "Customer")
    Booking = apps.get_model("bookings", "Booking")

    customers_by_email = {}

    def get_or_build_customer(email, full_name="", phone="", whatsapp_number=""):
        normalized = email.strip().lower()
        if not normalized:
            return None
        customer = customers_by_email.get(normalized)
        if customer is None:
            customer, _ = Customer.objects.get_or_create(
                email=normalized,
                defaults={
                    "full_name": full_name,
                    "phone": phone,
                    "whatsapp_number": whatsapp_number,
                },
            )
            customers_by_email[normalized] = customer
        return customer

    for inquiry in Inquiry.objects.all().iterator():
        customer = get_or_build_customer(
            inquiry.email,
            full_name=inquiry.full_name,
            phone=inquiry.phone,
            whatsapp_number=inquiry.whatsapp_number,
        )
        if customer and inquiry.customer_id != customer.id:
            inquiry.customer_id = customer.id
            inquiry.save(update_fields=["customer"])

    for booking in Booking.objects.all().iterator():
        get_or_build_customer(
            booking.customer_email,
            full_name=booking.customer_name,
            phone=booking.customer_phone,
        )

    for email, customer in customers_by_email.items():
        customer.lifetime_inquiries = Inquiry.objects.filter(customer_id=customer.id).count()
        customer.lifetime_bookings = Booking.objects.filter(customer_email__iexact=email).count()
        customer.save(update_fields=["lifetime_inquiries", "lifetime_bookings"])


def noop_reverse(apps, schema_editor):
    # Intentionally irreversible in the sense of "un-dedupe" — Customer rows
    # created here are left in place; only the Inquiry.customer links (which
    # the schema migration's reverse already nulls out via field removal)
    # need no extra handling.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inquiries", "0002_tag_inquiry_converted_at_inquiry_converted_booking_and_more"),
        ("bookings", "0004_booking_access_token"),
    ]

    operations = [
        migrations.RunPython(backfill_customers, noop_reverse),
    ]
