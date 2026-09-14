"""Cheap image quality gate run before analysis.

Rejects files that are the wrong type, too small, or unreadable. If Pillow is
installed it also checks pixel dimensions and a rough exposure/contrast heuristic.
Without Pillow it degrades to header checks only.
"""

from __future__ import annotations

import io

from app.config import get_settings

try:  # Pillow is optional
    from PIL import Image, ImageStat

    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False

_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # loose; refined below
}


def sniff_content_type(data: bytes) -> str | None:
    for magic, ctype in _MAGIC.items():
        if data.startswith(magic):
            if ctype == "image/webp" and data[8:12] != b"WEBP":
                continue
            return ctype
    return None


def run_quality_check(data: bytes, declared_content_type: str) -> tuple[bool, dict]:
    """Return ``(passed, report)``. ``report`` is stored on SkinImage.quality_report."""
    settings = get_settings()
    report: dict = {"checks": {}, "warnings": []}

    sniffed = sniff_content_type(data)
    report["checks"]["magic_matches_declared"] = sniffed == declared_content_type
    report["sniffed_content_type"] = sniffed

    if sniffed not in settings.allowed_image_types:
        report["reason"] = f"unsupported image type: {sniffed}"
        return False, report

    if len(data) > settings.max_upload_bytes:
        report["reason"] = "file too large"
        return False, report

    if not _HAS_PIL:
        report["warnings"].append("Pillow not installed; skipped pixel-level checks")
        report["passed"] = True
        return True, report

    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))  # reopen; verify() leaves it unusable
    except Exception as exc:  # noqa: BLE001
        report["reason"] = f"unreadable image: {exc}"
        return False, report

    w, h = img.size
    report["width"], report["height"] = w, h
    report["checks"]["min_dimension"] = min(w, h) >= settings.min_image_dimension_px
    if not report["checks"]["min_dimension"]:
        report["reason"] = f"image smaller than {settings.min_image_dimension_px}px"
        return False, report

    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    mean, stddev = stat.mean[0], stat.stddev[0]
    report["exposure_mean"] = round(mean, 1)
    report["contrast_stddev"] = round(stddev, 1)
    if mean < 40:
        report["warnings"].append("image looks underexposed (too dark)")
    elif mean > 220:
        report["warnings"].append("image looks overexposed (washed out)")
    if stddev < 12:
        report["warnings"].append("very low contrast — possibly blurry or out of focus")

    report["passed"] = True
    return True, report
