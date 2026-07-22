"""Regenerate the browser rule module from the authoritative JSON registry.

Run after editing data/profiles.json:

    python tools/sync_rules.py
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "profiles.json"
TARGET = ROOT / "src" / "rules.js"


def main():
    profiles = json.loads(SOURCE.read_text(encoding="utf-8"))
    encoded = json.dumps(profiles, ensure_ascii=False, indent=2)
    module = f"""// Generated from data/profiles.json by tools/sync_rules.py.
// Edit the JSON registry, then run the sync command. Do not edit this array by hand.
export const RULE_PROFILES = {encoded};

export const COUNTRIES = Array.from(
  new Map(RULE_PROFILES.map((profile) => [profile.country, {{ code: profile.country, name: profile.countryName }}])).values(),
).sort((a, b) => a.name.localeCompare(b.name));

export function getDefaultProfile() {{
  return RULE_PROFILES[0];
}}

export function getProfilesForCountry(countryCode) {{
  return RULE_PROFILES.filter((profile) => profile.country === countryCode);
}}
"""
    TARGET.write_text(module, encoding="utf-8", newline="\n")
    print(f"Synced {len(profiles)} profiles to {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
