from app.core.config import settings
from app.integrations.storage.base import StorageBackend
from app.integrations.storage.local import LocalStorageBackend
from app.integrations.storage.minio import MinioStorageBackend

_storage_backend = None


def get_storage_backend() -> StorageBackend:
    global _storage_backend
    if _storage_backend is None:
        if settings.STORAGE_BACKEND == "minio":
            _storage_backend = MinioStorageBackend()
        else:
            _storage_backend = LocalStorageBackend()
    return _storage_backend
