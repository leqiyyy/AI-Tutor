import shutil
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.integrations.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    def _base_dir(self, scope_id: str) -> Path:
        base = settings.LOCAL_STORAGE_ROOT / scope_id
        base.mkdir(parents=True, exist_ok=True)
        return base

    def save_upload(self, scope_id: str, original_filename: str, tmp_path: str) -> tuple[str, str]:
        ext = Path(original_filename).suffix
        storage_key = f"{uuid.uuid4().hex}{ext}"
        destination = self._base_dir(scope_id) / storage_key
        shutil.copy2(tmp_path, destination)
        return storage_key, str(destination)

    def get_file_path(self, scope_id: str, storage_key: str) -> Optional[str]:
        path = self._base_dir(scope_id) / storage_key
        return str(path) if path.exists() else None

    def delete_file(self, scope_id: str, storage_key: str) -> bool:
        path = self._base_dir(scope_id) / storage_key
        if not path.exists():
            return False
        path.unlink()
        return True

    def healthcheck(self) -> dict:
        root = settings.LOCAL_STORAGE_ROOT
        try:
            root.mkdir(parents=True, exist_ok=True)
            return {"ok": True, "backend": "local", "detail": str(root.resolve())}
        except Exception as exc:  # pragma: no cover - defensive health path
            return {"ok": False, "backend": "local", "detail": str(exc)}
