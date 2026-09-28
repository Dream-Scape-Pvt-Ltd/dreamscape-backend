from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('content_cms', '0007_sitesettings_beyond_description_and_more')]
    operations = [
        migrations.AddField(model_name='sitesettings', name='home_filter_destinations', field=models.TextField(default='|Anywhere\nnepal|Nepal\nbeyond-nepal|Beyond Nepal')),
        migrations.AddField(model_name='sitesettings', name='home_filter_difficulties', field=models.TextField(default='|Any difficulty\neasy|Easy\nmoderate|Moderate\nchallenging|Challenging')),
        migrations.AddField(model_name='sitesettings', name='home_filter_budgets', field=models.TextField(default='|Any budget\nunder-1500|Under $1,500\n1500-2500|$1,500 – $2,500\nover-2500|Above $2,500')),
    ]
