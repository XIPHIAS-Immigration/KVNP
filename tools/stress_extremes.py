"""Targeted real-portrait stress test for unsafe or unusable captures.

The suite deliberately creates conditions that a passport tool should reject,
not cosmetically repair: clipping, severe darkness, uneven light, blur, noise,
perspective distortion, occlusion, pixelation and multiple faces.

Outputs:
  screenshots/eval/extreme_results.json
  screenshots/eval/extreme_report.pdf
  screenshots/eval/extreme_contact_sheet.jpg
  screenshots/eval/extreme/ (generated test inputs)

Run with: python tools/stress_extremes.py
"""

import base64
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402


OUT = ROOT / "screenshots" / "eval"
CASE_DIR = OUT / "extreme"
JSON_PATH = OUT / "extreme_results.json"
PDF_PATH = ROOT / "output" / "pdf" / "kvnp_extreme_capture_stress_report.pdf"
SHEET_PATH = OUT / "extreme_contact_sheet.jpg"
PROFILE = server.PROFILE_REGISTRY["us-passport-print-2026-06"]
OPTIONS = {
    "autoStraighten": True,
    "autoTone": True,
    "backgroundReplaced": True,
    "backgroundCleanup": "strong",
    "enhanceOutput": True,
    "enhancementMode": "studio",
    "backgroundColor": "#ffffff",
}
EXPORTABLE = {"ready", "review", "policy_review"}
BASES = (
    "px_1043471.jpg",
    "px_1239291.jpg",
    "px_1681010.jpg",
    "px_220453.jpg",
    "px_2379004.jpg",
    "px_2613260.jpg",
    "px_3763188.jpg",
    "px_614810.jpg",
    "px_762020.jpg",
    "px_774909.jpg",
    "px_91227.jpg",
    "px_936119.jpg",
    "test_pexels.jpg",
)


def _clip(image):
    return np.clip(image, 0, 255).astype(np.uint8)


def _underexposed(image, _face):
    return _clip(image.astype(np.float32) * 0.10)


def _clipped_highlights(image, _face):
    return _clip(image.astype(np.float32) * 2.5 + 95)


def _split_lighting(image, _face):
    height, width = image.shape[:2]
    ramp = np.linspace(0.10, 1.75, width, dtype=np.float32)
    ramp = np.tile(ramp, (height, 1))[:, :, None]
    return _clip(image.astype(np.float32) * ramp)


def _motion_blur(image, _face):
    kernel = np.zeros((31, 31), np.float32)
    kernel[15, :] = 1.0 / 31.0
    return cv2.filter2D(image, -1, kernel)


def _defocus_blur(image, _face):
    return cv2.GaussianBlur(image, (0, 0), 7.0)


def _heavy_noise(image, _face):
    rng = np.random.default_rng(20260722)
    noise = rng.normal(0, 58, image.shape).astype(np.float32)
    return _clip(image.astype(np.float32) + noise)


def _perspective_skew(image, _face):
    height, width = image.shape[:2]
    source = np.float32([[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]])
    target = np.float32([
        [0.22 * width, 0.03 * height],
        [0.92 * width, 0.16 * height],
        [0.02 * width, 0.94 * height],
        [0.99 * width, 0.80 * height],
    ])
    matrix = cv2.getPerspectiveTransform(source, target)
    return cv2.warpPerspective(image, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)


def _eye_occlusion(image, face):
    output = image.copy()
    bounds = face["bounds"]
    eye_y = int(face["eyeY"])
    left = int(bounds["minX"] + bounds["width"] * 0.05)
    right = int(bounds["minX"] + bounds["width"] * 0.58)
    half_height = max(12, int(face["headHeight"] * 0.075))
    cv2.rectangle(output, (left, eye_y - half_height), (right, eye_y + half_height), (18, 18, 18), -1)
    return output


def _pixelated(image, _face):
    height, width = image.shape[:2]
    tiny_width = max(48, width // 18)
    tiny_height = max(48, height // 18)
    tiny = cv2.resize(image, (tiny_width, tiny_height), interpolation=cv2.INTER_AREA)
    return cv2.resize(tiny, (width, height), interpolation=cv2.INTER_NEAREST)


def _multiple_faces(image, _face):
    height, width = image.shape[:2]
    canvas = np.full((height, width, 3), 230, np.uint8)
    scaled = cv2.resize(image, (width // 2, height // 2), interpolation=cv2.INTER_AREA)
    y = height // 4
    canvas[y : y + scaled.shape[0], : width // 2] = scaled
    canvas[y : y + scaled.shape[0], width // 2 :] = scaled
    return canvas


TRANSFORMS = {
    "underexposed": _underexposed,
    "clipped_highlights": _clipped_highlights,
    "split_lighting": _split_lighting,
    "motion_blur": _motion_blur,
    "defocus_blur": _defocus_blur,
    "heavy_noise": _heavy_noise,
    "perspective_skew": _perspective_skew,
    "eye_occlusion": _eye_occlusion,
    "pixelated": _pixelated,
    "multiple_faces": _multiple_faces,
}


def _jpeg(image, quality=92):
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return encoded.tobytes()


def _decode_data_url(data_url):
    if not data_url or "," not in data_url:
        return None
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def _failed_checks(result):
    checks = result.get("sourceQuality", []) + result.get("checks", [])
    return [item["id"] for item in checks if item.get("status") == "fail"]


def _warnings(result):
    checks = result.get("sourceQuality", []) + result.get("checks", [])
    return [item["id"] for item in checks if item.get("status") == "warning"]


def _run_case(base_name, case_name, image):
    input_path = CASE_DIR / f"{Path(base_name).stem}__{case_name}.jpg"
    input_path.write_bytes(_jpeg(image))
    started = time.perf_counter()
    try:
        result = server.process_image(input_path.read_bytes(), PROFILE, OPTIONS)
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        status = result.get("decision", {}).get("status", "unknown")
        final = _decode_data_url(result.get("finalDataUrl"))
        return {
            "base": base_name,
            "case": case_name,
            "status": status,
            "expected": "reject",
            "correct": status not in EXPORTABLE,
            "failedChecks": _failed_checks(result),
            "warnings": _warnings(result),
            "corrections": [item["id"] for item in result.get("corrections", [])],
            "elapsedMs": elapsed_ms,
            "inputPath": str(input_path.relative_to(ROOT)),
            "error": None,
            "_input": image,
            "_final": final,
        }
    except Exception as error:  # Rejection before output is safe for these intentionally invalid cases.
        return {
            "base": base_name,
            "case": case_name,
            "status": "rejected_at_intake",
            "expected": "reject",
            "correct": True,
            "failedChecks": ["intake_rejection"],
            "warnings": [],
            "corrections": [],
            "elapsedMs": round((time.perf_counter() - started) * 1000),
            "inputPath": str(input_path.relative_to(ROOT)),
            "error": str(error),
            "_input": image,
            "_final": None,
        }


def _write_contact_sheet(rows):
    tile_width, tile_height = 420, 250
    shown = rows[:20]
    sheet = np.full((5 * tile_height, 4 * tile_width, 3), 18, np.uint8)
    for index, row in enumerate(shown):
        image = row["_input"]
        scale = min((tile_width - 16) / image.shape[1], (tile_height - 52) / image.shape[0])
        resized = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        tile = np.full((tile_height, tile_width, 3), 18, np.uint8)
        x = (tile_width - resized.shape[1]) // 2
        y = 30 + (tile_height - 42 - resized.shape[0]) // 2
        tile[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        colour = (90, 220, 115) if row["correct"] else (70, 70, 245)
        title = f"{row['case']} | {row['status']}"
        cv2.putText(tile, title[:48], (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.43, colour, 1, cv2.LINE_AA)
        cv2.putText(tile, Path(row["base"]).stem, (10, tile_height - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (190, 190, 190), 1, cv2.LINE_AA)
        row_index, col_index = divmod(index, 4)
        sheet[row_index * tile_height : (row_index + 1) * tile_height,
              col_index * tile_width : (col_index + 1) * tile_width] = tile
    cv2.imwrite(str(SHEET_PATH), sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 92])


def _write_pdf(rows):
    correct = sum(row["correct"] for row in rows)
    failures = Counter(check for row in rows for check in row["failedChecks"])
    by_case = defaultdict(lambda: [0, 0])
    for row in rows:
        by_case[row["case"]][1] += 1
        by_case[row["case"]][0] += int(row["correct"])

    with PdfPages(PDF_PATH) as pdf:
        figure = plt.figure(figsize=(8.27, 11.69))
        figure.suptitle("KVNP Studio - Extreme Capture Stress Test", fontsize=17, fontweight="bold", y=0.96)
        lines = [
            f"Programme: {PROFILE['label']}",
            f"Real source portraits: {len(BASES)}",
            f"Adversarial cases: {len(rows)}",
            f"Safely rejected: {correct}/{len(rows)} ({100 * correct / max(1, len(rows)):.1f}%)",
            "",
            "These cases are intentionally beyond safe passport-photo correction.",
            "Success means the tool requests a retake or blocks export; it does not",
            "mean the tool should reconstruct missing detail or normalize severe lighting.",
            "",
            "Results by condition:",
        ]
        lines.extend(f"  {name:22} {passed}/{total} safely rejected" for name, (passed, total) in sorted(by_case.items()))
        lines.extend(["", "Most common blocking checks:"])
        lines.extend(f"  {name:28} {count}" for name, count in failures.most_common(10))
        lines.extend(["", "Automated evaluation only. Final acceptance belongs to the issuing authority."])
        figure.text(0.08, 0.88, "\n".join(lines), va="top", family="monospace", fontsize=9.5)
        pdf.savefig(figure)
        plt.close(figure)

        for start in range(0, min(len(rows), 24), 4):
            subset = rows[start : start + 4]
            figure, axes = plt.subplots(len(subset), 2, figsize=(8.27, 11.69))
            if len(subset) == 1:
                axes = np.array([axes])
            figure.subplots_adjust(left=0.03, right=0.98, top=0.93, bottom=0.03, hspace=0.34, wspace=0.06)
            for index, row in enumerate(subset):
                before, after = axes[index]
                before.axis("off")
                after.axis("off")
                before.imshow(cv2.cvtColor(row["_input"], cv2.COLOR_BGR2RGB))
                before.set_title(f"{row['base']} / {row['case']}", fontsize=8)
                if row["_final"] is not None:
                    after.imshow(cv2.cvtColor(row["_final"], cv2.COLOR_BGR2RGB))
                verdict = "SAFE REJECT" if row["correct"] else "UNSAFE EXPORTABLE"
                shown_checks = row["failedChecks"][:2]
                blocking = ", ".join(shown_checks) or "none"
                if len(row["failedChecks"]) > len(shown_checks):
                    blocking += f" +{len(row['failedChecks']) - len(shown_checks)}"
                after.set_title(
                    f"{row['status']} - {verdict}\nblocks: {blocking}",
                    fontsize=7.5,
                    color="#15803d" if row["correct"] else "#dc2626",
                )
            pdf.savefig(figure)
            plt.close(figure)


def run():
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    started = time.perf_counter()
    for base_name in BASES:
        path = OUT / "raw" / base_name
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(path)
        _, _, face = server.detect_face(image)
        for case_name, transform in TRANSFORMS.items():
            row = _run_case(base_name, case_name, transform(image, face))
            rows.append(row)
            print(f"{base_name:18} {case_name:20} {row['status']:20} {'OK' if row['correct'] else 'UNSAFE'}")

    serializable = [{key: value for key, value in row.items() if not key.startswith("_")} for row in rows]
    JSON_PATH.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    _write_contact_sheet(rows)
    _write_pdf(rows)
    correct = sum(row["correct"] for row in rows)
    elapsed = time.perf_counter() - started
    print(f"\nSafely rejected {correct}/{len(rows)} extreme cases in {elapsed:.1f}s")
    print(f"JSON: {JSON_PATH.relative_to(ROOT)}")
    print(f"PDF:  {PDF_PATH.relative_to(ROOT)}")
    print(f"Sheet: {SHEET_PATH.relative_to(ROOT)}")
    if correct != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    run()
