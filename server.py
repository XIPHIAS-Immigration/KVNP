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
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image

import kvnp_platform as platform
from kvnp_payments import gateway_for


ROOT = Path(__file__).resolve().parent
SERVER_VERSION = "python-mediapipe-2026-08-08-birefnet-matting"
MODEL_DIR = Path(os.getenv("KVNP_MODEL_DIR", str(ROOT / "models"))).expanduser()
TOOLS_DIR = ROOT / "tools"
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
SEGMENTER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
SUPERRES_MODEL_URL = "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x2.pb"
POSE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
FACE_MODEL_PATH = MODEL_DIR / "face_landmarker.task"
SEGMENTER_MODEL_PATH = MODEL_DIR / "selfie_segmenter.tflite"
SUPERRES_MODEL_PATH = MODEL_DIR / "FSRCNN_x2.pb"
POSE_MODEL_PATH = MODEL_DIR / "pose_landmarker_lite.task"
MODNET_MODEL_PATH = MODEL_DIR / "modnet.onnx"
BIREFNET_MODEL_PATH = MODEL_DIR / "birefnet-portrait.onnx"
GFPGAN_MODEL_PATH = MODEL_DIR / "GFPGANv1.4.pth"
REALESRGAN_MODEL_NAME = "realesrgan-x4plus"
MATTING_ENGINE_PREFERENCE = os.getenv("KVNP_MATTING_ENGINE", "auto").strip().lower()
if MATTING_ENGINE_PREFERENCE not in {"auto", "birefnet", "modnet", "mediapipe"}:
    MATTING_ENGINE_PREFERENCE = "auto"
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
LEFT_IRIS_CENTER = 468
RIGHT_IRIS_CENTER = 473


def ensure_model(path, url):
    if path.exists() and path.stat().st_size > 100_000:
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, path)


ensure_model(FACE_MODEL_PATH, FACE_MODEL_URL)
ensure_model(SEGMENTER_MODEL_PATH, SEGMENTER_MODEL_URL)
try:
    ensure_model(POSE_MODEL_PATH, POSE_MODEL_URL)
except Exception as error:
    log_message = f"Pose model unavailable: {error}"
    print(f"[kvnp] {log_message}", file=sys.stderr, flush=True)
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
        output_facial_transformation_matrixes=True,
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
pose_landmarker = None
if POSE_MODEL_PATH.exists():
    try:
        pose_landmarker = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(POSE_MODEL_PATH)),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.45,
                min_pose_presence_confidence=0.45,
            )
        )
    except Exception as error:
        print(f"[kvnp] Pose Landmarker initialization failed: {error}", file=sys.stderr, flush=True)
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
birefnet_session = None
birefnet_unavailable = False
birefnet_provider = None
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
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")
app.mount("/screenshots", StaticFiles(directory=ROOT / "screenshots"), name="screenshots")
app.mount("/docs", StaticFiles(directory=ROOT / "docs"), name="docs")


# ============================================================
# Accounts / sessions
# ============================================================
DATA_DIR = Path(os.environ.get("KVNP_DATA_DIR", str(ROOT / "data"))).resolve()
ARTIFACT_DIR = (DATA_DIR / "artifacts").resolve()
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
SESSION_COOKIE = "kvnp_session"
SESSION_TTL = 60 * 60 * 24 * 30  # 30 days
CHECKOUT_CLAIM_COOKIE = "kvnp_checkout_claim"
CHECKOUT_CLAIM_TTL = 60 * 60 * 48
PBKDF2_ROUNDS = 200_000
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
COOKIE_SECURE = os.getenv("KVNP_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
DATABASE_BACKEND = platform.initialise(DATA_DIR)
PAYMENT_MODE = os.getenv("KVNP_PAYMENT_MODE", "disabled").strip().lower()
PAYMENT_GATEWAY = gateway_for(PAYMENT_MODE)
ALLOW_MOCK_PAYMENTS = os.getenv("KVNP_ALLOW_MOCK_PAYMENTS", "false").strip().lower() in {"1", "true", "yes"}
COMMERCE_ENFORCED = os.getenv("KVNP_COMMERCE_ENFORCED", "false").strip().lower() in {"1", "true", "yes"}
APPLICATION_PRICE_MINOR = max(100, int(os.getenv("KVNP_APPLICATION_PRICE_MINOR", "19900")))
APPLICATION_CURRENCY = os.getenv("KVNP_APPLICATION_CURRENCY", "INR").strip().upper()[:3] or "INR"
SUBSCRIPTION_PRICE_MINOR = max(100, int(os.getenv("KVNP_SUBSCRIPTION_PRICE_MINOR", "500")))
PUBLIC_BASE_URL = os.getenv("KVNP_PUBLIC_URL", "").strip().rstrip("/")
SUBSCRIPTION_PRICE_LABEL = os.getenv("KVNP_SUBSCRIPTION_PRICE_LABEL", "Price shown at checkout").strip()
AUTH_FAILURES = {}


def hash_legacy_password(password, salt):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return digest.hex(), salt


def verify_user_password(user, password):
    if user.password_hash:
        try:
            valid = PASSWORD_HASHER.verify(user.password_hash, password)
            if valid and PASSWORD_HASHER.check_needs_rehash(user.password_hash):
                platform.upgrade_legacy_password(user.id, PASSWORD_HASHER.hash(password))
            return bool(valid)
        except (VerifyMismatchError, InvalidHashError):
            return False
    if not user.legacy_pw_hash or not user.legacy_pw_salt:
        return False
    candidate, _ = hash_legacy_password(password, user.legacy_pw_salt)
    if not hmac.compare_digest(candidate, user.legacy_pw_hash):
        return False
    platform.upgrade_legacy_password(user.id, PASSWORD_HASHER.hash(password))
    return True


def current_identity(request):
    return platform.resolve_auth_session(request.cookies.get(SESSION_COOKIE))


def current_user(request):
    identity = current_identity(request)
    return platform.user_dict(identity[0]) if identity else None


def require_identity(request):
    identity = current_identity(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return identity


def require_csrf(request, identity):
    supplied = request.headers.get("x-kvnp-csrf", "")
    if not supplied or not hmac.compare_digest(supplied, identity[1].csrf_token):
        raise HTTPException(status_code=403, detail="Security token expired. Refresh and try again.")


def require_admin(request, csrf=False):
    identity = require_identity(request)
    if identity[0].role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    if csrf:
        require_csrf(request, identity)
    return identity


def authenticated_response(user):
    token, csrf_token = platform.create_auth_session(user.id, SESSION_TTL)
    response = JSONResponse({"ok": True, "user": platform.user_dict(user), "csrfToken": csrf_token})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response


def read_json_body_error():
    return JSONResponse({"ok": False, "error": "Invalid JSON body."}, status_code=422)


def normalise_email(value):
    return str(value or "").strip().lower()


def valid_email(email):
    try:
        local, domain = email.rsplit("@", 1)
        return bool(local and "." in domain and len(email) <= 320)
    except Exception:
        return False


def auth_attempt_key(request, email):
    client = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"{client}|{email}".encode("utf-8")).hexdigest()


def enforce_login_throttle(request, email):
    key = auth_attempt_key(request, email)
    cutoff = time.time() - 600
    attempts = [item for item in AUTH_FAILURES.get(key, []) if item > cutoff]
    AUTH_FAILURES[key] = attempts
    if len(attempts) >= 8:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in ten minutes.")
    return key


def record_login_failure(key):
    AUTH_FAILURES.setdefault(key, []).append(time.time())


@app.post("/api/auth/signup")
async def auth_signup(request: Request):
    if PAYMENT_MODE == "stripe":
        return JSONResponse(
            {
                "ok": False,
                "error": "Complete membership payment before creating your KVNP account.",
                "action": "/pricing",
            },
            status_code=403,
        )
    try:
        body = await request.json()
    except Exception:
        return read_json_body_error()
    email = normalise_email(body.get("email"))
    password = str(body.get("password", ""))
    name = str(body.get("name", "")).strip()
    if not valid_email(email):
        return JSONResponse({"ok": False, "error": "Enter a valid email address."}, status_code=422)
    if len(name) < 2 or len(name) > 120:
        return JSONResponse({"ok": False, "error": "Enter your full name."}, status_code=422)
    if len(password) < 8 or len(password) > 256:
        return JSONResponse({"ok": False, "error": "Password must be 8 to 256 characters."}, status_code=422)
    try:
        user = platform.create_user(email, name, PASSWORD_HASHER.hash(password))
    except ValueError:
        return JSONResponse({"ok": False, "error": "An account with this email already exists."}, status_code=409)

    return authenticated_response(user)


@app.post("/api/auth/login")
async def auth_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        return read_json_body_error()
    email = normalise_email(body.get("email"))
    password = str(body.get("password", ""))
    attempt_key = enforce_login_throttle(request, email)
    user = platform.get_user_by_email(email)
    if user is None:
        hash_legacy_password(password, "0" * 32)
    if user is None or not verify_user_password(user, password):
        record_login_failure(attempt_key)
        return JSONResponse({"ok": False, "error": "Invalid email or password."}, status_code=401)

    AUTH_FAILURES.pop(attempt_key, None)
    platform.touch_login(user.id)
    return authenticated_response(user)


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    platform.revoke_auth_session(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/api/auth/me")
def auth_me(request: Request):
    identity = current_identity(request)
    return {
        "ok": True,
        "user": platform.user_dict(identity[0]) if identity else None,
        "csrfToken": identity[1].csrf_token if identity else None,
    }


def commerce_config(user=None):
    user_id = (user.get("id") if isinstance(user, dict) else user.id) if user else None
    subscription = platform.subscription_dict(platform.subscription_for_user(user_id)) if user_id else platform.subscription_dict(None)
    stripe_enabled = PAYMENT_MODE == "stripe" and PAYMENT_GATEWAY.configured
    return {
        "mode": PAYMENT_MODE,
        "enabled": PAYMENT_MODE in {"mock", "slice"} or stripe_enabled,
        "configured": PAYMENT_GATEWAY.configured,
        "enforced": COMMERCE_ENFORCED,
        "legacyCurrency": APPLICATION_CURRENCY,
        "mockCompletionAvailable": PAYMENT_MODE == "mock" and ALLOW_MOCK_PAYMENTS,
        "product": {
            "code": "studio-membership" if PAYMENT_MODE == "stripe" else "application-pack",
            "label": "KVNP Studio membership" if PAYMENT_MODE == "stripe" else "Application photo pack",
            "amountMinor": SUBSCRIPTION_PRICE_MINOR if PAYMENT_MODE == "stripe" else APPLICATION_PRICE_MINOR,
            "currency": "CAD" if PAYMENT_MODE == "stripe" else APPLICATION_CURRENCY,
            "priceLabel": SUBSCRIPTION_PRICE_LABEL if PAYMENT_MODE == "stripe" else None,
            "recurring": PAYMENT_MODE == "stripe",
            "includes": [
                "Country and programme presets",
                "JPEG, PNG, PDF and print sheets",
                "Background and tone studio tools",
                "Photo audit reports",
                "Unlimited prepared projects while active",
            ],
        },
        "signedIn": bool(user),
        "subscription": subscription,
    }


@app.get("/api/commerce/config")
def get_commerce_config(request: Request):
    return {"ok": True, **commerce_config(current_user(request))}


@app.get("/api/account/summary")
def account_summary(request: Request):
    identity = require_identity(request)
    return {
        "ok": True,
        "user": platform.user_dict(identity[0]),
        "projects": platform.list_projects(identity[0].id),
        "orders": platform.list_orders(identity[0].id),
        "subscription": platform.subscription_dict(platform.subscription_for_user(identity[0].id)),
        "commerce": commerce_config(identity[0]),
    }


@app.get("/api/projects")
def projects_list(request: Request):
    identity = require_identity(request)
    return {"ok": True, "projects": platform.list_projects(identity[0].id)}


@app.post("/api/projects")
async def projects_save(request: Request):
    identity = require_identity(request)
    require_csrf(request, identity)
    try:
        body = await request.json()
        project = platform.save_project(identity[0].id, body)
    except PermissionError:
        raise HTTPException(status_code=403, detail="This project belongs to another account.")
    except Exception as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=422)
    return {"ok": True, "project": platform.project_dict(project, platform.has_download_access(identity[0].id, project.id))}


def validated_project_uuid(project_id):
    try:
        return str(uuid.UUID(str(project_id)))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Project not found.")


def cleanup_expired_artifact_files():
    for stored_path in platform.remove_expired_artifacts():
        candidate = Path(stored_path).resolve()
        if ARTIFACT_DIR in candidate.parents and candidate.is_file():
            try:
                candidate.unlink()
            except OSError:
                pass


@app.post("/api/projects/{project_id}/artifact")
async def project_artifact_upload(project_id: str, request: Request, image: UploadFile = File(...)):
    identity = require_identity(request)
    require_csrf(request, identity)
    project_id = validated_project_uuid(project_id)
    if not platform.get_owned_project(identity[0].id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    cleanup_expired_artifact_files()
    payload = await image.read()
    if not payload or len(payload) > 20 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Prepared file must be between 1 byte and 20 MB.")
    decoded = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(status_code=422, detail="Prepared artifact is not a valid image.")
    ok, encoded = cv2.imencode(".jpg", decoded, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise HTTPException(status_code=422, detail="Prepared artifact could not be encoded.")
    target_dir = (ARTIFACT_DIR / str(identity[0].id) / project_id).resolve()
    if ARTIFACT_DIR not in target_dir.parents:
        raise HTTPException(status_code=422, detail="Invalid artifact destination.")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "prepared.jpg"
    temporary = target_dir / "prepared.tmp"
    temporary.write_bytes(encoded.tobytes())
    temporary.replace(target)
    artifact = platform.register_artifact(
        identity[0].id,
        project_id,
        str(target),
        "image/jpeg",
        target.stat().st_size,
    )
    return {"ok": True, "artifact": {"available": True, "bytes": artifact.bytes, "expiresAt": artifact.expires_at}}


@app.get("/api/projects/{project_id}/artifact")
def project_artifact_download(project_id: str, request: Request):
    identity = require_identity(request)
    project_id = validated_project_uuid(project_id)
    project = platform.get_owned_project(identity[0].id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    access = platform.has_download_access(identity[0].id, project_id)
    if COMMERCE_ENFORCED and not access:
        raise HTTPException(status_code=402, detail="An active KVNP membership is required for prepared downloads.")
    artifact = platform.get_artifact(identity[0].id, project_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="No saved prepared file is available for this application.")
    artifact_path = Path(artifact.storage_path).resolve()
    if ARTIFACT_DIR not in artifact_path.parents or not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="The saved prepared file has expired.")
    platform.record_download(identity[0].id, project_id, "saved_prepared", artifact.format, artifact.bytes, False)
    filename = f"kvnp-{project.profile_id}-{project_id[:8]}.jpg"
    return FileResponse(artifact_path, media_type=artifact.format, filename=filename)


def public_url(request: Request) -> str:
    return PUBLIC_BASE_URL or str(request.base_url).rstrip("/")


def checkout_email(source: dict) -> str | None:
    details = source.get("customer_details") or {}
    return platform.normalise_checkout_email(details.get("email") or source.get("customer_email"))


def safe_provider_error(error: Exception) -> str:
    value = str(error).replace("\r", " ").replace("\n", " ")
    return value[:500]


def start_stripe_subscription(identity, request: Request, project_id: str | None = None):
    if PAYMENT_MODE != "stripe" or not PAYMENT_GATEWAY.configured:
        return JSONResponse({"ok": False, "error": "Stripe checkout is not configured."}, status_code=503)
    user = identity[0] if identity else None
    if user and platform.active_subscription(user.id):
        return JSONResponse(
            {"ok": False, "error": "Your KVNP membership is already active. Manage it from your account."},
            status_code=409,
        )
    base_url = public_url(request)
    claim, claim_token = platform.create_checkout_claim(user.id if user else None, CHECKOUT_CLAIM_TTL)
    try:
        checkout = PAYMENT_GATEWAY.create_subscription_checkout(
            platform.user_dict(user) if user else None,
            (
                f"{base_url}/account?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
                if user
                else f"{base_url}/activate?session_id={{CHECKOUT_SESSION_ID}}"
            ),
            f"{base_url}/pricing?checkout=cancelled",
            claim.id,
        )
        platform.attach_checkout_session(claim.id, checkout.provider_order_id)
    except Exception as error:
        print(
            f"[kvnp] Stripe Checkout could not start: {type(error).__name__}: {safe_provider_error(error)}",
            file=sys.stderr,
            flush=True,
        )
        return JSONResponse(
            {"ok": False, "error": "Checkout is temporarily unavailable. Please try again."}, status_code=503
        )
    platform.record_event(
        "checkout_started",
        user.id if user else None,
        project_id,
        metadata={"provider": "stripe", "sessionId": checkout.provider_order_id, "claimId": claim.id},
    )
    response = JSONResponse({
        "ok": True,
        "checkout": {
            "provider": checkout.provider,
            "status": checkout.status,
            "url": checkout.checkout_url,
            "development": checkout.development,
        },
    })
    if not user:
        response.set_cookie(
            CHECKOUT_CLAIM_COOKIE,
            claim_token,
            max_age=CHECKOUT_CLAIM_TTL,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    return response


@app.post("/api/billing/checkout")
async def billing_checkout(request: Request):
    identity = current_identity(request)
    if identity:
        require_csrf(request, identity)
    else:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != public_url(request):
            raise HTTPException(status_code=403, detail="Checkout must be started from the KVNP website.")
    return start_stripe_subscription(identity, request)


def stripe_id(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        identifier = value.get("id")
        return str(identifier) if identifier else None
    return None


def refresh_checkout_claim(token: str | None, session_id: str):
    claim = platform.checkout_claim(token, session_id)
    if not claim:
        return None
    if claim.status in {"paid", "claimed"}:
        return claim
    source = PAYMENT_GATEWAY.retrieve_checkout(session_id)
    metadata = source.get("metadata") or {}
    if metadata.get("kvnp_checkout_id") != claim.id:
        raise ValueError("checkout_claim_mismatch")
    if source.get("mode") != "subscription":
        raise ValueError("checkout_mode")
    if source.get("payment_status") not in {"paid", "no_payment_required"}:
        return claim
    return platform.mark_checkout_paid(
        claim.id,
        session_id,
        stripe_id(source.get("customer")),
        stripe_subscription_id(source),
        checkout_email(source),
    )


def masked_email(email: str | None) -> str:
    value = str(email or "")
    if "@" not in value:
        return "your payment email"
    local, domain = value.split("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(2, min(8, len(local) - len(visible)))}@{domain}"


@app.get("/api/billing/activation")
def billing_activation_status(request: Request):
    session_id = str(request.query_params.get("session_id") or "")
    if not session_id.startswith("cs_") or len(session_id) > 160:
        return JSONResponse({"ok": False, "error": "Invalid checkout reference."}, status_code=422)
    try:
        claim = refresh_checkout_claim(request.cookies.get(CHECKOUT_CLAIM_COOKIE), session_id)
    except Exception as error:
        print(
            f"[kvnp] Checkout activation lookup failed: {type(error).__name__}: {safe_provider_error(error)}",
            file=sys.stderr,
            flush=True,
        )
        return JSONResponse({"ok": False, "error": "Payment verification is temporarily unavailable."}, status_code=503)
    if not claim:
        return JSONResponse(
            {"ok": False, "error": "This checkout link is invalid, expired, or belongs to another browser."},
            status_code=404,
        )
    return {
        "ok": True,
        "status": claim.status,
        "paid": claim.status == "paid",
        "claimed": claim.status == "claimed",
        "email": masked_email(claim.email),
        "existingAccount": bool(claim.email and platform.get_user_by_email(claim.email)),
    }


@app.post("/api/billing/activate")
async def billing_activate(request: Request):
    try:
        body = await request.json()
    except Exception:
        return read_json_body_error()
    session_id = str(body.get("sessionId") or "")
    name = str(body.get("name") or "").strip()
    password = str(body.get("password") or "")
    if not session_id.startswith("cs_") or len(session_id) > 160:
        return JSONResponse({"ok": False, "error": "Invalid checkout reference."}, status_code=422)
    if len(password) < 8 or len(password) > 256:
        return JSONResponse({"ok": False, "error": "Password must be 8 to 256 characters."}, status_code=422)
    token = request.cookies.get(CHECKOUT_CLAIM_COOKIE)
    try:
        claim = refresh_checkout_claim(token, session_id)
    except Exception as error:
        print(
            f"[kvnp] Checkout activation verification failed: {type(error).__name__}: {safe_provider_error(error)}",
            file=sys.stderr,
            flush=True,
        )
        return JSONResponse({"ok": False, "error": "Payment verification is temporarily unavailable."}, status_code=503)
    if not claim or claim.status != "paid" or not claim.email or not claim.provider_subscription_id:
        return JSONResponse(
            {"ok": False, "error": "Stripe has not confirmed this subscription yet. Try again in a few seconds."},
            status_code=409,
        )

    user = platform.get_user_by_email(claim.email)
    if user:
        attempt_key = enforce_login_throttle(request, claim.email)
        if not verify_user_password(user, password):
            record_login_failure(attempt_key)
            return JSONResponse(
                {"ok": False, "error": "That email already has a KVNP account. Enter its existing password."},
                status_code=401,
            )
        AUTH_FAILURES.pop(attempt_key, None)
    else:
        if len(name) < 2 or len(name) > 120:
            return JSONResponse({"ok": False, "error": "Enter your full name."}, status_code=422)
        try:
            user = platform.create_user(claim.email, name, PASSWORD_HASHER.hash(password))
        except ValueError:
            return JSONResponse(
                {"ok": False, "error": "An account with this payment email already exists. Refresh and sign in."},
                status_code=409,
            )

    try:
        subscription = PAYMENT_GATEWAY.retrieve_subscription(claim.provider_subscription_id)
        saved = platform.upsert_stripe_subscription(user.id, subscription)
        if saved.status not in {"active", "trialing"}:
            return JSONResponse(
                {"ok": False, "error": "Your Stripe subscription is not active yet. Try again shortly."},
                status_code=409,
            )
        latest_invoice = subscription.get("latest_invoice")
        if isinstance(latest_invoice, dict) and str(latest_invoice.get("id") or "").startswith("in_"):
            invoice_status = "paid" if latest_invoice.get("paid") or latest_invoice.get("status") == "paid" else str(
                latest_invoice.get("status") or "open"
            )
            platform.upsert_stripe_invoice(user.id, latest_invoice, invoice_status)
        platform.complete_checkout_claim(token, session_id, user.id)
    except Exception as error:
        print(
            f"[kvnp] Paid account activation failed: {type(error).__name__}: {safe_provider_error(error)}",
            file=sys.stderr,
            flush=True,
        )
        return JSONResponse({"ok": False, "error": "Your payment is safe, but account setup needs another attempt."}, status_code=503)

    platform.touch_login(user.id)
    platform.record_event(
        "paid_account_activated",
        user.id,
        metadata={"provider": "stripe", "subscriptionId": saved.provider_subscription_id},
    )
    response = authenticated_response(user)
    response.delete_cookie(CHECKOUT_CLAIM_COOKIE, path="/")
    return response


@app.post("/api/billing/portal")
async def billing_portal(request: Request):
    identity = require_identity(request)
    require_csrf(request, identity)
    if PAYMENT_MODE != "stripe" or not PAYMENT_GATEWAY.configured:
        return JSONResponse({"ok": False, "error": "Stripe billing is not configured."}, status_code=503)
    customer = platform.billing_customer_for_user(identity[0].id)
    if not customer:
        return JSONResponse({"ok": False, "error": "No Stripe billing profile exists yet."}, status_code=404)
    try:
        url = PAYMENT_GATEWAY.create_portal_session(customer.provider_customer_id, f"{public_url(request)}/account")
    except Exception as error:
        print(f"[kvnp] Stripe portal could not start: {type(error).__name__}", file=sys.stderr, flush=True)
        return JSONResponse(
            {"ok": False, "error": "Billing management is temporarily unavailable."}, status_code=503
        )
    return {"ok": True, "url": url}


def stripe_subscription_id(source: dict) -> str | None:
    direct = source.get("subscription")
    if isinstance(direct, str):
        return direct
    parent = source.get("parent") or {}
    details = parent.get("subscription_details") or {}
    nested = details.get("subscription")
    if isinstance(nested, str):
        return nested
    if isinstance(nested, dict):
        return nested.get("id")
    return None


def process_stripe_event(event: dict) -> bool:
    event_type = str(event.get("type") or "")
    source = event["data"]["object"]
    if not isinstance(source, dict):
        source = dict(source)

    subscription = None
    source_metadata = source.get("metadata") or {}
    supplied_user_id = source_metadata.get("kvnp_user_id")
    checkout_claim_id = source_metadata.get("kvnp_checkout_id")
    if event_type == "checkout.session.completed":
        if source.get("mode") != "subscription" or source.get("payment_status") not in {"paid", "no_payment_required"}:
            return False
        supplied_user_id = source.get("client_reference_id") or supplied_user_id
        subscription_id = stripe_subscription_id(source)
        if checkout_claim_id:
            platform.mark_checkout_paid(
                str(checkout_claim_id),
                str(source.get("id") or ""),
                stripe_id(source.get("customer")),
                subscription_id,
                checkout_email(source),
            )
        if subscription_id:
            subscription = PAYMENT_GATEWAY.retrieve_subscription(subscription_id)
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        subscription = source
    elif event_type in {"invoice.paid", "invoice.payment_failed"}:
        subscription_id = stripe_subscription_id(source)
        if subscription_id:
            subscription = PAYMENT_GATEWAY.retrieve_subscription(subscription_id)
    else:
        return False

    if not subscription:
        return False
    metadata = subscription.get("metadata") or {}
    checkout_claim_id = metadata.get("kvnp_checkout_id") or checkout_claim_id
    customer_id = subscription.get("customer") or source.get("customer")
    user_id = platform.resolve_billing_user(
        str(customer_id) if customer_id else None,
        metadata.get("kvnp_user_id") or supplied_user_id,
    )
    if not user_id:
        # Guest subscriptions are deliberately unassigned until the payer proves
        # possession of the browser claim and chooses account credentials.
        return bool(checkout_claim_id)
    saved = platform.upsert_stripe_subscription(user_id, subscription)
    if event_type == "invoice.paid":
        platform.upsert_stripe_invoice(user_id, source, "paid")
    elif event_type == "invoice.payment_failed":
        platform.upsert_stripe_invoice(user_id, source, "failed")
    if event_type == "checkout.session.completed" and saved.status in {"active", "trialing"}:
        platform.record_event(
            "payment_completed",
            user_id,
            metadata={"provider": "stripe", "subscriptionId": saved.provider_subscription_id},
        )
    return True


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    if PAYMENT_MODE != "stripe" or not PAYMENT_GATEWAY.configured:
        raise HTTPException(status_code=404, detail="Stripe webhooks are disabled.")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = PAYMENT_GATEWAY.construct_event(payload, signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.")
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Malformed Stripe event.")
    if not platform.reserve_provider_event("stripe", event_id, event_type):
        return {"ok": True, "duplicate": True}
    try:
        handled = process_stripe_event(event)
        platform.finish_provider_event(event_id, "processed" if handled else "ignored")
    except Exception as error:
        platform.finish_provider_event(event_id, "failed", str(error))
        print(f"[kvnp] Stripe webhook failed: {event_type}: {type(error).__name__}", file=sys.stderr, flush=True)
        return JSONResponse({"ok": False, "error": "Webhook processing failed."}, status_code=500)
    return {"ok": True, "handled": handled}


@app.post("/api/checkout/start")
async def checkout_start(request: Request):
    identity = require_identity(request)
    require_csrf(request, identity)
    if PAYMENT_MODE == "disabled":
        return JSONResponse({"ok": False, "error": "Online checkout is not open yet."}, status_code=503)
    try:
        body = await request.json()
        project_id = str(body.get("projectId") or "")
        if PAYMENT_MODE == "stripe":
            project = platform.get_owned_project(identity[0].id, project_id) if project_id else None
            return start_stripe_subscription(identity, request, project.id if project else None)
        order = platform.create_order(
            identity[0].id,
            project_id,
            APPLICATION_PRICE_MINOR,
            APPLICATION_CURRENCY,
            PAYMENT_GATEWAY.name,
        )
        order_data = platform.order_dict(order)
        checkout = PAYMENT_GATEWAY.create_checkout(order_data, str(request.base_url) + "app")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Save this project to your account before checkout.")
    except RuntimeError as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=503)
    platform.record_event("checkout_started", identity[0].id, project_id, metadata={"orderId": order.id})
    return {
        "ok": True,
        "order": order_data,
        "checkout": {
            "provider": checkout.provider,
            "status": checkout.status,
            "url": checkout.checkout_url,
            "development": checkout.development,
        },
    }


@app.post("/api/checkout/mock/complete")
async def checkout_mock_complete(request: Request):
    identity = require_identity(request)
    require_csrf(request, identity)
    if PAYMENT_MODE != "mock" or not ALLOW_MOCK_PAYMENTS:
        raise HTTPException(status_code=404, detail="Development checkout is disabled.")
    body = await request.json()
    try:
        order = platform.complete_mock_order(identity[0].id, str(body.get("orderId") or ""))
    except PermissionError:
        raise HTTPException(status_code=403, detail="This order belongs to another account.")
    except ValueError:
        raise HTTPException(status_code=409, detail="This order cannot be completed.")
    platform.record_event("payment_completed", identity[0].id, order.project_id, metadata={"orderId": order.id})
    return {"ok": True, "order": platform.order_dict(order), "entitled": True}


@app.post("/api/downloads/authorize")
async def authorize_download(request: Request):
    identity = require_identity(request)
    require_csrf(request, identity)
    body = await request.json()
    project_id = str(body.get("projectId") or "")
    file_kind = str(body.get("fileKind") or "prepared")
    project = platform.get_owned_project(identity[0].id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    entitled = platform.has_download_access(identity[0].id, project_id)
    if COMMERCE_ENFORCED and file_kind != "original" and not entitled:
        return JSONResponse(
            {"ok": False, "error": "An active KVNP membership is required for prepared downloads."},
            status_code=402,
        )
    platform.record_download(
        identity[0].id,
        project_id,
        file_kind,
        str(body.get("format") or "unknown"),
        int(body.get("bytes") or 0) or None,
        bool(body.get("warningAcknowledged")),
    )
    platform.record_event("download_completed", identity[0].id, project_id, metadata={"fileKind": file_kind})
    return {"ok": True, "entitled": entitled, "enforced": COMMERCE_ENFORCED}


@app.post("/api/events")
async def events_create(request: Request):
    identity = current_identity(request)
    try:
        body = await request.json()
        platform.record_event(
            str(body.get("name") or ""),
            identity[0].id if identity else None,
            str(body.get("projectId") or "") or None,
            str(body.get("anonymousId") or "") or None,
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
        )
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid event."}, status_code=422)
    return {"ok": True}


@app.post("/api/enquiries")
async def enquiries_create(request: Request):
    identity = current_identity(request)
    try:
        body = await request.json()
    except Exception:
        return read_json_body_error()
    name = str(body.get("name") or "").strip()
    email = normalise_email(body.get("email"))
    subject = str(body.get("subject") or "").strip()
    message = str(body.get("message") or "").strip()
    if (
        len(name) < 2
        or len(name) > 160
        or not valid_email(email)
        or len(subject) < 3
        or len(subject) > 200
        or len(message) < 10
        or len(message) > 5000
    ):
        return JSONResponse({"ok": False, "error": "Complete every enquiry field."}, status_code=422)
    item = platform.create_enquiry(identity[0].id if identity else None, name, email, subject, message)
    platform.record_event("enquiry_created", identity[0].id if identity else None, metadata={"enquiryId": item.id})
    return {"ok": True, "reference": item.id[:8].upper()}


@app.get("/api/admin/dashboard")
def admin_dashboard(request: Request):
    require_admin(request)
    return {"ok": True, **platform.admin_dashboard(), "commerce": commerce_config(current_user(request))}


@app.patch("/api/admin/enquiries/{enquiry_id}")
async def admin_enquiry_update(enquiry_id: str, request: Request):
    identity = require_admin(request, csrf=True)
    body = await request.json()
    try:
        item = platform.update_enquiry(
            identity[0].id,
            enquiry_id,
            str(body.get("status") or "new"),
            str(body.get("adminNote") or ""),
        )
    except ValueError:
        return JSONResponse({"ok": False, "error": "Invalid enquiry status."}, status_code=422)
    if not item:
        raise HTTPException(status_code=404, detail="Enquiry not found.")
    return {"ok": True, "enquiry": platform.enquiry_dict(item)}


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


@app.get("/account")
def account_page():
    return FileResponse(ROOT / "account.html")


@app.get("/pricing")
def pricing_page():
    return FileResponse(ROOT / "pricing.html")


@app.get("/activate")
def activate_page():
    return FileResponse(ROOT / "activate.html")


@app.get("/admin")
def admin_page():
    return FileResponse(ROOT / "admin.html")


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
        "poseLandmarker": pose_landmarker is not None,
        "selfieSegmentation": True,
        "birefnet": birefnet_ready(),
        "mattingPreference": MATTING_ENGINE_PREFERENCE,
        "realEsrgan": real_esrgan_ready(),
        "gfpgan": gfpgan_ready(),
        "modnet": modnet_active(),
        "guidedFilter": HAS_GUIDED_FILTER,
        "database": DATABASE_BACKEND,
        "commerceMode": PAYMENT_MODE,
        "commerceConfigured": PAYMENT_GATEWAY.configured,
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


@app.post("/api/export")
async def export_photo(image: UploadFile = File(...), spec: str = Form("{}")):
    """Encode the finished photo without re-running or altering the face pipeline."""
    try:
        try:
            spec_data = json.loads(spec)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON in export spec.")
        photo = decode_image(await image.read())
        output, metadata = encode_photo_export(photo, spec_data)
        filename = f'passport-photo.{metadata["extension"]}'
        return Response(
            content=output,
            media_type=metadata["mime"],
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-KVNP-Width": str(metadata["width"]),
                "X-KVNP-Height": str(metadata["height"]),
                "X-KVNP-Upscale": metadata["upscaleEngine"],
            },
        )
    except ValueError as error:
        return JSONResponse({"ok": False, "error": str(error)}, status_code=422)
    except Exception:
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": "Export failed. See server log."}, status_code=500)


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
    official_allowed = dict(profile.get("allowedEdits") or {})
    policy = edit_policy(profile)
    if policy["strict"]:
        for key in ("straighten", "tone", "lighting", "background", "enhance", "rescue"):
            official_allowed[key] = False
    allowed = dict(official_allowed)
    # Editing preview is the only escape hatch from a programme policy lock. It
    # is deliberately enforced on the server and always produces a conspicuous
    # watermark, so a client cannot request a clean altered submission photo.
    preview_mode = bool(options.get("previewMode", False))
    if preview_mode:
        for key in ("straighten", "tone", "lighting", "background", "enhance"):
            allowed[key] = True
        allowed["rescue"] = False
    # Authorities that require an original/unaltered capture get a hard server
    # lock. Client flags are untrusted and can never re-enable pixel edits.
    if policy["strict"] and not preview_mode:
        for key in ("straighten", "tone", "lighting", "background", "enhance", "rescue"):
            allowed[key] = False
    policy_clamped = []
    if policy["strict"] and has_manual and not preview_mode:
        has_manual = False
        policy_clamped.append("manual_geometry")

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
    posture = measure_pose_posture(original_source, original_face)

    source = original_source
    if do_tone:
        source, tone_corrections = auto_tone_correct(source, landmarks=landmarks)
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
    matte, matte_engine = build_person_mask(
        mp_image,
        source,
        face,
        True,
        width,
        height,
        landmarks=None if has_manual else landmarks,
    )
    if matte is not None and not has_manual:
        face = refine_head_from_matte(
            face,
            matte,
            width,
            height,
            measure=profile.get("head", {}).get("measure", "chin_to_top_of_head"),
        )

    # When the background is replaced we can pad the canvas with background to
    # compose exactly to spec (head size + margins) even from a tightly-framed
    # source; otherwise the crop must fit within the source pixels.
    can_pad = replace_background and matte is not None
    crop = calculate_crop(width, height, face, profile, allow_pad=can_pad)

    if replace_background and matte is not None:
        background_cleanup = str(options.get("backgroundCleanup") or "balanced")
        composite_matte = apply_background_cleanup(matte, background_cleanup, engine=matte_engine)
        mask_stats = describe_mask(composite_matte, face, width, height, matte_engine)
        # Composite at the final canvas resolution. Besides bounding memory on
        # phone photos, this lets edge decontamination operate on the exact
        # pixels the applicant will download rather than on a later-resampled
        # halo.
        final_source = crop_and_resize(
            source,
            crop,
            profile["output"]["widthPx"],
            profile["output"]["heightPx"],
            pad_color=background_rgb,
        )
        final_matte = crop_mask_and_resize(
            composite_matte,
            crop,
            profile["output"]["widthPx"],
            profile["output"]["heightPx"],
        )
        final_matte = refine_output_matte(final_matte, final_source, engine=matte_engine)
        final = composite_background(final_source, final_matte, background_rgb)
        pad_color = background_rgb
    else:
        mask_stats = describe_mask(None, face, width, height, "unavailable" if replace_background else "disabled")
        pad_color = None
        final = crop_and_resize(
            source,
            crop,
            profile["output"]["widthPx"],
            profile["output"]["heightPx"],
            pad_color=pad_color,
        )
    if enhance:
        final = enhance_passport_photo(final, enhancement_mode)
    # Stamp the print DPI into the JFIF metadata so labs print at the physical
    # size the programme requires (losslessly, after size-targeting).
    output_spec = profile["output"]
    if output_spec.get("printWidthMm"):
        dpi_final = round(output_spec["widthPx"] / (output_spec["printWidthMm"] / 25.4))
    else:
        dpi_final = 300
    output_final = add_preview_watermark(final) if preview_mode else final
    final_bytes = set_jpeg_dpi(encode_jpeg(output_final, profile), dpi_final)
    overlay = build_overlay(source, landmarks, crop, matte=matte, face=face, profile=profile, posture=posture)
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
        posture,
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
    if preview_mode:
        checks.insert(
            0,
            check(
                "preview_only",
                "Output mode",
                "warning",
                "watermarked editing preview",
                "not valid for submission",
            ),
        )
    pipeline = build_pipeline_report(replace_background, mask_stats, enhance, enhancement_mode)
    decision = build_decision(source_quality, checks, pipeline)
    if preview_mode:
        decision = {
            **decision,
            "status": "review",
            "title": "Editing preview",
            "message": "Cleanup tools are active. This watermarked result is for visual evaluation only, not submission.",
        }

    correction_ids = {item.get("id") for item in corrections}
    effective_edits = {
        "crop_resize": True,
        "straighten": "straighten" in correction_ids,
        "tone": bool(correction_ids.intersection({"exposure", "white_balance"})),
        "lighting": bool(correction_ids.intersection({"even_lighting", "red_eye"})),
        "background": bool(replace_background and matte is not None),
        "enhance": bool(enhance),
        "rescue": False,
    }

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
        "posture": posture,
        "checks": checks,
        "corrections": corrections,
        "policyClamped": policy_clamped,
        "allowedEdits": official_allowed,
        # What actually touched pixels, not merely what this mode was allowed to
        # do. The UI uses this as the processing audit source of truth.
        "effectiveEdits": effective_edits,
        "previewOnly": preview_mode,
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


def estimate_eye_gaze(points, yaw_proxy=0.0):
    """Estimate whether both irises are aligned with the camera.

    Iris position is measured inside each eyelid box. A small yaw compensation
    prevents a slightly turned but camera-looking face from being mislabeled.
    The vertical bias accounts for Face Landmarker iris centers sitting a little
    above the midpoint of the eyelid landmarks on a neutral forward gaze.
    """
    if len(points) <= RIGHT_IRIS_CENTER:
        return {
            "gazeHorizontalPercent": None,
            "gazeVerticalPercent": None,
            "gazeOffsetPercent": None,
        }

    eye_specs = [
        (LEFT_EYE, LEFT_EYE_INNER, LEFT_EYE_TOP, LEFT_EYE_BOTTOM, LEFT_IRIS_CENTER),
        (RIGHT_EYE, RIGHT_EYE_INNER, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM, RIGHT_IRIS_CENTER),
    ]
    positions = []
    for outer, inner, top, bottom, iris in eye_specs:
        x1, x2 = sorted((float(points[outer]["x"]), float(points[inner]["x"])))
        y1, y2 = sorted((float(points[top]["y"]), float(points[bottom]["y"])))
        if x2 - x1 < 1.0 or y2 - y1 < 1.0:
            continue
        positions.append(
            (
                (float(points[iris]["x"]) - x1) / (x2 - x1),
                (float(points[iris]["y"]) - y1) / (y2 - y1),
            )
        )
    if len(positions) != 2:
        return {
            "gazeHorizontalPercent": None,
            "gazeVerticalPercent": None,
            "gazeOffsetPercent": None,
        }

    mean_x = sum(item[0] for item in positions) / 2.0
    mean_y = sum(item[1] for item in positions) / 2.0
    horizontal = (mean_x - 0.5) * 100.0 + float(yaw_proxy) * 0.6
    vertical = (mean_y - 0.5) * 100.0 + 5.5
    return {
        "gazeHorizontalPercent": round(horizontal, 2),
        "gazeVerticalPercent": round(vertical, 2),
        "gazeOffsetPercent": round(max(abs(horizontal), abs(vertical)), 2),
    }


def facial_pose_from_matrix(matrix):
    if matrix is None:
        return {"pitchDegrees": None, "pitchOffsetDegrees": None}
    try:
        rotation = np.asarray(matrix, dtype=np.float64)[:3, :3]
        sy = math.sqrt(rotation[0, 0] ** 2 + rotation[1, 0] ** 2)
        pitch = math.degrees(math.atan2(rotation[2, 1], rotation[2, 2]))
        # MediaPipe's canonical neutral face sits at roughly +8 degrees in this
        # coordinate frame. Reporting the calibrated offset makes zero mean
        # "camera level with the face"; negative values mean the chin is down.
        pitch_offset = pitch - 8.0
        return {
            "pitchDegrees": round(float(pitch), 2),
            "pitchOffsetDegrees": round(float(pitch_offset), 2),
        }
    except (TypeError, ValueError, IndexError):
        return {"pitchDegrees": None, "pitchOffsetDegrees": None}


def measure_face(points, face_count, transformation_matrix=None):
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
    gaze = estimate_eye_gaze(points, yaw_proxy)
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
        **facial_pose_from_matrix(transformation_matrix),
        **gaze,
        "bounds": {
            "minX": round(float(min_x), 2),
            "minY": round(float(min_y), 2),
            "maxX": round(float(max_x), 2),
            "maxY": round(float(max_y), 2),
            "width": round(float(max_x - min_x), 2),
            "height": round(float(max_y - min_y), 2),
        },
    }


def refine_head_from_matte(face, mask, width, height, measure="chin_to_top_of_head"):
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
    refined["silhouetteTopY"] = round(crown_y, 2)
    # Crown-based specifications measure the anatomical skull, not the top of
    # voluminous hair. Keep Face Landmarker geometry for the measurement while
    # retaining the matte top so calculate_crop can still avoid clipping hair.
    if measure in {"chin_to_crown", "face_area_estimate"}:
        refined["headSource"] = "landmark-crown+matte-silhouette"
        return refined
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
    visible_top = min(head_top, float(face.get("silhouetteTopY", head_top)))
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
                top = min(top, visible_top - ch * 0.015)
            return top
        top = head_top - ch * (profile["head"]["topMarginPercent"] / 100)
        return min(top, visible_top - ch * 0.015)

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
    if len(faces) != 1:
        raise ValueError(f"Multiple faces detected ({len(faces)}). Use a photo containing only one person.")
    landmarks = get_landmarks(faces[0], width, height)
    matrices = result.facial_transformation_matrixes or []
    face = measure_face(landmarks, len(faces), matrices[0] if matrices else None)
    return mp_image, landmarks, face


def measure_pose_posture(source_bgr, face):
    """Measure shoulder level and upper-body alignment on the original capture.

    Face Landmarker answers head geometry; Pose Landmarker supplies the shoulder
    line and, when visible, the hip axis. Tight portraits fall back to checking
    whether the head is centered over the shoulders.
    """
    posture = {
        "available": False,
        "shoulderLevelDegrees": None,
        "shoulderSignedDegrees": None,
        "bodyLeanPercent": None,
        "bodyLeanSource": None,
        "pitchOffsetDegrees": face.get("pitchOffsetDegrees"),
        "shoulderPoints": None,
    }
    if pose_landmarker is None:
        return posture

    try:
        height, width = source_bgr.shape[:2]
        result = pose_landmarker.detect(build_mp_image(source_bgr))
        poses = result.pose_landmarks or []
        if not poses:
            return posture
        points = poses[0]

        def landmark(index):
            point = points[index]
            return {
                "x": float(point.x),
                "y": float(point.y),
                "visibility": float(getattr(point, "visibility", 0.0) or 0.0),
                "presence": float(getattr(point, "presence", 0.0) or 0.0),
            }

        left_shoulder = landmark(11)
        right_shoulder = landmark(12)
        shoulder_confidence = min(
            left_shoulder["visibility"],
            left_shoulder["presence"],
            right_shoulder["visibility"],
            right_shoulder["presence"],
        )
        if shoulder_confidence < 0.45:
            return posture

        dx = right_shoulder["x"] - left_shoulder["x"]
        dy = right_shoulder["y"] - left_shoulder["y"]
        shoulder_width = max(1e-4, math.hypot(dx, dy))
        raw_angle = math.degrees(math.atan2(dy, dx))
        signed_angle = ((raw_angle + 90.0) % 180.0) - 90.0
        shoulder_mid_x = (left_shoulder["x"] + right_shoulder["x"]) / 2.0
        posture.update(
            {
                "available": True,
                "shoulderLevelDegrees": round(abs(float(signed_angle)), 2),
                "shoulderSignedDegrees": round(float(signed_angle), 2),
                "shoulderPoints": [
                    [round(left_shoulder["x"] * width, 1), round(left_shoulder["y"] * height, 1)],
                    [round(right_shoulder["x"] * width, 1), round(right_shoulder["y"] * height, 1)],
                ],
            }
        )

        left_hip = landmark(23)
        right_hip = landmark(24)
        hip_confidence = min(
            left_hip["visibility"],
            left_hip["presence"],
            right_hip["visibility"],
            right_hip["presence"],
        )
        if hip_confidence >= 0.45:
            hip_mid_x = (left_hip["x"] + right_hip["x"]) / 2.0
            posture["bodyLeanPercent"] = round(abs(shoulder_mid_x - hip_mid_x) / shoulder_width * 100.0, 2)
            posture["bodyLeanSource"] = "shoulders over hips"
        else:
            face_x = float(face["centerX"]) / max(1.0, float(width))
            posture["bodyLeanPercent"] = round(abs(face_x - shoulder_mid_x) / shoulder_width * 100.0, 2)
            posture["bodyLeanSource"] = "head over shoulders"
        return posture
    except Exception as error:
        log_warn_once(f"Pose measurement failed: {error}")
        return posture


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


def auto_tone_correct(source_bgr, landmarks=None):
    """Gentle, identity-preserving exposure + white-balance normalization.

    Returns ``(image, corrections)``. Only acts when there is a visible colour
    cast or the image is clearly under/over-exposed, and uses bounded gains so
    skin tone and likeness are preserved.
    """
    image = ensure_bgr(source_bgr)
    corrections = []
    height, width = image.shape[:2]
    if landmarks:
        tone_mask = face_oval_mask(landmarks, width, height, feather=max(8.0, width * 0.018))
        sample_mask = tone_mask > 0.62
    else:
        tone_mask = np.ones((height, width), dtype=np.float32)
        sample_mask = np.ones((height, width), dtype=bool)

    means = image[sample_mask].astype(np.float32).mean(axis=0)
    spread = (float(means.max()) - float(means.min())) / (float(means.mean()) + 1e-6)
    if spread > 0.10:
        source_float = image.astype(np.float32)
        gray = float(means.mean())
        gains = np.clip(gray / np.maximum(means, 1.0), 0.92, 1.08)
        balanced = np.clip(source_float * gains[None, None, :], 0, 255)
        blend = tone_mask[..., None] * 0.72
        image = np.clip(source_float * (1.0 - blend) + balanced * blend, 0, 255).astype(np.uint8)
        corrections.append(
            {"id": "white_balance", "label": "Auto white balance", "detail": "neutralised colour cast", "applied": True}
        )

    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    luma = float(gray_image[sample_mask].mean())
    if luma < 96.0 or luma > 190.0:
        # Gamma on the LAB L channel brightens shadows/midtones toward the target
        # without a linear multiply that would blow highlights to pure white.
        # (gamma maps [0,1] -> [0,1], so white stays white - no new clipping - and
        # chroma is untouched, preserving skin tone and likeness.)
        normalized = max(1.0, luma) / 255.0
        target = 125.0 / 255.0
        gamma = clamp(math.log(target) / math.log(normalized), 0.72, 1.35)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = np.power(lab[:, :, 0].astype(np.float32) / 255.0, gamma) * 255.0
        lab[:, :, 0] = np.clip(l_channel, 0, 255).astype(np.uint8)
        corrected = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR).astype(np.float32)
        original = image.astype(np.float32)
        blend = tone_mask[..., None] * 0.78
        image = np.clip(original * (1.0 - blend) + corrected * blend, 0, 255).astype(np.uint8)
        new_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        new_luma = float(new_gray[sample_mask].mean())
        corrections.append(
            {
                "id": "exposure",
                "label": "Auto-exposure",
                "detail": f"face brightness {luma:.0f} -> {new_luma:.0f}",
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
    if unevenness < 16.0:
        return image, False  # lighting is already reasonably even; leave it
    # Correct illumination gently. Strong flattening makes skin look synthetic
    # even when no generative model is involved.
    lab[:, :, 0] = np.clip(l_channel - (illum - mean_illum) * 0.24 * mask, 0, 255)
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


def build_person_mask(mp_image, source_bgr, face, enabled, width, height, landmarks=None):
    """Return ``(alpha_mask, engine_label)`` for the person matte.

    Prefers BiRefNet Portrait for export-grade still-image edges, then MODNet,
    and finally the MediaPipe selfie segmenter. High-quality alpha mattes keep
    their learned soft edges; the coarse MediaPipe fallback receives the more
    aggressive guided-filter and anatomical guard processing.

    ``engine`` is ``"disabled"`` when replacement is off, ``"unavailable"`` when
    replacement was requested but no matte engine produced a mask (so the
    operator is told the photo was left unchanged, not that it was skipped).
    """
    if not enabled:
        return None, "disabled"

    rgb = cv2.cvtColor(ensure_bgr(source_bgr), cv2.COLOR_BGR2RGB)
    mask = None
    engine = None
    if MATTING_ENGINE_PREFERENCE in {"auto", "birefnet"}:
        mask = run_birefnet_matte(rgb, width, height)
        if mask is not None:
            engine = "BiRefNet Portrait Matting"
    if mask is None and MATTING_ENGINE_PREFERENCE in {"auto", "birefnet", "modnet"}:
        mask = run_modnet_matte(rgb, width, height)
        if mask is not None:
            engine = "MODNet Portrait Matting"
    if mask is None:
        engine = "MediaPipe Image Segmenter"
        mask = run_selfie_segmenter(mp_image, width, height)
        if mask is None:
            return None, "unavailable"
        mask = clean_coarse_matte(mask)

    quality_alpha = engine == "BiRefNet Portrait Matting"
    mask = finalize_matte(mask, source_bgr, face, width, height, preserve_detail=quality_alpha)
    if not quality_alpha:
        mask = protect_head_and_neck(mask, face, width, height, landmarks=landmarks, source_bgr=source_bgr)
    return np.clip(mask, 0, 1).astype(np.float32), engine


def protect_head_and_neck(mask, face, width, height, landmarks=None, source_bgr=None):
    """Restore low-confidence biometric features after portrait segmentation.

    Coarse selfie masks can classify ears, a narrow jaw edge, or the neck as
    background. Once composited, that looks like a missing body part. This guard
    is anchored to detected face geometry and only expands into pixels supported
    by the nearby person mask, so it preserves real features without drawing an
    artificial head silhouette into the background.
    """
    alpha = np.clip(np.asarray(mask, dtype=np.float32).squeeze(), 0, 1)
    if alpha.shape[:2] != (height, width):
        alpha = cv2.resize(alpha, (width, height), interpolation=cv2.INTER_LINEAR)

    face_width = max(8.0, float(face.get("faceWidth", min(width, height) * 0.25)))
    head_height = max(12.0, float(face.get("headHeight", min(width, height) * 0.38)))
    cx = float(face.get("centerX", width / 2))
    cy = float(face.get("centerY", height * 0.42))
    bounds = face.get("bounds") or {}
    min_x = float(bounds.get("minX", cx - face_width / 2))
    max_x = float(bounds.get("maxX", cx + face_width / 2))
    min_y = float(bounds.get("minY", cy - head_height * 0.34))
    max_y = float(bounds.get("maxY", cy + head_height * 0.42))

    if source_bgr is None:
        return alpha
    source = ensure_bgr(source_bgr)
    if source.shape[:2] != (height, width):
        source = cv2.resize(source, (width, height), interpolation=cv2.INTER_AREA)

    # Learn skin chroma from the detected face itself; fixed RGB skin rules are
    # inaccurate across complexions and lighting. The inner-face ellipse avoids
    # hair/background and the median resists eyes, brows, lips, and facial hair.
    sample_mask = np.zeros((height, width), dtype=np.uint8)
    face_h = max(8.0, max_y - min_y)
    cv2.ellipse(
        sample_mask,
        (int(round(cx)), int(round(min_y + face_h * 0.58))),
        (max(2, int(round(face_width * 0.28))), max(3, int(round(face_h * 0.27)))),
        0,
        0,
        360,
        255,
        -1,
    )
    sample_pixels = (sample_mask > 0) & (alpha > 0.72)
    if int(sample_pixels.sum()) < 24:
        return alpha
    lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
    skin_lab = np.median(lab[sample_pixels], axis=0)
    delta = np.abs(lab - skin_lab[None, None, :])
    # Luminance varies strongly between a lit cheek and a shadowed ear; chroma
    # is the stronger identity-independent signal, with a generous L allowance.
    skin_like = (delta[:, :, 0] <= 62) & (delta[:, :, 1] <= 19) & (delta[:, :, 2] <= 23)
    skin_like = cv2.morphologyEx(
        skin_like.astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    ).astype(np.float32)

    guard = np.zeros((height, width), dtype=np.uint8)

    # Ear guards sit just outside the face oval. Keep them compact: enough to
    # retain the pinna and lobe without pulling a large patch of background in.
    eye_y = float(face.get("eyeY", min_y + (max_y - min_y) * 0.34))
    ear_y = int(round(eye_y + head_height * 0.08))
    ear_axes = (max(2, int(round(face_width * 0.075))), max(3, int(round(head_height * 0.13))))
    for ear_x in (min_x - face_width * 0.015, max_x + face_width * 0.015):
        cv2.ellipse(guard, (int(round(ear_x)), ear_y), ear_axes, 0, 0, 360, 255, -1)

    # A conservative neck bridge prevents detached-head cutouts. Skin matching
    # stops clothing or background inside this geometry from being retained.
    chin_y = max_y
    neck = np.array(
        [
            [cx - face_width * 0.28, chin_y - head_height * 0.03],
            [cx + face_width * 0.28, chin_y - head_height * 0.03],
            [cx + face_width * 0.34, chin_y + head_height * 0.34],
            [cx - face_width * 0.34, chin_y + head_height * 0.34],
        ],
        dtype=np.int32,
    )
    cv2.fillConvexPoly(guard, neck, 255)

    # Nearby alpha support prevents the guard from jumping to a similarly
    # coloured object that is not connected to the detected subject.
    sigma = max(2.0, face_width * 0.045)
    support = cv2.GaussianBlur(alpha, (0, 0), sigmaX=sigma, sigmaY=sigma)
    support = np.clip((support - 0.025) / 0.24, 0, 1)
    # Cool/blue backgrounds can be close to shadowed skin in LAB distance. Only
    # *newly restored* pixels must also follow the face's warm chroma direction;
    # pixels already supported by the matte keep their original alpha. This is
    # what prevents the familiar coloured wedges behind an otherwise good ear.
    bgr = source.astype(np.float32)
    red_excess = bgr[:, :, 2] - bgr[:, :, 0]
    sample_red_excess = float(np.median(red_excess[sample_pixels]))
    warm_floor = max(2.0, min(12.0, sample_red_excess * 0.16))
    chroma_supported = (red_excess >= warm_floor) | (alpha >= 0.16)
    protected = (
        (guard.astype(np.float32) / 255.0)
        * skin_like
        * chroma_supported.astype(np.float32)
        * support
        * 0.985
    )
    return np.maximum(alpha, protected).astype(np.float32)


def finalize_matte(mask, source_bgr, face, width, height, preserve_detail=False):
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
        small = keep_main_subject(small, scale_face(face, scale), preserve_nearby=preserve_detail)
        if not preserve_detail:
            small = refine_matte_edges(small, guide)
        return np.clip(cv2.resize(small, (width, height), interpolation=cv2.INTER_LINEAR), 0, 1).astype(np.float32)

    mask = keep_main_subject(mask, face, preserve_nearby=preserve_detail)
    return mask if preserve_detail else refine_matte_edges(mask, source_bgr)


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


def keep_main_subject(mask, face=None, preserve_nearby=False):
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
    if preserve_nearby:
        # A high-quality portrait matte can contain detached curls or flyaway
        # hair. Keep components inside the edge band while dropping distant
        # people and background objects.
        other_solid &= keep_region < 0.5
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


def birefnet_ready():
    return bool(
        BIREFNET_MODEL_PATH.exists()
        and BIREFNET_MODEL_PATH.stat().st_size > 100_000_000
        and importlib.util.find_spec("onnxruntime") is not None
    )


def birefnet_inventory_status():
    if birefnet_unavailable:
        return "error"
    return "ready" if birefnet_ready() else "optional-not-installed"


def disable_birefnet(reason):
    global birefnet_unavailable
    birefnet_unavailable = True
    log_warn_once(f"BiRefNet disabled: {reason}. Falling back to a lighter matte engine.")


def preferred_onnx_providers(ort):
    requested = os.getenv("KVNP_ONNX_PROVIDER", "auto").strip().lower()
    available = set(ort.get_available_providers())
    if requested in {"cuda", "gpu"} and "CUDAExecutionProvider" not in available:
        log_warn_once("CUDA matting was requested but CUDAExecutionProvider is unavailable; using CPU.")
    if requested in {"auto", "cuda", "gpu"} and "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if requested in {"auto", "openvino"} and "OpenVINOExecutionProvider" in available:
        return ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def get_birefnet_session():
    global birefnet_session, birefnet_unavailable, birefnet_provider
    if birefnet_session is not None:
        return birefnet_session
    if birefnet_unavailable or not birefnet_ready():
        return None
    try:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        default_threads = min(4, os.cpu_count() or 1)
        options.intra_op_num_threads = max(1, int(os.getenv("KVNP_ONNX_THREADS", str(default_threads))))
        providers = preferred_onnx_providers(ort)
        birefnet_session = ort.InferenceSession(
            str(BIREFNET_MODEL_PATH),
            sess_options=options,
            providers=providers,
        )
        active = birefnet_session.get_providers()
        birefnet_provider = active[0] if active else "unknown"
        log_warn_once(f"BiRefNet Portrait Matting ready via {birefnet_provider}.")
    except Exception as error:
        disable_birefnet(f"failed to load {BIREFNET_MODEL_PATH.name}: {error}")
        return None
    return birefnet_session


def normalize_birefnet_output(output):
    logits = np.asarray(output, dtype=np.float32)
    if logits.ndim >= 4:
        logits = logits[0, 0]
    else:
        logits = np.squeeze(logits)
    if logits.ndim != 2:
        return None
    alpha = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
    low = float(alpha.min()) if alpha.size else 0.0
    high = float(alpha.max()) if alpha.size else 0.0
    if high - low > 1e-5:
        # Match the established BiRefNet ONNX inference contract used by rembg.
        alpha = (alpha - low) / (high - low)
    return np.clip(alpha, 0, 1).astype(np.float32)


def run_birefnet_matte(rgb, width, height, input_size=1024):
    """Run the BiRefNet portrait ONNX model and return a full-resolution alpha."""
    session = get_birefnet_session()
    if session is None:
        return None
    try:
        resized = cv2.resize(rgb, (input_size, input_size), interpolation=cv2.INTER_LANCZOS4)
        tensor = resized.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = (tensor - mean[None, None, :]) / std[None, None, :]
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...].astype(np.float32)
        output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
        alpha = normalize_birefnet_output(output)
        if alpha is None:
            disable_birefnet(f"unexpected output shape {np.asarray(output).shape}")
            return None
        return cv2.resize(alpha, (width, height), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    except Exception as error:
        disable_birefnet(f"inference error: {error}")
        return None


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


def apply_background_cleanup(mask, strength, engine=None):
    """Harden a person matte so faint background haze/spots snap to clean
    background, at the cost of slightly tighter hair edges. "strong" remaps the
    alpha so anything below ~0.5 becomes fully transparent (pure background),
    "max" pushes that threshold higher for a perfectly flat field.
    """
    if mask is None or strength in (None, "soft"):
        return mask
    mask = np.asarray(mask, dtype=np.float32)
    quality_alpha = engine == "BiRefNet Portrait Matting"
    if quality_alpha and strength == "balanced":
        low, high = (0.01, 0.99)
    elif quality_alpha and strength == "strong":
        low, high = (0.025, 0.975)
    elif quality_alpha:
        low, high = (0.05, 0.95)
    elif strength == "balanced":
        low, high = (0.06, 0.94)
    elif strength == "strong":
        low, high = (0.18, 0.84)
    else:
        low, high = (0.32, 0.72)
    cleaned = np.clip((mask - low) / max(1e-3, high - low), 0.0, 1.0)
    # Smoothstep suppresses low-confidence background haze while retaining
    # gradual high-confidence hair edges better than a hard threshold.
    cleaned = cleaned * cleaned * (3.0 - 2.0 * cleaned)
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
    foreground = decontaminate_foreground(source, mask)
    composed = foreground * alpha + background_bgr * (1 - alpha)
    return ensure_bgr(np.clip(composed, 0, 255).astype(np.uint8))


def refine_output_matte(mask, source_bgr, engine=None):
    """Resolve the uncertain hair band from image colour at final resolution.

    MediaPipe provides the semantic person prior. GrabCut receives only that
    trimap (definite foreground/background plus an uncertain band), then a small
    guided filter aligns the retained edge to the source. Confident ears, face,
    hair and shoulders are locked as foreground and can never be removed here.
    """
    alpha = np.clip(np.asarray(mask, dtype=np.float32).squeeze(), 0, 1)
    source = ensure_bgr(source_bgr)
    if alpha.shape[:2] != source.shape[:2]:
        alpha = cv2.resize(alpha, (source.shape[1], source.shape[0]), interpolation=cv2.INTER_LINEAR)

    if engine == "BiRefNet Portrait Matting":
        # BiRefNet already predicts a high-resolution alpha matte. GrabCut is a
        # semantic classifier, not a matting model; running it here can erase
        # valid translucent curls and ear edges. Only snap certain pixels.
        alpha[alpha <= 0.002] = 0.0
        alpha[alpha >= 0.998] = 1.0
        return alpha.astype(np.float32)

    definite_bg = alpha <= 0.035
    definite_fg = alpha >= 0.94
    if int(definite_bg.sum()) < 64 or int(definite_fg.sum()) < 64:
        return alpha

    trimap = np.full(alpha.shape, cv2.GC_PR_BGD, dtype=np.uint8)
    trimap[alpha >= 0.38] = cv2.GC_PR_FGD
    trimap[definite_bg] = cv2.GC_BGD
    trimap[definite_fg] = cv2.GC_FGD
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            source,
            trimap,
            None,
            background_model,
            foreground_model,
            3,
            cv2.GC_INIT_WITH_MASK,
        )
    except cv2.error:
        return alpha

    selected = (trimap == cv2.GC_FGD) | (trimap == cv2.GC_PR_FGD)
    refined = np.where(selected, alpha, alpha * 0.025).astype(np.float32)
    if HAS_GUIDED_FILTER:
        try:
            guide = source.astype(np.float32) / 255.0
            refined = cv2.ximgproc.guidedFilter(guide=guide, src=refined, radius=4, eps=2e-4)
        except Exception:
            pass
    refined = np.clip(refined, 0, 1)
    rejected = (trimap == cv2.GC_BGD) | (trimap == cv2.GC_PR_BGD)
    refined[rejected & (alpha < 0.75)] = 0.0
    # Resampling and the guided filter can widen a one-pixel camera edge into a
    # visible grey ring. A final smooth remap contracts that uncertainty while
    # preserving a soft transition for real wisps and curls.
    refined = np.clip((refined - 0.16) / 0.68, 0, 1)
    refined = refined * refined * (3.0 - 2.0 * refined)
    refined[definite_fg] = 1.0
    refined[definite_bg] = 0.0
    return refined.astype(np.float32)


def decontaminate_foreground(source_bgr, mask):
    """Estimate true RGB at soft matte edges before changing the background.

    Fine hair pixels are optical mixtures of foreground and the capture's old
    background. Alpha compositing alone carries that old colour into the new
    background as a grey/green/blue halo. Local known-background and
    known-foreground samples let us solve the standard compositing equation for
    a much cleaner foreground colour without inventing shape or facial detail.
    """
    source = ensure_bgr(source_bgr).astype(np.float32)
    alpha = np.clip(np.asarray(mask, dtype=np.float32).squeeze(), 0, 1)
    if alpha.shape[:2] != source.shape[:2]:
        alpha = cv2.resize(alpha, (source.shape[1], source.shape[0]), interpolation=cv2.INTER_LINEAR)

    height, width = alpha.shape
    sigma = max(2.0, min(12.0, min(width, height) * 0.014))
    background_weight = np.clip((0.08 - alpha) / 0.08, 0, 1)
    foreground_weight = np.clip((alpha - 0.88) / 0.12, 0, 1)

    def local_average(weight):
        denominator = cv2.GaussianBlur(weight, (0, 0), sigmaX=sigma, sigmaY=sigma)
        numerator = cv2.GaussianBlur(source * weight[..., None], (0, 0), sigmaX=sigma, sigmaY=sigma)
        return numerator / np.maximum(denominator[..., None], 1e-4), denominator

    background_estimate, background_support = local_average(background_weight)
    foreground_estimate, foreground_support = local_average(foreground_weight)
    background_estimate = np.where(background_support[..., None] > 1e-4, background_estimate, source)
    foreground_estimate = np.where(foreground_support[..., None] > 1e-4, foreground_estimate, source)

    a = alpha[..., None]
    solved = (source - (1.0 - a) * background_estimate) / np.maximum(a, 0.12)
    solved = np.clip(solved, 0, 255)
    solve_confidence = np.clip((a - 0.12) / 0.62, 0, 1)
    recovered = solved * solve_confidence + foreground_estimate * (1.0 - solve_confidence)

    # Opaque interiors remain byte-for-byte source pixels. The correction peaks
    # on the semi-transparent band where colour spill exists and fades smoothly
    # at both sides of the matte.
    edge_blend = np.clip((0.98 - a) / 0.45, 0, 1) * np.clip((a - 0.025) / 0.18, 0, 1)
    supported = (background_support[..., None] > 1e-4) & (foreground_support[..., None] > 1e-4)
    edge_blend *= supported.astype(np.float32)
    return source * (1.0 - edge_blend) + recovered * edge_blend


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
    mode = mode if mode in {"natural", "studio", "ai-clean", "strong"} else "natural"
    if mode == "ai-clean":
        return identity_clean_enhance(image_bgr)
    if mode == "strong":
        return ai_clean_enhance(image_bgr, strength="strong", restore_face=True)

    settings = {
        "natural": {"denoise": 2, "clahe": 1.04, "chroma": 0.10, "amount": 0.08, "blend": 0.30},
        "studio": {"denoise": 3, "clahe": 1.10, "chroma": 0.18, "amount": 0.14, "blend": 0.48},
    }[mode]

    enhanced = gray_world_balance(image_bgr)
    enhanced = cv2.fastNlMeansDenoisingColored(
        enhanced,
        None,
        h=settings["denoise"],
        hColor=settings["denoise"],
        templateWindowSize=7,
        searchWindowSize=17,
    )
    enhanced = chroma_noise_reduction(enhanced, strength=settings["chroma"])
    enhanced = local_contrast(enhanced, settings["clahe"])
    enhanced = preserve_skin_tone(image_bgr, enhanced, strength=0.20)
    enhanced = edge_aware_sharpen(enhanced, amount=settings["amount"], radius=0.72)
    # Preserve the capture as the dominant signal. This avoids waxy skin,
    # crunchy hair, and segmentation halos while still reducing minor noise.
    enhanced = cv2.addWeighted(image_bgr, 1 - settings["blend"], enhanced, settings["blend"], 0)
    return ensure_bgr(enhanced)


def identity_clean_enhance(image_bgr):
    original = ensure_bgr(image_bgr)
    balanced = gray_world_balance(original)
    denoised = cv2.fastNlMeansDenoisingColored(
        balanced,
        None,
        h=2,
        hColor=2,
        templateWindowSize=7,
        searchWindowSize=17,
    )
    denoised = chroma_noise_reduction(denoised, strength=0.12)
    enhanced = cv2.addWeighted(original, 0.82, denoised, 0.18, 0)
    enhanced = local_contrast(enhanced, 1.04)
    enhanced = preserve_skin_tone(original, enhanced, strength=0.18)
    enhanced = edge_aware_sharpen(enhanced, amount=0.10, radius=0.68)
    return ensure_bgr(cv2.addWeighted(original, 0.72, enhanced, 0.28, 0))


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


def crop_mask_and_resize(mask, crop, output_width, output_height):
    """Crop/pad an alpha matte with the same geometry used for the RGB image."""
    matte = np.clip(np.asarray(mask, dtype=np.float32).squeeze(), 0, 1)
    src_h, src_w = matte.shape[:2]
    x = int(round(crop["x"]))
    y = int(round(crop["y"]))
    width = max(1, int(round(crop["width"])))
    height = max(1, int(round(crop["height"])))

    if x >= 0 and y >= 0 and x + width <= src_w and y + height <= src_h:
        crop_mask = matte[y : y + height, x : x + width]
    else:
        crop_mask = np.zeros((height, width), dtype=np.float32)
        sx1, sy1 = max(0, x), max(0, y)
        sx2, sy2 = min(src_w, x + width), min(src_h, y + height)
        if sx2 > sx1 and sy2 > sy1:
            crop_mask[sy1 - y : sy2 - y, sx1 - x : sx2 - x] = matte[sy1:sy2, sx1:sx2]

    interpolation = cv2.INTER_LINEAR if output_width > crop_mask.shape[1] else cv2.INTER_AREA
    resized = cv2.resize(crop_mask, (output_width, output_height), interpolation=interpolation)
    return np.clip(resized, 0, 1).astype(np.float32)


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


def head_outline_from_matte(mask, points, face, width, height):
    """Return a visible head silhouette: hair + ears from the person matte and
    the lower jaw from Face Landmarker. MediaPipe's built-in FACE_OVAL traces
    facial skin, so presenting it as a head outline is misleading.
    """
    if mask is None or face is None or len(points) <= max(FACE_OVAL):
        return None

    matte = np.asarray(mask, dtype=np.float32)
    if matte.shape[:2] != (height, width):
        matte = cv2.resize(matte, (width, height), interpolation=cv2.INTER_LINEAR)
    binary = (matte > 0.34).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return None

    cx = int(clamp(float(face["centerX"]), 0, width - 1))
    cy = int(clamp(float(face["centerY"]), 0, height - 1))
    radius = max(3, int(round(float(face.get("faceWidth", face["headHeight"] * 0.55)) * 0.12)))
    patch = labels[max(0, cy - radius) : min(height, cy + radius + 1), max(0, cx - radius) : min(width, cx + radius + 1)]
    candidates = patch[patch > 0]
    if candidates.size:
        component_label = int(np.bincount(candidates).argmax())
    else:
        component_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    component = labels == component_label

    head_height = float(face["headHeight"])
    face_width = float(face.get("faceWidth", head_height * 0.58))
    half_roi = max(face_width * 0.92, head_height * 0.66)
    roi_x1 = int(clamp(cx - half_roi, 0, width - 1))
    roi_x2 = int(clamp(cx + half_roi, roi_x1 + 1, width))
    # Join below the ears so their full outer edge comes from the matte; below
    # these landmarks the Face Landmarker jaw is more stable than the body mask.
    right_join = points[288]
    left_join = points[58]
    scan_bottom = int(clamp(max(right_join["y"], left_join["y"]), 1, height - 1))
    expected_crown = float(face["centerY"]) - head_height / 2.0
    scan_top = int(clamp(expected_crown - head_height * 0.08, 0, scan_bottom - 1))

    rows = []
    for row_y in range(scan_top, scan_bottom + 1):
        xs = np.flatnonzero(component[row_y, roi_x1:roi_x2])
        if xs.size >= 2:
            rows.append((row_y, float(roi_x1 + xs[0]), float(roi_x1 + xs[-1])))
    if len(rows) < 10:
        return None

    # Ignore isolated pixels above the real crown, then smooth segmentation
    # stair-steps without rounding away curls or ears.
    first_run = 0
    for index in range(len(rows) - 3):
        if rows[index + 3][0] - rows[index][0] <= 4:
            first_run = index
            break
    rows = rows[first_run:]
    step = max(2, int(round(head_height / 110.0)))
    sampled = rows[::step]
    if sampled[-1] != rows[-1]:
        sampled.append(rows[-1])

    ys = np.array([item[0] for item in sampled], dtype=np.float32)
    left_x = np.array([item[1] for item in sampled], dtype=np.float32)
    right_x = np.array([item[2] for item in sampled], dtype=np.float32)

    def smooth(values):
        if len(values) < 5:
            return values
        kernel = np.array([1, 2, 3, 2, 1], dtype=np.float32)
        kernel /= kernel.sum()
        return np.convolve(np.pad(values, (2, 2), mode="edge"), kernel, mode="valid")

    left_x = smooth(left_x)
    right_x = smooth(right_x)
    left_side = [(int(round(left_x[i])), int(round(ys[i]))) for i in range(len(ys) - 1, -1, -1)]
    right_side = [(int(round(right_x[i])), int(round(ys[i]))) for i in range(len(ys))]

    right_pos = FACE_OVAL.index(288)
    left_pos = FACE_OVAL.index(58)
    jaw = [
        (int(round(points[index]["x"])), int(round(points[index]["y"])))
        for index in FACE_OVAL[right_pos : left_pos + 1]
    ]
    polygon = np.array(left_side + right_side + jaw, dtype=np.int32)
    return polygon if len(polygon) >= 12 else None


def add_preview_watermark(image_bgr):
    result = ensure_bgr(image_bgr).copy()
    height, width = result.shape[:2]
    band_height = max(34, int(round(height * 0.09)))
    band = result.copy()
    cv2.rectangle(band, (0, height - band_height), (width, height), (12, 15, 19), thickness=-1)
    result = cv2.addWeighted(band, 0.82, result, 0.18, 0)
    label = "EDITING PREVIEW - NOT FOR SUBMISSION"
    scale = max(0.38, min(0.9, width / 720.0))
    thickness = max(1, int(round(scale * 2)))
    text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0]
    while text_size[0] > width - 20 and scale > 0.3:
        scale -= 0.04
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0]
    origin = (max(10, (width - text_size[0]) // 2), height - max(9, (band_height - text_size[1]) // 2))
    cv2.putText(result, label, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (64, 186, 255), thickness, cv2.LINE_AA)
    return result


def draw_dashed_line(image, start, end, color, thickness=2, dash=14, gap=9):
    """Draw a scale-independent dashed guide between two pixel coordinates."""
    x1, y1 = start
    x2, y2 = end
    distance_px = math.hypot(x2 - x1, y2 - y1)
    if distance_px < 1:
        return
    step = max(1, dash + gap)
    for offset in range(0, int(distance_px) + 1, step):
        end_offset = min(distance_px, offset + dash)
        start_ratio = offset / distance_px
        end_ratio = end_offset / distance_px
        p1 = (int(round(x1 + (x2 - x1) * start_ratio)), int(round(y1 + (y2 - y1) * start_ratio)))
        p2 = (int(round(x1 + (x2 - x1) * end_ratio)), int(round(y1 + (y2 - y1) * end_ratio)))
        cv2.line(image, p1, p2, color, thickness, lineType=cv2.LINE_AA)


def build_overlay(source_bgr, points, crop, matte=None, face=None, profile=None, posture=None):
    source = ensure_bgr(source_bgr)
    dim = source.copy()
    cv2.rectangle(dim, (0, 0), (source.shape[1], source.shape[0]), (10, 24, 39), thickness=-1)
    overlay = cv2.addWeighted(dim, 0.36, source, 0.64, 0)

    x = int(round(crop["x"]))
    y = int(round(crop["y"]))
    w = int(round(crop["width"]))
    h = int(round(crop["height"]))
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(source.shape[1], x + w), min(source.shape[0], y + h)
    if x2 > x1 and y2 > y1:
        overlay[y1:y2, x1:x2] = source[y1:y2, x1:x2]

    crop_thickness = max(3, int(round(max(source.shape[:2]) / 420)))
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (46, 204, 113), crop_thickness, lineType=cv2.LINE_AA)

    head_outline = head_outline_from_matte(matte, points, face, source.shape[1], source.shape[0])
    if head_outline is None:
        head_outline = np.array(
            [[int(points[index]["x"]), int(points[index]["y"])] for index in FACE_OVAL],
            dtype=np.int32,
        )
    cv2.polylines(
        overlay,
        [head_outline],
        isClosed=True,
        color=(255, 178, 36),
        thickness=max(2, crop_thickness - 1),
        lineType=cv2.LINE_AA,
    )

    guide_thickness = max(2, crop_thickness - 1)
    target_color = (60, 105, 255)
    draw_dashed_line(
        overlay,
        (x + w // 2, y),
        (x + w // 2, y + h),
        target_color,
        guide_thickness,
        dash=max(10, crop_thickness * 5),
        gap=max(7, crop_thickness * 3),
    )
    font_scale = max(0.42, min(0.78, max(source.shape[:2]) / 1500.0))

    # Draw the detected eye line and head axis, not an abstract oval. These
    # guides make tilt and face alignment visible without suggesting that the
    # cyan silhouette is the skin-only FaceMesh oval.
    level_status = "review"
    gaze_status = "review"
    direction_status = "review"
    if face is not None:
        roll = abs(float(face.get("rollDegrees", 0)))
        yaw = abs(float(face.get("yawProxy", 0)))
        gaze = face.get("gazeOffsetPercent")
        level_status = threshold_status(roll, 4.0, 7.0)
        direction_status = threshold_status(yaw, 9.0, 14.0)
        gaze_status = "review" if gaze is None else threshold_status(abs(float(gaze)), 3.0, 4.0)
        pitch_offset = (posture or {}).get("pitchOffsetDegrees")
        pitch_status = "review" if pitch_offset is None else threshold_status(abs(float(pitch_offset)), 5.0, 9.0)
        shoulder_level = (posture or {}).get("shoulderLevelDegrees")
        shoulder_level_status = "review" if shoulder_level is None else threshold_status(float(shoulder_level), 4.0, 7.0)
        shoulder_status = "review"
        shoulder_room = None
        source_background_status = "review"
        source_background_value = ""
        profile_head = (profile or {}).get("head") or {}
        if profile_head:
            head_percent = float(face["headHeight"]) / max(1.0, float(h)) * 100.0
            top_margin = ((float(face["centerY"]) - float(face["headHeight"]) / 2.0 - float(y)) / max(1.0, float(h))) * 100.0
            shoulder_room = 100.0 - top_margin - head_percent
            target_room = 100.0 - float(profile_head["topMarginPercent"]) - float(profile_head["targetPercent"])
            shoulder_status = threshold_status(abs(shoulder_room - target_room), 8.0, 12.0)
            if shoulder_room < 6:
                shoulder_status = "fail"
        if profile:
            source_background = background_stats(source, profile, replaced=False)
            source_background_status = source_background["status"]
            source_background_value = source_background["value"]

        status_colors = {
            "pass": (125, 217, 65),
            "warning": (41, 180, 240),
            "fail": (46, 68, 232),
            "review": (255, 167, 106),
        }
        level_color = status_colors[level_status]

        if len(points) > max(LEFT_EYE_INNER, RIGHT_EYE_INNER):
            left_center = (
                int(round((points[LEFT_EYE]["x"] + points[LEFT_EYE_INNER]["x"]) / 2)),
                int(round((points[LEFT_EYE]["y"] + points[LEFT_EYE_INNER]["y"]) / 2)),
            )
            right_center = (
                int(round((points[RIGHT_EYE]["x"] + points[RIGHT_EYE_INNER]["x"]) / 2)),
                int(round((points[RIGHT_EYE]["y"] + points[RIGHT_EYE_INNER]["y"]) / 2)),
            )
            cv2.line(overlay, left_center, right_center, level_color, guide_thickness, cv2.LINE_AA)
            cv2.circle(overlay, left_center, max(3, crop_thickness + 1), level_color, -1, cv2.LINE_AA)
            cv2.circle(overlay, right_center, max(3, crop_thickness + 1), level_color, -1, cv2.LINE_AA)

        if len(points) > max(FOREHEAD, CHIN):
            forehead = (int(round(points[FOREHEAD]["x"])), int(round(points[FOREHEAD]["y"])))
            chin = (int(round(points[CHIN]["x"])), int(round(points[CHIN]["y"])))
            cv2.line(overlay, forehead, chin, level_color, guide_thickness, cv2.LINE_AA)

        shoulder_points = (posture or {}).get("shoulderPoints")
        if shoulder_points and len(shoulder_points) == 2:
            p1 = tuple(int(round(value)) for value in shoulder_points[0])
            p2 = tuple(int(round(value)) for value in shoulder_points[1])
            cv2.line(overlay, p1, p2, status_colors[shoulder_level_status], guide_thickness, cv2.LINE_AA)
            cv2.circle(overlay, p1, max(3, crop_thickness + 1), status_colors[shoulder_level_status], -1, cv2.LINE_AA)
            cv2.circle(overlay, p2, max(3, crop_thickness + 1), status_colors[shoulder_level_status], -1, cv2.LINE_AA)

        eye_rule = ((profile or {}).get("head") or {}).get("eye")
        if eye_rule and eye_rule.get("targetFromTopPercent") is not None:
            target_eye_y = int(round(y + h * float(eye_rule["targetFromTopPercent"]) / 100.0))
            draw_dashed_line(
                overlay,
                (x + max(8, crop_thickness * 3), target_eye_y),
                (x + w - max(8, crop_thickness * 3), target_eye_y),
                target_color,
                guide_thickness,
                dash=max(10, crop_thickness * 5),
                gap=max(7, crop_thickness * 3),
            )

        status_label = {"pass": "PASS", "warning": "CHECK", "fail": "RETAKE", "review": "CHECK"}
        rows = [
            ("HEAD LEVEL", level_status, f'{roll:.1f} DEG'),
            ("CHIN / CAMERA", pitch_status, "N/A" if pitch_offset is None else f'{abs(float(pitch_offset)):.1f} DEG'),
            ("HEAD DIRECTION", direction_status, f'{yaw:.1f}%'),
            ("EYE GAZE", gaze_status, "N/A" if gaze is None else f'{abs(float(gaze)):.1f}%'),
            ("SHOULDER LEVEL", shoulder_level_status, "N/A" if shoulder_level is None else f'{float(shoulder_level):.1f} DEG'),
            ("SHOULDER FRAME", shoulder_status, "N/A" if shoulder_room is None else f'{shoulder_room:.1f}%'),
            ("SOURCE BACKGROUND", source_background_status, source_background_value),
        ]
        row_height = max(24, int(round(font_scale * 36)))
        panel_width = max(235, int(round(font_scale * 390)))
        panel_height = row_height * len(rows) + 14
        panel_x = int(clamp(x + 12, 6, max(6, source.shape[1] - panel_width - 6)))
        panel_y = int(clamp(y + h - panel_height - 12, 6, max(6, source.shape[0] - panel_height - 6)))
        panel = overlay.copy()
        cv2.rectangle(panel, (panel_x, panel_y), (panel_x + panel_width, panel_y + panel_height), (11, 13, 16), -1)
        overlay = cv2.addWeighted(panel, 0.78, overlay, 0.22, 0)
        for index, (name, status, value) in enumerate(rows):
            baseline = panel_y + 10 + row_height * index + int(row_height * 0.65)
            color = status_colors[status]
            cv2.putText(overlay, name, (panel_x + 10, baseline), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.72, (236, 233, 226), 1, cv2.LINE_AA)
            right = status_label[status] if not value else f'{status_label[status]}  {value}'
            right_size = cv2.getTextSize(right, cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.68, 1)[0]
            cv2.putText(
                overlay,
                right,
                (panel_x + panel_width - right_size[0] - 10, baseline),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale * 0.68,
                color,
                1,
                cv2.LINE_AA,
            )
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
    saturation = np.zeros_like(max_channel, dtype=np.float32)
    np.divide(max_channel - min_channel, max_channel, out=saturation, where=max_channel > 1)
    saturation *= 100

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
    # Without replacement these are the actual submission pixels. A mandatory
    # background rule is binary: values outside the programme tolerance require
    # a retake, not a dismissible warning.
    if not replaced and status == "warning":
        status = "fail"

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
    policy_text = " ".join(
        [
            *profile.get("reviewChecks", []),
            str((profile.get("allowedEdits") or {}).get("note", "")),
        ]
    ).lower()
    strict_terms = (
        "unaltered",
        "must not be altered",
        "must not be digitally altered",
        "no digital retouching",
        "no retouching",
        "must not be retouched",
        "digitally enhanced or altered",
        "true likeness",
    )
    strict = any(term in policy_text for term in strict_terms)
    if profile.get("country") in {"US", "CA", "GB", "AU"}:
        strict = True
    return {
        "strict": strict,
        "mode": "validation_only" if strict else "assisted_editing",
        "label": "government may reject digitally altered or AI-restored photos" if strict else "identity must not be changed",
    }


def build_checks(face, crop, profile, stats, background_stats_result, output_bytes, background_replaced, mask_stats, enhanced, enhancement_mode, corrections=None):
    corrections = corrections or []
    head_percent = (face["headHeight"] / crop["height"]) * 100
    center_offset = abs((face["centerX"] - (crop["x"] + crop["width"] / 2)) / crop["width"]) * 100
    top_margin = (((face["centerY"] - face["headHeight"] / 2) - crop["y"]) / crop["height"]) * 100
    shoulder_room = 100.0 - top_margin - head_percent
    target_shoulder_room = 100.0 - float(profile["head"]["topMarginPercent"]) - float(profile["head"]["targetPercent"])
    shoulder_delta = shoulder_room - target_shoulder_room
    shoulder_status = threshold_status(abs(shoulder_delta), 8.0, 12.0)
    if shoulder_room < 6:
        shoulder_status = "fail"
    if shoulder_delta > 8:
        shoulder_note = "too much upper body"
    elif shoulder_delta < -8:
        shoulder_note = "shoulders too tight"
    else:
        shoulder_note = "balanced upper shoulders"
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

    gaze_offset = face.get("gazeOffsetPercent")
    gaze_status = "review" if gaze_offset is None else threshold_status(float(gaze_offset), 3.0, 4.0)
    gaze_value = "not measurable" if gaze_offset is None else f'{float(gaze_offset):.1f}% iris offset'

    checks = [
        check("face_detection", "Face detection", "pass" if face["faceCount"] == 1 else "fail", f'{face["faceCount"]} face / Python FaceMesh', "1 clear face"),
        check("face_outline", "Head outline", "pass", "hair, ears and jaw mapped", "visible head silhouette"),
        check("head_size", "Head size", range_status(head_percent, profile["head"]["minPercent"], profile["head"]["maxPercent"]), f"{head_percent:.1f}%", f'{profile["head"]["minPercent"]}-{profile["head"]["maxPercent"]}%'),
        check("head_center", "Horizontal center", threshold_status(center_offset, 5, 8), f"{center_offset:.1f}% offset", "<= 5%"),
        check("top_margin", "Top margin", top_margin_status, f"{top_margin:.1f}%", f'{profile["head"]["topMarginPercent"]}% target'),
        check(
            "shoulder_framing",
            "Shoulder framing",
            shoulder_status,
            f"{shoulder_room:.1f}% below chin / {shoulder_note}",
            f"about {target_shoulder_room:.0f}% / head and upper shoulders only",
        ),
        check("head_tilt", "Head tilt", threshold_status(abs(face["rollDegrees"]), 4, 7), f'{abs(face["rollDegrees"]):.1f} deg', "<= 4 deg"),
        check("face_direction", "Head direction", threshold_status(abs(face["yawProxy"]), 9, 14), f'{abs(face["yawProxy"]):.1f}% nose offset', "head facing camera"),
        check("mouth", "Mouth", threshold_status(face["mouthGapPercent"], 1.4, 2.4), f'{face["mouthGapPercent"]:.1f}%', "closed/neutral"),
        check("eyes_open", "Eyes open", threshold_status_inverse(face.get("eyeOpenness", 0.3), 0.17, 0.12), f'{face.get("eyeOpenness", 0):.2f} aperture', "eyes fully open"),
        check("eye_gaze", "Eye gaze", gaze_status, gaze_value, "both eyes looking into camera"),
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


def build_posture_checks(posture):
    posture = posture or {}
    pitch = posture.get("pitchOffsetDegrees")
    shoulder_level = posture.get("shoulderLevelDegrees")
    body_lean = posture.get("bodyLeanPercent")

    if pitch is None:
        pitch_check = check("source_head_pitch", "Chin and camera level", "review", "not measurable", "chin neutral, camera at eye level")
    else:
        pitch_note = "chin neutral"
        if float(pitch) < -5.0:
            pitch_note = "chin down - raise chin and place lens at eye level"
        elif float(pitch) > 5.0:
            pitch_note = "chin raised - lower chin and place lens at eye level"
        pitch_check = check(
            "source_head_pitch",
            "Chin and camera level",
            threshold_status(abs(float(pitch)), 5.0, 9.0),
            f"{abs(float(pitch)):.1f} deg offset / {pitch_note}",
            "<= 5 deg / neutral chin",
        )

    if shoulder_level is None:
        shoulder_check = check("source_shoulder_level", "Shoulder level", "review", "not measurable", "both shoulders level and relaxed")
    else:
        shoulder_note = "level"
        if float(shoulder_level) > 4.0:
            shoulder_note = "one shoulder higher - sit upright and relax both arms"
        shoulder_check = check(
            "source_shoulder_level",
            "Shoulder level",
            threshold_status(float(shoulder_level), 4.0, 7.0),
            f"{float(shoulder_level):.1f} deg / {shoulder_note}",
            "<= 4 deg / shoulders level",
        )

    if body_lean is None:
        alignment_check = check("source_body_alignment", "Body alignment", "review", "not measurable", "head centered over shoulders")
    else:
        source = posture.get("bodyLeanSource") or "upper body"
        alignment_check = check(
            "source_body_alignment",
            "Body alignment",
            threshold_status(float(body_lean), 10.0, 18.0),
            f"{float(body_lean):.1f}% offset / {source}",
            "<= 10% / sit upright, do not lean",
        )
    return [pitch_check, shoulder_check, alignment_check]


def build_source_quality(
    source_bgr,
    face,
    profile,
    source_stats,
    face_stats,
    source_bytes,
    background_replaced,
    mask_stats,
    corrections=None,
    posture=None,
):
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
        source_background = background_stats(source_bgr, profile, replaced=False)
        background_status = source_background["status"]
        background_value = source_background["value"]
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
        *build_posture_checks(posture),
        check("source_background_path", "Source background", background_status, background_value, "programme-required plain background"),
        check("source_file", "Source file", "pass", format_bytes(source_bytes), "original image retained for audit"),
    ]


def build_pipeline_report(background_replaced, mask_stats, enhanced, enhancement_mode):
    stages = [
        {
            "id": "geometry",
            "label": "Geometry",
            "engine": "MediaPipe Face + Pose Landmarkers",
            "status": "pass",
            "detail": "478-point face mesh, chin pitch, shoulder level, body alignment and crop placement",
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
    background_failure = any(
        item["id"] in {"source_background_path", "background_uniformity"} and item["status"] == "fail"
        for item in [*source_quality, *checks]
    )
    gaze_failure = any(item["id"] == "eye_gaze" and item["status"] == "fail" for item in checks)
    posture_failure = any(
        item["id"] in {"source_head_pitch", "source_shoulder_level", "source_body_alignment"} and item["status"] == "fail"
        for item in source_quality
    )
    unfixable_failure = background_failure or gaze_failure or posture_failure

    if source_failures or unfixable_failure:
        status = "retake"
        title = "Retake source photo"
        if background_failure and gaze_failure:
            message = "Retake against the required plain background while looking directly into the camera lens."
        elif background_failure and posture_failure:
            message = "Retake against the required plain background while sitting upright with a neutral chin and level shoulders."
        elif background_failure:
            message = "The selected programme requires a plain capture background and does not permit replacing this one digitally."
        elif gaze_failure:
            message = "The eyes are not aligned with the camera. Retake while looking directly into the lens."
        elif posture_failure:
            message = "The capture posture is unsuitable. Retake with the lens at eye level, a neutral chin and both shoulders level."
        else:
            message = "The input has a capture problem that cannot be repaired safely for this programme."
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
        if background_failure:
            actions.append("Use the programme-required plain background when taking the photo")
        if gaze_failure:
            actions.append("Look directly into the camera lens")
        if any(item["id"] in {"source_focus", "source_face_pixels", "source_resolution"} and item["status"] == "fail" for item in source_quality):
            actions.append("Use a sharper, higher-resolution source")
        if any(item["id"] == "source_lighting" and item["status"] == "fail" for item in source_quality):
            actions.append("Use brighter, even light without clipping")
        if any(item["id"] in {"source_pose", "source_head_pitch", "face_direction", "head_tilt"} and item["status"] == "fail" for item in [*source_quality, *checks]):
            actions.append("Keep the head level and face the camera directly")
    pitch_issue = next((item for item in source_quality if item["id"] == "source_head_pitch" and item["status"] != "pass"), None)
    if pitch_issue:
        actions.append("Place the lens at eye level and keep the chin neutral; do not lean down toward the camera")
    shoulder_issue = next((item for item in source_quality if item["id"] == "source_shoulder_level" and item["status"] != "pass"), None)
    if shoulder_issue:
        actions.append("Sit upright with both shoulders level and both arms relaxed")
    alignment_issue = next((item for item in source_quality if item["id"] == "source_body_alignment" and item["status"] != "pass"), None)
    if alignment_issue:
        actions.append("Center the head over the shoulders and avoid leaning sideways")
    if any(item["id"] == "background_cleanup" and item["status"] != "pass" and item["value"] != "disabled" for item in checks):
        actions.append("Review hair and shoulder edges")
    if any(item["id"] == "shoulder_framing" and item["status"] != "pass" for item in checks):
        actions.append("Keep only the head and upper shoulders; avoid excess torso")
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
            "id": "mediapipe_pose_landmarker",
            "label": "MediaPipe Pose Landmarker Lite",
            "stage": "posture",
            "status": "ready" if pose_landmarker is not None else "optional-not-installed",
            "weight": POSE_MODEL_PATH.name,
        },
        {
            "id": "birefnet_portrait",
            "label": "BiRefNet Portrait Matting",
            "stage": "matting-quality",
            "status": birefnet_inventory_status(),
            "weight": BIREFNET_MODEL_PATH.name,
            "provider": birefnet_provider or "loads on first background job",
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


def encode_photo_export(image_bgr, spec=None):
    """Return an identity-preserving photo export and machine-readable metadata.

    The optional 2x path enlarges pixels with FSRCNN (or Lanczos when the model
    is unavailable). It never invokes face restoration or generative models.
    """
    spec = dict(spec or {})
    format_aliases = {
        "jpg": ("image/jpeg", "jpg"),
        "jpeg": ("image/jpeg", "jpg"),
        "image/jpeg": ("image/jpeg", "jpg"),
        "png": ("image/png", "png"),
        "image/png": ("image/png", "png"),
        "webp": ("image/webp", "webp"),
        "image/webp": ("image/webp", "webp"),
        "pdf": ("application/pdf", "pdf"),
        "application/pdf": ("application/pdf", "pdf"),
    }
    requested_format = str(spec.get("format", "image/jpeg")).strip().lower()
    if requested_format not in format_aliases:
        raise ValueError("Unsupported export format. Choose JPEG, PNG, WebP, or PDF.")
    mime, extension = format_aliases[requested_format]

    try:
        scale = int(spec.get("scale", 1))
        quality = int(round(float(spec.get("quality", 92))))
        dpi = int(round(float(spec.get("dpi", 300))))
    except (TypeError, ValueError):
        raise ValueError("Invalid export scale, quality, or DPI.")
    if scale not in (1, 2):
        raise ValueError("Export scale must be 1x or 2x.")
    quality = max(60, min(100, quality))
    dpi = max(72, min(1200, dpi))

    photo = ensure_bgr(image_bgr)
    height, width = photo.shape[:2]
    if width * height * scale * scale > int(MAX_MEGAPIXELS * 1_000_000):
        raise ValueError(f"High-resolution export exceeds the {MAX_MEGAPIXELS} MP safety limit.")

    upscale_engine = "none"
    if scale == 2:
        enlarged = superres_upscale(photo)
        if enlarged is not None:
            photo = enlarged
            upscale_engine = "FSRCNN 2x"
        else:
            photo = cv2.resize(photo, (width * 2, height * 2), interpolation=cv2.INTER_LANCZOS4)
            upscale_engine = "Lanczos 2x fallback"

    if mime == "image/jpeg":
        binary = set_jpeg_dpi(encode_jpeg_bytes(photo, quality), dpi)
    else:
        rgb = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        buffer = io.BytesIO()
        if mime == "image/png":
            pil.save(buffer, format="PNG", compress_level=5, dpi=(dpi, dpi))
        elif mime == "image/webp":
            pil.save(buffer, format="WEBP", quality=quality, method=4)
        else:
            # Pillow derives the PDF MediaBox from pixel dimensions/resolution,
            # producing a page whose physical size matches the selected DPI.
            pil.save(buffer, format="PDF", resolution=float(dpi), quality=quality)
        binary = buffer.getvalue()

    out_height, out_width = photo.shape[:2]
    return binary, {
        "mime": mime,
        "extension": extension,
        "width": int(out_width),
        "height": int(out_height),
        "dpi": dpi,
        "scale": scale,
        "upscaleEngine": upscale_engine,
    }


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
    uvicorn.run("server:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "4173")), reload=False)


