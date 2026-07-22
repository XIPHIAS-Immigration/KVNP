"""Local smoke test for the KVNP passport pipeline.

Runs server.process_image on sample portraits for a few representative
profiles and prints the matte diagnostics, decision, and key checks.
Saves the generated photo + overlay so edges can be inspected by eye.

Usage:
    python tools/pipeline_smoketest.py
"""
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402

OUT_DIR = ROOT / "screenshots" / "smoketest"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Minimal profiles that mirror src/rules.js (only the fields the backend reads).
US_PASSPORT = {
    "country": "US",
    "countryName": "United States",
    "programme": "Passport photo",
    "output": {"widthPx": 600, "heightPx": 600, "printWidthMm": 51, "printHeightMm": 51, "quality": 0.92},
    "head": {"minPercent": 49, "maxPercent": 69, "targetPercent": 62, "topMarginPercent": 13},
    "background": {"mode": "white_or_off_white", "minEdgeLuma": 190, "maxEdgeSaturation": 52, "maxEdgeSpread": 42},
    "file": {"minBytes": None, "maxBytes": None},
    "automation": {"backgroundReplacement": True, "backgroundColor": "#ffffff", "enhanceOutput": True, "enhancementMode": "ai-clean"},
    "reviewChecks": ["neutral expression", "eyes open", "mouth closed", "no face covering"],
}

INDIA_ICAO = {
    "country": "IN",
    "countryName": "India",
    "programme": "Passport ICAO upload",
    "output": {"widthPx": 630, "heightPx": 810, "quality": 0.9},
    "head": {"minPercent": 80, "maxPercent": 85, "targetPercent": 82.5, "topMarginPercent": 5},
    "background": {"mode": "white", "minEdgeLuma": 195, "maxEdgeSaturation": 45, "maxEdgeSpread": 38},
    "file": {"minBytes": 20000, "maxBytes": 100000},
    "automation": {"backgroundReplacement": True, "backgroundColor": "#ffffff", "enhanceOutput": True, "compressionTarget": 100000},
    "reviewChecks": ["natural expression", "eyes visible", "no head tilt", "unaltered photo"],
}

SAMPLES = [
    ("portrait", ROOT / "screenshots" / "test-inputs" / "portrait.jpg"),
    ("frame-1", ROOT / "screenshots" / "reference-video" / "frame-1.jpg"),
    ("frame-3", ROOT / "screenshots" / "reference-video" / "frame-3.jpg"),
]

PROFILES = [("us-passport", US_PASSPORT), ("india-icao", INDIA_ICAO)]


def save_data_url(data_url, path):
    payload = data_url.split(",", 1)[1]
    path.write_bytes(base64.b64decode(payload))


def run():
    for sample_name, sample_path in SAMPLES:
        if not sample_path.exists():
            print(f"!! missing sample {sample_path}")
            continue
        image_bytes = sample_path.read_bytes()
        for profile_name, profile in PROFILES:
            options = {
                "backgroundReplaced": True,
                "enhanceOutput": True,
                "enhancementMode": profile["automation"].get("enhancementMode", "ai-clean"),
                "backgroundColor": "#ffffff",
            }
            try:
                result = server.process_image(image_bytes, profile, options)
            except Exception as error:  # noqa: BLE001
                print(f"\n=== {sample_name} / {profile_name} -> ERROR: {error}")
                continue

            matte = result["matte"]
            decision = result["decision"]
            tag = f"{sample_name}__{profile_name}"
            save_data_url(result["finalDataUrl"], OUT_DIR / f"{tag}__final.jpg")
            save_data_url(result["overlayDataUrl"], OUT_DIR / f"{tag}__overlay.jpg")
            print(f"\n=== {sample_name} / {profile_name}")
            print(f"  decision: {decision['status']} - {decision['title']}")
            print(f"  matte:    {json.dumps(matte)}")
            fails = [c["id"] for c in result["checks"] if c["status"] == "fail"]
            warns = [c["id"] for c in result["checks"] if c["status"] == "warning"]
            print(f"  fail:     {fails}")
            print(f"  warn:     {warns}")


if __name__ == "__main__":
    run()
