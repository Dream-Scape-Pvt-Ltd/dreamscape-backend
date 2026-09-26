"""
Replace the six trip grades with four difficulty levels: Easy, Normal,
Difficult and Extreme.

Existing trips are moved to the nearest level before the field's choices
change. Going back maps each level to one representative old grade, so a
reverse migration keeps every trip valid but cannot restore the finer grade.
"""
from django.db import migrations, models

FORWARD = {
    "GRADE_1": "EASY",
    "GRADE_2": "NORMAL",
    "GRADE_3": "DIFFICULT",
    "GRADE_4": "DIFFICULT",
    "GRADE_5": "EXTREME",
    "ALPINE": "EXTREME",
}
BACKWARD = {"EASY": "GRADE_1", "NORMAL": "GRADE_2", "DIFFICULT": "GRADE_4", "EXTREME": "GRADE_5"}


def remap(mapping):
    def run(apps, schema_editor):
        Trip = apps.get_model("trips", "Trip")
        for old, new in mapping.items():
            Trip.objects.filter(difficulty_grade=old).update(difficulty_grade=new)
    return run


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0004_departure_seat_ledger"),
    ]

    operations = [
        migrations.RunPython(remap(FORWARD), remap(BACKWARD)),
        migrations.AlterField(
            model_name="trip",
            name="difficulty_grade",
            field=models.CharField(
                choices=[("EASY", "Easy"), ("NORMAL", "Normal"), ("DIFFICULT", "Difficult"), ("EXTREME", "Extreme")],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
