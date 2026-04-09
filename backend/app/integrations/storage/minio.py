from typing import Optional

from app.core.config import settings
from app.integrations.storage.base import StorageBackend

try:  # pragma: no cover - optional dependency handling
    from minio import Minio
except ImportError:  # pragma: no cover
    Minio = None


class MinioStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._client = None

    def _client_or_raise(self):
        if Minio is None:
            raise RuntimeError("minio_package_not_installed")
        if self._client is None:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        return self._client

    def _ensure_bucket(self) -> None:
        client = self._client_or_raise()
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)

    def save_upload(self, scope_id: str, original_filename: str, tmp_path: str) -> tuple[str, str]:
        from pathlib import Path
        import uuid

        self._ensure_bucket()
        ext = Path(original_filename).suffix
        storage_key = f"{scope_id}/{uuid.uuid4().hex}{ext}"
        client = self._client_or_raise()
        client.fput_object(settings.MINIO_BUCKET, storage_key, tmp_path)
        return storage_key, storage_key

    def get_file_path(self, scope_id: str, storage_key: str) -> Optional[str]:
        return None

    def delete_file(self, scope_id: str, storage_key: str) -> bool:
        client = self._client_or_raise()
        client.remove_object(settings.MINIO_BUCKET, storage_key)
        return True

    def healthcheck(self) -> dict:
        try:
            self._ensure_bucket()
            return {
                "ok": True,
                "backend": "minio",
                "detail": f"{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}",
            }
        except Exception as exc:  # pragma: no cover - defensive health path
            return {"ok": False, "backend": "minio", "detail": str(exc)}
