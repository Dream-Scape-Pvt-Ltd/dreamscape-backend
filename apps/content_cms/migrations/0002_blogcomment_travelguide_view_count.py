import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content_cms", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="travelguide",
            name="view_count",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="BlogComment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author_name", models.CharField(max_length=255)),
                ("body", models.TextField()),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("guide", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="content_cms.travelguide")),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="blog_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "blog_comments",
                "ordering": ["created_at", "id"],
                "indexes": [models.Index(fields=["guide", "is_active", "created_at"], name="blog_comment_list_idx")],
            },
        ),
    ]
