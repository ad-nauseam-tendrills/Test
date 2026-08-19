"""
Upload validation and safe local file storage helpers.

Files are never stored under their user-supplied name. Every stored file
gets a random UUID-based storage key, which is what's persisted in the
database and used to build URLs -- this avoids path traversal, filename
collisions, and leaking the user's original filesystem structure.
"""
import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def ensure_storage_dirs() -> None:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.VARIANT_DIR, exist_ok=True)


def validate_upload(file: UploadFile, size_bytes: int) -> str:
    """Validate content-type and size; returns the safe file extension."""
    if file.content_type not in settings.ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}. Allowed: {settings.ALLOWED_IMAGE_CONTENT_TYPES}",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    return ALLOWED_EXTENSIONS.get(file.content_type, ".jpg")


def generate_storage_key(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"


def upload_path(storage_key: str) -> str:
    return os.path.join(settings.UPLOAD_DIR, storage_key)


def variant_path(storage_key: str) -> str:
    return os.path.join(settings.VARIANT_DIR, storage_key)
