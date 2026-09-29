import json
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.content_cms.models import TravelGuide
from apps.destinations.models import Destination


class Command(BaseCommand):
    help = "Import the existing Dreamscape photo stories and regions without overwriting CMS edits."

    def add_arguments(self, parser):
        parser.add_argument('--asset-base-url', required=True, help='Public frontend origin serving /images, e.g. https://your-domain.com')
        parser.add_argument('--publish', action='store_true', help='Publish imported stories; otherwise create drafts.')

    @transaction.atomic
    def handle(self, *args, **options):
        origin = options['asset_base_url'].rstrip('/')
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise CommandError('Supply an http(s) origin without a path, query or fragment.')
        data = json.loads((Path(__file__).resolve().parents[2] / 'seed_data' / 'website.json').read_text(encoding='utf-8'))
        count = 0
        for row in data['destinations']:
            row['hero_media'] = origin + row['hero_media']
            _, created = Destination.objects.get_or_create(slug=row.pop('slug'), defaults=row)
            count += created
        for row in data['stories']:
            row['hero_image_url'] = origin + row['hero_image_url']
            row['gallery_images'] = [origin + path for path in row['gallery_images']]
            row['is_published'] = options['publish']
            _, created = TravelGuide.objects.get_or_create(slug=row.pop('slug'), defaults=row)
            count += created
        self.stdout.write(self.style.SUCCESS(f'Created {count} records. Existing CMS records were preserved.'))
