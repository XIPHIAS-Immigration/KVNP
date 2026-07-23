"""Safety regressions for face gating and identity-faithful enhancement."""

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PASS = "  ok"
EXPORTABLE = {"ready", "review", "policy_review"}


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


def test_iris_gaze_detects_looking_away():
    points = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(478)]
    eye_specs = [
        (server.LEFT_EYE, server.LEFT_EYE_INNER, server.LEFT_EYE_TOP, server.LEFT_EYE_BOTTOM, server.LEFT_IRIS_CENTER, 20, 60),
        (server.RIGHT_EYE, server.RIGHT_EYE_INNER, server.RIGHT_EYE_TOP, server.RIGHT_EYE_BOTTOM, server.RIGHT_IRIS_CENTER, 80, 120),
    ]
    for outer, inner, top, bottom, iris, x1, x2 in eye_specs:
        points[outer].update(x=float(x1), y=50.0)
        points[inner].update(x=float(x2), y=50.0)
        points[top].update(x=float((x1 + x2) / 2), y=40.0)
        points[bottom].update(x=float((x1 + x2) / 2), y=60.0)
        points[iris].update(x=float((x1 + x2) / 2), y=48.9)

    centered = server.estimate_eye_gaze(points, yaw_proxy=0.0)
    assert centered["gazeOffsetPercent"] < 0.2, centered
    points[server.LEFT_IRIS_CENTER]["x"] -= 4.0
    points[server.RIGHT_IRIS_CENTER]["x"] -= 4.0
    away = server.estimate_eye_gaze(points, yaw_proxy=0.0)
    assert away["gazeOffsetPercent"] > 4.5, away
    print("test_iris_gaze_detects_looking_away", PASS)


def test_extreme_lighting_and_blur_are_blocked():
    portrait = cv2.imread(str(ROOT / "screenshots" / "eval" / "raw" / "px_1681010.jpg"))
    assert portrait is not None
    dark = np.clip(portrait.astype(np.float32) * 0.10, 0, 255).astype(np.uint8)
    clipped = np.clip(portrait.astype(np.float32) * 2.5 + 95, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(portrait, (0, 0), 7.0)
    profile = server.PROFILE_REGISTRY["us-passport-print-2026-06"]

    for label, image in (("dark", dark), ("clipped", clipped), ("blurred", blurred)):
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        assert ok
        result = server.process_image(encoded.tobytes(), profile, {})
        status = result["decision"]["status"]
        assert status not in EXPORTABLE, f"{label} source was incorrectly exportable: {status}"
    print("test_extreme_lighting_and_blur_are_blocked", PASS)


def test_posture_checks_separate_pitch_shoulders_and_body_lean():
    checks = {
        item["id"]: item
        for item in server.build_posture_checks(
            {
                "pitchOffsetDegrees": -7.1,
                "shoulderLevelDegrees": 9.0,
                "bodyLeanPercent": 0.5,
                "bodyLeanSource": "head over shoulders",
            }
        )
    }
    assert checks["source_head_pitch"]["status"] == "warning", checks
    assert "raise chin" in checks["source_head_pitch"]["value"], checks
    assert checks["source_shoulder_level"]["status"] == "fail", checks
    assert "one shoulder higher" in checks["source_shoulder_level"]["value"], checks
    assert checks["source_body_alignment"]["status"] == "pass", checks
    print("test_posture_checks_separate_pitch_shoulders_and_body_lean", PASS)


def test_level_posture_passes():
    checks = server.build_posture_checks(
        {
            "pitchOffsetDegrees": 1.5,
            "shoulderLevelDegrees": 2.0,
            "bodyLeanPercent": 4.0,
            "bodyLeanSource": "shoulders over hips",
        }
    )
    assert all(item["status"] == "pass" for item in checks), checks
    print("test_level_posture_passes", PASS)


def main():
    tests = [
        test_non_portrait_is_rejected,
        test_occluded_face_is_rejected,
        test_multiple_faces_are_rejected,
        test_faithful_enhancement_has_bounded_pixel_delta,
        test_iris_gaze_detects_looking_away,
        test_extreme_lighting_and_blur_are_blocked,
        test_posture_checks_separate_pitch_shoulders_and_body_lean,
        test_level_posture_passes,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} safety tests passed.")


if __name__ == "__main__":
    main()
