from django.conf import settings
import os
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property

# Bucket prefix for partner files. apps.common.media only redirects media/ and
# site/ keys, so nothing under this prefix is reachable through /media/.
B2_PRIVATE_PREFIX = "b2b-private"


@deconstructible
class PrivateAssetStorage(Storage):
    """
    Partner files: the private prefix of the B2 bucket when USE_B2 is on (the
    instance disk is wiped on every deploy), otherwise B2B_PRIVATE_ROOT on disk.
    Never exposes a URL; files are streamed by the B2B download view.
    """

    @property
    def backend(self):
        if settings.USE_B2:
            return self._b2_backend
        # Rebuilt on each access (cheap) so the root follows settings, e.g. in tests.
        return FileSystemStorage(location=os.path.abspath(settings.B2B_PRIVATE_ROOT))

    @cached_property
    def _b2_backend(self):
        from storages.backends.s3 import S3Storage

        return S3Storage(**{**settings.STORAGES["default"]["OPTIONS"], "location": B2_PRIVATE_PREFIX})

    def _open(self, name, mode="rb"):
        return self.backend._open(name, mode)

    def _save(self, name, content):
        return self.backend._save(name, content)

    def get_available_name(self, name, max_length=None):
        return self.backend.get_available_name(name, max_length=max_length)

    def delete(self, name):
        return self.backend.delete(name)

    def exists(self, name):
        return self.backend.exists(name)

    def listdir(self, path):
        return self.backend.listdir(path)

    def size(self, name):
        return self.backend.size(name)

    def path(self, name):
        return self.backend.path(name)

    def url(self, name):
        raise ValueError("Private assets must be downloaded through the B2B API.")
