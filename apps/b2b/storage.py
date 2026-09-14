from django.conf import settings
import os
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateAssetStorage(FileSystemStorage):
    """Local assets live outside public media and never expose a storage URL."""

    @property
    def base_location(self):
        return settings.B2B_PRIVATE_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private assets must be downloaded through the B2B API.")
