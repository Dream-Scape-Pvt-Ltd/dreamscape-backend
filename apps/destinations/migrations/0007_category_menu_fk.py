import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Swap the old TREKS/TOURS/CLIMBING code for the menu link filled in by 0006."""

    dependencies = [
        ("destinations", "0006_seed_navigation_menus"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="activitycategory", name="category_menu_name_unique"),
        migrations.RemoveField(model_name="activitycategory", name="menu"),
        migrations.RenameField(model_name="activitycategory", old_name="nav_menu", new_name="menu"),
        migrations.AlterField(
            model_name="activitycategory",
            name="menu",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="categories", to="destinations.navigationmenu"),
        ),
        migrations.AlterModelOptions(
            name="activitycategory",
            options={"ordering": ["menu__sort_order", "sort_order", "name"], "verbose_name_plural": "Activity Categories"},
        ),
        migrations.AddConstraint(
            model_name="activitycategory",
            constraint=models.UniqueConstraint(fields=("menu", "name"), name="category_menu_name_unique"),
        ),
    ]
