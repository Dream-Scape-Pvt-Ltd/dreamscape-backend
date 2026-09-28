from django.db import migrations


SANTA_BIO = """Santa Bahadur Tama is a government-licensed trekking guide with experience leading groups across a wide range of trekking regions in Nepal.

He completed his trekking guide training at the Nepal Academy of Tourism and Hotel Management (NATHM) and has led treks in the Annapurna, Langtang, Everest, Kanchenjunga, Manaslu and Mustang regions. His work across these areas has given him practical experience with different terrain, communities and trekking conditions.

Santa has also completed a first aid course with the Kathmandu Environmental Education Project (KEEP), adding an important element of safety preparation to his professional training.

As a guide, he accompanies travellers throughout their trek, providing practical support and helping them better understand the places and communities they encounter along the way."""


def place_santa_in_guides(apps, schema_editor):
    TrekGuide = apps.get_model('content_cms', 'TrekGuide')
    SiteSettings = apps.get_model('content_cms', 'SiteSettings')

    # Preserve any existing guide photo or edited biography.
    guide = TrekGuide.objects.filter(slug__in=['santa-bahadur-tama', 'santa-bahadur-tamang']).first()
    if guide is None:
        TrekGuide.objects.create(
            slug='santa-bahadur-tama', name='Santa Bahadur Tama',
            role='Trekking Guide', photo_url='', bio=SANTA_BIO,
            certifications=['NATHM trekking guide training', 'KEEP first aid course'],
            is_published=True,
        )
    else:
        guide.name = 'Santa Bahadur Tama'
        guide.role = 'Trekking Guide'
        guide.is_published = True
        guide.save(update_fields=['name', 'role', 'is_published', 'updated_at'])

    for settings in SiteSettings.objects.all():
        content = settings.company_content
        if not isinstance(content, dict) or not isinstance(content.get('team_profiles'), list):
            continue
        profiles = []
        for profile in content['team_profiles']:
            if not isinstance(profile, dict):
                continue
            name = profile.get('name', '')
            if name.startswith('Santa Bahadur'):
                continue
            if name == 'Amar Jung Lama':
                profile.setdefault('image', '/images/team/amar-jung-lama.png')
            elif name in ['Saput Man Tama', 'Saput Man Tamang']:
                profile['name'] = 'Saput Man Tama'
                profile.setdefault('image', '/images/team/saput-man-tama.png')
            profiles.append(profile)
        content['team_profiles'] = profiles
        settings.company_content = content
        settings.save(update_fields=['company_content', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [('content_cms', '0012_trekguide')]
    operations = [migrations.RunPython(place_santa_in_guides, migrations.RunPython.noop)]
