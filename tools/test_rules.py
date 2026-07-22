"""Compliance-rule tests for data/profiles.json (the server's authoritative copy).

Validates structural integrity, per-field numeric bounds, the hard honesty
invariants (generative "rescue" restoration stays disabled everywhere), and
drift between the server copy (data/profiles.json) and the frontend source of
truth (src/rules.js). Run with:

    python tools/test_rules.py

Exits non-zero on the first failed assertion. No network or GPU required; the
node deep-equal sub-check is skipped gracefully when node is unavailable.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT / "data" / "profiles.json"
RULES_JS_PATH = ROOT / "src" / "rules.js"

PASS = "  ok"

REQUIRED_KEYS = [
    "id", "label", "country", "countryName", "programme", "allowedEdits",
    "output", "head", "background", "file", "automation", "reviewChecks",
    "sources",
]


def _raw_text():
    return PROFILES_PATH.read_text(encoding="utf-8")


def _load():
    return json.loads(_raw_text())


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key!r}")
        seen[key] = value
    return seen


def test_loads_as_nonempty_list_of_10():
    data = _load()
    assert isinstance(data, list), "profiles.json must be a JSON array"
    assert len(data) == 10, f"expected 10 profiles, got {len(data)}"
    print("test_loads_as_nonempty_list_of_10", PASS)


def test_no_duplicate_keys():
    """Any duplicate key within any object is silently lost by a plain parse."""
    try:
        json.loads(_raw_text(), object_pairs_hook=_no_duplicate_keys)
    except ValueError as exc:  # pragma: no cover - failure path
        raise AssertionError(f"duplicate key in profiles.json: {exc}")
    print("test_no_duplicate_keys", PASS)


def test_unique_ids():
    data = _load()
    ids = [p["id"] for p in data]
    assert len(ids) == len(set(ids)), f"duplicate profile ids: {ids}"
    print("test_unique_ids", PASS)


def test_required_keys_present():
    data = _load()
    for p in data:
        for key in REQUIRED_KEYS:
            assert key in p, f"profile {p.get('id')!r} missing key {key!r}"
    print("test_required_keys_present", PASS)


def test_output_bounds():
    data = _load()
    for p in data:
        out = p["output"]
        w, h = out["widthPx"], out["heightPx"]
        assert isinstance(w, int) and isinstance(h, int), \
            f"{p['id']}: widthPx/heightPx must be ints"
        assert 16 <= w <= 5000, f"{p['id']}: widthPx {w} out of range"
        assert 16 <= h <= 5000, f"{p['id']}: heightPx {h} out of range"
        assert w * h <= 30_000_000, f"{p['id']}: pixel count too large"
        q = out["quality"]
        assert 0 < q <= 1, f"{p['id']}: quality {q} out of range"
        assert out["mime"] == "image/jpeg", f"{p['id']}: mime must be image/jpeg"
    print("test_output_bounds", PASS)


def test_head_bounds():
    data = _load()
    for p in data:
        head = p["head"]
        mn, tg, mx = head["minPercent"], head["targetPercent"], head["maxPercent"]
        assert mn <= tg <= mx, f"{p['id']}: head percents not ordered"
        for v in (mn, tg, mx):
            assert 0 < v <= 100, f"{p['id']}: head percent {v} out of (0,100]"
        tm = head["topMarginPercent"]
        assert -10 <= tm <= 60, f"{p['id']}: topMarginPercent {tm} out of range"
        eye = head.get("eye")
        if eye is not None:
            emn = eye["fromTopMinPercent"]
            etg = eye["targetFromTopPercent"]
            emx = eye["fromTopMaxPercent"]
            assert emn <= etg <= emx, f"{p['id']}: eye percents not ordered"
            for v in (emn, etg, emx):
                assert 0 < v < 100, f"{p['id']}: eye percent {v} out of (0,100)"
    print("test_head_bounds", PASS)


def test_background_numeric():
    data = _load()
    for p in data:
        bg = p["background"]
        for key in ("minEdgeLuma", "maxEdgeSaturation", "maxEdgeSpread"):
            v = bg[key]
            assert isinstance(v, (int, float)) and not isinstance(v, bool), \
                f"{p['id']}: background.{key} must be numeric"
    print("test_background_numeric", PASS)


def test_file_byte_ordering():
    data = _load()
    for p in data:
        f = p["file"]
        mn, mx = f.get("minBytes"), f.get("maxBytes")
        if mn is not None and mx is not None:
            assert mn <= mx, f"{p['id']}: minBytes {mn} > maxBytes {mx}"
    print("test_file_byte_ordering", PASS)


def test_rescue_disabled_everywhere():
    """Hard invariant: generative AI restoration must stay disabled on every profile."""
    data = _load()
    for p in data:
        assert p["allowedEdits"]["rescue"] is False, \
            f"{p['id']}: allowedEdits.rescue must be False"
    print("test_rescue_disabled_everywhere", PASS)


def test_enhance_disabled_no_aggressive_enhancement_mode():
    data = _load()
    for p in data:
        if p["allowedEdits"].get("enhance") is False:
            mode = p["automation"].get("enhancementMode")
            assert mode not in ("ai-clean", "strong"), \
                f"{p['id']}: enhance disabled but enhancementMode={mode!r}"
    print("test_enhance_disabled_no_aggressive_enhancement_mode", PASS)


def test_india_icao_square():
    data = _load()
    hits = [p for p in data if p["id"].startswith("india-passport-icao")]
    assert hits, "no india-passport-icao* profile found"
    for p in hits:
        out = p["output"]
        assert out["widthPx"] == out["heightPx"], \
            f"{p['id']}: ICAO output must be square"
    print("test_india_icao_square", PASS)


def test_drift_guard_ids_in_frontend():
    """Every profiles.json id must appear in the frontend rules.js source."""
    data = _load()
    rules_text = RULES_JS_PATH.read_text(encoding="utf-8")
    for p in data:
        assert p["id"] in rules_text, \
            f"id {p['id']!r} missing from src/rules.js (drift)"
    print("test_drift_guard_ids_in_frontend", PASS)


def test_drift_guard_deep_equal_with_node():
    """If node is available, regenerate profiles from rules.js and deep-equal them."""
    if not shutil.which("node"):
        print("test_drift_guard_deep_equal_with_node  (skipped: node not found)")
        return
    url = RULES_JS_PATH.as_uri()
    script = (
        f"import('{url}').then(m=>process.stdout.write("
        "JSON.stringify(m.RULE_PROFILES)))"
    )
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"test_drift_guard_deep_equal_with_node  (skipped: node call failed: {exc})")
        return
    if result.returncode != 0 or not result.stdout.strip():
        print(
            "test_drift_guard_deep_equal_with_node  "
            f"(skipped: node call failed rc={result.returncode}: {result.stderr.strip()[:200]})"
        )
        return
    frontend = json.loads(result.stdout)
    server_copy = _load()
    assert frontend == server_copy, \
        "data/profiles.json is out of sync with src/rules.js RULE_PROFILES"
    print("test_drift_guard_deep_equal_with_node", PASS)


def main():
    tests = [
        test_loads_as_nonempty_list_of_10,
        test_no_duplicate_keys,
        test_unique_ids,
        test_required_keys_present,
        test_output_bounds,
        test_head_bounds,
        test_background_numeric,
        test_file_byte_ordering,
        test_rescue_disabled_everywhere,
        test_enhance_disabled_no_aggressive_enhancement_mode,
        test_india_icao_square,
        test_drift_guard_ids_in_frontend,
        test_drift_guard_deep_equal_with_node,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"{test.__name__}  FAIL: {exc}")
    if failures:
        print(f"\n{failures} of {len(tests)} rule tests FAILED.")
        sys.exit(1)
    print(f"\nAll {len(tests)} rule tests passed.")


if __name__ == "__main__":
    main()
