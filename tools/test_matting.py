"""Matting regression tests for server.py.

Covers the matte engine selection, stray-island removal, soft-edge
preservation, and the honest mask diagnostics (stray islands, enclosed holes,
shoulder coverage). Run with:

    python tools/test_matting.py

Exits non-zero on the first failed assertion. No network or GPU required.
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

PASS = "  ok"


FACE = {"headHeight": 40, "centerX": 50, "centerY": 50}


def test_disabled_path():
    mask, engine = server.build_person_mask(None, np.zeros((100, 100, 3), np.uint8), FACE, False, 100, 100)
    stats = server.describe_mask(mask, FACE, 100, 100, engine)
    assert mask is None
    assert engine == "disabled"
    assert stats["available"] is False
    assert stats["status"] == "review"
    print("test_disabled_path", PASS)


def test_unavailable_is_not_disabled():
    """A failed matte must be reported as a warning, not a benign 'disabled' state."""
    stats = server.describe_mask(None, FACE, 100, 100, "unavailable")
    assert stats["available"] is False
    assert stats["engine"] == "unavailable"
    assert stats["status"] == "warning", stats
    assert "NOT replaced" in stats["message"]
    print("test_unavailable_is_not_disabled", PASS)


def test_face_aware_selection_preserves_person():
    """If the largest >0.5 blob is background, the face's component must still win."""
    m = np.zeros((200, 200), np.float32)
    m[150:200, 0:200] = 1.0   # large spurious background bar (the biggest blob)
    m[40:110, 70:130] = 1.0   # the actual head, smaller, where the face sits
    face = {"headHeight": 70, "centerX": 100, "centerY": 75}
    kept = server.keep_main_subject(m, face)
    assert kept[75, 100] > 0.0, "the face's component must be preserved"
    assert float(kept[175, 100]) == 0.0, "the larger background bar must be removed"
    print("test_face_aware_selection_preserves_person", PASS)


def test_stray_in_dilation_band_removed():
    """A stray solid island near the subject must still be zeroed (not rescued by dilation)."""
    m = np.zeros((300, 300), np.float32)
    m[100:200, 100:200] = 1.0   # subject
    m[100:115, 210:225] = 1.0   # stray island ~10px from subject (inside a 6px band? no - test removal)
    face = {"headHeight": 100, "centerX": 150, "centerY": 150}
    kept = server.keep_main_subject(m, face)
    assert float(kept[107, 217]) == 0.0, "stray solid island must be removed even if near the subject"
    print("test_stray_in_dilation_band_removed", PASS)


def test_shoulder_unmeasurable_no_false_warning():
    """Face near the frame bottom -> shoulder band too thin to measure -> no clipped warning."""
    m = np.zeros((200, 200), np.float32)
    m[20:198, 60:140] = 1.0   # a clean, well-formed subject
    face = {"headHeight": 120, "centerX": 100, "centerY": 190}  # chin near bottom
    stats = server.describe_mask(m, face, 200, 200, "test")
    assert stats["shoulderCoverage"] is None, "shoulder band should be unmeasurable here"
    assert "shoulders" not in stats["message"], stats
    print("test_shoulder_unmeasurable_no_false_warning", PASS)


def test_high_coverage_not_failed():
    """A legitimately close-framed subject (high coverage) must not be failed outright."""
    m = np.zeros((200, 200), np.float32)
    m[10:195, 25:175] = 1.0   # subject fills most of the frame (~70% coverage)
    face = {"headHeight": 120, "centerX": 100, "centerY": 80}
    stats = server.describe_mask(m, face, 200, 200, "test")
    assert stats["status"] != "fail", stats
    print("test_high_coverage_not_failed", PASS)


def test_stray_and_hole_detection():
    m = np.zeros((200, 200), np.float32)
    m[40:160, 40:160] = 1.0   # solid subject
    m[90:110, 90:110] = 0.0   # enclosed hole
    m[5:15, 5:15] = 1.0       # stray corner island
    stats = server.describe_mask(m, {"headHeight": 80, "centerX": 100, "centerY": 100}, 200, 200, "test")
    assert stats["strayIslands"] >= 1, stats
    assert stats["holePercent"] > 0, stats
    assert stats["status"] == "warning", stats
    print("test_stray_and_hole_detection", PASS)


def test_no_false_holes_when_subject_in_corner():
    m = np.zeros((200, 200), np.float32)
    m[0:120, 0:120] = 1.0  # subject fills the (0,0) corner, no enclosed holes
    stats = server.describe_mask(m, {"headHeight": 80, "centerX": 60, "centerY": 60}, 200, 200, "test")
    assert stats["holePercent"] == 0.0, stats
    print("test_no_false_holes_when_subject_in_corner", PASS)


def test_keep_main_subject_preserves_soft_edges():
    m = np.zeros((200, 200), np.float32)
    m[60:140, 60:140] = 1.0
    m[55:60, 60:140] = 0.4  # soft top band, below the 0.5 binary threshold
    m[5:12, 5:12] = 1.0     # distant stray island
    kept = server.keep_main_subject(m)
    assert kept[57, 100] > 0.0, "soft edge band near the subject must survive"
    assert float(kept[8, 8]) == 0.0, "distant stray island must be removed"
    print("test_keep_main_subject_preserves_soft_edges", PASS)


def test_head_guard_restores_ears_and_neck():
    """A coarse mask with clipped side features must recover both ears and neck."""
    m = np.zeros((120, 120), np.float32)
    cv2.ellipse(m, (60, 50), (20, 31), 0, 0, 360, 1.0, -1)
    m[75:116, 45:76] = 1.0
    source = np.full((120, 120, 3), (70, 150, 70), np.uint8)
    skin = (92, 132, 184)
    cv2.ellipse(source, (60, 50), (20, 31), 0, 0, 360, skin, -1)
    cv2.ellipse(source, (40, 53), (4, 9), 0, 0, 360, skin, -1)
    cv2.ellipse(source, (80, 53), (4, 9), 0, 0, 360, skin, -1)
    source[73:108, 49:72] = skin
    face = {
        "headHeight": 62,
        "faceWidth": 38,
        "centerX": 60,
        "centerY": 50,
        "bounds": {"minX": 41, "maxX": 79, "minY": 27, "maxY": 73},
    }
    guarded = server.protect_head_and_neck(m, face, 120, 120, source_bgr=source)
    ear_y = 53
    assert guarded[ear_y, 40] > 0.65, guarded[ear_y, 40]
    assert guarded[ear_y, 80] > 0.65, guarded[ear_y, 80]
    assert guarded[88, 60] > 0.9, guarded[88, 60]
    assert guarded[5, 5] == 0.0, "background far from the head must remain transparent"
    assert guarded[53, 35] == 0.0, "nearby non-skin background must not become an ear blob"
    print("test_head_guard_restores_ears_and_neck", PASS)


def test_soft_hair_edge_removes_old_background_spill():
    """Semi-transparent hair must carry hair colour, not the old green wall."""
    alpha = np.zeros((80, 80), np.float32)
    alpha[:, 28:52] = 1.0
    alpha[:, 24:28] = np.array([0.15, 0.35, 0.6, 0.82], np.float32)
    alpha[:, 52:56] = np.array([0.82, 0.6, 0.35, 0.15], np.float32)
    old_background = np.array([72, 138, 78], np.float32)
    hair = np.array([20, 24, 28], np.float32)
    source = hair * alpha[..., None] + old_background * (1.0 - alpha[..., None])
    result = server.composite_background(source.astype(np.uint8), alpha, (255, 255, 255)).astype(np.float32)
    expected = hair * alpha[..., None] + 255.0 * (1.0 - alpha[..., None])
    edge = (alpha > 0.1) & (alpha < 0.9)
    mean_error = float(np.abs(result[edge] - expected[edge]).mean())
    assert mean_error < 16.0, mean_error
    assert np.array_equal(result[:, 30:50].astype(np.uint8), source[:, 30:50].astype(np.uint8))
    print("test_soft_hair_edge_removes_old_background_spill", PASS)


def test_output_trimap_rejects_halo_but_keeps_dark_curl():
    source = np.full((120, 120, 3), (70, 145, 72), np.uint8)
    source[20:115, 40:80] = (22, 24, 28)
    source[34:64, 36:42] = (22, 24, 28)  # a real curl outside the solid core
    matte = np.zeros((120, 120), np.float32)
    matte[20:115, 40:80] = 1.0
    matte[16:119, 34:86] = np.maximum(matte[16:119, 34:86], 0.45)
    refined = server.refine_output_matte(matte, source)
    assert refined[90, 35] < 0.08, refined[90, 35]
    assert refined[45, 38] > 0.3, refined[45, 38]
    assert refined[50, 50] == 1.0
    print("test_output_trimap_rejects_halo_but_keeps_dark_curl", PASS)


def test_modnet_path_with_synthetic_model():
    """Validate the MODNet ONNX code path end to end with a tiny stand-in model."""
    import onnx
    from onnx import TensorProto, helper

    inp = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, "h", "w"])
    out = helper.make_tensor_value_info("alpha", TensorProto.FLOAT, [1, 1, "h", "w"])
    nodes = [
        helper.make_node("ReduceMean", ["input"], ["m"], axes=[1], keepdims=1),
        helper.make_node("Sigmoid", ["m"], ["alpha"]),
    ]
    model = helper.make_model(
        helper.make_graph(nodes, "tiny_modnet", [inp], [out]),
        opset_imports=[helper.make_opsetid("", 11)],
    )
    model.ir_version = 8
    tmp = Path(tempfile.gettempdir()) / "kvnp_tiny_modnet.onnx"
    onnx.save(model, str(tmp))

    saved_path = server.MODNET_MODEL_PATH
    try:
        server.MODNET_MODEL_PATH = tmp
        server.modnet_session = None
        server.modnet_unavailable = False
        assert server.modnet_ready() is True

        bgr = cv2.imread(str(ROOT / "screenshots" / "test-inputs" / "portrait.jpg"))
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        alpha = server.run_modnet_matte(rgb, w, h)
        assert alpha is not None and alpha.shape == (h, w)
        assert 0.0 <= float(alpha.min()) and float(alpha.max()) <= 1.0

        face = {"headHeight": h * 0.5, "centerX": w * 0.5, "centerY": h * 0.45}
        mask, engine = server.build_person_mask(None, bgr, face, True, w, h)
        assert engine == "MODNet Portrait Matting"
        assert mask.shape == (h, w)
    finally:
        server.MODNET_MODEL_PATH = saved_path
        server.modnet_session = None
        server.modnet_unavailable = False
        if tmp.exists():
            tmp.unlink()
    print("test_modnet_path_with_synthetic_model", PASS)


def test_real_portrait_clean_matte():
    """The bundled sample should produce a connected, hole-free matte."""
    bgr = cv2.imread(str(ROOT / "screenshots" / "test-inputs" / "portrait.jpg"))
    h, w = bgr.shape[:2]
    face = {"headHeight": h * 0.5, "centerX": w * 0.5, "centerY": h * 0.45}
    mask, engine = server.build_person_mask(server_mp_image(bgr), bgr, face, True, w, h)
    assert mask is not None
    stats = server.describe_mask(mask, face, w, h, engine)
    assert stats["available"] is True
    assert stats["strayIslands"] == 0, stats
    assert stats["status"] in {"pass", "warning"}, stats
    print("test_real_portrait_clean_matte", PASS)


def server_mp_image(bgr):
    import mediapipe as mp

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


def main():
    tests = [
        test_disabled_path,
        test_unavailable_is_not_disabled,
        test_face_aware_selection_preserves_person,
        test_stray_in_dilation_band_removed,
        test_shoulder_unmeasurable_no_false_warning,
        test_high_coverage_not_failed,
        test_stray_and_hole_detection,
        test_no_false_holes_when_subject_in_corner,
        test_keep_main_subject_preserves_soft_edges,
        test_head_guard_restores_ears_and_neck,
        test_soft_hair_edge_removes_old_background_spill,
        test_output_trimap_rejects_halo_but_keeps_dark_curl,
        test_modnet_path_with_synthetic_model,
        test_real_portrait_clean_matte,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} matting tests passed.")


if __name__ == "__main__":
    main()
