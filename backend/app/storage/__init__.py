"""Compatibility wrapper around the storage integration layer."""

from typing import Optional

from app.integrations.storage import get_storage_backend


def save_upload(scope_id: str, original_filename: str, tmp_path: str) -> tuple[str, str]:
    return get_storage_backend().save_upload(scope_id, original_filename, tmp_path)


def get_file_path(scope_id: str, storage_key: str) -> Optional[str]:
    return get_storage_backend().get_file_path(scope_id, storage_key)


def delete_file(scope_id: str, storage_key: str) -> bool:
    return get_storage_backend().delete_file(scope_id, storage_key)
