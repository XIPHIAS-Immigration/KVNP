"""Standard-camera (laptop webcam / budget phone) capture simulation.

Real webcams differ from studio photos in reproducible ways:
  - low resolution (720p / 480p sensor)
  - JPEG compression (q ~60-78)
  - sensor noise (luma + chroma, worse in low light)
  - white-balance drift (greenish/bluish office lighting)
  - mild softness (small plastic lens, slight defocus)
  - slightly low, uneven indoor exposure

`simulate(img, profile_name)` applies a named combination so tests are
reproducible and each case is labelled with what was applied.
"""
import cv2
import numpy as np

PROFILES = {
    # name: (long_side, jpeg_q, noise_sigma, wb_shift, blur_sigma, exposure)
    "webcam720":     (1280, 74, 4.0, "cool",  0.5, 0.92),
    "webcam480":     (640,  68, 6.0, "green", 0.7, 0.90),
    "lowlight720":   (1280, 70, 10.0, "warm", 0.6, 0.62),
    "oldphone":      (960,  60, 7.0, "warm",  0.9, 0.95),
    "webcam720_ok":  (1280, 78, 3.0, "none",  0.3, 1.0),
}


def simulate(bgr, profile="webcam720", seed=7):
    long_side, q, noise_sigma, wb, blur_sigma, exposure = PROFILES[profile]
    rng = np.random.default_rng(seed)
    img = bgr.copy()

    # 1) downscale to sensor resolution
    h, w = img.shape[:2]
    scale = long_side / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # 2) exposure drop (indoor)
    if exposure != 1.0:
        img = cv2.convertScaleAbs(img, alpha=exposure, beta=0)

    # 3) white-balance drift
    f = img.astype(np.float32)
    if wb == "cool":
        f[:, :, 0] *= 1.08; f[:, :, 2] *= 0.94
    elif wb == "green":
        f[:, :, 1] *= 1.09; f[:, :, 2] *= 0.95
    elif wb == "warm":
        f[:, :, 2] *= 1.10; f[:, :, 0] *= 0.92
    img = np.clip(f, 0, 255).astype(np.uint8)

    # 4) small-lens softness
    if blur_sigma > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur_sigma)

    # 5) sensor noise (luma + a little chroma)
    noise = rng.normal(0, noise_sigma, img.shape[:2]).astype(np.float32)
    chroma = rng.normal(0, noise_sigma * 0.4, img.shape).astype(np.float32)
    f = img.astype(np.float32) + noise[..., None] + chroma
    img = np.clip(f, 0, 255).astype(np.uint8)

    # 6) webcam JPEG compression
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def simulate_bytes(bgr, profile="webcam720", seed=7):
    out = simulate(bgr, profile, seed)
    ok, buf = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return buf.tobytes()
