"""1000-case bucketed stress test (bigger sibling of stress300.py).

Same 3-bucket methodology, scaled up:
  A realistic frontal/neutral -> true pass rate
  B degraded-but-fixable (multiple degradations per source) -> recovery rate
  C hard negatives -> correct-rejection rate

Writes screenshots/eval/stress1000_report.pdf + stress1000_results.json.
Run: python tools/stress1000.py
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from tools.eval_portraits import US_PASSPORT, BEFORE_OPTS, AFTER_OPTS  # noqa: E402
from tools import stress300 as s  # reuse helpers  # noqa: E402

STRESS = ROOT / "screenshots" / "eval" / "stress"
PDF_PATH = ROOT / "screenshots" / "eval" / "stress1000_report.pdf"
JSON_PATH = ROOT / "screenshots" / "eval" / "stress1000_results.json"
EXPORTABLE = s.EXPORTABLE

MAX_A = 400
B_TARGET = 430
KINDS = ["tilt", "dark", "cast", "lowcontrast", "soft"]


def run():
    import glob
    files = sorted(glob.glob(str(STRESS / "*.jpg")))
    print(f"Classifying {len(files)} source images...")
    A, C = [], []
    for f in files:
        img = cv2.imread(f)
        if img is None:
            continue
        try:
            _, _, face = server.detect_face(img)
        except Exception:
            continue
        (A if s.classify(face) == "A" else C).append(f)
    A = A[:MAX_A]
    print(f"  A (frontal-neutral): {len(A)} | C (hard negatives): {len(C)}")

    rows, t0 = [], time.time()

    for f in A:
        ib = Path(f).read_bytes()
        b, a = s.process(ib, BEFORE_OPTS), s.process(ib, AFTER_OPTS)
        rows.append(_row("A", Path(f).name, "original", b, a))

    # B: multiple degradations per source until we hit the target
    made = 0
    idx = 0
    while made < B_TARGET and A and idx < len(A) * len(KINDS):
        f = A[idx // len(KINDS)]
        kind = KINDS[idx % len(KINDS)]
        idx += 1
        deg = s.degrade(cv2.imread(f), kind)
        ib = s.jpeg(deg)
        b, a = s.process(ib, BEFORE_OPTS), s.process(ib, AFTER_OPTS)
        rows.append(_row("B", f"{Path(f).stem}+{kind}", kind, b, a))
        made += 1
        if made % 50 == 0:
            print(f"  B {made}/{B_TARGET} ({time.time()-t0:.0f}s)")

    for f in C:
        ib = Path(f).read_bytes()
        a = s.process(ib, AFTER_OPTS)
        row = _row("C", Path(f).name, "hard-negative", None, a)
        row["correct_reject"] = a["decision"]["status"] not in EXPORTABLE
        rows.append(row)

    print(f"  {len(rows)} cases in {time.time()-t0:.0f}s")
    summarize(rows)
    write_pdf(rows)
    JSON_PATH.write_text(json.dumps([{k: v for k, v in r.items() if not k.endswith("_img")} for r in rows], indent=2))


def _row(bucket, name, kind, before, after):
    return dict(
        bucket=bucket, name=name, kind=kind,
        before=before["decision"]["status"] if before else "-",
        after=after["decision"]["status"], after_fails=s.fails(after),
        corrections=[c["id"] for c in after.get("corrections", [])],
        before_img=before["finalDataUrl"] if before else None, after_img=after["finalDataUrl"],
        ok=after["decision"]["status"] in EXPORTABLE,
    )


def stats(rows):
    out = {}
    for bk in ("A", "B", "C"):
        br = [r for r in rows if r["bucket"] == bk]
        good = sum(1 for r in br if (r.get("correct_reject") if bk == "C" else r["ok"]))
        out[bk] = (good, len(br))
    return out


def pct(p):
    return 100 * p[0] // max(1, p[1])


def summarize(rows):
    st = stats(rows)
    print("\n" + "=" * 64)
    print(f"A realistic frontal   passed:             {st['A'][0]}/{st['A'][1]} ({pct(st['A'])}%)")
    print(f"B degraded            recovered:          {st['B'][0]}/{st['B'][1]} ({pct(st['B'])}%)")
    print(f"C hard negatives      correctly rejected: {st['C'][0]}/{st['C'][1]} ({pct(st['C'])}%)")
    print(f"TOTAL cases: {len(rows)}")
    rem = Counter(x for r in rows if r["bucket"] in ("A", "B") for x in r["after_fails"])
    print("top remaining A/B:", dict(rem.most_common(8)))


def write_pdf(rows):
    st = stats(rows)
    with PdfPages(PDF_PATH) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.suptitle("KVNP Passport Studio — 1000-Case Stress Test", fontsize=17, fontweight="bold", y=0.96)
        lines = [
            f"Total test cases: {len(rows)}   (open-source portraits + degraded variants)",
            "Programme: United States passport",
            "",
            f"  A  Realistic frontal / neutral   PASSED:             {st['A'][0]} / {st['A'][1]}  ({pct(st['A'])}%)",
            "        -> true pass rate for real passport-style photos",
            "",
            f"  B  Degraded but fixable          RECOVERED:          {st['B'][0]} / {st['B'][1]}  ({pct(st['B'])}%)",
            "        -> tilt / dark / colour-cast / low-contrast / soft, auto-fixed",
            "",
            f"  C  Hard negatives (smile/turn)   CORRECTLY REJECTED: {st['C'][0]} / {st['C'][1]}  ({pct(st['C'])}%)",
            "        -> the tool should NOT pass these",
            "",
            "Auto-fix: straighten, exposure, white balance, even face lighting, red-eye,",
            "background replace + padded composition, enhancement. Never alters expression/pose.",
            "",
            "Automated estimate; not a government service; no guarantee of acceptance.",
        ]
        fig.text(0.08, 0.87, "\n".join(lines), fontsize=10.5, va="top", family="monospace")
        pdf.savefig(fig); plt.close(fig)
        sample = [r for bk in ("A", "B", "C") for r in [x for x in rows if x["bucket"] == bk][:24]]
        for start in range(0, len(sample), 5):
            s._detail_page(pdf, sample[start : start + 5])


if __name__ == "__main__":
    run()
