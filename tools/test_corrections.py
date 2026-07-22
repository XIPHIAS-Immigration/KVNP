"""Auto-correction regression tests for server.py.

Covers identity-preserving geometry (straighten) and tone (exposure/white
balance) correction, the manual-override skip, and that corrections actually
flip the relevant compliance check from fail to pass. Run with:

    python tools/test_corrections.py
"""
import base64
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PASS = "  ok"

US_PASSPORT = {
    "country": "US",
    "countryName": "United States",
    "programme": "Passport",
    "output": {"widthPx": 600, "heightPx": 600, "quality": 0.92},
    "head": {"minPercent": 49, "maxPercent": 69, "targetPercent": 62, "topMarginPercent": 13},
    "background": {"mode": "white_or_off_white", "minEdgeLuma": 190, "maxEdgeSaturation": 52, "maxEdgeSpread": 42},
    "file": {"minBytes": None, "maxBytes": None},
    "automation": {"backgroundReplacement": True, "backgroundColor": "#ffffff", "enhanceOutput": True, "enhancementMode": "ai-clean"},
    "reviewChecks": ["neutral expression"],
}

ASSISTED_PROFILE = {
    **US_PASSPORT,
    "country": "IN",
    "countryName": "India",
    "programme": "e-Visa test profile",
    "allowedEdits": {
        "straighten": True,
        "tone": True,
        "lighting": True,
        "background": True,
        "enhance": True,
        "rescue": False,
        "note": "Conservative preparation allowed; facial restoration prohibited.",
    },
}


def _portrait():
    return cv2.imread(str(ROOT / "screenshots" / "test-inputs" / "portrait.jpg"))


def _tilt(bgr, degrees):
    h, w = bgr.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(bgr, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _jpeg_bytes(bgr):
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    assert ok
    return buf.tobytes()


def test_straighten_levels_tilt():
    tilted = _tilt(_portrait(), 8.0)
    _, landmarks, face = server.detect_face(tilted)
    assert abs(face["rollDegrees"]) > 4, "test setup should be clearly tilted"
    _, _, _, new_face, correction = server.auto_straighten_source(tilted, landmarks, face)
    assert correction is not None and correction["id"] == "straighten"
    assert abs(new_face["rollDegrees"]) < 2.0, new_face["rollDegrees"]
    print("test_straighten_levels_tilt", PASS)


def test_straighten_skips_level_face():
    bgr = _portrait()
    _, landmarks, face = server.detect_face(bgr)
    image, _, _, _, correction = server.auto_straighten_source(bgr, landmarks, face)
    # A roughly level face must not be rotated.
    if abs(face["rollDegrees"]) < 1.5:
        assert correction is None
        assert image is bgr
    print("test_straighten_skips_level_face", PASS)


def test_tone_corrects_dark_image():
    dark = cv2.convertScaleAbs(_portrait(), alpha=0.4, beta=0)
    before = float(cv2.cvtColor(dark, cv2.COLOR_BGR2GRAY).mean())
    corrected, corrections = server.auto_tone_correct(dark)
    after = float(cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY).mean())
    assert any(c["id"] == "exposure" for c in corrections), corrections
    assert after > before + 10, (before, after)
    print("test_tone_corrects_dark_image", PASS)


def test_correction_flips_tilt_check_to_pass():
    image_bytes = _jpeg_bytes(_tilt(_portrait(), 8.0))
    base_options = {"backgroundReplaced": True, "enhanceOutput": True, "enhancementMode": "ai-clean", "backgroundColor": "#ffffff"}

    with_fix = server.process_image(image_bytes, ASSISTED_PROFILE, base_options)
    tilt = next(c for c in with_fix["checks"] if c["id"] == "head_tilt")
    assert tilt["status"] == "pass", tilt
    assert any(c["id"] == "straighten" for c in with_fix["corrections"]), with_fix["corrections"]

    without_fix = server.process_image(image_bytes, ASSISTED_PROFILE, {**base_options, "autoStraighten": False})
    tilt_no = next(c for c in without_fix["checks"] if c["id"] == "head_tilt")
    assert tilt_no["status"] == "fail", tilt_no
    assert not any(c["id"] == "straighten" for c in without_fix["corrections"]), without_fix["corrections"]
    print("test_correction_flips_tilt_check_to_pass", PASS)


def test_manual_override_keeps_corrections_and_placement():
    """Under manual placement, corrections still apply (so the slider coordinate
    frame matches the corrected output), but manualFace controls head position."""
    image_bytes = _jpeg_bytes(_tilt(_portrait(), 8.0))
    options = {
        "backgroundReplaced": True,
        "enhanceOutput": True,
        "enhancementMode": "ai-clean",
        "backgroundColor": "#ffffff",
        "manualFace": {"centerX": 300, "centerY": 300, "headHeight": 250, "faceWidth": 180},
    }
    result = server.process_image(image_bytes, ASSISTED_PROFILE, options)
    # manualFace controls placement...
    assert abs(result["face"]["centerX"] - 300) < 1, result["face"]
    assert abs(result["face"]["headHeight"] - 250) < 1, result["face"]
    # ...and corrections (straighten/tone) are still applied to the pixels.
    assert any(c["id"] == "straighten" for c in result["corrections"]), result["corrections"]
    print("test_manual_override_keeps_corrections_and_placement", PASS)


def test_clipping_capture_fails_lighting_even_after_tone():
    """Highlight clipping is unrecoverable and must fail source lighting even when
    auto-tone was applied (so a blown-out capture is never marked exportable)."""
    clipped = np.full((400, 400, 3), 255, np.uint8)  # fully clipped face region
    face = {"headHeight": 200, "centerX": 200, "centerY": 200, "faceWidth": 150, "rollDegrees": 0, "yawProxy": 0}
    stats = {"luma": 252.0, "contrast": 4.0, "sharpness": 20.0, "noise": 2.0}
    face_stats = {"luma": 255.0, "contrast": 1.0, "sharpness": 20.0, "noise": 1.0}
    mask_stats = {"available": True, "engine": "x", "faceCoverage": 0.95, "status": "pass"}
    rows = server.build_source_quality(
        clipped, face, US_PASSPORT, stats, face_stats, 50000, True, mask_stats,
        corrections=[{"id": "exposure", "label": "Auto-exposure"}],  # toned, yet still must fail
    )
    lighting = next(c for c in rows if c["id"] == "source_lighting")
    assert lighting["status"] == "fail", lighting
    assert "clip 100%" in lighting["value"], lighting
    print("test_clipping_capture_fails_lighting_even_after_tone", PASS)


def test_strict_programme_clamps_every_pixel_edit():
    """A strict programme must reject client attempts to enable pixel edits."""
    image_bytes = _jpeg_bytes(_tilt(_portrait(), 8.0))
    options = {
        "backgroundReplaced": True,
        "enhanceOutput": True,
        "autoStraighten": True,
        "autoTone": True,
        "autoLighting": True,
        "manualFace": {"centerX": 300, "centerY": 300, "headHeight": 250, "faceWidth": 180},
    }
    result = server.process_image(image_bytes, US_PASSPORT, options)  # US is strict
    edit = next(c for c in result["checks"] if c["id"] == "edit_policy")
    assert edit["status"] == "pass", edit
    assert edit["value"] == "crop/format only", edit
    assert result["corrections"] == [], result["corrections"]
    assert result["allowedEdits"]["enhance"] is False
    assert result["effectiveEdits"]["crop_resize"] is True
    assert all(
        result["effectiveEdits"][key] is False
        for key in ("straighten", "tone", "lighting", "background", "enhance", "rescue")
    ), result["effectiveEdits"]
    assert "manual_geometry" in result["policyClamped"]
    assert {"straighten", "tone", "lighting", "background", "enhance"}.issubset(set(result["policyClamped"]))
    print("test_strict_programme_clamps_every_pixel_edit", PASS)


def test_strict_programme_preview_is_watermarked():
    """Preview may exercise locked tools, but the server must mark the pixels."""
    options = {
        "previewMode": True,
        "backgroundReplaced": True,
        "enhanceOutput": True,
        "autoStraighten": True,
        "autoTone": True,
        "autoLighting": True,
    }
    result = server.process_image(_jpeg_bytes(_portrait()), US_PASSPORT, options)
    assert result["previewOnly"] is True
    assert result["allowedEdits"]["background"] is False
    assert result["effectiveEdits"]["background"] is True
    assert result["decision"]["title"] == "Editing preview"
    assert next(c for c in result["checks"] if c["id"] == "preview_only")["status"] == "warning"

    encoded = base64.b64decode(result["finalDataUrl"].split(",", 1)[1])
    image = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)
    top_band = image[: max(20, image.shape[0] // 6), :, :]
    white_fraction = float(np.mean(np.all(top_band > 240, axis=2)))
    assert white_fraction > 0.85, f"preview background replacement did not produce white: {white_fraction:.3f}"
    strip = image[int(image.shape[0] * 0.91) :, :, :]
    orange_text = (strip[:, :, 2] > 210) & (strip[:, :, 1] > 110) & (strip[:, :, 0] < 150)
    assert int(orange_text.sum()) > 20, "preview watermark text is missing"
    print("test_strict_programme_preview_is_watermarked", PASS)


def test_locked_noncompliant_background_requires_retake():
    source = np.full((400, 400, 3), 170, np.uint8)
    face = {
        "headHeight": 180,
        "faceWidth": 130,
        "centerX": 200,
        "centerY": 180,
        "rollDegrees": 0,
        "yawProxy": 0,
    }
    stats = server.image_stats(source)
    face_stats = {**stats, "focus": 30.0}
    rows = server.build_source_quality(
        source,
        face,
        US_PASSPORT,
        stats,
        face_stats,
        50000,
        False,
        {"available": True, "faceCoverage": 1.0, "status": "pass", "engine": "test"},
    )
    background = next(item for item in rows if item["id"] == "source_background_path")
    assert background["status"] == "fail", background
    print("test_locked_noncompliant_background_requires_retake", PASS)


def test_shoulder_framing_flags_too_much_upper_body():
    face = {
        "faceCount": 1,
        "headHeight": 50.0,
        "faceWidth": 35.0,
        "centerX": 50.0,
        "centerY": 30.0,  # 5% top margin, leaving 45% below the chin
        "rollDegrees": 0.0,
        "yawProxy": 0.0,
        "mouthGapPercent": 0.0,
        "eyeOpenness": 0.2,
        "gazeOffsetPercent": 0.0,
        "glareFraction": 0.0,
        "eyeY": 30.0,
    }
    checks = server.build_checks(
        face,
        {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
        US_PASSPORT,
        {
            "noise": 2.0,
            "focus": 30.0,
            "sharpness": 30.0,
            "luma": 140.0,
            "contrast": 40.0,
            "faceLuma": 140.0,
            "faceContrast": 40.0,
        },
        {"status": "pass", "value": "plain", "target": "plain light background"},
        50000,
        False,
        {"available": False, "status": "review", "message": "disabled"},
        False,
        "natural",
        [],
    )
    shoulder = next(item for item in checks if item["id"] == "shoulder_framing")
    assert shoulder["status"] == "fail", shoulder
    assert "too much upper body" in shoulder["value"], shoulder
    print("test_shoulder_framing_flags_too_much_upper_body", PASS)


def main():
    tests = [
        test_straighten_levels_tilt,
        test_straighten_skips_level_face,
        test_tone_corrects_dark_image,
        test_correction_flips_tilt_check_to_pass,
        test_manual_override_keeps_corrections_and_placement,
        test_clipping_capture_fails_lighting_even_after_tone,
        test_strict_programme_clamps_every_pixel_edit,
        test_strict_programme_preview_is_watermarked,
        test_locked_noncompliant_background_requires_retake,
        test_shoulder_framing_flags_too_much_upper_body,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} correction tests passed.")


if __name__ == "__main__":
    main()
