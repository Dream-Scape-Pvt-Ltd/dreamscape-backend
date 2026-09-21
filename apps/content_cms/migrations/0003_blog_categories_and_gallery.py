from django.db import migrations, models


def simplify_categories(apps, schema_editor):
    TravelGuide = apps.get_model("content_cms", "TravelGuide")
    mapping = {
        "VISAS": "TRAVEL_TIPS",
        "PERMITS": "TRAVEL_TIPS",
        "ALTITUDE": "TRAVEL_TIPS",
        "BEST_TIME": "TRAVEL_TIPS",
    }
    for old, new in mapping.items():
        TravelGuide.objects.filter(category=old).update(category=new)


class Migration(migrations.Migration):
    dependencies = [("content_cms", "0002_blogcomment_travelguide_view_count")]

    operations = [
        migrations.AddField(
            model_name="travelguide",
            name="gallery_images",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(simplify_categories, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="travelguide",
            name="category",
            field=models.CharField(
                choices=[
                    ("ADVENTURE", "Adventure"),
                    ("TRAVEL_TIPS", "Travel Tips"),
                    ("CULTURE", "Culture"),
                    ("NATURE", "Nature"),
                    ("FOOD", "Food"),
                    ("OTHER", "Other"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
