from django.db import migrations


def assigned_back_to_new(apps, schema_editor):
    """The Assigned stage was retired with agent routing; those leads are simply New again."""
    Inquiry = apps.get_model("inquiries", "Inquiry")
    Inquiry.objects.filter(status="ASSIGNED").update(status="NEW")


class Migration(migrations.Migration):
    dependencies = [
        ("inquiries", "0006_inquiry_completed_at_revenue_entry"),
    ]

    operations = [
        # Not reversible: which leads were Assigned before is not recorded.
        migrations.RunPython(assigned_back_to_new, migrations.RunPython.noop),
    ]
