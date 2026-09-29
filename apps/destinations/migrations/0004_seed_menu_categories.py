from django.db import migrations

# The header's Treks / Tours / Climbing sub-items as they were hard-coded in the
# frontend, so the menus look the same after the switch. get_or_create by slug:
# re-running never duplicates, and admin edits are never overwritten.
MENU_ITEMS = [
    ("TREKS", "everest", "Everest Region", "Khumbu trails, lakes & high passes"),
    ("TREKS", "langtang", "Langtang Region", "Valley walks & mountain villages"),
    ("TREKS", "annapurna", "Annapurna Region", "Classic circuits & glacial lakes"),
    ("TREKS", "manaslu", "Manaslu Region", "Remote trails & the Tsum Valley"),
    ("TREKS", "mustang", "Mustang Region", "Red cliffs & ancient kingdoms"),
    ("TREKS", "off-the-beaten-path", "Off the Beaten Path", "Dolpo, Kanchenjunga & quieter trails"),
    ("TOURS", "wildlife-tours", "Wildlife Tours", "Forests, wildlife & jungle stays"),
    ("TOURS", "luxury-tours", "Luxury Tours", "Thoughtful journeys with extra comfort"),
    ("TOURS", "culture-sightseeing", "Culture & Sightseeing", "Heritage, local life & living traditions"),
    ("TOURS", "day-tours", "Day Tours", "A different perspective in a single day"),
    ("TOURS", "heli-tours", "Heli Tours", "The Himalaya from above"),
    ("CLIMBING", "everest-climbing", "Everest Region", "Khumbu trails, lakes & high passes"),
    ("CLIMBING", "annapurna-climbing", "Annapurna Region", "Classic circuits & glacial lakes"),
]


def seed(apps, schema_editor):
    ActivityCategory = apps.get_model("destinations", "ActivityCategory")
    for order, (menu, slug, name, description) in enumerate(MENU_ITEMS):
        if ActivityCategory.objects.filter(menu=menu, name=name).exists():
            continue
        ActivityCategory.objects.get_or_create(
            slug=slug,
            defaults={"menu": menu, "name": name, "description": description, "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("destinations", "0003_category_menu"),
    ]

    # Seeded rows may already be referenced by treks, so reversing leaves them.
    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
