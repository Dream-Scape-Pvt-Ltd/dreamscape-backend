from django.db import migrations

# The regions and activity types the trek editor offers out of the box.
# get_or_create by slug, so re-running (or an admin having added one already)
# never duplicates a row.
REGIONS = [
    ("nepal", "Nepal", "NEPAL"),
    ("tibet", "Tibet", "TIBET"),
    ("india", "India", "INDIA"),
    ("bhutan", "Bhutan", "BHUTAN"),
]
CATEGORIES = [
    ("trekking", "Trekking", "Multi-day walking journeys on established Himalayan trails."),
    ("mountain-expedition", "Mountain Expedition", "Guided summit climbs and technical high-altitude expeditions."),
]


def seed(apps, schema_editor):
    Destination = apps.get_model("destinations", "Destination")
    ActivityCategory = apps.get_model("destinations", "ActivityCategory")
    for slug, name, country in REGIONS:
        Destination.objects.get_or_create(slug=slug, defaults={"name": name, "country": country})
    for slug, name, description in CATEGORIES:
        if not ActivityCategory.objects.filter(name=name).exists():
            ActivityCategory.objects.get_or_create(slug=slug, defaults={"name": name, "description": description})


class Migration(migrations.Migration):
    dependencies = [
        ("destinations", "0001_initial"),
    ]

    # Seeded rows may already be referenced by treks, so reversing leaves them.
    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
