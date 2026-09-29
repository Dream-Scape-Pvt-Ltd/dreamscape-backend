"""
Copies existing images into the Backblaze B2 bucket and fixes stored image URLs.

    python manage.py migrate_media_to_b2            # dry run: report only
    python manage.py migrate_media_to_b2 --apply

1. Every MediaAsset file on local disk (MEDIA_ROOT) is uploaded under the same
   key, so its /media/<key> URL keeps working through the redirect view.
2. Frontend content photos (public/images/{treks,blog,team,trek-memories}) are
   uploaded as site/<folder>/<file>; the frontend rewrites /images/<folder>/…
   to the backend's /media/site/<folder>/….
3. Image URLs saved against localhost are re-pointed at MEDIA_PUBLIC_BASE_URL.

Safe to re-run: files already in the bucket are skipped.
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.common.models import MediaAsset
from apps.content_cms.models import SiteSettings, TravelGuide, TrekGuide
from apps.destinations.models import Destination, NavigationMenu
from apps.trips.models import Trip

SITE_FOLDERS = ("treks", "blog", "team", "trek-memories")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
LOCAL_MEDIA = re.compile(r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?(?=/media/)")
IMAGE_FIELDS = (
    (Trip, ("hero_image_url", "gallery_images")),
    (TravelGuide, ("hero_image_url", "gallery_images", "sections", "markdown_content")),
    (TrekGuide, ("photo_url",)),
    (Destination, ("hero_media",)),
    (NavigationMenu, ("image",)),
    (SiteSettings, ("content",)),
)


def rewrite(value, base):
    if isinstance(value, str):
        return LOCAL_MEDIA.sub(base, value)
    if isinstance(value, list):
        return [rewrite(v, base) for v in value]
    if isinstance(value, dict):
        return {k: rewrite(v, base) for k, v in value.items()}
    return value


class Command(BaseCommand):
    help = "Upload existing media and frontend content photos to B2 and fix localhost image URLs."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually upload and save. Without it, only report.")
        parser.add_argument(
            "--frontend-public",
            default=str(Path(settings.BASE_DIR).parent / "frontend" / "public" / "images"),
            help="Folder holding treks/, blog/, team/ and trek-memories/.",
        )
        parser.add_argument("--skip-site-upload", action="store_true", help="Don't upload frontend content photos.")

    def handle(self, *args, apply, frontend_public, skip_site_upload, **options):
        if not settings.USE_B2:
            raise CommandError("USE_B2 is off, so default storage is not the B2 bucket.")
        self.apply = apply
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run: nothing will be uploaded or saved. Pass --apply to run."))

        self.upload_media_assets()
        if not skip_site_upload:
            self.upload_site_images(Path(frontend_public))
        self.rewrite_urls()

    def copy(self, source, key):
        if default_storage.exists(key):
            return "exists"
        if self.apply:
            with source.open("rb") as fh:
                saved = default_storage.save(key, fh)
            if saved != key:
                raise CommandError(f"Storage renamed {key} to {saved}.")
        return "uploaded"

    def upload_media_assets(self):
        local = FileSystemStorage(location=settings.MEDIA_ROOT)
        counts, missing = {"uploaded": 0, "exists": 0}, []
        for name in MediaAsset.objects.values_list("file", flat=True):
            if not local.exists(name):
                missing.append(name)
                continue
            counts[self.copy(Path(local.path(name)), name)] += 1
        self.stdout.write(f"Media assets: {counts['uploaded']} to upload/uploaded, {counts['exists']} already in B2.")
        for name in missing:
            self.stdout.write(self.style.WARNING(f"  missing on local disk: {name}"))

    def upload_site_images(self, root):
        if not root.is_dir():
            raise CommandError(f"Frontend images folder not found: {root}")
        counts = {"uploaded": 0, "exists": 0}
        for folder in SITE_FOLDERS:
            for path in sorted((root / folder).glob("*")):
                if path.suffix.lower() in IMAGE_SUFFIXES:
                    counts[self.copy(path, f"site/{folder}/{path.name}")] += 1
        self.stdout.write(f"Site photos: {counts['uploaded']} to upload/uploaded, {counts['exists']} already in B2.")

    def rewrite_urls(self):
        base, changed = settings.MEDIA_PUBLIC_BASE_URL, 0
        with transaction.atomic():
            for model, fields in IMAGE_FIELDS:
                for obj in model.objects.all():
                    dirty = [f for f in fields if rewrite(getattr(obj, f), base) != getattr(obj, f)]
                    if not dirty:
                        continue
                    changed += 1
                    self.stdout.write(f"  {model.__name__} {obj.pk}: {', '.join(dirty)}")
                    if self.apply:
                        for f in dirty:
                            setattr(obj, f, rewrite(getattr(obj, f), base))
                        obj.save(update_fields=dirty)
        self.stdout.write(f"Records with localhost image URLs re-pointed at {base}: {changed}.")
