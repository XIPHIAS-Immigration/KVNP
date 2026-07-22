import base64
import copy
import hashlib
import hmac
import importlib.util
import io
import json
import math
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import uuid
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image


ROOT = Path(__file__).resolve().parent
SERVER_VERSION = "python-mediapipe-2026-06-18-production-pipeline"
MODEL_DIR = ROOT / "models"
TOOLS_DIR = ROOT / "tools"
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
SEGMENTER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
SUPERRES_MODEL_URL = "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x2.pb"
FACE_MODEL_PATH = MODEL_DIR / "face_landmarker.task"
SEGMENTER_MODEL_PATH = MODEL_DIR / "selfie_segmenter.tflite"
SUPERRES_MODEL_PATH = MODEL_DIR / "FSRCNN_x2.pb"
MODNET_MODEL_PATH = MODEL_DIR / "modnet.onnx"
GFPGAN_MODEL_PATH = MODEL_DIR / "GFPGANv1.4.pth"
REALESRGAN_MODEL_NAME = "realesrgan-x4plus"
# Heavy matte post-processing (guided filter, dilation, connected components)
# runs at a capped working resolution for speed; the final alpha is upsampled
# to the source resolution for compositing.
MATTE_WORK_MAX_SIDE = 1280
FACE_OVAL = [
    10,
    338,
    297,
    332,
    284,
    251,
    389,
    356,
    454,
    323,
    361,
    288,
    397,
    365,
    379,
    378,
    400,
    377,
    152,
    148,
    176,
    149,
    150,
    136,
    172,
    58,
    132,
    93,
    234,
    127,
    162,
    21,
    54,
    103,
    67,
    109,
]

CHIN = 152
FOREHEAD = 10
LEFT_EYE = 33
RIGHT_EYE = 263
NOSE_TIP = 1
MOUTH_UPPER = 13
MOUTH_LOWER = 14
# Eyelid landmarks for eye-aspect-ratio (open-eyes) detection.
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145
LEFT_EYE_INNER = 133
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374
RIGHT_EYE_INNER = 362


def ensure_model(path, url):
    if path.exists() and path.stat().st_size > 100_000:
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, path)


ensure_model(FACE_MODEL_PATH, FACE_MODEL_URL)
ensure_model(SEGMENTER_MODEL_PATH, SEGMENTER_MODEL_URL)
try:
    ensure_model(SUPERRES_MODEL_PATH, SUPERRES_MODEL_URL)
except Exception:
    pass

face_landmarker = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(FACE_MODEL_PATH)),
        running_mode=vision.RunningMode.IMAGE,
        num_faces=2,
        min_face_detection_confidence=0.55,
        min_face_presence_confidence=0.55,
        output_face_blendshapes=True,
    )
)
image_segmenter = vision.ImageSegmenter.create_from_options(
    vision.ImageSegmenterOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(SEGMENTER_MODEL_PATH)),
        running_mode=vision.RunningMode.IMAGE,
        output_confidence_masks=True,
        output_category_mask=False,
    )
)
superres = None
if hasattr(cv2, "dnn_superres") and SUPERRES_MODEL_PATH.exists():
    try:
        superres = cv2.dnn_superres.DnnSuperResImpl_create()
        superres.readModel(str(SUPERRES_MODEL_PATH))
        superres.setModel("fsrcnn", 2)
    except Exception:
        superres = None
realesrgan_exe = None
realesrgan_model_dir = None
gfpgan_restorer = None
gfpgan_unavailable = False
modnet_session = None
modnet_unavailable = False
HAS_GUIDED_FILTER = hasattr(cv2, "ximgproc") and hasattr(getattr(cv2, "ximgproc", None), "guidedFilter")
_logged_warnings = set()


def log_warn(message):
    print(f"[kvnp] {message}", file=sys.stderr, flush=True)


def log_warn_once(message):
    if message not in _logged_warnings:
        _logged_warnings.add(message)
        log_warn(message)


# ============================================================
# Authoritative profile registry
# ============================================================
# The server owns the compliance rules. Registered programmes are resolved from
# this server-side copy so a client cannot smuggle in altered rule VALUES (e.g. a
# forgiving head size or an oversized canvas). data/profiles.json is generated
# from src/rules.js and is the authoritative source.
PROFILE_REGISTRY = {}


def load_profile_registry():
    registry = {}
    path = ROOT / "data" / "profiles.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("profiles.json is not a JSON array")
        for entry in raw:
            if isinstance(entry, dict) and entry.get("id"):
                registry[entry["id"]] = entry
    except Exception as error:
        print(f"[kvnp] Could not load profile registry from {path}: {error}", file=sys.stderr, flush=True)
    return registry


PROFILE_REGISTRY = load_profile_registry()


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def enforce_profile_bounds(profile):
    """Clamp/validate the safety-critical fields of a resolved profile. Raises
    ValueError('Invalid profile: <reason>') on any violation. This guards against
    crash / DoS vectors (huge canvases, non-numeric head geometry) regardless of
    whether the profile came from the registry or a lenient client payload."""
    output = profile.get("output")
    if not isinstance(output, dict):
        raise ValueError("Invalid profile: output missing.")
    for key in ("widthPx", "heightPx"):
        if output.get(key) is None:
            raise ValueError(f"Invalid profile: output.{key} missing.")
        try:
            value = int(output[key])
        except (TypeError, ValueError):
            raise ValueError(f"Invalid profile: output.{key} is not an integer.")
        if value < 16 or value > 5000:
            raise ValueError(f"Invalid profile: output.{key} out of range (16-5000).")
        output[key] = value
    if output["widthPx"] * output["heightPx"] > 30_000_000:
        raise ValueError("Invalid profile: output canvas exceeds pixel limit.")

    head = profile.get("head")
    if not isinstance(head, dict):
        raise ValueError("Invalid profile: head missing.")
    target = head.get("targetPercent")
    if not _is_number(target) or not (0 < target <= 100):
        raise ValueError("Invalid profile: head.targetPercent out of range (0-100].")
    min_percent = head.get("minPercent")
    max_percent = head.get("maxPercent")
    if min_percent is not None and max_percent is not None:
        if not _is_number(min_percent) or not _is_number(max_percent):
            raise ValueError("Invalid profile: head.minPercent/maxPercent must be numeric.")
        if min_percent > max_percent:
            raise ValueError("Invalid profile: head.minPercent exceeds head.maxPercent.")
    top_margin = head.get("topMarginPercent")
    if top_margin is not None:
        if not _is_number(top_margin) or not (-10 <= top_margin <= 60):
            raise ValueError("Invalid profile: head.topMarginPercent out of range (-10 to 60).")


def resolve_profile(client_profile):
    """Resolve a client-supplied profile against the authoritative registry.

    Registered programmes (by id) are replaced by a deep copy of the server-side
    profile so client-supplied RULE VALUES are ignored. Unregistered ids fall
    through unchanged (lenient path so existing test tools keep working). Safety
    bounds are ALWAYS enforced. Returns (profile, meta)."""
    if not isinstance(client_profile, dict):
        raise ValueError("Invalid profile payload.")
    pid = client_profile.get("id")
    if pid in PROFILE_REGISTRY:
        profile = copy.deepcopy(PROFILE_REGISTRY[pid])
        authoritative = True
    else:
        profile = client_profile
        authoritative = False
    enforce_profile_bounds(profile)
    meta = {"authoritative": authoritative, "requestedId": pid, "resolvedId": profile.get("id")}
    return profile, meta


app = FastAPI(title="KVNP Holdings Inc Passport Photo Studio")
app.mount("/src", StaticFiles(directory=ROOT / "src"), name="src")
app.mount("/screenshots", StaticFiles(directory=ROOT / "screenshots"), name="screenshots")
app.mount("/docs", StaticFiles(directory=ROOT / "docs"), name="docs")


# ============================================================
# Accounts / sessions (local SQLite, signed session cookie)
# ============================================================
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "kvnp.db"
SECRET_PATH = DATA_DIR / "secret.key"
SESSION_COOKIE = "kvnp_session"
SESSION_TTL = 60 * 60 * 24 * 30  # 30 days
PBKDF2_ROUNDS = 200_000


def get_secret():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_PATH.exists():
        return SECRET_PATH.read_bytes()
    secret = secrets.token_bytes(32)
    SECRET_PATH.write_bytes(secret)
    return secret


SESSION_SECRET = get_secret()


def db_connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                pw_hash TEXT NOT NULL,
                pw_salt TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )


init_db()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return digest.hex(), salt


def sign_session(user_id):
    issued = int(time.time())
    payload = f"{user_id}.{issued}".encode("utf-8")
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(SESSION_SECRET, body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def verify_session(token):
    if not token or token.count(".") != 1:
        return None
    body, signature = token.split(".", 1)
    try:
        # body.encode('ascii') is inside the try so a non-ASCII cookie yields a
        # clean null user (logged-out), never an unhandled 500.
        expected = hmac.new(SESSION_SECRET, body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = body + "=" * (-len(body) % 4)
        user_id, issued = base64.urlsafe_b64decode(padded).decode("utf-8").split(".")
        if int(time.time()) - int(issued) > SESSION_TTL:
            return None
        return int(user_id)
    except Exception:
        return None


def user_public(row):
    return {"id": row["id"], "email": row["email"], "name": row["name"] or row["email"].split("@")[0]}


def current_user(request):
    user_id = verify_session(request.cookies.get(SESSION_COOKIE))
    if user_id is None:
        return None
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return user_public(row) if row else None


def set_session_cookie(response, user_id):
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(user_id),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        path="/",
    )


@app.post("/api/auth/signup")
async def auth_signup(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body."}, status_code=422)
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    name = str(body.get("name", "")).strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return JSONResponse({"ok": False, "error": "Enter a valid email address."}, status_code=422)
    if len(password) < 6:
        return JSONResponse({"ok": False, "error": "Password must be at least 6 characters."}, status_code=422)

    pw_hash, pw_salt = hash_password(password)
    try:
        with db_connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, name, pw_hash, pw_salt, created_at) VALUES (?, ?, ?, ?, ?)",
                (email, name or None, pw_hash, pw_salt, int(time.time())),
            )
            user_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.IntegrityError:
        return JSONResponse({"ok": False, "error": "An account with this email already exists."}, status_code=409)

    response = JSONResponse({"ok": True, "user": user_public(row)})
    set_session_cookie(response, row["id"])
    return response


@app.post("/api/auth/login")
async def auth_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body."}, status_code=422)
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    # One generic response + a dummy compare when the user is missing, so neither
    # the message nor the timing reveals whether an email is registered.
    salt = row["pw_salt"] if row else "0" * 32
    expected = row["pw_hash"] if row else "0" * 64
    candidate, _ = hash_password(password, salt)
    if row is None or not hmac.compare_digest(candidate, expected):
        return JSONResponse({"ok": False, "error": "Invalid email or password."}, status_code=401)

    response = JSONResponse({"ok": True, "user": user_public(row)})
    set_session_cookie(response, row["id"])
    return response


@app.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/auth/me")
def auth_me(request: Request):
    return {"ok": True, "user": current_user(request)}


@app.get("/")
def index():
    landing = ROOT / "landing.html"
    if landing.exists():
        return FileResponse(landing)
    return FileResponse(ROOT / "index.html")


@app.get("/app")
def app_page():
    return FileResponse(ROOT / "index.html")


@app.get("/studio")
def studio_page():
    return FileResponse(ROOT / "index.html")


@app.get("/api/profiles")
def list_profiles():
    return {"ok": True, "profiles": list(PROFILE_REGISTRY.values()), "count": len(PROFILE_REGISTRY)}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": SERVER_VERSION,
        "processor": "python-mediapipe",
        "faceMesh": True,
        "selfieSegmentation": True,
        "realEsrgan": real_esrgan_ready(),
        "gfpgan": gfpgan_ready(),
        "modnet": modnet_active(),
        "guidedFilter": HAS_GUIDED_FILTER,
        "models": model_inventory(),
    }


@app.post("/api/process")
async def process_photo(
    image: UploadFile = File(...),
    profile: str = Form(...),
    options: str = Form("{}"),
):
    try:
        try:
            profile_data = json.loads(profile)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON in profile.")
        try:
            option_data = json.loads(options)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON in options.")
        image_bytes = await image.read()
        result = process_image(image_bytes, profile_data, option_data)
        return JSONResponse(result)
    except ValueError as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=422)
    except Exception:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": "Processing failed. See server log."}, status_code=500)


@app.post("/api/analyze")
async def analyze_output(image: UploadFile = File(...), profile: str = Form(...), options: str = Form("{}")):
    """Re-run the pixel-dependent compliance checks on an adjusted output image so
    the analysis updates live as the operator tunes the photo."""
    try:
        try:
            profile_data = json.loads(profile)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON in profile.")
        try:
            option_data = json.loads(options)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON in options.")
        resolved_profile, _ = resolve_profile(profile_data)
        final = decode_image(await image.read())
        background_replaced = bool(option_data.get("backgroundReplaced", True))
        output_bytes = int(option_data.get("outputBytes") or 0)
        checks = recompute_quality_checks(final, resolved_profile, background_replaced, output_bytes)
        return JSONResponse({"ok": True, "checks": checks})
    except ValueError as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=422)
    except Exception:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": "Analyze failed. See server log."}, status_code=500)


@app.post("/api/print-sheet")
async def print_sheet(image: UploadFile = File(...), spec: str = Form("{}")):
    try:
        try:
            spec_data = json.loads(spec)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON in spec.")
        photo = decode_image(await image.read())
        sheet, layout = build_print_sheet(photo, spec_data)
        sheet_bytes = set_jpeg_dpi(encode_jpeg_bytes(sheet, 94), layout["dpi"])
        return JSONResponse(
            {
                "ok": True,
                "sheetDataUrl": data_url(sheet_bytes, "image/jpeg"),
                "layout": layout,
                "bytes": len(sheet_bytes),
            }
        )
    except ValueError as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=422)
    except Exception:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": "Print sheet failed. See server log."}, status_code=500)


def process_image(image_bytes, profile, options):
    # Resolve against the authoritative registry (and enforce safety bounds)
    # before any pixel work, so /api/process and any direct caller are covered.
    profile, profile_authority = resolve_profile(profile)
    original_source = decode_image(image_bytes)
    has_manual = isinstance(options.get("manualFace"), dict)
    # Auto-correction is identity-preserving only: geometry (straighten) and tone
    # (exposure/white-balance). It is applied even under manual head placement so
    # the slider coordinate frame stays consistent with the corrected output;
    # manualFace overrides only the head position, never the pixels.
    auto_correct = bool(options.get("autoCorrect", True))
    # Country law: the selected programme's allowedEdits gates every correction,
    # REGARDLESS of what the client asked for. Clamped requests are reported so
    # the UI can say "disabled by <country> policy" instead of silently ignoring.
    allowed = profile.get("allowedEdits") or {}
    policy_clamped = []

    def permit(kind, requested):
        if not requested:
            return False
        if allowed.get(kind, True) is False:
            policy_clamped.append(kind)
            return False
        return True

    do_straighten = auto_correct and permit("straighten", bool(options.get("autoStraighten", True)))
    do_tone = auto_correct and permit("tone", bool(options.get("autoTone", True)))
    corrections = []

    # Detect on the ORIGINAL capture first. Capture-quality gates (pose, lighting,
    # focus, clipping) must reflect the photo as taken, never the corrected
    # artifact - otherwise a retake-worthy capture could be marked "ready".
    mp_image, landmarks, face = detect_face(original_source)
    original_face = dict(face)

    source = original_source
    if do_tone:
        source, tone_corrections = auto_tone_correct(source)
        corrections.extend(tone_corrections)
        mp_image = build_mp_image(source)

    if do_straighten:
        source, mp_image, landmarks, face, straighten = auto_straighten_source(source, landmarks, face)
        if straighten:
            corrections.append(straighten)

    height, width = source.shape[:2]

    # Identity-preserving facial corrections (even lighting + red-eye) on the face
    # region, and glasses-glare measurement for the compliance check.
    glare_fraction = glasses_glare_fraction(source, landmarks, width, height)
    if auto_correct and permit("lighting", bool(options.get("autoLighting", True))):
        source, facial_corrections = apply_facial_corrections(source, landmarks, face, width, height)
        if facial_corrections:
            corrections.extend(facial_corrections)
            mp_image = build_mp_image(source)

    if has_manual:
        face = apply_manual_face(face, options["manualFace"])
    face["glareFraction"] = round(float(glare_fraction), 4)

    background_rgb = parse_color(options.get("backgroundColor") or profile.get("automation", {}).get("backgroundColor") or "#ffffff")
    replace_background = permit("background", bool(options.get("backgroundReplaced", profile.get("automation", {}).get("backgroundReplacement", True))))
    enhance = permit("enhance", bool(options.get("enhanceOutput", profile.get("automation", {}).get("enhanceOutput", True))))
    enhancement_mode = str(options.get("enhancementMode") or profile.get("automation", {}).get("enhancementMode") or "studio")
    if enhancement_mode == "strong":
        # AI face restoration is rejected by every supported authority.
        # No shipped profile permits it, so "strong" always downgrades to
        # "studio" with a disclosed rescue clamp - unconditionally.
        enhancement_mode = "studio"
        policy_clamped.append("rescue")

    # Always estimate the matte: it yields a real crown for accurate head sizing,
    # and is reused for background replacement when that is enabled.
    matte, matte_engine = build_person_mask(mp_image, source, face, True, width, height)
    if matte is not None and not has_manual:
        face = refine_head_from_matte(face, matte, width, height)

    # When the background is replaced we can pad the canvas with background to
    # compose exactly to spec (head size + margins) even from a tightly-framed
    # source; otherwise the crop must fit within the source pixels.
    can_pad = replace_background and matte is not None
    crop = calculate_crop(width, height, face, profile, allow_pad=can_pad)

    if replace_background and matte is not None:
        background_cleanup = str(options.get("backgroundCleanup") or "balanced")
        composite_matte = apply_background_cleanup(matte, background_cleanup)
        mask_stats = describe_mask(composite_matte, face, width, height, matte_engine)
        edited = composite_background(source, composite_matte, background_rgb)
        pad_color = background_rgb
    else:
        mask_stats = describe_mask(None, face, width, height, "unavailable" if replace_background else "disabled")
        edited = source.copy()
        pad_color = None
    final = crop_and_resize(edited, crop, profile["output"]["widthPx"], profile["output"]["heightPx"], pad_color=pad_color)
    if enhance:
        final = enhance_passport_photo(final, enhancement_mode)
    # Stamp the print DPI into the JFIF metadata so labs print at the physical
    # size the programme requires (losslessly, after size-targeting).
    output_spec = profile["output"]
    if output_spec.get("printWidthMm"):
        dpi_final = round(output_spec["widthPx"] / (output_spec["printWidthMm"] / 25.4))
    else:
        dpi_final = 300
    final_bytes = set_jpeg_dpi(encode_jpeg(final, profile), dpi_final)
    overlay = build_overlay(source, landmarks, crop)
    overlay_bytes = encode_jpeg_bytes(overlay, 88)
    # "Before": the original capture framed to the same output size with no
    # correction/matte/enhancement, for an honest before/after comparison.
    original_height, original_width = original_source.shape[:2]
    before_crop = calculate_crop(original_width, original_height, original_face, profile)
    before = crop_and_resize(original_source, before_crop, profile["output"]["widthPx"], profile["output"]["heightPx"])
    before_bytes = encode_jpeg_bytes(before, 88)
    source_stats = image_stats(original_source)
    face_source = extract_face_quality_region(original_source, original_face)
    face_source_stats = image_stats(face_source)
    face_source_stats["focus"] = face_focus_score(face_source)
    final_stats = image_stats(final)
    final_stats["focus"] = output_focus_score(final)
    _ofs = output_face_stats(final)
    final_stats["faceLuma"] = _ofs["luma"]
    final_stats["faceContrast"] = _ofs["contrast"]
    final_background_stats = background_stats(final, profile, replace_background)
    source_quality = build_source_quality(
        original_source,
        original_face,
        profile,
        source_stats,
        face_source_stats,
        len(image_bytes),
        replace_background,
        mask_stats,
        corrections,
    )
    checks = build_checks(
        face,
        crop,
        profile,
        final_stats,
        final_background_stats,
        len(final_bytes),
        replace_background,
        mask_stats,
        enhance,
        enhancement_mode,
        corrections,
    )
    pipeline = build_pipeline_report(replace_background, mask_stats, enhance, enhancement_mode)
    decision = build_decision(source_quality, checks, pipeline)

    return {
        "ok": True,
        "processor": "python-mediapipe",
        "finalDataUrl": data_url(final_bytes, "image/jpeg"),
        "beforeDataUrl": data_url(before_bytes, "image/jpeg"),
        "overlayDataUrl": data_url(overlay_bytes, "image/jpeg"),
        "face": face,
        "crop": crop,
        "sourceQuality": source_quality,
        "pipeline": pipeline,
        "decision": decision,
        "matte": mask_stats,
        "checks": checks,
        "corrections": corrections,
        "policyClamped": policy_clamped,
        "allowedEdits": allowed,
        "profileAuthority": profile_authority,
        "outputBytes": len(final_bytes),
        "source": {"width": width, "height": height},
    }


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_MEGAPIXELS = 40.0
MAX_WORK_SIDE = 4000  # downscale very large inputs before the heavy CV/ML stages

# Refuse decompression-bomb images (Pillow's own guard only trips ~178 MP).
Image.MAX_IMAGE_PIXELS = int(MAX_MEGAPIXELS * 1_000_000)


def decode_image(image_bytes):
    if not image_bytes:
        raise ValueError("Empty upload.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Image is too large (max 25 MB).")
    try:
        pil = Image.open(io.BytesIO(image_bytes))
        pil.verify()  # detect truncated/bomb images before full decode
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Image.DecompressionBombError as error:
        raise ValueError("Image resolution is too high (max 40 MP).") from error
    except Exception as error:
        raise ValueError("Could not read that file as an image.") from error

    if (pil.width * pil.height) > MAX_MEGAPIXELS * 1_000_000:
        raise ValueError("Image resolution is too high (max 40 MP).")

    image = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    # Bound the working resolution so a single huge image can't pin the worker.
    longest = max(image.shape[0], image.shape[1])
    if longest > MAX_WORK_SIDE:
        scale = MAX_WORK_SIDE / float(longest)
        image = cv2.resize(image, (int(image.shape[1] * scale), int(image.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    return image


def get_landmarks(face_landmarks, width, height):
    return [
        {
            "x": float(point.x * width),
            "y": float(point.y * height),
            "z": float(point.z),
        }
        for point in face_landmarks
    ]


def measure_face(points, face_count):
    oval = np.array([[points[index]["x"], points[index]["y"]] for index in FACE_OVAL], dtype=np.float32)
    min_x, min_y = oval.min(axis=0)
    max_x, max_y = oval.max(axis=0)
    chin = points[CHIN]
    forehead = points[FOREHEAD]
    left_eye = points[LEFT_EYE]
    right_eye = points[RIGHT_EYE]
    nose = points[NOSE_TIP]
    mouth_upper = points[MOUTH_UPPER]
    mouth_lower = points[MOUTH_LOWER]
    mesh_height = float(max_y - min_y)
    chin_to_forehead = abs(chin["y"] - forehead["y"])
    head_height = max(chin_to_forehead * 1.18, mesh_height * 1.08)
    face_width = float(max_x - min_x)
    center_x = float((min_x + max_x) / 2)
    center_y = float(chin["y"] - head_height / 2)
    roll = math.degrees(math.atan2(right_eye["y"] - left_eye["y"], right_eye["x"] - left_eye["x"]))
    yaw_proxy = ((nose["x"] - center_x) / max(1.0, face_width)) * 100
    mouth_gap = (distance(mouth_upper, mouth_lower) / max(1.0, head_height)) * 100

    # Eye-aspect-ratio: eyelid gap relative to eye width, averaged over both eyes.
    # Open eyes ~0.22-0.40; closed/squinting drops below ~0.15.
    left_ear = distance(points[LEFT_EYE_TOP], points[LEFT_EYE_BOTTOM]) / max(1.0, distance(points[LEFT_EYE], points[LEFT_EYE_INNER]))
    right_ear = distance(points[RIGHT_EYE_TOP], points[RIGHT_EYE_BOTTOM]) / max(1.0, distance(points[RIGHT_EYE], points[RIGHT_EYE_INNER]))
    eye_openness = round(float((left_ear + right_ear) / 2.0), 3)

    return {
        "source": "python-mediapipe-facemesh",
        "faceCount": face_count,
        "centerX": round(center_x, 2),
        "centerY": round(center_y, 2),
        "headHeight": round(float(head_height), 2),
        "faceWidth": round(face_width, 2),
        "rollDegrees": round(float(roll), 2),
        "yawProxy": round(float(yaw_proxy), 2),
        "eyeY": round((left_eye["y"] + right_eye["y"]) / 2.0, 2),
        "mouthGapPercent": round(float(mouth_gap), 2),
        "eyeOpenness": eye_openness,
        "bounds": {
            "minX": round(float(min_x), 2),
            "minY": round(float(min_y), 2),
            "maxX": round(float(max_x), 2),
            "maxY": round(float(max_y), 2),
            "width": round(float(max_x - min_x), 2),
            "height": round(float(max_y - min_y), 2),
        },
    }


def refine_head_from_matte(face, mask, width, height):
    """Measure the true crown (top of head/hair) from the person matte instead of
    extrapolating it from facial landmarks. Head height = chin-to-crown then
    reflects reality (tall/voluminous hair, head coverings, bald heads), which is
    the single most-rejected passport attribute. Falls back to the landmark
    estimate if the matte is missing or implausible.
    """
    if mask is None:
        return face
    mask = np.asarray(mask, dtype=np.float32)
    head = float(face["headHeight"])
    chin_y = float(face["centerY"]) + head / 2.0
    cx = float(face["centerX"])
    x1 = int(clamp(cx - head * 0.5, 0, width - 1))
    x2 = int(clamp(cx + head * 0.5, x1 + 1, width))
    band = (mask[:, x1:x2] > 0.5)
    band_width = max(1, x2 - x1)
    rows = np.where(band.sum(axis=1) > band_width * 0.15)[0]
    if rows.size == 0:
        return face
    crown_y = float(rows.min())
    new_head = chin_y - crown_y
    # Sanity: crown above chin, within a plausible range of the landmark estimate.
    if crown_y >= chin_y or new_head < head * 0.7 or new_head > head * 1.9:
        return face
    refined = dict(face)
    refined["headHeight"] = round(new_head, 2)
    refined["centerY"] = round(chin_y - new_head / 2.0, 2)
    refined["headSource"] = "matte-crown"
    return refined


def calculate_crop(width, height, face, profile, allow_pad=False):
    aspect = profile["output"]["widthPx"] / profile["output"]["heightPx"]
    target_head_ratio = profile["head"]["targetPercent"] / 100
    crop_height = face["headHeight"] / target_head_ratio
    crop_width = crop_height * aspect

    head_top = face["centerY"] - face["headHeight"] / 2
    eye_rule = profile["head"].get("eye")
    eye_y = face.get("eyeY")

    def vertical_top(ch):
        # When the programme has an eye-height rule (a hard government requirement,
        # e.g. US: eyes 28-35mm from the bottom), compose so the eyes land at the
        # eye target and let the top margin fall out - the crop can never satisfy a
        # fixed top margin AND an eye line AND a head size at once, and the eye line
        # is the rule that actually gets checked. Fall back to the top-margin target
        # for programmes without an eye rule.
        if eye_rule and eye_y is not None:
            target = eye_rule.get("targetFromTopPercent")
            if target is None:
                target = (eye_rule.get("fromTopMinPercent", 33) + eye_rule.get("fromTopMaxPercent", 45)) / 2.0
            top = eye_y - ch * (target / 100.0)
            if not allow_pad:
                # Without padding we cannot invent headroom, so never let the crown
                # clip: keep at least a sliver of margin above the top of the head.
                top = min(top, head_top - ch * 0.015)
            return top
        return head_top - ch * (profile["head"]["topMarginPercent"] / 100)

    crop_x = face["centerX"] - crop_width / 2
    crop_y = vertical_top(crop_height)

    if allow_pad:
        # Compose to spec exactly; the crop may extend past the source and will be
        # padded with the (replaced) background, so head size and margins are met
        # even when the source was framed too tightly. (Studio-style re-matting.)
        return {
            "x": round(float(crop_x), 2),
            "y": round(float(crop_y), 2),
            "width": round(float(crop_width), 2),
            "height": round(float(crop_height), 2),
            "padded": True,
        }

    # No padding available (background not replaced): fit + clamp to the source.
    if crop_width > width:
        crop_width = width
        crop_height = crop_width / aspect
    if crop_height > height:
        crop_height = height
        crop_width = crop_height * aspect
    crop_x = face["centerX"] - crop_width / 2
    crop_y = vertical_top(crop_height)
    crop_x = clamp(crop_x, 0, width - crop_width)
    crop_y = clamp(crop_y, 0, height - crop_height)

    return {
        "x": round(float(crop_x), 2),
        "y": round(float(crop_y), 2),
        "width": round(float(crop_width), 2),
        "height": round(float(crop_height), 2),
        "padded": False,
    }


def apply_manual_face(face, manual_face):
    updated = dict(face)
    for key in ("centerX", "centerY", "headHeight", "faceWidth"):
        if key in manual_face:
            try:
                updated[key] = round(float(manual_face[key]), 2)
            except (TypeError, ValueError):
                pass
    updated["source"] = "python-mediapipe-manual-override"
    return updated


def build_mp_image(source_bgr):
    rgb = cv2.cvtColor(ensure_bgr(source_bgr), cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)


def detect_face(source_bgr):
    """Detect the primary face and return ``(mp_image, landmarks, face)``.

    Raises ValueError when no face is found so the caller can surface a clear
    retake message.
    """
    height, width = source_bgr.shape[:2]
    mp_image = build_mp_image(source_bgr)
    result = face_landmarker.detect(mp_image)
    faces = result.face_landmarks or []
    if not faces:
        raise ValueError("No face detected. Use a clear front-facing portrait.")
    landmarks = get_landmarks(faces[0], width, height)
    face = measure_face(landmarks, len(faces))
    return mp_image, landmarks, face


def rotate_image(image, angle_deg, center):
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((float(center[0]), float(center[1])), float(angle_deg), 1.0)
    return cv2.warpAffine(
        ensure_bgr(image),
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def auto_straighten_source(source_bgr, landmarks, face):
    """Rotate the source so the eye line is level (identity-preserving geometry).

    Returns ``(image, mp_image, landmarks, face, correction|None)``. A tilt is
    only corrected when it is meaningful but still plausibly a level head that
    was photographed crooked (not an extreme pose). The result is re-detected
    and kept only if the residual tilt actually improved, so a wrong assumption
    can never make the photo worse.
    """
    roll = float(face.get("rollDegrees", 0.0))
    if abs(roll) < 1.5 or abs(roll) > 18.0:
        return source_bgr, build_mp_image(source_bgr), landmarks, face, None

    center = (float(face["centerX"]), float(face["centerY"]))
    rotated = rotate_image(source_bgr, roll, center)
    try:
        mp_image, new_landmarks, new_face = detect_face(rotated)
    except ValueError:
        return source_bgr, build_mp_image(source_bgr), landmarks, face, None

    new_roll = float(new_face.get("rollDegrees", roll))
    if abs(new_roll) >= abs(roll) - 0.5:
        # No real improvement (or rotation hurt detection); keep the original.
        return source_bgr, build_mp_image(source_bgr), landmarks, face, None

    correction = {
        "id": "straighten",
        "label": "Auto-straighten",
        "detail": f"levelled head tilt {abs(roll):.1f} deg -> {abs(new_roll):.1f} deg",
        "applied": True,
    }
    return rotated, mp_image, new_landmarks, new_face, correction


def auto_tone_correct(source_bgr):
    """Gentle, identity-preserving exposure + white-balance normalization.

    Returns ``(image, corrections)``. Only acts when there is a visible colour
    cast or the image is clearly under/over-exposed, and uses bounded gains so
    skin tone and likeness are preserved.
    """
    image = ensure_bgr(source_bgr)
    corrections = []

    means = image.reshape(-1, 3).astype(np.float32).mean(axis=0)
    spread = (float(means.max()) - float(means.min())) / (float(means.mean()) + 1e-6)
    if spread > 0.10:
        image = gray_world_balance(image)
        corrections.append(
            {"id": "white_balance", "label": "Auto white balance", "detail": "neutralised colour cast", "applied": True}
        )

    luma = float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).mean())
    if luma < 100.0 or luma > 185.0:
        # Gamma on the LAB L channel brightens shadows/midtones toward the target
        # without a linear multiply that would blow highlights to pure white.
        # (gamma maps [0,1] -> [0,1], so white stays white - no new clipping - and
        # chroma is untouched, preserving skin tone and likeness.)
        normalized = max(1.0, luma) / 255.0
        target = 140.0 / 255.0
        gamma = clamp(math.log(target) / math.log(normalized), 0.45, 2.2)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = np.power(lab[:, :, 0].astype(np.float32) / 255.0, gamma) * 255.0
        lab[:, :, 0] = np.clip(l_channel, 0, 255).astype(np.uint8)
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        new_luma = float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).mean())
        corrections.append(
            {
                "id": "exposure",
                "label": "Auto-exposure",
                "detail": f"brightness {luma:.0f} -> {new_luma:.0f}",
                "applied": True,
            }
        )

    return ensure_bgr(image), corrections


def face_oval_mask(landmarks, width, height, feather=None):
    """Feathered 0..1 mask of the face oval (for face-only corrections)."""
    polygon = np.array([[int(landmarks[i]["x"]), int(landmarks[i]["y"])] for i in FACE_OVAL], dtype=np.int32)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(polygon), 255)
    if feather is None:
        feather = max(3.0, (polygon[:, 0].max() - polygon[:, 0].min()) * 0.06)
    mask = cv2.GaussianBlur(mask, (0, 0), feather)
    return mask.astype(np.float32) / 255.0


def even_face_lighting(image, landmarks, face, width, height):
    """Flatten harsh shadows/hotspots ACROSS the face (illumination only), keeping
    fine detail and identity. Returns (image, applied)."""
    image = ensure_bgr(image)
    mask = face_oval_mask(landmarks, width, height)
    if mask.sum() < 10:
        return image, False
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_channel = lab[:, :, 0]
    face_w = max(12.0, float(face.get("faceWidth", width * 0.3)))
    illum = cv2.GaussianBlur(l_channel, (0, 0), max(6.0, face_w / 3.5))
    mean_illum = float((illum * mask).sum() / max(1e-6, mask.sum()))
    unevenness = float(np.sqrt(((illum - mean_illum) ** 2 * mask).sum() / max(1e-6, mask.sum())))
    if unevenness < 11.0:
        return image, False  # lighting is already reasonably even; leave it
    lab[:, :, 0] = np.clip(l_channel - (illum - mean_illum) * 0.55 * mask, 0, 255)
    return ensure_bgr(cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)), True


def remove_red_eye(image, landmarks, face, width, height):
    """Desaturate red-eye pupils using the eye landmarks. Returns (image, applied)."""
    image = ensure_bgr(image).copy()
    applied = False
    for outer, inner in ((LEFT_EYE, LEFT_EYE_INNER), (RIGHT_EYE, RIGHT_EYE_INNER)):
        p1, p2 = landmarks[outer], landmarks[inner]
        cx = (p1["x"] + p2["x"]) / 2.0
        cy = (p1["y"] + p2["y"]) / 2.0
        radius = max(2.0, distance(p1, p2) * 0.25)  # pupil-sized, not the whole eye
        x1 = int(clamp(cx - radius, 0, width - 1))
        x2 = int(clamp(cx + radius, x1 + 1, width))
        y1 = int(clamp(cy - radius, 0, height - 1))
        y2 = int(clamp(cy + radius, y1 + 1, height))
        roi = image[y1:y2, x1:x2].astype(np.float32)
        blue, green, red = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
        other = np.maximum(green, blue)
        # True red-eye is a BRIGHT red pupil glow (flash): strongly red-dominant
        # and luminous. Strict thresholds avoid touching natural iris/skin tones.
        red_pixels = (red >= 140) & ((red - other) >= 70) & (red >= 1.85 * (other + 1))
        area = red_pixels.size
        count = int(red_pixels.sum())
        if area > 0 and 0.05 * area <= count <= 0.5 * area:
            roi[:, :, 2][red_pixels] = (other * 0.6)[red_pixels]
            image[y1:y2, x1:x2] = np.clip(roi, 0, 255).astype(np.uint8)
            applied = True
    return image, applied


def glasses_glare_fraction(image, landmarks, width, height):
    """Fraction of blown-highlight (specular) pixels over the eyes - a proxy for
    glasses glare / a flash hotspot on the lenses (a common rejection)."""
    xs = [landmarks[i]["x"] for i in (LEFT_EYE, LEFT_EYE_INNER, RIGHT_EYE, RIGHT_EYE_INNER)]
    ys = [landmarks[i]["y"] for i in (LEFT_EYE_TOP, LEFT_EYE_BOTTOM, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM)]
    pad = (max(xs) - min(xs)) * 0.12
    x1 = int(clamp(min(xs) - pad, 0, width - 1))
    x2 = int(clamp(max(xs) + pad, x1 + 1, width))
    y1 = int(clamp(min(ys) - pad, 0, height - 1))
    y2 = int(clamp(max(ys) + pad, y1 + 1, height))
    region = image[y1:y2, x1:x2]
    if region.size == 0:
        return 0.0
    gray = cv2.cvtColor(ensure_bgr(region), cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray >= 248))


def apply_facial_corrections(image, landmarks, face, width, height):
    """Identity-preserving facial fixes: even out lighting + remove red-eye. Also
    measures glasses-glare for the compliance check. Returns (image, corrections)."""
    corrections = []
    image, lit = even_face_lighting(image, landmarks, face, width, height)
    if lit:
        corrections.append({"id": "even_lighting", "label": "Even out face lighting", "detail": "reduced facial shadows/hotspots", "applied": True})
    image, red = remove_red_eye(image, landmarks, face, width, height)
    if red:
        corrections.append({"id": "red_eye", "label": "Red-eye removal", "detail": "neutralised red pupils", "applied": True})
    return image, corrections


def build_person_mask(mp_image, source_bgr, face, enabled, width, height):
    """Return ``(alpha_mask, engine_label)`` for the person matte.

    Prefers MODNet portrait matting (when ``models/modnet.onnx`` is present)
    and otherwise falls back to the MediaPipe selfie segmenter. Both paths are
    cleaned to a single connected subject (no stray background islands) and
    edge-refined with a guided filter so hair and shoulders follow the real
    image rather than a blocky cutout.

    ``engine`` is ``"disabled"`` when replacement is off, ``"unavailable"`` when
    replacement was requested but no matte engine produced a mask (so the
    operator is told the photo was left unchanged, not that it was skipped).
    """
    if not enabled:
        return None, "disabled"

    rgb = cv2.cvtColor(ensure_bgr(source_bgr), cv2.COLOR_BGR2RGB)
    matte = run_modnet_matte(rgb, width, height)
    if matte is not None:
        engine = "MODNet Portrait Matting"
        mask = matte
    else:
        engine = "MediaPipe Image Segmenter"
        mask = run_selfie_segmenter(mp_image, width, height)
        if mask is None:
            return None, "unavailable"
        mask = clean_coarse_matte(mask)

    mask = finalize_matte(mask, source_bgr, face, width, height)
    return np.clip(mask, 0, 1).astype(np.float32), engine


def finalize_matte(mask, source_bgr, face, width, height):
    """Single-subject cleanup + edge refinement at a capped working resolution.

    MODNet runs at ~512px but the alpha is upsampled to full source resolution;
    running the guided filter / dilation / connected-components on a 12 MP frame
    is needlessly slow, so the heavy steps run on a downscaled copy and only the
    final alpha is upsampled back for compositing.
    """
    scale = min(1.0, MATTE_WORK_MAX_SIDE / max(width, height))
    if scale < 1.0:
        work_w = max(1, int(round(width * scale)))
        work_h = max(1, int(round(height * scale)))
        small = cv2.resize(mask, (work_w, work_h), interpolation=cv2.INTER_LINEAR)
        guide = cv2.resize(ensure_bgr(source_bgr), (work_w, work_h), interpolation=cv2.INTER_AREA)
        small = keep_main_subject(small, scale_face(face, scale))
        small = refine_matte_edges(small, guide)
        return np.clip(cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR), 0, 1).astype(np.float32)

    mask = keep_main_subject(mask, face)
    return refine_matte_edges(mask, source_bgr)


def scale_face(face, scale):
    scaled = dict(face)
    for key in ("centerX", "centerY", "headHeight", "faceWidth"):
        value = face.get(key)
        if value is not None:
            scaled[key] = float(value) * scale
    return scaled


def run_selfie_segmenter(mp_image, width, height):
    result = image_segmenter.segment(mp_image)
    masks = result.confidence_masks or []
    if not masks:
        return None
    mask_index = 1 if len(masks) > 1 else 0
    raw = np.array(masks[mask_index].numpy_view(), dtype=np.float32).squeeze()
    if raw.shape[:2] != (height, width):
        raw = cv2.resize(raw, (width, height), interpolation=cv2.INTER_LINEAR)
    return np.clip(raw, 0, 1).astype(np.float32)


def clean_coarse_matte(mask):
    """Tidy a coarse confidence mask (MediaPipe) into a solid soft-edged matte."""
    mask = np.clip((mask - 0.16) / 0.66, 0, 1).astype(np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    solid = (mask > 0.28).astype(np.uint8)
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, kernel, iterations=2)
    solid = cv2.morphologyEx(solid, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    mask = np.maximum(mask, solid.astype(np.float32) * 0.96)
    mask = cv2.medianBlur((mask * 255).astype(np.uint8), 3).astype(np.float32) / 255.0
    return np.clip(mask, 0, 1).astype(np.float32)


def keep_main_subject(mask, face=None):
    """Keep the person silhouette and drop disconnected background islands.

    A single-person passport photo is one connected silhouette, so stray blobs
    are almost always background bleed. We keep the component that the detected
    face actually sits in (falling back to the largest), so an inverted or weak
    matte whose largest ``>0.5`` blob is the *background* cannot silently erase
    the person. The kept region is dilated by a small (bounded) edge band to
    preserve soft hair/shoulder alpha, but every *other* solid component is
    zeroed outright - so coloured bleed near the subject is still removed.
    """
    binary = (mask > 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 2:
        return mask

    height, width = mask.shape[:2]
    areas = stats[1:, cv2.CC_STAT_AREA]
    chosen = 1 + int(np.argmax(areas))
    if face is not None:
        head = max(1.0, float(face.get("headHeight", min(width, height) * 0.4)))
        fx1 = int(clamp(face["centerX"] - head * 0.4, 0, width - 1))
        fx2 = int(clamp(face["centerX"] + head * 0.4, fx1 + 1, width))
        fy1 = int(clamp(face["centerY"] - head * 0.4, 0, height - 1))
        fy2 = int(clamp(face["centerY"] + head * 0.4, fy1 + 1, height))
        face_labels = labels[fy1:fy2, fx1:fx2]
        present = face_labels[face_labels > 0]
        if present.size:
            values, counts = np.unique(present, return_counts=True)
            chosen = int(values[int(np.argmax(counts))])

    keep_core = (labels == chosen).astype(np.uint8)
    edge_band = min(24, max(6, int(round(min(height, width) * 0.02))))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (edge_band * 2 + 1, edge_band * 2 + 1))
    keep_region = cv2.dilate(keep_core, kernel, iterations=1).astype(np.float32)

    result = mask * keep_region
    other_solid = (binary == 1) & (labels != chosen)
    result[other_solid] = 0.0
    return result.astype(np.float32)


def refine_matte_edges(mask, guide_bgr):
    """Edge-align the matte to image structure (hair/shoulders) with a guided filter."""
    mask = np.clip(np.asarray(mask, dtype=np.float32).squeeze(), 0, 1)
    if HAS_GUIDED_FILTER:
        try:
            guide = ensure_bgr(guide_bgr).astype(np.float32) / 255.0
            refined = cv2.ximgproc.guidedFilter(guide=guide, src=mask, radius=9, eps=1e-4)
            refined = np.clip(refined, 0, 1)
            # Keep the confidently solid interior fully opaque after refinement.
            refined = np.where(mask > 0.95, np.maximum(refined, mask), refined)
            return refined.astype(np.float32)
        except Exception:
            pass
    return np.clip(cv2.GaussianBlur(mask, (0, 0), 2.4), 0, 1).astype(np.float32)


def modnet_ready():
    """A MODNet model file and the onnxruntime package are present (static)."""
    return bool(MODNET_MODEL_PATH.exists() and importlib.util.find_spec("onnxruntime") is not None)


def modnet_active():
    """The MODNet session actually loaded and is usable this run (runtime-honest)."""
    return get_modnet_session() is not None


def modnet_inventory_status():
    """Honest inventory status: a present-but-broken model reports 'error', not 'ready'."""
    if not modnet_ready():
        return "optional-not-installed"
    return "optional-ready" if modnet_active() else "error"


def disable_modnet(reason):
    global modnet_unavailable
    modnet_unavailable = True
    log_warn_once(f"MODNet disabled: {reason}. Using MediaPipe matting fallback.")


def get_modnet_session():
    global modnet_session, modnet_unavailable
    if modnet_session is not None:
        return modnet_session
    if modnet_unavailable or not modnet_ready():
        return None
    try:
        import onnxruntime as ort

        modnet_session = ort.InferenceSession(str(MODNET_MODEL_PATH), providers=["CPUExecutionProvider"])
    except Exception as error:
        disable_modnet(f"failed to load {MODNET_MODEL_PATH.name}: {error}")
        return None
    return modnet_session


def normalize_modnet_output(output):
    """Reduce a MODNet ONNX output to a 2-D alpha in [0, 1], tolerating common
    export variations (channel-first/last, raw logits, or a [0, 255] scale)."""
    alpha = np.squeeze(np.asarray(output, dtype=np.float32))
    if alpha.ndim == 3:
        # Pick the foreground channel from (C, H, W) or (H, W, C).
        if alpha.shape[0] <= 4 and alpha.shape[0] < alpha.shape[-1]:
            alpha = alpha[-1]
        elif alpha.shape[-1] <= 4:
            alpha = alpha[..., -1]
    if alpha.ndim != 2:
        return None
    max_value = float(alpha.max()) if alpha.size else 0.0
    min_value = float(alpha.min()) if alpha.size else 0.0
    if max_value > 1.5:
        alpha = alpha / 255.0  # likely a 0..255 export
    elif min_value < -0.01 or max_value > 1.01:
        alpha = 1.0 / (1.0 + np.exp(-np.clip(alpha, -30.0, 30.0)))  # likely raw logits
    return np.clip(alpha, 0.0, 1.0).astype(np.float32)


def run_modnet_matte(rgb, width, height, ref_size=512):
    """Run MODNet ONNX matting. Returns a full-res alpha in [0, 1] or None."""
    session = get_modnet_session()
    if session is None:
        return None
    try:
        src_h, src_w = rgb.shape[:2]
        scale = min(1.0, ref_size / max(src_h, src_w))
        # MODNet requires both input dimensions to be multiples of 32; the
        # reference implementation floors each axis after a single uniform scale.
        in_w = max(32, (int(round(src_w * scale)) // 32) * 32)
        in_h = max(32, (int(round(src_h * scale)) // 32) * 32)
        interp = cv2.INTER_AREA if in_w * in_h < src_w * src_h else cv2.INTER_LINEAR
        resized = cv2.resize(rgb, (in_w, in_h), interpolation=interp)
        tensor = resized.astype(np.float32) / 255.0
        tensor = (tensor - 0.5) / 0.5  # normalize to [-1, 1] as MODNet expects
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...].astype(np.float32)
        input_name = session.get_inputs()[0].name
        output = session.run(None, {input_name: tensor})[0]
        alpha = normalize_modnet_output(output)
        if alpha is None:
            disable_modnet(f"unexpected output shape {np.asarray(output).shape}")
            return None
        alpha = cv2.resize(alpha, (width, height), interpolation=cv2.INTER_LINEAR)
        return np.clip(alpha, 0, 1).astype(np.float32)
    except Exception as error:
        disable_modnet(f"inference error: {error}")
        return None


def describe_mask(mask, face, width, height, engine="MediaPipe Image Segmenter"):
    if mask is None:
        # Distinguish "operator turned replacement off" (review) from "replacement
        # was requested but no engine produced a matte, so the photo is unchanged"
        # (warning) - never present a failed matte as a benign disabled state.
        unavailable = engine == "unavailable"
        return {
            "available": False,
            "engine": "unavailable" if unavailable else "disabled",
            "coverage": 0,
            "faceCoverage": 0,
            "softEdgePercent": 0,
            "strayIslands": 0,
            "holePercent": 0,
            "shoulderCoverage": None,
            "status": "warning" if unavailable else "review",
            "message": (
                "matte engine unavailable; background was NOT replaced"
                if unavailable
                else "background replacement disabled"
            ),
        }

    # Run the metric ops (two connected-components passes) at a capped working
    # resolution; coverage/ratios are scale-invariant so this only bounds cost.
    mask = np.asarray(mask, dtype=np.float32).squeeze()
    scale = min(1.0, MATTE_WORK_MAX_SIDE / max(width, height))
    if scale < 1.0:
        width = max(1, int(round(width * scale)))
        height = max(1, int(round(height * scale)))
        mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)
        face = scale_face(face, scale)

    coverage = float(np.mean(mask > 0.5))
    soft_edge = float(np.mean((mask > 0.08) & (mask < 0.92)) * 100)

    head = max(1.0, float(face["headHeight"]))
    # Face-core coverage measured over a tight ELLIPSE on the forehead/cheeks/chin
    # - the region any working matte fully covers. A bounding box would include
    # background corners above the crown and beside the head, making even a
    # perfect matte read ~78% and falsely fail.
    cx = float(face["centerX"])
    cy = float(face["centerY"])
    ax = max(2.0, head * 0.33)
    ay = max(2.0, head * 0.44)
    yy, xx = np.ogrid[0:height, 0:width]
    core_ellipse = (((xx - cx) / ax) ** 2 + ((yy - cy) / ay) ** 2) <= 1.0
    core = mask[core_ellipse]
    face_coverage = float(np.mean(core > 0.45)) if core.size else 0.0

    binary = (mask > 0.5).astype(np.uint8)
    stray_islands = 0
    stray_ratio = 0.0
    hole_percent = 0.0
    if binary.any():
        count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if count > 1:
            areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
            total = float(areas.sum())
            main = float(areas.max())
            stray_islands = int((areas >= max(25.0, 0.004 * main)).sum() - 1)
            stray_ratio = float(1 - main / total) if total > 0 else 0.0
        # Holes = background components fully enclosed by the silhouette, i.e.
        # background blobs that do not touch any image border. Border-based so it
        # is correct even if the subject reaches a corner of the frame.
        inverse = (binary == 0).astype(np.uint8)
        bg_count, _, bg_stats, _ = cv2.connectedComponentsWithStats(inverse, connectivity=8)
        holes = 0
        for label in range(1, bg_count):
            bx = bg_stats[label, cv2.CC_STAT_LEFT]
            by = bg_stats[label, cv2.CC_STAT_TOP]
            bw = bg_stats[label, cv2.CC_STAT_WIDTH]
            bh = bg_stats[label, cv2.CC_STAT_HEIGHT]
            touches_border = bx == 0 or by == 0 or (bx + bw) >= width or (by + bh) >= height
            if not touches_border:
                holes += int(bg_stats[label, cv2.CC_STAT_AREA])
        person_area = float(binary.sum()) or 1.0
        hole_percent = float(holes / person_area * 100)

    # Shoulder/torso band below the chin. Only meaningful if a real band exists;
    # a 1-px sliver at the frame bottom must not trigger a false "clipped" warning.
    sb_y1 = int(clamp(face["centerY"] + head * 0.6, 0, height - 1))
    sb_x1 = int(clamp(face["centerX"] - head * 0.7, 0, width - 1))
    sb_x2 = int(clamp(face["centerX"] + head * 0.7, sb_x1 + 1, width))
    band_height = height - sb_y1
    shoulder_measurable = band_height >= max(3, int(round(head * 0.1)))
    if shoulder_measurable:
        shoulder_region = mask[sb_y1:height, sb_x1:sb_x2]
        shoulder_coverage = float(np.mean(shoulder_region > 0.5)) if shoulder_region.size else 0.0
    else:
        shoulder_coverage = None

    status = "pass"
    message = "portrait matte ready"
    if coverage < 0.08 or coverage > 0.97 or face_coverage < 0.82:
        # coverage > 0.97 means almost the whole frame reads as person, i.e. an
        # inverted/saturated matte; high-but-plausible coverage is NOT failed.
        status = "fail"
        message = "person mask is unreliable"
    elif stray_islands > 0 or hole_percent > 0.8:
        status = "warning"
        message = "matte has stray background or holes; inspect edges"
    elif coverage < 0.12 or face_coverage < 0.92 or soft_edge > 24:
        status = "warning"
        message = "matte should be reviewed around hair and shoulders"
    elif shoulder_measurable and shoulder_coverage < 0.35:
        status = "warning"
        message = "shoulders may be clipped in the matte; check framing"

    return {
        "available": True,
        "engine": engine,
        "coverage": round(coverage, 4),
        "faceCoverage": round(face_coverage, 4),
        "softEdgePercent": round(soft_edge, 2),
        "strayIslands": stray_islands,
        "strayRatio": round(stray_ratio, 4),
        "holePercent": round(hole_percent, 3),
        "shoulderCoverage": round(shoulder_coverage, 4) if shoulder_coverage is not None else None,
        "status": status,
        "message": message,
    }


def apply_background_cleanup(mask, strength):
    """Harden a person matte so faint background haze/spots snap to clean
    background, at the cost of slightly tighter hair edges. "strong" remaps the
    alpha so anything below ~0.5 becomes fully transparent (pure background),
    "max" pushes that threshold higher for a perfectly flat field.
    """
    if mask is None or strength in (None, "balanced", "soft"):
        return mask
    mask = np.asarray(mask, dtype=np.float32)
    low, high = (0.5, 0.85) if strength == "strong" else (0.62, 0.93)
    cleaned = np.clip((mask - low) / max(1e-3, high - low), 0.0, 1.0)
    # Keep confidently-solid interior fully opaque.
    cleaned = np.where(mask > 0.96, 1.0, cleaned)
    return cleaned.astype(np.float32)


def composite_background(source_bgr, mask, background_rgb):
    if mask is None:
        return ensure_bgr(source_bgr.copy())

    mask = np.asarray(mask, dtype=np.float32).squeeze()
    if mask.shape[:2] != source_bgr.shape[:2]:
        mask = cv2.resize(mask, (source_bgr.shape[1], source_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    background_bgr = np.array([background_rgb[2], background_rgb[1], background_rgb[0]], dtype=np.float32)
    alpha = mask[..., None].astype(np.float32)
    source = ensure_bgr(source_bgr).astype(np.float32)
    composed = source * alpha + background_bgr * (1 - alpha)
    return ensure_bgr(np.clip(composed, 0, 255).astype(np.uint8))


def normalize_light(image_bgr):
    image_bgr = ensure_bgr(image_bgr)
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.35, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    return cv2.convertScaleAbs(enhanced, alpha=1.02, beta=2)


def enhance_passport_photo(image_bgr, mode="studio"):
    image_bgr = ensure_bgr(image_bgr)
    mode = mode if mode in {"natural", "studio", "ai-clean", "strong"} else "ai-clean"
    if mode == "ai-clean":
        return identity_clean_enhance(image_bgr)
    if mode == "strong":
        return ai_clean_enhance(image_bgr, strength="strong", restore_face=True)

    settings = {
        "natural": {"denoise": 4, "clahe": 1.18, "detail": 0.08, "amount": 0.22, "radius": 0.9},
        "studio": {"denoise": 8, "clahe": 1.32, "detail": 0.14, "amount": 0.38, "radius": 0.9},
    }[mode]

    enhanced = gray_world_balance(image_bgr)
    enhanced = cv2.fastNlMeansDenoisingColored(
        enhanced,
        None,
        h=settings["denoise"],
        hColor=max(3, settings["denoise"] - 1),
        templateWindowSize=7,
        searchWindowSize=21,
    )
    enhanced = chroma_noise_reduction(enhanced, strength=0.35 if mode == "natural" else 0.55)
    enhanced = local_contrast(enhanced, settings["clahe"])
    enhanced = preserve_skin_tone(image_bgr, enhanced, strength=0.92)

    if mode == "studio" and hasattr(cv2, "detailEnhance"):
        detailed = cv2.detailEnhance(enhanced, sigma_s=7, sigma_r=0.08)
        enhanced = cv2.addWeighted(enhanced, 1 - settings["detail"], detailed, settings["detail"], 0)

    enhanced = edge_aware_sharpen(enhanced, amount=settings["amount"], radius=settings["radius"])
    enhanced = mild_output_curve(enhanced, mode)
    return ensure_bgr(enhanced)


def identity_clean_enhance(image_bgr):
    original = ensure_bgr(image_bgr)
    balanced = gray_world_balance(original)
    denoised = cv2.fastNlMeansDenoisingColored(
        balanced,
        None,
        h=3,
        hColor=3,
        templateWindowSize=7,
        searchWindowSize=17,
    )
    denoised = chroma_noise_reduction(denoised, strength=0.22)
    enhanced = cv2.addWeighted(original, 0.74, denoised, 0.26, 0)
    enhanced = local_contrast(enhanced, 1.08)
    enhanced = preserve_skin_tone(original, enhanced, strength=0.96)
    enhanced = edge_aware_sharpen(enhanced, amount=0.28, radius=0.72)
    return ensure_bgr(cv2.convertScaleAbs(enhanced, alpha=1.01, beta=1))


def ai_clean_enhance(image_bgr, strength="balanced", restore_face=False):
    original = ensure_bgr(image_bgr)
    strong = strength == "strong"
    denoise_h = 10 if strong else 7

    base = gray_world_balance(original)
    base = cv2.fastNlMeansDenoisingColored(
        base,
        None,
        h=denoise_h,
        hColor=max(5, denoise_h - 1),
        templateWindowSize=7,
        searchWindowSize=25,
    )
    base = chroma_noise_reduction(base, strength=0.68 if strong else 0.5)
    base = local_contrast(base, 1.25 if strong else 1.18)
    base = preserve_skin_tone(original, base, strength=0.9)

    ai_input = limit_ai_input_size(base, max_side=1120 if strong else 1024)
    restored = run_realesrgan(ai_input, model_name=REALESRGAN_MODEL_NAME, scale=4)
    if restored is None and superres is not None:
        restored = superres_refine(base)

    if restored is not None:
        restored = cv2.resize(restored, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_AREA)
        restored = preserve_skin_tone(base, restored, strength=0.88)
        blend = 0.54 if strong else 0.38
        base = cv2.addWeighted(base, 1 - blend, restored, blend, 0)

    if restore_face:
        face_restored = run_gfpgan_face_restore(base, weight=0.18)
        if face_restored is not None:
            base = cv2.addWeighted(base, 0.76, face_restored, 0.24, 0)
            base = preserve_skin_tone(image_bgr, base, strength=0.9)

    base = smooth_flat_noise(base, strength=0.5 if strong else 0.34)
    base = edge_aware_sharpen(base, amount=0.62 if strong else 0.46, radius=0.78)
    base = mild_output_curve(base, "studio")
    return ensure_bgr(base)


def limit_ai_input_size(image_bgr, max_side=1024):
    image = ensure_bgr(image_bgr)
    height, width = image.shape[:2]
    largest_side = max(width, height)
    if largest_side <= max_side:
        return image
    ratio = max_side / largest_side
    target_size = (max(1, int(round(width * ratio))), max(1, int(round(height * ratio))))
    return cv2.resize(image, target_size, interpolation=cv2.INTER_AREA)


def gray_world_balance(image_bgr):
    image = image_bgr.astype(np.float32)
    means = image.reshape(-1, 3).mean(axis=0)
    gray = means.mean()
    scale = np.clip(gray / np.maximum(means, 1.0), 0.9, 1.1)
    balanced = image * scale
    balanced = np.clip(balanced, 0, 255).astype(np.uint8)
    return cv2.addWeighted(image_bgr, 0.62, balanced, 0.38, 0)


def local_contrast(image_bgr, clip_limit):
    lab = cv2.cvtColor(ensure_bgr(image_bgr), cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def preserve_skin_tone(original_bgr, enhanced_bgr, strength=0.88):
    original_lab = cv2.cvtColor(ensure_bgr(original_bgr), cv2.COLOR_BGR2LAB)
    enhanced_lab = cv2.cvtColor(ensure_bgr(enhanced_bgr), cv2.COLOR_BGR2LAB)
    l_channel = enhanced_lab[:, :, 0]
    a_channel = cv2.addWeighted(enhanced_lab[:, :, 1], strength, original_lab[:, :, 1], 1 - strength, 0)
    b_channel = cv2.addWeighted(enhanced_lab[:, :, 2], strength, original_lab[:, :, 2], 1 - strength, 0)
    return cv2.cvtColor(cv2.merge((l_channel, a_channel, b_channel)), cv2.COLOR_LAB2BGR)


def chroma_noise_reduction(image_bgr, strength=0.55):
    image = ensure_bgr(image_bgr)
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    y_channel, cr_channel, cb_channel = cv2.split(ycrcb)
    sigma = 1.0 + float(strength) * 1.8
    cr_blur = cv2.GaussianBlur(cr_channel, (0, 0), sigmaX=sigma, sigmaY=sigma)
    cb_blur = cv2.GaussianBlur(cb_channel, (0, 0), sigmaX=sigma, sigmaY=sigma)
    cr_channel = cv2.addWeighted(cr_channel, 1 - strength, cr_blur, strength, 0)
    cb_channel = cv2.addWeighted(cb_channel, 1 - strength, cb_blur, strength, 0)
    return cv2.cvtColor(cv2.merge((y_channel, cr_channel, cb_channel)), cv2.COLOR_YCrCb2BGR)


def smooth_flat_noise(image_bgr, strength=0.45):
    image = ensure_bgr(image_bgr)
    filtered = cv2.bilateralFilter(image, d=7, sigmaColor=24 + strength * 26, sigmaSpace=8)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 110).astype(np.float32) / 255.0
    edge_mask = cv2.GaussianBlur(edges, (0, 0), 2.0)[..., None]
    flat_mask = np.clip(1.0 - edge_mask * 1.4, 0.0, 1.0) * float(strength)
    smoothed = image.astype(np.float32) * (1 - flat_mask) + filtered.astype(np.float32) * flat_mask
    return ensure_bgr(np.clip(smoothed, 0, 255).astype(np.uint8))


def unsharp_mask(image_bgr, amount=0.9, radius=1.1):
    image = ensure_bgr(image_bgr)
    sigma = max(0.4, float(radius))
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)
    sharpened = cv2.addWeighted(image, 1 + float(amount), blurred, -float(amount), 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def edge_aware_sharpen(image_bgr, amount=0.35, radius=0.9):
    image = ensure_bgr(image_bgr)
    sharpened = unsharp_mask(image, amount=amount, radius=radius)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gradient_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(gradient_x, gradient_y)
    edge_mask = np.clip((gradient - 12) / 58, 0, 1)
    edge_mask = cv2.GaussianBlur(edge_mask, (0, 0), 1.2)[..., None]
    blended = image.astype(np.float32) * (1 - edge_mask) + sharpened.astype(np.float32) * edge_mask
    return ensure_bgr(np.clip(blended, 0, 255).astype(np.uint8))


def run_realesrgan(image_bgr, model_name=REALESRGAN_MODEL_NAME, scale=2):
    exe, model_dir = get_realesrgan_runtime()
    if exe is None or model_dir is None:
        return None

    with tempfile.TemporaryDirectory(prefix="kvnp-esrgan-") as tmp_dir:
        input_path = Path(tmp_dir) / f"input-{uuid.uuid4().hex}.png"
        output_path = Path(tmp_dir) / f"output-{uuid.uuid4().hex}.png"
        if not cv2.imwrite(str(input_path), ensure_bgr(image_bgr)):
            return None
        command = [
            str(exe),
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "-n",
            model_name,
            "-m",
            str(model_dir),
            "-s",
            str(scale),
            "-f",
            "png",
        ]
        try:
            subprocess.run(
                command,
                cwd=str(exe.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=45,
                check=True,
            )
        except Exception:
            return None
        restored = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
        return ensure_bgr(restored) if restored is not None else None


def get_realesrgan_runtime():
    global realesrgan_exe, realesrgan_model_dir
    if realesrgan_exe is not None and realesrgan_model_dir is not None:
        return realesrgan_exe, realesrgan_model_dir

    candidates = list((TOOLS_DIR / "realesrgan-ncnn-vulkan").glob("**/realesrgan-ncnn-vulkan.exe"))
    exe = candidates[0] if candidates else shutil.which("realesrgan-ncnn-vulkan")
    exe = Path(exe) if exe else None
    if exe is None or not exe.exists():
        return None, None

    model_dir = exe.parent / "models"
    required = [model_dir / f"{REALESRGAN_MODEL_NAME}.param", model_dir / f"{REALESRGAN_MODEL_NAME}.bin"]
    if not all(path.exists() for path in required):
        return None, None

    realesrgan_exe = exe
    realesrgan_model_dir = model_dir
    return realesrgan_exe, realesrgan_model_dir


def real_esrgan_ready():
    exe, model_dir = get_realesrgan_runtime()
    return bool(exe and model_dir)


def gfpgan_ready():
    return bool(GFPGAN_MODEL_PATH.exists() and importlib.util.find_spec("gfpgan"))


def run_gfpgan_face_restore(image_bgr, weight=0.2):
    restorer = get_gfpgan_restorer()
    if restorer is None:
        return None
    try:
        _, _, restored = restorer.enhance(
            ensure_bgr(image_bgr),
            has_aligned=False,
            only_center_face=True,
            paste_back=True,
            weight=float(weight),
        )
    except Exception:
        return None
    return ensure_bgr(restored) if restored is not None else None


def get_gfpgan_restorer():
    global gfpgan_restorer, gfpgan_unavailable
    if gfpgan_restorer is not None:
        return gfpgan_restorer
    if gfpgan_unavailable or not gfpgan_ready():
        return None

    try:
        install_torchvision_functional_tensor_shim()
        from gfpgan import GFPGANer

        gfpgan_restorer = GFPGANer(
            model_path=str(GFPGAN_MODEL_PATH),
            upscale=1,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=None,
            device="cpu",
        )
    except Exception:
        gfpgan_unavailable = True
        return None
    return gfpgan_restorer


def install_torchvision_functional_tensor_shim():
    import sys
    import types
    from torchvision.transforms.functional import rgb_to_grayscale

    module_name = "torchvision.transforms.functional_tensor"
    if module_name in sys.modules:
        return
    shim = types.ModuleType(module_name)
    shim.rgb_to_grayscale = rgb_to_grayscale
    sys.modules[module_name] = shim


def superres_upscale(image_bgr):
    """True 2x FSRCNN upscale (identity-preserving CNN pixel upsampler).
    Returns the enlarged image, or None when the model is unavailable."""
    if superres is None:
        return None
    try:
        return ensure_bgr(superres.upsample(ensure_bgr(image_bgr)))
    except Exception:
        return None


def superres_refine(image_bgr):
    if superres is None:
        return image_bgr
    try:
        upscaled = superres.upsample(ensure_bgr(image_bgr))
        return cv2.resize(upscaled, (image_bgr.shape[1], image_bgr.shape[0]), interpolation=cv2.INTER_AREA)
    except Exception:
        return image_bgr


def mild_output_curve(image_bgr, mode):
    alpha = 1.015 if mode == "natural" else 1.035 if mode == "studio" else 1.05
    beta = 1 if mode == "natural" else 2 if mode == "studio" else 3
    return cv2.convertScaleAbs(ensure_bgr(image_bgr), alpha=alpha, beta=beta)


def ensure_bgr(image):
    image = np.asarray(image)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 1:
        return cv2.cvtColor(image[:, :, 0], cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image
    squeezed = np.squeeze(image)
    if squeezed.ndim == 2:
        return cv2.cvtColor(squeezed, cv2.COLOR_GRAY2BGR)
    raise ValueError(f"Unsupported image shape: {image.shape}")


def crop_and_resize(image, crop, output_width, output_height, pad_color=None):
    image = ensure_bgr(image)
    src_h, src_w = image.shape[:2]
    x = int(round(crop["x"]))
    y = int(round(crop["y"]))
    width = max(1, int(round(crop["width"])))
    height = max(1, int(round(crop["height"])))

    if x >= 0 and y >= 0 and x + width <= src_w and y + height <= src_h:
        crop_img = image[y : y + height, x : x + width]
    else:
        # Crop extends past the source: build a canvas and pad the missing area
        # with the (replaced) background colour, so we can compose to spec.
        canvas = np.empty((height, width, 3), dtype=np.uint8)
        if pad_color is not None:
            canvas[:] = (int(pad_color[2]), int(pad_color[1]), int(pad_color[0]))  # RGB -> BGR
        else:
            canvas[:] = (255, 255, 255)
        sx1, sy1 = max(0, x), max(0, y)
        sx2, sy2 = min(src_w, x + width), min(src_h, y + height)
        if sx2 > sx1 and sy2 > sy1:
            canvas[sy1 - y : sy2 - y, sx1 - x : sx2 - x] = image[sy1:sy2, sx1:sx2]
        crop_img = canvas

    # Direction-aware resampling. Low-res sources (webcams/old phones) UPSCALE to
    # the output; INTER_AREA is a downscale filter and produces mush there. Use
    # FSRCNN CNN super-resolution for big enlargements (identity-preserving pixel
    # upsampler, standard photo-tool practice) and Lanczos for the remainder.
    factor = output_width / max(1, crop_img.shape[1])
    if factor > 1.02:
        if factor >= 1.35:
            upscaled = superres_upscale(crop_img)
            if upscaled is not None:
                crop_img = upscaled
        return ensure_bgr(cv2.resize(crop_img, (output_width, output_height), interpolation=cv2.INTER_LANCZOS4))
    return ensure_bgr(cv2.resize(crop_img, (output_width, output_height), interpolation=cv2.INTER_AREA))


PRINT_SHEETS = {
    "4x6": {"label": "4 x 6 in", "width_in": 6.0, "height_in": 4.0},
    "5x7": {"label": "5 x 7 in", "width_in": 7.0, "height_in": 5.0},
    "a4": {"label": "A4", "width_in": 11.69, "height_in": 8.27},
    "letter": {"label": "US Letter", "width_in": 11.0, "height_in": 8.5},
}


def build_print_sheet(photo_bgr, spec):
    """Tile a passport photo onto a print sheet (4x6 / 5x7 / A4 / Letter) at a
    real DPI, with thin cut guides around each copy, for a photo-lab print run.
    Returns (sheet_bgr, layout_metadata).
    """
    photo = ensure_bgr(photo_bgr)
    dpi = max(150, min(600, int(spec.get("dpi", 300))))
    sheet_key = str(spec.get("sheet", "4x6")).lower()
    sheet = PRINT_SHEETS.get(sheet_key, PRINT_SHEETS["4x6"])
    sheet_w = int(round(sheet["width_in"] * dpi))
    sheet_h = int(round(sheet["height_in"] * dpi))

    photo_w_mm = spec.get("photoWidthMm")
    photo_h_mm = spec.get("photoHeightMm")
    if photo_w_mm and photo_h_mm:
        cell_w = max(1, int(round(float(photo_w_mm) / 25.4 * dpi)))
        cell_h = max(1, int(round(float(photo_h_mm) / 25.4 * dpi)))
    else:
        # No physical size for this programme (digital-only): print a 2 in tall
        # copy preserving the photo's own aspect ratio.
        ph, pw = photo.shape[:2]
        cell_h = int(round(2.0 * dpi))
        cell_w = max(1, int(round(cell_h * pw / max(1, ph))))

    # Cells abut (the classic passport sheet) so the maximum number of copies fit
    # - e.g. six 2x2 in photos on a 4x6. A 2% tolerance absorbs mm/inch rounding
    # (a 51 mm rule is really 2.0 in = 50.8 mm), then cells shrink to fit exactly
    # so nothing overflows the sheet. A thin grey cut guide is drawn per copy.
    tolerance = 1.02
    cols = int(sheet_w * tolerance) // cell_w
    rows = int(sheet_h * tolerance) // cell_h
    if cols < 1 or rows < 1:
        raise ValueError("Photo print size is larger than the selected sheet; choose a bigger sheet or lower DPI.")
    if cols * cell_w > sheet_w:
        cell_w = sheet_w // cols
    if rows * cell_h > sheet_h:
        cell_h = sheet_h // rows

    capacity = int(cols * rows)
    copies = max(1, min(capacity, int(spec.get("copies", capacity))))

    resized = cv2.resize(photo, (cell_w, cell_h), interpolation=cv2.INTER_AREA)
    sheet_img = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    grid_w = cols * cell_w
    grid_h = rows * cell_h
    start_x = (sheet_w - grid_w) // 2
    start_y = (sheet_h - grid_h) // 2

    placed = 0
    cut_color = (170, 170, 170)
    for row in range(int(rows)):
        for col in range(int(cols)):
            if placed >= copies:
                break
            x = start_x + col * cell_w
            y = start_y + row * cell_h
            sheet_img[y : y + cell_h, x : x + cell_w] = resized
            cv2.rectangle(sheet_img, (x, y), (x + cell_w - 1, y + cell_h - 1), cut_color, 1, lineType=cv2.LINE_AA)
            placed += 1
        if placed >= copies:
            break

    layout = {
        "sheet": sheet_key,
        "label": sheet["label"],
        "dpi": dpi,
        "cols": int(cols),
        "rows": int(rows),
        "capacity": capacity,
        "copies": int(placed),
        "cellPx": [cell_w, cell_h],
        "sheetPx": [sheet_w, sheet_h],
    }
    return sheet_img, layout


def extract_face_quality_region(source_bgr, face):
    image = ensure_bgr(source_bgr)
    height, width = image.shape[:2]
    head = max(1.0, float(face["headHeight"]))
    region_width = head * 1.28
    region_height = head * 1.18
    x1 = int(round(face["centerX"] - region_width / 2))
    y1 = int(round(face["centerY"] - region_height / 2))
    x2 = int(round(face["centerX"] + region_width / 2))
    y2 = int(round(face["centerY"] + region_height / 2))
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width, x2))
    y2 = max(y1 + 1, min(height, y2))
    return image[y1:y2, x1:x2]


def build_overlay(source_bgr, points, crop):
    overlay = source_bgr.copy()
    dim = overlay.copy()
    cv2.rectangle(dim, (0, 0), (overlay.shape[1], overlay.shape[0]), (10, 24, 39), thickness=-1)
    overlay = cv2.addWeighted(dim, 0.28, overlay, 0.72, 0)

    x = int(round(crop["x"]))
    y = int(round(crop["y"]))
    w = int(round(crop["width"]))
    h = int(round(crop["height"]))
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (46, 204, 113), 5, lineType=cv2.LINE_AA)

    oval = np.array([[int(points[index]["x"]), int(points[index]["y"])] for index in FACE_OVAL], dtype=np.int32)
    cv2.polylines(overlay, [oval], isClosed=True, color=(255, 178, 36), thickness=4, lineType=cv2.LINE_AA)

    for index in FACE_OVAL[::2]:
        point = points[index]
        cv2.circle(overlay, (int(point["x"]), int(point["y"])), 2, (255, 235, 173), -1, lineType=cv2.LINE_AA)

    cv2.line(overlay, (x + w // 2, y), (x + w // 2, y + h), (60, 105, 255), 2, lineType=cv2.LINE_AA)
    return overlay


def background_stats(image_bgr, profile, replaced=False):
    image = ensure_bgr(image_bgr)
    height, width = image.shape[:2]
    # Sample the top corners - the most reliable background region in a head-and-
    # shoulders portrait (shoulders fill the bottom, the head is centred).
    patch_w = max(6, int(round(width * 0.22)))
    patch_h = max(6, int(round(height * 0.30)))
    corners = [
        image[0:patch_h, 0:patch_w],
        image[0:patch_h, width - patch_w : width],
    ]
    pixels = np.concatenate([corner.reshape(-1, 3) for corner in corners], axis=0)
    if pixels.size == 0:
        return {"status": "warning", "value": "not measurable", "target": "plain light background"}

    rgb = pixels[:, ::-1].astype(np.float32)
    luma = rgb[:, 0] * 0.2126 + rgb[:, 1] * 0.7152 + rgb[:, 2] * 0.0722
    max_channel = rgb.max(axis=1)
    min_channel = rgb.min(axis=1)
    saturation = np.where(max_channel <= 1, 0, ((max_channel - min_channel) / max_channel) * 100)

    # When the background is replaced it is a known light colour by construction.
    # Measure only the light (background) pixels so that the subject's hair/
    # shoulders reaching the corner is treated as framing, not a dirty background.
    if replaced:
        is_bg = luma > 150
        bg_fraction = float(np.mean(is_bg))
        if bg_fraction < 0.15:
            # Corner is almost entirely subject - the background can't be assessed
            # here; that is a framing matter, not a background-cleanliness fault.
            return {"status": "pass", "value": "subject fills frame corners", "target": "plain light background"}
        luma = luma[is_bg]
        saturation = saturation[is_bg]

    avg_luma = float(np.mean(luma))
    avg_saturation = float(np.mean(saturation))
    spread = float(np.std(luma))
    rules = profile.get("background", {})
    min_luma = rules.get("minEdgeLuma", 170)
    max_saturation = rules.get("maxEdgeSaturation", 70)
    max_spread = rules.get("maxEdgeSpread", 50)

    status = "pass"
    if avg_luma < min_luma or avg_saturation > max_saturation or spread > max_spread:
        status = "warning"
    if avg_luma < min_luma - 35 or avg_saturation > max_saturation + 30 or spread > max_spread + 25:
        status = "fail"

    # When we are actively replacing the background, residual non-uniformity is a
    # touch-up item (manual brush / stronger cleanup), not a reason to force a
    # retake - so never hard-fail the output on it.
    if replaced and status == "fail":
        status = "warning"

    return {
        "status": status,
        "value": f"L {avg_luma:.0f} / S {avg_saturation:.0f} / spread {spread:.0f}",
        "target": "plain light background",
    }


def mask_value(mask_stats, background_replaced):
    if not background_replaced:
        return "disabled"
    if not mask_stats.get("available"):
        return "mask unavailable"
    value = (
        f'{mask_stats["engine"]} / {mask_stats["coverage"] * 100:.0f}% person / '
        f'{mask_stats["faceCoverage"] * 100:.0f}% face kept'
    )
    flags = []
    if mask_stats.get("strayIslands"):
        flags.append(f'{mask_stats["strayIslands"]} stray')
    if mask_stats.get("holePercent", 0) > 0.8:
        flags.append(f'{mask_stats["holePercent"]:.1f}% holes')
    shoulder = mask_stats.get("shoulderCoverage")
    if shoulder is not None and shoulder < 0.35:
        flags.append("shoulders clipped")
    if flags:
        value += " / " + ", ".join(flags)
    return value


def edit_policy(profile):
    review_text = " ".join(profile.get("reviewChecks", [])).lower()
    strict_terms = ("unaltered", "no digital retouching", "no retouching", "photo must not be altered", "true likeness")
    strict = any(term in review_text for term in strict_terms)
    if profile.get("country") in {"US", "CA", "GB", "AU"}:
        strict = True
    return {
        "strict": strict,
        "label": "government may reject digitally altered or AI-restored photos" if strict else "identity must not be changed",
    }


def build_checks(face, crop, profile, stats, background_stats_result, output_bytes, background_replaced, mask_stats, enhanced, enhancement_mode, corrections=None):
    corrections = corrections or []
    head_percent = (face["headHeight"] / crop["height"]) * 100
    center_offset = abs((face["centerX"] - (crop["x"] + crop["width"] / 2)) / crop["width"]) * 100
    top_margin = (((face["centerY"] - face["headHeight"] / 2) - crop["y"]) / crop["height"]) * 100
    file_rules = profile.get("file", {})
    max_bytes = profile.get("automation", {}).get("compressionTarget") or file_rules.get("maxBytes")
    min_bytes = file_rules.get("minBytes")
    mask_ready = bool(mask_stats.get("available"))
    policy = edit_policy(profile)

    # Any pixel-level edit (geometry rotation/resampling, tone, background, or
    # enhancement) counts as "processing" for the editing-policy risk gate. A
    # strict "no digital alteration" programme must never be told "crop/format
    # only" once we have rotated or tone-shifted the pixels.
    correction_labels = [c.get("label", c.get("id", "correction")) for c in corrections]
    processed = bool(corrections) or background_replaced or enhanced

    # Top margin: when an eye-height rule governs vertical placement, the margin is
    # a derived value (eye line + head size fix it), so a tight-but-legal margin is
    # reported as a warning, never a hard fail. eye_level is the check that governs.
    top_margin_status = threshold_status(abs(top_margin - profile["head"]["topMarginPercent"]), 6, 9)
    if profile["head"].get("eye") and top_margin_status == "fail":
        top_margin_status = "warning"
    edit_risk_status = "pass"
    edit_risk_value = "crop/format only" if not processed else "processing applied"
    edit_risk_target = "allowed adjustments"
    if correction_labels:
        edit_risk_value = ", ".join(correction_labels)
    if policy["strict"] and processed:
        edit_risk_status = "warning"
        edit_risk_target = policy["label"]
    if enhancement_mode == "strong" and enhanced:
        edit_risk_status = "warning"
        edit_risk_value = "face restoration rescue mode"
        edit_risk_target = "avoid unless retake is impossible"

    checks = [
        check("face_detection", "Face detection", "pass" if face["faceCount"] == 1 else "fail", f'{face["faceCount"]} face / Python FaceMesh', "1 clear face"),
        check("face_outline", "Face outline", "pass", "Face oval mapped", "shape contour"),
        check("head_size", "Head size", range_status(head_percent, profile["head"]["minPercent"], profile["head"]["maxPercent"]), f"{head_percent:.1f}%", f'{profile["head"]["minPercent"]}-{profile["head"]["maxPercent"]}%'),
        check("head_center", "Horizontal center", threshold_status(center_offset, 5, 8), f"{center_offset:.1f}% offset", "<= 5%"),
        check("top_margin", "Top margin", top_margin_status, f"{top_margin:.1f}%", f'{profile["head"]["topMarginPercent"]}% target'),
        check("head_tilt", "Head tilt", threshold_status(abs(face["rollDegrees"]), 4, 7), f'{abs(face["rollDegrees"]):.1f} deg', "<= 4 deg"),
        check("face_direction", "Face direction", threshold_status(abs(face["yawProxy"]), 9, 14), f'{abs(face["yawProxy"]):.1f}% nose offset', "facing camera"),
        check("mouth", "Mouth", threshold_status(face["mouthGapPercent"], 1.4, 2.4), f'{face["mouthGapPercent"]:.1f}%', "closed/neutral"),
        check("eyes_open", "Eyes open", threshold_status_inverse(face.get("eyeOpenness", 0.3), 0.17, 0.12), f'{face.get("eyeOpenness", 0):.2f} aperture', "eyes fully open"),
        check("glasses_glare", "Glasses glare", "warning" if face.get("glareFraction", 0) > 0.04 else "pass", f'{face.get("glareFraction", 0) * 100:.1f}% hotspot over eyes', "no glare/reflection on lenses"),
        check("background_cleanup", "Background cleanup", mask_stats.get("status", "review") if background_replaced else "review", mask_value(mask_stats, background_replaced), "clean matte with visible face/hair edges"),
        check("background_uniformity", "Background uniformity", background_stats_result["status"], background_stats_result["value"], background_stats_result["target"]),
        check("studio_enhancement", "Image processing", "warning" if (enhanced and enhancement_mode == "strong") else "pass" if enhanced else "review", enhancement_label(enhancement_mode) if enhanced else "disabled", "identity-preserving output"),
        check("edit_policy", "Editing policy risk", edit_risk_status, edit_risk_value, edit_risk_target),
        check("grain", "Noise / grain", threshold_status(stats["noise"], 9, 14), f'{stats["noise"]:.1f}', "<= 9"),
        check("sharpness", "Clean detail", threshold_status_inverse(stats.get("focus", stats["sharpness"]), 22, 10), f'{stats.get("focus", stats["sharpness"]):.0f}', "sharp facial detail"),
        check("brightness", "Brightness", brightness_status(stats.get("faceLuma", stats["luma"])), f'{stats.get("faceLuma", stats["luma"]):.0f} face', "80-220 on face"),
        check("contrast", "Contrast", threshold_status_inverse(stats.get("faceContrast", stats["contrast"]), 28, 20), f'{stats.get("faceContrast", stats["contrast"]):.0f} face', ">= 28 on face"),
        check("output_size", "Output canvas", "pass", f'{profile["output"]["widthPx"]} x {profile["output"]["heightPx"]}px', f'{profile["output"]["widthPx"]} x {profile["output"]["heightPx"]}px'),
    ]

    # Eye-line placement, only for programmes that specify an eye rule (e.g. US).
    eye = profile.get("head", {}).get("eye")
    if eye and face.get("eyeY") is not None:
        eye_from_top = ((face["eyeY"] - crop["y"]) / crop["height"]) * 100
        checks.append(
            check(
                "eye_level",
                "Eye level",
                range_status(eye_from_top, eye["fromTopMinPercent"], eye["fromTopMaxPercent"]),
                f"{eye_from_top:.1f}% from top",
                f'{eye["fromTopMinPercent"]}-{eye["fromTopMaxPercent"]}% from top',
            )
        )

    if min_bytes or max_bytes:
        status = "pass"
        if min_bytes and output_bytes < min_bytes:
            status = "warning"
        if max_bytes and output_bytes > max_bytes:
            status = "fail"
        checks.append(check("file_size", "File size", status, format_bytes(output_bytes), file_size_target(min_bytes, max_bytes)))

    for item in profile.get("reviewChecks", []):
        checks.append(check(f"review_{item.replace(' ', '_')}", title_case(item), "review", "Human check", "Required"))

    return checks


def build_source_quality(source_bgr, face, profile, source_stats, face_stats, source_bytes, background_replaced, mask_stats, corrections=None):
    """Assess the ORIGINAL capture. Dimensions we can auto-correct (tilt via
    straighten, exposure via tone) are not failed when the correction was
    applied, but unrecoverable problems - highlight/shadow clipping, turned head
    (yaw), blur, low resolution - still drive a retake. The capture, not the
    corrected artifact, is what is measured here.
    """
    corrections = corrections or []
    straightened = any(c.get("id") == "straighten" for c in corrections)
    toned = any(c.get("id") in ("exposure", "white_balance") for c in corrections)

    height, width = source_bgr.shape[:2]
    output = profile["output"]
    output_width = float(output["widthPx"])
    output_height = float(output["heightPx"])
    source_scale = min(width / max(1.0, output_width), height / max(1.0, output_height))
    target_output_head = output_height * (profile["head"]["targetPercent"] / 100)
    face_detail_ratio = float(face["headHeight"]) / max(1.0, target_output_head)
    face_focus = float(face_stats.get("focus", face_stats["sharpness"]))
    face_noise = float(face_stats["noise"])
    source_luma = float(source_stats["luma"])
    source_contrast = float(source_stats["contrast"])
    roll = abs(float(face.get("rollDegrees", 0)))
    yaw = abs(float(face.get("yawProxy", 0)))

    # Clipping in the captured face is NOT recoverable by tone correction.
    face_region = extract_face_quality_region(source_bgr, face)
    face_gray = cv2.cvtColor(ensure_bgr(face_region), cv2.COLOR_BGR2GRAY)
    clip_fraction = float(np.mean((face_gray <= 3) | (face_gray >= 252)))

    # Mean exposure is fixable by auto-tone; clipping and low contrast are not.
    lighting_status = "pass"
    if (not toned and not (70 <= source_luma <= 220)) or source_contrast < 24 or clip_fraction > 0.12:
        lighting_status = "warning"
    if (not toned and not (50 <= source_luma <= 238)) or source_contrast < 16 or clip_fraction > 0.25:
        lighting_status = "fail"
    lighting_value = f"L {source_luma:.0f} / C {source_contrast:.0f} / clip {clip_fraction * 100:.0f}%"
    if toned:
        lighting_value += " (auto-toned)"

    # Tilt (roll) is corrected by auto-straighten; a turned head (yaw) is not.
    effective_roll = 0.0 if straightened else roll
    pose_status = "pass"
    if effective_roll > 4 or yaw > 9:
        pose_status = "warning"
    if effective_roll > 7 or yaw > 14:
        pose_status = "fail"
    pose_value = f"{roll:.1f} deg tilt"
    if straightened:
        pose_value += " (auto-straightened)"
    pose_value += f" / {yaw:.1f}% yaw"

    if not background_replaced:
        background_status = "review"
        background_value = "replacement off"
    elif mask_stats.get("available"):
        background_status = mask_stats.get("status", "warning")
        background_value = f'{mask_stats["engine"]} / face kept {mask_stats["faceCoverage"] * 100:.0f}%'
    else:
        background_status = "warning"
        background_value = "mask unavailable"

    return [
        check("source_resolution", "Source resolution", threshold_status_inverse(source_scale, 1.0, 0.55), f"{width} x {height}px", f"~{int(output_width)} x {int(output_height)}px (2x CNN upscale available)"),
        check("source_face_pixels", "Face pixel detail", threshold_status_inverse(face_detail_ratio, 0.72, 0.45), f'{int(round(face["headHeight"]))} px head / {face_detail_ratio:.2f}x target', "enough detail (2x CNN upscale available)"),
        check("source_focus", "Input focus", threshold_status_inverse(face_focus, 28, 13), f"{face_focus:.0f}", "sharp facial detail"),
        check("source_noise", "Input noise", threshold_status(face_noise, 9, 14), f"{face_noise:.1f}", "low grain before enhancement"),
        check("source_lighting", "Input lighting", lighting_status, lighting_value, "even exposure, no clipping"),
        check("source_pose", "Capture pose", pose_status, pose_value, "front-facing, level head"),
        check("source_background_path", "Background path", background_status, background_value, "matte-ready portrait"),
        check("source_file", "Source file", "pass", format_bytes(source_bytes), "original image retained for audit"),
    ]


def build_pipeline_report(background_replaced, mask_stats, enhanced, enhancement_mode):
    stages = [
        {
            "id": "geometry",
            "label": "Geometry",
            "engine": "MediaPipe Face Landmarker",
            "status": "pass",
            "detail": "478-point face mesh, pose, mouth, crop placement",
        },
        {
            "id": "matting",
            "label": "Matting",
            "engine": mask_stats.get("engine") if background_replaced else "disabled",
            "status": mask_stats.get("status", "review") if background_replaced else "review",
            "detail": mask_stats.get("message", "background replacement disabled"),
        },
        {
            "id": "enhancement",
            "label": "Enhancement",
            "engine": enhancement_label(enhancement_mode) if enhanced else "disabled",
            "status": "warning" if enhanced and enhancement_mode == "strong" else "pass" if enhanced else "review",
            "detail": "identity-preserving clean-up" if enhancement_mode != "strong" else "face restoration rescue; verify likeness",
        },
        {
            "id": "validation",
            "label": "Validation",
            "engine": "KVNP compliance rules",
            "status": "pass",
            "detail": "geometry, background, quality, file, and human-review flags",
        },
    ]
    return {
        "version": SERVER_VERSION,
        "models": model_inventory(),
        "stages": stages,
    }


def build_decision(source_quality, checks, pipeline):
    fail_items = [item for item in [*source_quality, *checks] if item["status"] == "fail"]
    warning_items = [item for item in [*source_quality, *checks] if item["status"] == "warning"]
    review_items = [item for item in checks if item["status"] == "review"]
    source_failures = [item for item in source_quality if item["status"] == "fail"]
    policy_warnings = [item for item in checks if item["id"] == "edit_policy" and item["status"] == "warning"]

    if source_failures:
        status = "retake"
        title = "Retake source photo"
        message = "The input does not have enough clean detail for a reliable passport output."
    elif fail_items:
        status = "fix"
        title = "Fix output before export"
        message = "The generated photo fails at least one machine compliance check."
    elif policy_warnings:
        status = "policy_review"
        title = "Policy review required"
        message = "The photo is technically formed, but the selected programme may reject digital alteration or AI restoration."
    elif warning_items:
        status = "review"
        title = "Review warnings"
        message = "The output is close, but the marked warnings should be checked before submission."
    else:
        status = "ready"
        title = "Ready for export"
        message = "Machine checks pass. Human-only requirements still need visual confirmation."

    actions = []
    if status == "retake":
        actions.extend(["Use a sharper source", "Face the camera directly", "Use brighter even light"])
    if any(item["id"] == "background_cleanup" and item["status"] != "pass" for item in checks):
        actions.append("Review hair and shoulder edges")
    if policy_warnings:
        actions.append("Use crop/background only if the government allows edited photos")
    if review_items:
        actions.append("Confirm human-only checks before submission")

    return {
        "status": status,
        "title": title,
        "message": message,
        "failures": len(fail_items),
        "warnings": len(warning_items),
        "reviews": len(review_items),
        "actions": actions[:5],
        "pipelineVersion": pipeline["version"],
    }


def model_inventory():
    return [
        {
            "id": "mediapipe_face_landmarker",
            "label": "MediaPipe Face Landmarker",
            "stage": "geometry",
            "status": "ready" if FACE_MODEL_PATH.exists() else "missing",
            "weight": FACE_MODEL_PATH.name,
        },
        {
            "id": "mediapipe_selfie_segmenter",
            "label": "MediaPipe Image Segmenter",
            "stage": "matting",
            "status": "ready" if SEGMENTER_MODEL_PATH.exists() else "missing",
            "weight": SEGMENTER_MODEL_PATH.name,
        },
        {
            "id": "modnet",
            "label": "MODNet Portrait Matting",
            "stage": "matting",
            "status": modnet_inventory_status(),
            "weight": MODNET_MODEL_PATH.name,
        },
        {
            "id": "opencv_fsrcnn",
            "label": "OpenCV FSRCNN x2",
            "stage": "detail",
            "status": "ready" if superres is not None else "fallback",
            "weight": SUPERRES_MODEL_PATH.name,
        },
        {
            "id": "realesrgan",
            "label": "Real-ESRGAN NCNN Vulkan",
            "stage": "rescue",
            "status": "ready" if real_esrgan_ready() else "optional-not-installed",
            "weight": REALESRGAN_MODEL_NAME,
        },
        {
            "id": "gfpgan",
            "label": "GFPGAN face restoration",
            "stage": "rescue",
            "status": "ready" if gfpgan_ready() else "optional-not-installed",
            "weight": GFPGAN_MODEL_PATH.name,
        },
    ]


def image_stats(image_bgr):
    image_bgr = ensure_bgr(image_bgr)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (180, max(1, int(gray.shape[0] * 180 / gray.shape[1]))), interpolation=cv2.INTER_AREA)
    median = cv2.medianBlur(small, 3)
    denoised = cv2.bilateralFilter(small, d=5, sigmaColor=18, sigmaSpace=5)
    laplacian = cv2.Laplacian(denoised, cv2.CV_64F)
    noise = np.std(small.astype(np.float32) - median.astype(np.float32))
    return {
        "luma": float(np.mean(small)),
        "contrast": float(np.std(small)),
        "sharpness": float(np.mean(np.abs(laplacian))),
        "noise": float(noise),
    }


def face_focus_score(face_bgr):
    """Resolution-normalized variance-of-Laplacian focus score for a face crop.

    Calibrated on real portraits: sharp faces score ~30-420, mildly soft ~10-25,
    clearly blurred ~2-12. Higher = sharper. Unlike the old metric it does NOT
    pre-denoise (which destroyed the high-frequency detail it was meant to
    measure) and normalizes for face size so the threshold is stable.
    """
    gray = cv2.cvtColor(ensure_bgr(face_bgr), cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    if height < 4 or width < 4:
        return 0.0
    scale = 400.0 / float(height)
    gray = cv2.resize(gray, (max(1, int(round(width * scale))), 400), interpolation=cv2.INTER_AREA)
    # Light median denoise so sensor noise cannot masquerade as detail - a noisy
    # but out-of-focus webcam frame must NOT pass the focus gate. Real edges
    # survive a 3x3 median; Gaussian pixel noise largely does not.
    gray = cv2.medianBlur(gray, 3)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def output_face_stats(final_bgr):
    """Tone statistics of the central head region of a passport-framed output.
    Brightness/contrast must be judged on the FACE, not the frame mean - a
    replaced white background legitimately dominates the frame and would push
    the mean above any sane band."""
    image = ensure_bgr(final_bgr)
    height, width = image.shape[:2]
    region = image[int(height * 0.16):int(height * 0.74), int(width * 0.27):int(width * 0.73)]
    if region.size == 0:
        region = image
    return image_stats(region)


def output_focus_score(final_bgr):
    """Focus score of the central head region of a passport-framed output, using
    the same calibrated variance-of-Laplacian as the source-focus check (sharp
    outputs ~22-220, blurred ~3-8). The flat replaced background is excluded so
    the metric reflects facial detail, not the white field."""
    image = ensure_bgr(final_bgr)
    height, width = image.shape[:2]
    region = image[int(height * 0.16):int(height * 0.74), int(width * 0.27):int(width * 0.73)]
    if region.size == 0:
        region = image
    return face_focus_score(region)


def recompute_quality_checks(final_bgr, profile, background_replaced, output_bytes):
    """Recompute ONLY the pixel-dependent compliance checks for a (possibly
    user-adjusted) output image, using the exact same metrics/thresholds as the
    main pipeline. Returns a dict keyed by check id so the live UI can merge them
    over the geometry/matte checks (which don't change with tone adjustments).
    """
    stats = image_stats(final_bgr)
    stats["focus"] = output_focus_score(final_bgr)
    _ofs = output_face_stats(final_bgr)
    stats["faceLuma"] = _ofs["luma"]
    stats["faceContrast"] = _ofs["contrast"]
    bg = background_stats(final_bgr, profile, background_replaced)
    checks = {
        "sharpness": check("sharpness", "Clean detail", threshold_status_inverse(stats["focus"], 22, 10), f'{stats["focus"]:.0f}', "sharp facial detail"),
        "brightness": check("brightness", "Brightness", brightness_status(stats.get("faceLuma", stats["luma"])), f'{stats.get("faceLuma", stats["luma"]):.0f} face', "80-220 on face"),
        "contrast": check("contrast", "Contrast", threshold_status_inverse(stats.get("faceContrast", stats["contrast"]), 28, 20), f'{stats.get("faceContrast", stats["contrast"]):.0f} face', ">= 28 on face"),
        "grain": check("grain", "Noise / grain", threshold_status(stats["noise"], 9, 14), f'{stats["noise"]:.1f}', "<= 9"),
        "background_uniformity": check("background_uniformity", "Background uniformity", bg["status"], bg["value"], bg["target"]),
    }
    file_rules = profile.get("file", {})
    max_bytes = profile.get("automation", {}).get("compressionTarget") or file_rules.get("maxBytes")
    min_bytes = file_rules.get("minBytes")
    if output_bytes and (min_bytes or max_bytes):
        status = "pass"
        if min_bytes and output_bytes < min_bytes:
            status = "warning"
        if max_bytes and output_bytes > max_bytes:
            status = "fail"
        checks["file_size"] = check("file_size", "File size", status, format_bytes(output_bytes), file_size_target(min_bytes, max_bytes))
    return checks


def enhancement_label(mode):
    labels = {
        "natural": "natural compliance",
        "studio": "studio clean",
        "ai-clean": "passport clean / identity-preserving",
        "strong": "AI strong / Real-ESRGAN + GFPGAN" if gfpgan_ready() else "AI strong / Real-ESRGAN x4plus",
    }
    return labels.get(mode, mode)


def encode_jpeg(image_bgr, profile):
    image_bgr = ensure_bgr(image_bgr)
    quality = int(round(profile["output"].get("quality", 0.92) * 100))
    max_bytes = profile.get("automation", {}).get("compressionTarget") or profile.get("file", {}).get("maxBytes")
    quality = max(45, min(95, quality))
    encoded = encode_jpeg_bytes(image_bgr, quality)
    while max_bytes and len(encoded) > max_bytes and quality > 48:
        quality -= 5
        encoded = encode_jpeg_bytes(image_bgr, quality)
    return encoded


def encode_jpeg_bytes(image_bgr, quality):
    image_bgr = ensure_bgr(image_bgr)
    ok, encoded = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise ValueError("Could not encode JPEG output.")
    return encoded.tobytes()


def set_jpeg_dpi(jpeg_bytes, dpi):
    """Losslessly patch the JFIF APP0 density so the JPEG declares a real print
    DPI (dots/inch). If the standard APP0/JFIF marker is not present, fall back to
    a best-effort PIL re-encode with the requested dpi. Returns the patched bytes.

    JFIF APP0 layout: FF D8 FF E0 <len2> 'JFIF\\x00' <ver2> <units1> <Xdens2>
    <Ydens2> ... -> units at byte 13, Xdensity at 14-15, Ydensity at 16-17."""
    dpi = int(round(dpi))
    data = bytearray(jpeg_bytes)
    if (
        len(data) >= 18
        and data[0] == 0xFF
        and data[1] == 0xD8
        and data[2] == 0xFF
        and data[3] == 0xE0
        and data[6:11] == b"JFIF\x00"
    ):
        data[13] = 1  # density units = dots per inch
        data[14] = (dpi >> 8) & 0xFF
        data[15] = dpi & 0xFF
        data[16] = (dpi >> 8) & 0xFF
        data[17] = dpi & 0xFF
        return bytes(data)
    # No JFIF APP0 to patch: re-encode via PIL to embed the DPI (best effort).
    try:
        pil = Image.open(io.BytesIO(jpeg_bytes))
        buffer = io.BytesIO()
        pil.save(buffer, format="JPEG", quality=95, dpi=(dpi, dpi))
        return buffer.getvalue()
    except Exception:
        return bytes(jpeg_bytes)


def data_url(binary, mime):
    return f"data:{mime};base64,{base64.b64encode(binary).decode('ascii')}"


def parse_color(value):
    value = str(value).strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        return (255, 255, 255)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def distance(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def clamp(value, low, high):
    return min(max(value, low), high)


def range_status(value, low, high):
    return "pass" if low <= value <= high else "fail"


def brightness_status(luma):
    """Face-region brightness with a real fail tier for blown/black faces."""
    if luma < 55 or luma > 245:
        return "fail"
    if 80 <= luma <= 220:
        return "pass"
    return "warning"


def threshold_status(value, pass_max, warning_max):
    if value <= pass_max:
        return "pass"
    if value <= warning_max:
        return "warning"
    return "fail"


def threshold_status_inverse(value, pass_min, warning_min):
    if value >= pass_min:
        return "pass"
    if value >= warning_min:
        return "warning"
    return "fail"


def check(check_id, label, status, value, target):
    return {"id": check_id, "label": label, "status": status, "value": str(value), "target": str(target)}


def format_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.2f} MB"


def file_size_target(min_bytes, max_bytes):
    parts = []
    if min_bytes:
        parts.append(f">= {format_bytes(min_bytes)}")
    if max_bytes:
        parts.append(f"<= {format_bytes(max_bytes)}")
    return " and ".join(parts)


def title_case(value):
    return " ".join(word[:1].upper() + word[1:] for word in value.split())


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=int(os.environ.get("PORT", "4173")), reload=False)
