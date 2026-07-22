"""300-image bucketed stress test.

Classifies open-source portraits into 3 buckets and reports each separately:
  A  realistic frontal/neutral   -> true pass rate (BEFORE vs AFTER)
  B  degraded-but-fixable        -> recovery rate (degrade an A image, then AFTER)
  C  hard negatives (smile/turn) -> correct-rejection rate (AFTER should NOT pass)

Writes screenshots/eval/stress300_report.pdf + stress300_results.json.
Run: python tools/stress300.py
"""
import base64
import glob
import json
import sys
import time
from collections import Counter
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
PDF_PATH = ROOT / "screenshots" / "eval" / "stress300_report.pdf"
JSON_PATH = ROOT / "screenshots" / "eval" / "stress300_results.json"
EXPORTABLE = {"ready", "review", "policy_review"}
MAX_A = 150
MAX_B = 110


def rgb(data_url):
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return cv2.cvtColor(cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)


def jpeg(bgr):
    return cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])[1].tobytes()


def fails(result):
    return [c["id"] for c in result.get("sourceQuality", []) + result.get("checks", []) if c["status"] == "fail"]


def classify(face):
    roll, yaw = abs(face["rollDegrees"]), abs(face["yawProxy"])
    mouth, eyes = face.get("mouthGapPercent", 0), face.get("eyeOpenness", 0.3)
    if yaw > 14 or mouth > 2.4 or eyes < 0.13:
        return "C"  # hard negative: turned / smiling / eyes closed
    return "A"  # realistic frontal-neutral


def degrade(bgr, kind):
    h, w = bgr.shape[:2]
    if kind == "tilt":
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 11, 1.0)
        return cv2.warpAffine(bgr, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    if kind == "dark":
        return cv2.convertScaleAbs(bgr, alpha=0.5)
    if kind == "cast":
        f = bgr.astype(np.float32); f[:, :, 2] *= 1.22; f[:, :, 0] *= 0.8
        return np.clip(f, 0, 255).astype(np.uint8)
    if kind == "lowcontrast":
        return cv2.convertScaleAbs(bgr, alpha=0.55, beta=70)
    if kind == "soft":
        return cv2.GaussianBlur(bgr, (0, 0), 1.3)
    return bgr


def process(image_bytes, opts):
    try:
        return server.process_image(image_bytes, US_PASSPORT, opts)
    except Exception as error:  # noqa: BLE001
        return {"decision": {"status": f"error:{error}"}, "checks": [], "sourceQuality": [], "corrections": [],
                "finalDataUrl": "data:image/jpeg;base64,"}


def run():
    files = sorted(glob.glob(str(STRESS / "*.jpg")))
    print(f"Classifying {len(files)} images...")
    A, C = [], []
    for f in files:
        img = cv2.imread(f)
        if img is None:
            continue
        try:
            _, _, face = server.detect_face(img)
        except Exception:
            continue
        (A if classify(face) == "A" else C).append(f)
    A, C = A[:MAX_A], C
    print(f"  bucket A (frontal-neutral): {len(A)} | bucket C (hard negatives): {len(C)}")

    rows = []
    t0 = time.time()

    # A: realistic pass rate (BEFORE vs AFTER)
    for f in A:
        ib = Path(f).read_bytes()
        before, after = process(ib, BEFORE_OPTS), process(ib, AFTER_OPTS)
        rows.append(dict(bucket="A", name=Path(f).name, kind="original",
                         before=before["decision"]["status"], after=after["decision"]["status"],
                         after_fails=fails(after), corrections=[c["id"] for c in after.get("corrections", [])],
                         before_img=before["finalDataUrl"], after_img=after["finalDataUrl"],
                         ok=after["decision"]["status"] in EXPORTABLE))

    # B: recovery (degrade an A image, then AFTER)
    kinds = ["tilt", "dark", "cast", "lowcontrast", "soft"]
    for i, f in enumerate(A[:MAX_B]):
        kind = kinds[i % len(kinds)]
        deg = degrade(cv2.imread(f), kind)
        ib = jpeg(deg)
        before, after = process(ib, BEFORE_OPTS), process(ib, AFTER_OPTS)
        rows.append(dict(bucket="B", name=f"{Path(f).stem}+{kind}", kind=kind,
                         before=before["decision"]["status"], after=after["decision"]["status"],
                         after_fails=fails(after), corrections=[c["id"] for c in after.get("corrections", [])],
                         before_img=before["finalDataUrl"], after_img=after["finalDataUrl"],
                         ok=after["decision"]["status"] in EXPORTABLE))

    # C: correct rejection (AFTER should NOT be exportable)
    for f in C:
        ib = Path(f).read_bytes()
        after = process(ib, AFTER_OPTS)
        exportable = after["decision"]["status"] in EXPORTABLE
        rows.append(dict(bucket="C", name=Path(f).name, kind="hard-negative",
                         before="-", after=after["decision"]["status"], after_fails=fails(after),
                         corrections=[c["id"] for c in after.get("corrections", [])],
                         before_img=None, after_img=after["finalDataUrl"],
                         ok=exportable, correct_reject=not exportable))

    print(f"  processed {len(rows)} in {time.time()-t0:.0f}s")
    summarize(rows)
    write_pdf(rows)
    JSON_PATH.write_text(json.dumps([{k: v for k, v in r.items() if not k.endswith("_img")} for r in rows], indent=2))


def bucket_stats(rows):
    out = {}
    for b in ("A", "B", "C"):
        br = [r for r in rows if r["bucket"] == b]
        if b == "C":
            good = sum(1 for r in br if r.get("correct_reject"))
        else:
            good = sum(1 for r in br if r["ok"])
        out[b] = (good, len(br))
    return out


def summarize(rows):
    st = bucket_stats(rows)
    print("\n" + "=" * 64)
    print(f"BUCKET A (realistic frontal)  passed:          {st['A'][0]}/{st['A'][1]}  ({pct(st['A'])}%)")
    print(f"BUCKET B (degraded)           recovered:       {st['B'][0]}/{st['B'][1]}  ({pct(st['B'])}%)")
    print(f"BUCKET C (hard negatives)     correctly rejected: {st['C'][0]}/{st['C'][1]}  ({pct(st['C'])}%)")
    print(f"TOTAL images: {len(rows)}")
    rem = Counter(f for r in rows if r["bucket"] in ("A", "B") for f in r["after_fails"])
    print("Top remaining issues in A/B:", dict(rem.most_common(6)))


def pct(pair):
    return 100 * pair[0] // max(1, pair[1])


def write_pdf(rows):
    st = bucket_stats(rows)
    with PdfPages(PDF_PATH) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.suptitle("KVNP Passport Studio — 300-Image Stress Test", fontsize=17, fontweight="bold", y=0.96)
        lines = [
            f"Total images: {len(rows)}   (open-source: synthetic + Pexels portraits)",
            "Programme: United States passport",
            "",
            "Results by bucket (each measures a different thing):",
            "",
            f"  A  Realistic frontal / neutral   PASSED:              {st['A'][0]} / {st['A'][1]}   ({pct(st['A'])}%)",
            "       -> the true pass rate for real passport-style photos",
            "",
            f"  B  Degraded but fixable          RECOVERED by auto-fix: {st['B'][0]} / {st['B'][1]}   ({pct(st['B'])}%)",
            "       -> tilt / dark / colour-cast / low-contrast / soft, then auto-fixed",
            "",
            f"  C  Hard negatives (smile/turn)   CORRECTLY REJECTED:   {st['C'][0]} / {st['C'][1]}   ({pct(st['C'])}%)",
            "       -> the tool should NOT pass these (would be a real rejection)",
            "",
            "Auto-fix: straighten, exposure, white balance, even face lighting,",
            "red-eye, background replace + padded composition, enhancement.",
            "It never alters expression/pose (that would make the photo non-compliant).",
            "",
            "Automated estimate only; not a government service; no guarantee of acceptance.",
        ]
        fig.text(0.08, 0.87, "\n".join(lines), fontsize=10.5, va="top", family="monospace")
        pdf.savefig(fig); plt.close(fig)

        # sample rows per bucket (cap to keep the PDF readable)
        sample = [r for b in ("A", "B", "C") for r in [x for x in rows if x["bucket"] == b][:18]]
        for start in range(0, len(sample), 5):
            _detail_page(pdf, sample[start : start + 5])


def _detail_page(pdf, rows):
    fig, axes = plt.subplots(len(rows), 2, figsize=(8.27, 11.69))
    if len(rows) == 1:
        axes = np.array([axes])
    fig.subplots_adjust(left=0.04, right=0.97, top=0.96, bottom=0.03, hspace=0.5, wspace=0.05)
    for i, row in enumerate(rows):
        ax_b, ax_a = axes[i, 0], axes[i, 1]
        ax_b.axis("off"); ax_a.axis("off")
        if row.get("before_img"):
            ax_b.imshow(rgb(row["before_img"]))
            ax_b.set_title(f"[{row['bucket']}] {row['name'][:22]}\nBEFORE: {row['before']}", fontsize=8)
        else:
            ax_b.set_title(f"[{row['bucket']}] {row['name'][:22]}\n(hard negative)", fontsize=8)
        if row.get("after_img") and len(row["after_img"]) > 40:
            ax_a.imshow(rgb(row["after_img"]))
        if row["bucket"] == "C":
            ok = row.get("correct_reject")
            verdict = "correctly REJECTED" if ok else "WRONGLY passed"
        else:
            ok = row["ok"]
            verdict = "PASS" if ok else "needs retake"
        ax_a.set_title(
            f"AFTER: {row['after']}  [{verdict}]\nfixed: {', '.join(row['corrections']) or 'none'}\nleft: {', '.join(row['after_fails']) or 'none'}",
            fontsize=7.5, color=("#1a7f37" if ok else "#b3261e"),
        )
    pdf.savefig(fig); plt.close(fig)


if __name__ == "__main__":
    run()
