"""Promote an existing KVNP account from a trusted server shell."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import kvnp_platform as platform  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Usage: python tools/promote_admin.py admin@example.com", file=sys.stderr)
        return 2
    data_dir = Path(os.getenv("KVNP_DATA_DIR", ROOT / "data")).resolve()
    platform.initialise(data_dir)
    try:
        user = platform.promote_admin(sys.argv[1])
    except ValueError:
        print("No account exists for that email. Sign up first, then retry.", file=sys.stderr)
        return 1
    print(f"Promoted {user.email} to administrator.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
