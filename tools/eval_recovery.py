"""Recovery test: take clean frontal portraits, DEGRADE them so they no longer
qualify, then measure how much the studio pipeline recovers them.

Run: python tools/eval_recovery.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from tools.eval_portraits import US_PASSPORT, BEFORE_OPTS, AFTER_OPTS, summarize  # noqa: E402

INDIA_VISA = {
    "id": "in-visa", "label": "India e-Visa", "country": "IN", "countryName": "India",
    "programme": "Visa Online", "category": "Visa", "document": "Visa", "delivery": "Digital",
    "output": {"widthPx": 600, "heightPx": 600, "printWidthMm": 51, "printHeightMm": 51, "mime": "image/jpeg", "quality": 0.9},
    "head": {"minPercent": 49, "maxPercent": 69, "targetPercent": 62, "topMarginPercent": 12},
    "background": {"mode": "white", "minEdgeLuma": 195, "maxEdgeSaturation": 45, "maxEdgeSpread": 38},
    "file": {"formats": ["jpg"], "minBytes": None, "maxBytes": 1000000},
    "automation": {"backgroundReplacement": True, "backgroundColor": "#ffffff", "enhanceOutput": True, "compressionTarget": 1000000},
    "reviewChecks": ["front view", "full face visible", "eyes open", "no shadows"],
}

# clean frontal portraits identified in the first eval
CLEAN = ["px_1681010", "px_220453", "test_pexels"]


def jpeg(img):
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return buf.tobytes()


def degrade(img, kind):
    h, w = img.shape[:2]
    if kind == "tilt12":
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 12, 1.0)
        return cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    if kind == "dark":
        return cv2.convertScaleAbs(img, alpha=0.5, beta=0)
    if kind == "warmcast":
        out = img.astype(np.float32)
        out[:, :, 2] *= 1.25  # boost red (BGR)
        out[:, :, 0] *= 0.8   # cut blue
        return np.clip(out, 0, 255).astype(np.uint8)
    if kind == "lowcontrast":
        return cv2.convertScaleAbs(img, alpha=0.55, beta=70)
    return img


def line(label, profile, image_bytes):
    before = summarize(server.process_image(image_bytes, profile, BEFORE_OPTS))
    after = summarize(server.process_image(image_bytes, profile, AFTER_OPTS))
    bfail = before["outFail"] + before["srcFail"]
    afail = after["outFail"] + after["srcFail"]
    print(f"  {label:14} BEFORE={before['decision']:>7} ({len(bfail)} fail)  ->  AFTER={after['decision']:>13} ({len(afail)} fail)  fixed: {'+'.join(after['corrections']) or '-'}")


def main():
    print("RECOVERY TEST — degrade a qualifying portrait, then measure the studio's lift (US passport)\n")
    for name in CLEAN:
        path = ROOT / "screenshots" / "eval" / "raw" / f"{name}.jpg"
        if not path.exists():
            continue
        img = cv2.imread(str(path))
        print(f"{name}:")
        line("original", US_PASSPORT, jpeg(img))
        for kind in ("tilt12", "dark", "warmcast", "lowcontrast"):
            line(kind, US_PASSPORT, jpeg(degrade(img, kind)))
        print()

    print("NON-STRICT programme (India e-Visa) — can a clean frontal reach 'ready'?")
    for name in CLEAN:
        path = ROOT / "screenshots" / "eval" / "raw" / f"{name}.jpg"
        if path.exists():
            after = summarize(server.process_image(path.read_bytes(), INDIA_VISA, AFTER_OPTS))
            print(f"  {name:14} -> {after['decision']}  (fails: {','.join(after['outFail']+after['srcFail']) or 'none'})")


if __name__ == "__main__":
    main()
