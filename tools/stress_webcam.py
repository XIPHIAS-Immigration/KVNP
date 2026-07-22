"""Real-world standard-camera stress test.

Takes real frontal/neutral portraits and pushes them through five simulated
standard-camera captures (720p webcam, 480p webcam, low-light, old phone,
good webcam) plus a truly-out-of-focus control that must be REJECTED.

Writes screenshots/eval/stress_webcam_report.pdf + stress_webcam_results.json.
Run: python tools/stress_webcam.py
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from tools.eval_portraits import US_PASSPORT, BEFORE_OPTS, AFTER_OPTS  # noqa: E402
from tools import stress300 as s  # noqa: E402
from tools import webcam_sim as ws  # noqa: E402

STRESS = ROOT / "screenshots" / "eval" / "stress"
PDF_PATH = ROOT / "screenshots" / "eval" / "stress_webcam_report.pdf"
JSON_PATH = ROOT / "screenshots" / "eval" / "stress_webcam_results.json"
MAX_SOURCES = 60


def run():
    import glob
    files = sorted(glob.glob(str(STRESS / "*.jpg")))
    A = []
    for f in files:
        img = cv2.imread(f)
        if img is None:
            continue
        try:
            _, _, face = server.detect_face(img)
        except Exception:
            continue
        if s.classify(face) == "A":
            A.append((f, img))
        if len(A) >= MAX_SOURCES:
            break
    print(f"Sources (frontal/neutral): {len(A)}")

    rows, t0 = [], time.time()
    profiles = list(ws.PROFILES.keys())

    for prof in profiles:
        for f, img in A:
            ib = ws.simulate_bytes(img, prof)
            before, after = s.process(ib, BEFORE_OPTS), s.process(ib, AFTER_OPTS)
            rows.append(dict(
                bucket=prof, name=f"{Path(f).stem}", kind=prof,
                before=before["decision"]["status"], after=after["decision"]["status"],
                after_fails=s.fails(after), corrections=[c["id"] for c in after.get("corrections", [])],
                before_img=before["finalDataUrl"], after_img=after["finalDataUrl"],
                ok=after["decision"]["status"] in s.EXPORTABLE,
            ))
        print(f"  {prof}: done ({time.time()-t0:.0f}s)")

    # Control: truly out-of-focus webcam captures MUST be rejected.
    for f, img in A[:20]:
        sim = ws.simulate(img, "webcam480")
        blurred = cv2.GaussianBlur(sim, (0, 0), 2.2)
        ok, buf = cv2.imencode(".jpg", blurred, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        after = s.process(buf.tobytes(), AFTER_OPTS)
        rows.append(dict(
            bucket="control_blurry", name=f"{Path(f).stem}+oof", kind="out-of-focus",
            before="-", after=after["decision"]["status"], after_fails=s.fails(after),
            corrections=[c["id"] for c in after.get("corrections", [])],
            before_img=None, after_img=after["finalDataUrl"],
            ok=after["decision"]["status"] in s.EXPORTABLE,
            correct_reject=after["decision"]["status"] not in s.EXPORTABLE,
        ))

    print(f"{len(rows)} cases in {time.time()-t0:.0f}s")
    summarize(rows, profiles)
    write_pdf(rows, profiles)
    JSON_PATH.write_text(json.dumps([{k: v for k, v in r.items() if not k.endswith("_img")} for r in rows], indent=2))


def summarize(rows, profiles):
    print("\n" + "=" * 66)
    for prof in profiles:
        br = [r for r in rows if r["bucket"] == prof]
        ok = sum(1 for r in br if r["ok"])
        print(f"{prof:14} exportable after auto-fix: {ok}/{len(br)} ({100*ok//max(1,len(br))}%)")
    ctrl = [r for r in rows if r["bucket"] == "control_blurry"]
    cr = sum(1 for r in ctrl if r.get("correct_reject"))
    print(f"{'out-of-focus':14} correctly rejected:        {cr}/{len(ctrl)} ({100*cr//max(1,len(ctrl))}%)")
    rem = Counter(x for r in rows if r["bucket"] != "control_blurry" for x in r["after_fails"])
    print("top remaining:", dict(rem.most_common(6)))


def write_pdf(rows, profiles):
    with PdfPages(PDF_PATH) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.suptitle("KVNP Passport Studio — Standard-Camera (Webcam) Stress Test", fontsize=15, fontweight="bold", y=0.96)
        lines = [
            f"Cases: {len(rows)}  = real portraits x 5 simulated standard-camera captures",
            "Programme: United States passport",
            "",
            "Capture simulation per case: sensor downscale + JPEG compression +",
            "sensor noise + white-balance drift + lens softness + indoor exposure.",
            "",
        ]
        for prof in profiles:
            br = [r for r in rows if r["bucket"] == prof]
            ok = sum(1 for r in br if r["ok"])
            spec = ws.PROFILES[prof]
            lines.append(f"  {prof:14} {ok:>3} / {len(br):<3} exportable   ({spec[0]}px, jpeg q{spec[1]}, noise {spec[2]})")
        ctrl = [r for r in rows if r["bucket"] == "control_blurry"]
        cr = sum(1 for r in ctrl if r.get("correct_reject"))
        lines += [
            f"  {'out-of-focus':14} {cr:>3} / {len(ctrl):<3} correctly REJECTED (control group)",
            "",
            "Auto-fix: straighten, exposure, white balance, even face lighting, red-eye,",
            "denoise, 2x CNN detail upscale for low-res sources, background replace +",
            "padded composition. Expression/pose are never altered.",
            "",
            "Automated estimate; not a government service; no guarantee of acceptance.",
        ]
        fig.text(0.07, 0.88, "\n".join(lines), fontsize=10, va="top", family="monospace")
        pdf.savefig(fig); plt.close(fig)

        sample = []
        for prof in [*profiles, "control_blurry"]:
            sample.extend([x for x in rows if x["bucket"] == prof][:6])
        for start in range(0, len(sample), 5):
            s._detail_page(pdf, sample[start : start + 5])


if __name__ == "__main__":
    run()
