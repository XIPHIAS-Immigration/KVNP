"""Download large optional inference weights into a persistent model directory."""

import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.getenv("KVNP_MODEL_DIR", str(ROOT / "models"))).expanduser()
MODELS = {
    "birefnet-portrait": {
        "filename": "birefnet-portrait.onnx",
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-portrait-epoch_150.onnx",
        "md5": "c3a64a6abf20250d090cd055f12a3b67",
        "min_bytes": 900_000_000,
    },
}


def digest(path):
    checksum = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def valid(path, spec):
    return path.exists() and path.stat().st_size >= spec["min_bytes"] and digest(path) == spec["md5"]


def download(name):
    spec = MODELS[name]
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    target = MODEL_DIR / spec["filename"]
    if valid(target, spec):
        print(f"[kvnp] {name} already verified at {target}")
        return target

    partial = target.with_suffix(target.suffix + ".part")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(spec["url"], headers={"User-Agent": "KVNP-Model-Installer/1.0"})
    print(f"[kvnp] Downloading {name} to {target} (about 973 MB)...", flush=True)
    try:
        with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if not valid(partial, spec):
            raise RuntimeError("downloaded file failed size or MD5 verification")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    print(f"[kvnp] Verified {name}: {target}", flush=True)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=[*MODELS, "none"], default="birefnet-portrait")
    args = parser.parse_args()
    if args.model == "none":
        print("[kvnp] Quality model download disabled.")
        return
    try:
        download(args.model)
    except Exception as error:
        print(f"[kvnp] Model download failed: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
