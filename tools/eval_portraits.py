"""Evaluation harness: measure the assisted-editing pipeline on real portraits.

For each portrait we run the pipeline twice for the same programme:
  BEFORE  - just crop/resize to spec, no corrections (autoCorrect off, no bg, no enhance)
  AFTER   - full corrective pipeline (straighten + tone + bg replace + strong cleanup + enhance)
and report the decision + failing checks for each, so the lift is measurable.

Run:  python tools/eval_portraits.py
"""
import base64
import glob
import json
import os
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402

OUT = ROOT / "screenshots" / "eval"
(OUT / "after").mkdir(parents=True, exist_ok=True)

EVAL_PROFILE = server.PROFILE_REGISTRY["india-visa-online-digital-2026-06"]

BEFORE_OPTS = {"autoCorrect": False, "backgroundReplaced": False, "enhanceOutput": False}
AFTER_OPTS = {
    "autoStraighten": True, "autoTone": True, "backgroundReplaced": True,
    "backgroundCleanup": "strong", "enhanceOutput": True, "enhancementMode": "studio",
    "backgroundColor": "#ffffff",
}


def summarize(result):
    sq = result.get("sourceQuality", [])
    checks = result.get("checks", [])
    src_fail = [c["id"] for c in sq if c["status"] == "fail"]
    out_fail = [c["id"] for c in checks if c["status"] == "fail"]
    warn = [c["id"] for c in [*sq, *checks] if c["status"] == "warning"]
    return {
        "decision": result["decision"]["status"],
        "srcFail": src_fail,
        "outFail": out_fail,
        "nWarn": len(warn),
        "corrections": [c["id"] for c in result.get("corrections", [])],
    }


def run_one(path, profile):
    image_bytes = Path(path).read_bytes()
    try:
        before = summarize(server.process_image(image_bytes, profile, BEFORE_OPTS))
    except Exception as error:  # noqa: BLE001
        before = {"decision": f"ERROR:{error}", "srcFail": [], "outFail": [], "nWarn": 0, "corrections": []}
    try:
        after_result = server.process_image(image_bytes, profile, AFTER_OPTS)
        after = summarize(after_result)
        save_data_url(after_result["finalDataUrl"], OUT / "after" / f"{Path(path).stem}_after.jpg")
    except Exception as error:  # noqa: BLE001
        after = {"decision": f"ERROR:{error}", "srcFail": [], "outFail": [], "nWarn": 0, "corrections": []}
    return before, after


def save_data_url(data_url, path):
    path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))


def verdict(before, after):
    rank = {"ready": 0, "review": 1, "policy_review": 1, "fix": 2, "retake": 3}
    b = rank.get(before["decision"], 3)
    a = rank.get(after["decision"], 3)
    if a < b:
        return "IMPROVED"
    if a == b and (len(after["outFail"]) + len(after["srcFail"])) < (len(before["outFail"]) + len(before["srcFail"])):
        return "improved (fewer fails)"
    if a > b:
        return "WORSE"
    return "same"


def main():
    images = sorted(glob.glob(str(ROOT / "screenshots" / "eval" / "raw" / "px_*.jpg")))
    images += [str(ROOT / "screenshots" / "eval" / "raw" / "test_pexels.jpg")]
    print(f"Evaluating {len(images)} real portraits on assisted-editing profile (BEFORE=no help, AFTER=faithful pipeline)\n")
    print(f"{'image':22} {'BEFORE':>9} {'AFTER':>9}  {'verdict':22} corrections / remaining fails")
    print("-" * 110)
    t0 = time.time()
    rows = []
    for path in images:
        name = Path(path).stem
        before, after = run_one(path, EVAL_PROFILE)
        v = verdict(before, after)
        rows.append((name, before, after, v))
        remain = ",".join(after["outFail"] + after["srcFail"]) or "none"
        corr = "+".join(after["corrections"]) or "-"
        print(f"{name:22} {before['decision']:>9} {after['decision']:>9}  {v:22} {corr} | left: {remain}")
    print("-" * 110)
    improved = sum(1 for _, _, _, v in rows if "improv" in v.lower() or v == "IMPROVED")
    ready_after = sum(1 for _, _, a, _ in rows if a["decision"] in ("ready", "review", "policy_review"))
    print(f"{len(rows)} portraits | improved: {improved} | exportable after (ready/review): {ready_after} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
