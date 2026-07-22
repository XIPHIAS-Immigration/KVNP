"""Print-sheet regression tests for server.build_print_sheet.

    python tools/test_print_sheet.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PASS = "  ok"


def _square_photo(size=600):
    img = np.full((size, size, 3), 220, np.uint8)
    cv2.circle(img, (size // 2, size // 2), size // 3, (40, 90, 160), -1)
    return img


def test_4x6_two_by_two_is_six_up():
    photo = _square_photo()
    sheet, layout = server.build_print_sheet(photo, {"sheet": "4x6", "dpi": 300, "photoWidthMm": 51, "photoHeightMm": 51})
    assert (layout["cols"], layout["rows"]) == (3, 2), layout
    assert layout["copies"] == 6, layout
    assert layout["sheetPx"] == [1800, 1200], layout
    assert sheet.shape == (1200, 1800, 3)
    print("test_4x6_two_by_two_is_six_up", PASS)


def test_copies_cap():
    photo = _square_photo()
    _, layout = server.build_print_sheet(photo, {"sheet": "a4", "dpi": 300, "photoWidthMm": 51, "photoHeightMm": 51, "copies": 4})
    assert layout["copies"] == 4, layout
    assert layout["capacity"] >= 4, layout
    print("test_copies_cap", PASS)


def test_digital_only_preserves_aspect():
    photo = np.full((1200, 900, 3), 200, np.uint8)  # 3:4 portrait, no mm
    _, layout = server.build_print_sheet(photo, {"sheet": "4x6", "dpi": 300})
    cw, ch = layout["cellPx"]
    assert abs((cw / ch) - (900 / 1200)) < 0.02, layout  # aspect preserved
    print("test_digital_only_preserves_aspect", PASS)


def test_oversized_photo_raises():
    photo = _square_photo()
    try:
        server.build_print_sheet(photo, {"sheet": "4x6", "dpi": 300, "photoWidthMm": 200, "photoHeightMm": 200})
    except ValueError:
        print("test_oversized_photo_raises", PASS)
        return
    raise AssertionError("expected ValueError for an oversized photo")


def test_dpi_clamped():
    photo = _square_photo()
    _, layout = server.build_print_sheet(photo, {"sheet": "4x6", "dpi": 9000, "photoWidthMm": 51, "photoHeightMm": 51})
    assert layout["dpi"] == 600, layout  # clamped to max
    print("test_dpi_clamped", PASS)


def main():
    tests = [
        test_4x6_two_by_two_is_six_up,
        test_copies_cap,
        test_digital_only_preserves_aspect,
        test_oversized_photo_raises,
        test_dpi_clamped,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} print-sheet tests passed.")


if __name__ == "__main__":
    main()
