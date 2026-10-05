import io

import pytest
from PIL import Image

from core.errors import AppError
from core.media import TRANSFORMS, validate_and_encode
from tests.conftest import png_bytes


def test_png_is_reencoded_to_webp_and_resized():
    out = validate_and_encode(png_bytes((3000, 1500)), max_mb=4)
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "WEBP"
        assert max(img.size) == 1024


def test_transparency_is_kept():
    out = validate_and_encode(png_bytes(mode="RGBA"), max_mb=4)
    with Image.open(io.BytesIO(out)) as img:
        assert img.mode == "RGBA"


def test_text_file_named_png_is_rejected():
    with pytest.raises(AppError) as exc:
        validate_and_encode(b"hello, I am not an image", max_mb=4)
    assert exc.value.status == 415


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff",
        b'<svg onload="alert(1)"></svg>',
        bytes(range(256)),
    ],
)
def test_malformed_uploads_are_rejected(raw):
    with pytest.raises(AppError) as exc:
        validate_and_encode(raw, max_mb=4)
    assert exc.value.status == 415


def test_embedded_script_tail_is_removed():
    out = validate_and_encode(png_bytes() + b"<script>alert(1)</script>", max_mb=4)
    assert b"<script>" not in out
    with Image.open(io.BytesIO(out)) as image:
        assert image.format == "WEBP"


def test_gif_is_rejected():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "GIF")
    with pytest.raises(AppError) as exc:
        validate_and_encode(buf.getvalue(), max_mb=4)
    assert exc.value.code == "UNSUPPORTED_IMAGE"


def test_too_large_is_413():
    with pytest.raises(AppError) as exc:
        validate_and_encode(b"x" * (2 * 1024 * 1024 + 1), max_mb=2)
    assert exc.value.status == 413


def test_exif_is_stripped():
    buf = io.BytesIO()
    img = Image.new("RGB", (20, 20))
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # Make
    img.save(buf, "JPEG", exif=exif.tobytes())
    out = validate_and_encode(buf.getvalue(), max_mb=4)
    assert b"SecretCam" not in out


def test_transform_strings():
    assert "w_256" in TRANSFORMS["thumb"] and "f_auto" in TRANSFORMS["full"]


@pytest.mark.parametrize(
    ("url", "fragment"),
    [
        (None, "not set"),
        ("https://x", "must look like"),
        ("cloudinary://<your_api_key>:<your_api_secret>@cud8ytoj", "placeholder"),
        ("cloudinary://API_KEY:API_SECRET@cloud", "placeholder"),
    ],
)
def test_cloudinary_url_problems_are_explained(url, fragment):
    from core.media import cloudinary_url_problem

    assert fragment in (cloudinary_url_problem(url) or "")


def test_real_looking_cloudinary_url_is_ok():
    from core.media import cloudinary_url_problem

    assert (
        cloudinary_url_problem("cloudinary://123456789012345:abcdefGHIJKLmnop_qrstuv@cud8ytoj")
        is None
    )
