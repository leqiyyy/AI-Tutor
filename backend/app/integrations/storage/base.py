from abc import ABC, abstractmethod
from typing import Optional


class StorageBackend(ABC):
    @abstractmethod
    def save_upload(self, scope_id: str, original_filename: str, tmp_path: str) -> tuple[str, str]:
        """Persist an uploaded file and return (storage_key, public_ref)."""

    @abstractmethod
    def get_file_path(self, scope_id: str, storage_key: str) -> Optional[str]:
        """Return a local path when one exists."""

    @abstractmethod
    def delete_file(self, scope_id: str, storage_key: str) -> bool:
        """Delete a stored file when possible."""

    @abstractmethod
    def healthcheck(self) -> dict:
        """Return backend health details."""
