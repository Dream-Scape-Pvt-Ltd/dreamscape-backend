import uuid
from django.db import migrations, models


def gen_uuid(apps, schema_editor):
    Booking = apps.get_model('bookings', 'Booking')
    for row in Booking.objects.all():
        row.access_token = uuid.uuid4()
        row.save(update_fields=['access_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0003_booking_cancellation_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='access_token',
            field=models.UUIDField(null=True, editable=False, db_index=True),
        ),
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='booking',
            name='access_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True),
        ),
    ]
