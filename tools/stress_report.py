"""Stress test: run every image in screenshots/eval/stress/ through the pipeline
BEFORE (no correction) vs AFTER (full auto-fix) for US passport, and write a PDF
showing original vs fixed with the decision + what was corrected.

    python tools/stress_report.py
Outputs: screenshots/eval/stress_report.pdf  +  screenshots/eval/stress_results.json
"""
import base64
import glob
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from tools.eval_portraits import US_PASSPORT, BEFORE_OPTS, AFTER_OPTS  # noqa: E402

STRESS = ROOT / "screenshots" / "eval" / "stress"
PDF_PATH = ROOT / "screenshots" / "eval" / "stress_report.pdf"
JSON_PATH = ROOT / "screenshots" / "eval" / "stress_results.json"
EXPORTABLE = {"ready", "review", "policy_review"}
ROWS_PER_PAGE = 5


def data_url_to_rgb(data_url):
    raw = base64.b64decode(data_url.split(",", 1)[1])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def fails_of(result):
    return [c["id"] for c in result.get("sourceQuality", []) + result.get("checks", []) if c["status"] == "fail"]


def run():
    images = sorted(glob.glob(str(STRESS / "*.jpg")))
    print(f"Stress-testing {len(images)} images (US passport, BEFORE vs AFTER)...")
    results = []
    t0 = time.time()
    for i, path in enumerate(images):
        name = Path(path).name
        image_bytes = Path(path).read_bytes()
        row = {"name": name}
        try:
            before = server.process_image(image_bytes, US_PASSPORT, BEFORE_OPTS)
            after = server.process_image(image_bytes, US_PASSPORT, AFTER_OPTS)
            row.update(
                before_status=before["decision"]["status"],
                after_status=after["decision"]["status"],
                before_fails=fails_of(before),
                after_fails=fails_of(after),
                corrections=[c["id"] for c in after.get("corrections", [])],
                before_img=before["finalDataUrl"],
                after_img=after["finalDataUrl"],
                exportable=after["decision"]["status"] in EXPORTABLE,
            )
        except Exception as error:  # noqa: BLE001
            row.update(error=str(error), exportable=False, after_status="error",
                       before_status="error", before_fails=[], after_fails=[], corrections=[])
        results.append(row)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(images)}  ({time.time() - t0:.0f}s)")

    write_pdf(results)
    JSON_PATH.write_text(json.dumps([{k: v for k, v in r.items() if not k.endswith("_img")} for r in results], indent=2))
    summarize(results)


def summarize(results):
    n = len(results)
    exportable = sum(1 for r in results if r.get("exportable"))
    errors = sum(1 for r in results if r.get("after_status") == "error")
    improved = sum(1 for r in results if len(r.get("after_fails", [])) < len(r.get("before_fails", [])))
    from collections import Counter
    remaining = Counter(f for r in results for f in r.get("after_fails", []))
    print("\n" + "=" * 60)
    print(f"{n} images | exportable after auto-fix: {exportable} ({100*exportable//max(1,n)}%) | improved: {improved} | errors: {errors}")
    print("most common remaining (un-auto-fixable) issues:")
    for issue, c in remaining.most_common(8):
        print(f"  {issue:22} {c}")
    print(f"\nPDF: {PDF_PATH}")


def write_pdf(results):
    with PdfPages(PDF_PATH) as pdf:
        _summary_page(pdf, results)
        for start in range(0, len(results), ROWS_PER_PAGE):
            _detail_page(pdf, results[start : start + ROWS_PER_PAGE], start)


def _summary_page(pdf, results):
    n = len(results)
    exportable = sum(1 for r in results if r.get("exportable"))
    improved = sum(1 for r in results if len(r.get("after_fails", [])) < len(r.get("before_fails", [])))
    from collections import Counter
    remaining = Counter(f for r in results for f in r.get("after_fails", []))

    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle("KVNP Passport Studio — Stress Test", fontsize=18, fontweight="bold", y=0.96)
    lines = [
        f"Images tested: {n}  (synthetic + real open-source portraits)",
        f"Programme: United States passport (strict — edits flag 'policy_review')",
        "",
        f"Exportable after auto-fix (ready / review / policy_review):  {exportable} / {n}  ({100*exportable//max(1,n)}%)",
        f"Improved by auto-fix (fewer failures):  {improved} / {n}",
        "",
        "Auto-fix applies: straighten, exposure, white balance, background replace,",
        "background-padded composition (head size + margins), enhancement.",
        "",
        "Most common REMAINING issues (need a retake — not auto-fixable):",
    ]
    for issue, c in remaining.most_common(8):
        label = {
            "mouth": "mouth open / smiling (neutral required)",
            "face_direction": "head turned (face the camera)",
            "source_pose": "head turned/tilted at capture",
            "source_face_pixels": "face too small/far in frame",
            "eyes_open": "eyes not fully open",
            "source_focus": "out of focus",
        }.get(issue, issue)
        lines.append(f"     {c:>3}   {label}")
    lines += [
        "",
        "Note: this is an automated estimate, not a government service, and not a",
        "guarantee of acceptance. The issuing authority makes the final decision.",
    ]
    fig.text(0.08, 0.86, "\n".join(lines), fontsize=11, va="top", family="monospace")
    pdf.savefig(fig)
    plt.close(fig)


def _detail_page(pdf, rows, offset):
    fig, axes = plt.subplots(len(rows), 2, figsize=(8.27, 11.69))
    if len(rows) == 1:
        axes = np.array([axes])
    fig.subplots_adjust(left=0.04, right=0.97, top=0.95, bottom=0.03, hspace=0.45, wspace=0.05)
    for r_idx, row in enumerate(rows):
        ax_b, ax_a = axes[r_idx, 0], axes[r_idx, 1]
        for ax in (ax_b, ax_a):
            ax.axis("off")
        if "before_img" in row:
            ax_b.imshow(data_url_to_rgb(row["before_img"]))
            ax_a.imshow(data_url_to_rgb(row["after_img"]))
        ax_b.set_title(f"#{offset + r_idx + 1} BEFORE: {row.get('before_status','?')}", fontsize=9)
        status = row.get("after_status", "?")
        ok = row.get("exportable")
        verdict = "PASS (exportable)" if ok else "needs retake"
        corr = ", ".join(row.get("corrections", [])) or "none"
        remain = ", ".join(row.get("after_fails", [])) or "none"
        ax_a.set_title(
            f"AFTER: {status}  [{verdict}]\nfixed: {corr}\nremaining: {remain}",
            fontsize=8,
            color=("#1a7f37" if ok else "#b3261e"),
        )
    pdf.savefig(fig)
    plt.close(fig)


if __name__ == "__main__":
    run()
