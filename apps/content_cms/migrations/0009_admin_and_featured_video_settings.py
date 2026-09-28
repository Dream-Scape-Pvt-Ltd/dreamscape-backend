from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content_cms", "0008_site_settings_home_finder_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="admin_login_image",
            field=models.CharField(default="/images/admin-login-background.png", max_length=500),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="featured_video_title",
            field=models.CharField(default="A journey through Nepal", max_length=180),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="featured_video_description",
            field=models.CharField(default="Mountain trails, village encounters and the quiet moments that stay with you. A glimpse of journeys with Dreamscape Treks.", max_length=500),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="featured_video_thumbnail",
            field=models.CharField(default="/images/trek-memories/home-slide-3.jpg", max_length=500),
        ),
    ]
