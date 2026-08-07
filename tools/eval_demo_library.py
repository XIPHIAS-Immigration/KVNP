"""Run every guest demo portrait through the same baseline passport pipeline."""

from collections import Counter
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


PROFILE = server.PROFILE_REGISTRY["us-passport-print-2026-06"]
OPTIONS = {
    "autoCorrect": False,
    "backgroundReplaced": False,
    "enhanceOutput": False,
}


def main():
    portraits = sorted((ROOT / "assets" / "demo").glob("*.jpg"))
    if len(portraits) != 24:
        raise SystemExit(f"Expected 24 demo portraits, found {len(portraits)}")

    decisions = Counter()
    errors = []
    started = time.time()
    print("Guest demo library / United States passport baseline")
    print(f"{'portrait':28} {'decision':14} leading measured issues")
    print("-" * 96)
    for portrait in portraits:
        try:
            result = server.process_image(portrait.read_bytes(), PROFILE, OPTIONS)
            decision = result.get("decision", {}).get("status", "unknown")
            decisions[decision] += 1
            checks = [*result.get("sourceQuality", []), *result.get("checks", [])]
            issues = [
                item.get("label", item.get("id", "check"))
                for item in checks
                if item.get("status") in {"fail", "warning"}
            ]
            summary = ", ".join(issues[:3]) or "no machine fail/warning"
            print(f"{portrait.name:28} {decision:14} {summary}")
        except Exception as error:  # noqa: BLE001
            errors.append((portrait.name, str(error)))
            print(f"{portrait.name:28} {'ERROR':14} {error}")

    print("-" * 96)
    totals = ", ".join(f"{key}={value}" for key, value in sorted(decisions.items()))
    print(f"24 portraits / {totals} / errors={len(errors)} / {time.time() - started:.1f}s")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
