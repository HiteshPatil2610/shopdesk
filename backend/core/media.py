"""Product images: validate with Pillow, re-encode in memory, store on Cloudinary (spec 03 §6).

Nothing touches local disk (serverless). Tests swap the store with `set_media_store`.
"""

from __future__ import annotations

import io
import uuid
from typing import Literal, Protocol
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

from core.config import get_settings
from core.errors import AppError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000  # refuse decompression bombs
MAX_SIDE = 1024
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

ImageSize = Literal["full", "thumb"]
TRANSFORMS: dict[ImageSize, str] = {
    "full": "c_limit,w_1024,h_1024,f_auto,q_auto",
    "thumb": "c_fill,w_256,h_256,f_auto,q_auto",
}


class MediaStore(Protocol):
    def upload(self, data: bytes, folder: str) -> str: ...
    def delete(self, public_id: str) -> None: ...


def validate_and_encode(raw: bytes, max_mb: int) -> bytes:
    """Check it's really a JPEG/PNG/WebP (by content, not extension), strip EXIF, resize, → WebP."""
    if len(raw) > max_mb * 1024 * 1024:
        raise AppError(f"Image is larger than {max_mb} MB", code="IMAGE_TOO_LARGE", status=413)
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise UnidentifiedImageError(fmt)
        with Image.open(io.BytesIO(raw)) as source:
            oriented: Image.Image = ImageOps.exif_transpose(source)  # honour rotation, drop EXIF
            has_alpha = oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info
            clean = oriented.convert("RGBA" if has_alpha else "RGB")
            clean.thumbnail((MAX_SIDE, MAX_SIDE))
            out = io.BytesIO()
            clean.save(out, format="WEBP", quality=85, method=4)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise AppError(
            "That file isn't a supported image (use JPG, PNG or WebP)",
            code="UNSUPPORTED_IMAGE",
            status=415,
        ) from exc


def cloud_name() -> str | None:
    url = get_settings().cloudinary_url
    return urlsplit(url).hostname if url else None


def image_url(public_id: str | None, size: ImageSize = "full") -> str | None:
    if not public_id:
        return None
    name = cloud_name()
    if not name:
        return None
    return f"https://res.cloudinary.com/{name}/image/upload/{TRANSFORMS[size]}/{public_id}"


class CloudinaryStore:
    def __init__(self, url: str) -> None:
        import cloudinary

        parts = urlsplit(url)
        cloudinary.config(
            cloud_name=parts.hostname,
            api_key=parts.username,
            api_secret=parts.password,
            secure=True,
        )

    def upload(self, data: bytes, folder: str) -> str:
        import cloudinary.uploader

        try:
            result = cloudinary.uploader.upload(
                io.BytesIO(data),
                folder=folder,
                public_id=uuid.uuid4().hex,
                overwrite=False,
                resource_type="image",
            )
        except Exception as exc:
            raise AppError(
                "Couldn't upload the image. Try again.", code="IMAGE_UPLOAD_FAILED", status=502
            ) from exc
        return str(result["public_id"])

    def delete(self, public_id: str) -> None:
        import cloudinary.uploader

        cloudinary.uploader.destroy(public_id, invalidate=True)


_store: MediaStore | None = None


def get_media_store() -> MediaStore:
    global _store
    if _store is None:
        url = get_settings().cloudinary_url
        if not url:
            raise AppError(
                "Image uploads aren't configured (CLOUDINARY_URL)",
                code="MEDIA_NOT_CONFIGURED",
                status=503,
            )
        _store = CloudinaryStore(url)
    return _store


def set_media_store(store: MediaStore | None) -> None:
    global _store
    _store = store


def upload_product_image(raw: bytes) -> str:
    settings = get_settings()
    encoded = validate_and_encode(raw, settings.max_upload_mb)
    return get_media_store().upload(encoded, settings.cloudinary_folder)


def delete_image_quietly(public_id: str | None) -> None:
    """Best-effort cleanup (compensating action); never fails the request."""
    if not public_id:
        return
    try:
        get_media_store().delete(public_id)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("Could not delete image %s", public_id)
