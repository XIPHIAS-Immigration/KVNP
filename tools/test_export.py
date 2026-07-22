"""Regression tests for the photo export and identity-preserving upscale path.

Run:  python tools/test_export.py
"""
import io
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PASS = "  ok"


def sample_photo(width=80, height=100):
    image = np.full((height, width, 3), (238, 240, 242), np.uint8)
    cv2.ellipse(image, (width // 2, height // 2), (20, 32), 0, 0, 360, (80, 130, 190), -1)
    return image


def test_jpeg_dimensions_and_dpi():
    binary, meta = server.encode_photo_export(sample_photo(), {"format": "jpeg", "dpi": 600, "quality": 90})
    decoded = cv2.imdecode(np.frombuffer(binary, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (100, 80)
    assert meta["mime"] == "image/jpeg" and meta["dpi"] == 600
    assert binary[13] == 1 and int.from_bytes(binary[14:16], "big") == 600
    print("test_jpeg_dimensions_and_dpi", PASS)


def test_png_2x_upscale():
    binary, meta = server.encode_photo_export(sample_photo(), {"format": "png", "scale": 2})
    decoded = cv2.imdecode(np.frombuffer(binary, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (200, 160)
    assert meta["scale"] == 2 and meta["upscaleEngine"] in {"FSRCNN 2x", "Lanczos 2x fallback"}
    print("test_png_2x_upscale", PASS)


def test_webp_export():
    binary, meta = server.encode_photo_export(sample_photo(), {"format": "webp", "quality": 88})
    decoded = Image.open(io.BytesIO(binary))
    assert decoded.size == (80, 100)
    assert meta["mime"] == "image/webp"
    print("test_webp_export", PASS)


def test_pdf_physical_page_size():
    binary, meta = server.encode_photo_export(sample_photo(), {"format": "pdf", "dpi": 300})
    assert binary.startswith(b"%PDF-") and meta["mime"] == "application/pdf"
    match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", binary)
    assert match, "PDF has no MediaBox"
    width_pt, height_pt = map(float, match.groups())
    assert abs(width_pt - 19.2) < 0.2 and abs(height_pt - 24.0) < 0.2
    print("test_pdf_physical_page_size", PASS)


def test_invalid_scale_rejected():
    try:
        server.encode_photo_export(sample_photo(), {"scale": 4})
    except ValueError:
        print("test_invalid_scale_rejected", PASS)
        return
    raise AssertionError("expected a ValueError for a 4x export")


def main():
    tests = [
        test_jpeg_dimensions_and_dpi,
        test_png_2x_upscale,
        test_webp_export,
        test_pdf_physical_page_size,
        test_invalid_scale_rejected,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} export tests passed.")


if __name__ == "__main__":
    main()
