from django.db import migrations

# (slug, name, subject, paragraphs, is_system)
TEMPLATES = [
    (
        "inquiry-received",
        "Inquiry received (automatic)",
        "We received your inquiry {{inquiry_number}}",
        [
            "Hi {{full_name}},",
            "Thank you for getting in touch with Dreamscape Treks. We have received your inquiry "
            "(reference {{inquiry_number}}) and one of our trip specialists will contact you soon.",
            "This is an automated message from a no-reply address. You can reply to this email "
            "if you would like to add anything to your inquiry.",
            "Warm regards,\nDreamscape Treks",
        ],
        True,
    ),
    (
        "follow-up",
        "Follow-up",
        "Following up on your inquiry {{inquiry_number}}",
        [
            "Hi {{full_name}},",
            "I am following up on your inquiry about {{trip_title}} (reference {{inquiry_number}}). "
            "Do you have any questions, or would you like us to share dates and a detailed itinerary?",
            "Warm regards,\nDreamscape Treks",
        ],
        False,
    ),
    (
        "itinerary-sent",
        "Itinerary and details",
        "Your {{trip_title}} itinerary",
        [
            "Hi {{full_name}},",
            "Thank you for your interest in {{trip_title}}. Please find the itinerary and trip details below.",
            "Let us know if you would like to adjust anything or hold a departure date.",
            "Warm regards,\nDreamscape Treks",
        ],
        False,
    ),
    (
        "quote",
        "Quote",
        "Your quote for {{trip_title}}",
        [
            "Hi {{full_name}},",
            "Here is the quote for {{trip_title}} (reference {{inquiry_number}}).",
            "Reply to this email to confirm your booking or to ask any questions.",
            "Warm regards,\nDreamscape Treks",
        ],
        False,
    ),
    (
        "payment-reminder",
        "Payment reminder",
        "Payment reminder for {{trip_title}}",
        [
            "Hi {{full_name}},",
            "This is a friendly reminder about the pending payment for {{trip_title}}"
            " departing {{departure_label}} (reference {{inquiry_number}}).",
            "If you have already paid, please ignore this message and reply with the payment details so we can match it.",
            "Warm regards,\nDreamscape Treks",
        ],
        False,
    ),
]


def to_html(paragraphs):
    body = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return f'<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.6;color:#222">{body}</div>'


def seed(apps, schema_editor):
    EmailTemplate = apps.get_model("emails", "EmailTemplate")
    for slug, name, subject, paragraphs, is_system in TEMPLATES:
        EmailTemplate.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "subject": subject,
                "body_html": to_html(paragraphs),
                "body_text": "\n\n".join(paragraphs),
                "is_system": is_system,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("emails", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
