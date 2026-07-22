"""Safety regressions for face gating and identity-faithful enhancement."""

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PASS = "  ok"


def _expect_detection_error(image, phrase):
    try:
        server.detect_face(image)
    except ValueError as error:
        assert phrase.lower() in str(error).lower(), str(error)
        return
    raise AssertionError(f"expected detection error containing {phrase!r}")


def test_non_portrait_is_rejected():
    image = cv2.imread(str(ROOT / "screenshots" / "eval" / "raw" / "test_picsum.jpg"))
    assert image is not None
    _expect_detection_error(image, "No face")
    print("test_non_portrait_is_rejected", PASS)


def test_occluded_face_is_rejected():
    image = cv2.imread(str(ROOT / "screenshots" / "eval" / "webcam" / "cm_01.jpg"))
    assert image is not None
    _expect_detection_error(image, "No face")
    print("test_occluded_face_is_rejected", PASS)


def test_multiple_faces_are_rejected():
    portrait = cv2.imread(str(ROOT / "screenshots" / "test-inputs" / "portrait.jpg"))
    assert portrait is not None
    _, _, face = server.detect_face(portrait)
    half = int(round(face["headHeight"] * 0.82))
    cx, cy = int(round(face["centerX"])), int(round(face["centerY"]))
    x1, x2 = max(0, cx - half), min(portrait.shape[1], cx + half)
    y1, y2 = max(0, cy - half), min(portrait.shape[0], cy + half)
    closeup = cv2.resize(portrait[y1:y2, x1:x2], (600, 600), interpolation=cv2.INTER_AREA)
    paired = np.concatenate([closeup, closeup], axis=1)
    _expect_detection_error(paired, "Multiple faces")
    print("test_multiple_faces_are_rejected", PASS)


def test_faithful_enhancement_has_bounded_pixel_delta():
    portrait = cv2.imread(str(ROOT / "screenshots" / "test-inputs" / "portrait.jpg"))
    assert portrait is not None
    for mode, max_mean_delta in (("natural", 5.0), ("studio", 8.0), ("ai-clean", 5.0)):
        output = server.enhance_passport_photo(portrait, mode)
        assert output.shape == portrait.shape
        delta = float(np.abs(output.astype(np.float32) - portrait.astype(np.float32)).mean())
        assert delta <= max_mean_delta, (mode, delta, max_mean_delta)
    print("test_faithful_enhancement_has_bounded_pixel_delta", PASS)


def main():
    tests = [
        test_non_portrait_is_rejected,
        test_occluded_face_is_rejected,
        test_multiple_faces_are_rejected,
        test_faithful_enhancement_has_bounded_pixel_delta,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} safety tests passed.")


if __name__ == "__main__":
    main()
