from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("destinations", "0002_destination_base_destination_description_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="destination",
            name="gallery_images",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Additional destination photo URLs, in display order (JSON array).",
            ),
        ),
    ]
