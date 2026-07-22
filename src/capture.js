// Capture director: live, on-device face analysis during camera preview.
// Not a "face in the oval" toy — it scores the capture 0-100 against the
// SELECTED programme's framing law, directs all three head axes (tilt, turn,
// chin pitch), distance, centering, eyes and expression, and tells the app
// when the best moment arrives. MediaPipe Face Landmarker, pinned version.

// Pinned MediaPipe Tasks-Vision 0.10.14. We prefer a LOCAL vendored copy so the
// coach works fully offline (matching the app's on-device / local-processing
// promise), and fall back to the pinned CDN at the SAME version if the local
// load fails at runtime — so vendoring can never regress the online case.
const LOCAL = {
  label: "local",
  bundle: "/src/vendor/mediapipe/vision_bundle.mjs",
  wasm: "/src/vendor/mediapipe/wasm",
  model: "/src/vendor/mediapipe/face_landmarker.task",
};
const VISION_CDN = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
const CDN = {
  label: "cdn",
  bundle: `${VISION_CDN}/vision_bundle.mjs`,
  wasm: `${VISION_CDN}/wasm`,
  model:
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
};

const L = {
  chin: 152,
  forehead: 10,
  leftEyeOuter: 33,
  rightEyeOuter: 263,
  nose: 1,
  mouthUpper: 13,
  mouthLower: 14,
  leftEyeTop: 159,
  leftEyeBottom: 145,
  leftEyeInner: 133,
  rightEyeTop: 386,
  rightEyeBottom: 374,
  rightEyeInner: 362,
};

// Calibrated on 40 real frontal portraits: nose position within the eye->chin
// span is 0.38 +/- 0.04 when the head is level (pitch proxy).
const PITCH_NEUTRAL = 0.38;
const PITCH_BAND = 0.09;

let landmarker = null;
let loadPromise = null;
let unavailable = false;

// The camera render loop only calls analyzeFrame() when coachAvailable() is
// true. We keep returning true even after the model fails to load so the loop
// keeps polling — analyzeFrame() then hands back a static fallback guide
// (present:false, no score) instead of vanishing. Use coachReady() if you need
// to know whether live scoring is actually running.
export function coachAvailable() {
  return true;
}

// True only when the live landmarker is loaded and scoring for real.
export function coachReady() {
  return Boolean(landmarker) && !unavailable;
}

// Shared framing law: the preview target oval is sized from the selected
// programme's head targetPercent. Live scoring, the fallback metrics object,
// and drawFallbackGuide() all derive their oval from this one function so they
// never drift apart.
function framingTarget(targetPercent) {
  const idealFrac = Math.min(0.72, Math.max(0.45, ((Number(targetPercent) || 62) / 100) * 0.9));
  return {
    idealFrac,
    target: { cx: 0.5, cy: 0.44, halfW: idealFrac * 0.36, halfH: idealFrac * 0.62 },
  };
}

/**
 * Static fallback guide for when the live coach is unavailable (offline / CDN
 * blocked). Draws the programme-sized target oval plus an instruction banner so
 * on-device framing guidance never fully disappears. Self-contained: pass a 2D
 * context, the pixel width/height of the region to draw into (its top-left is
 * treated as origin 0,0 — translate the context first if it isn't), and the
 * selected profile. Honest by design: it shows NO capture score, because none
 * is being computed. The zero-app.js-edit path (analyzeFrame's fallback object)
 * does not need this helper; it exists for any integrator that wants to draw
 * the guide directly.
 */
export function drawFallbackGuide(ctx, width, height, profile) {
  if (!ctx || !width || !height) return;
  const { idealFrac } = framingTarget(profile?.head?.targetPercent);
  const cx = 0.5 * width;
  const cy = 0.44 * height;
  const rx = idealFrac * 0.36 * width;
  const ry = idealFrac * 0.62 * height;

  ctx.save();
  ctx.setLineDash([10, 8]);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "#8f8c84"; // --mut: neutral, "no live judgement" state
  ctx.globalAlpha = 0.9;
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();

  ctx.save();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
  ctx.textAlign = "center";
  const bannerY = height - 44;
  ctx.fillStyle = "rgba(11, 11, 12, 0.72)";
  ctx.fillRect(0, bannerY - 20, width, 42);
  ctx.fillStyle = "#ece9e2";
  ctx.font = "700 17px 'Space Grotesk', sans-serif";
  ctx.fillText("Center your face in the oval — live scoring unavailable offline.", width / 2, bannerY + 7);
  ctx.font = "600 8.5px 'KVNP Mono', Consolas, monospace";
  ctx.fillStyle = "rgba(143,140,132,0.9)";
  ctx.fillText("PREVIEW MIRRORED — SAVED PHOTO IS TRUE ORIENTATION", width / 2, bannerY + 19);
  ctx.restore();
}

export async function initCoach() {
  if (landmarker) return landmarker;
  if (unavailable) return null;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    // Try the vendored local copy first, then the pinned CDN. Only when BOTH
    // fail do we mark the coach unavailable (which triggers the static fallback
    // guide via analyzeFrame). Success at either source is a full live coach.
    for (const src of [LOCAL, CDN]) {
      try {
        const vision = await import(/* @vite-ignore */ src.bundle);
        const { FaceLandmarker, FilesetResolver } = vision;
        const files = await FilesetResolver.forVisionTasks(src.wasm);
        landmarker = await FaceLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: src.model, delegate: "GPU" },
          runningMode: "VIDEO",
          numFaces: 1,
        });
        if (src.label !== "local") {
          console.info("Capture coach: loaded from CDN fallback (local vendor unavailable).");
        }
        return landmarker;
      } catch (error) {
        console.warn(`Capture coach: ${src.label} load failed:`, error);
      }
    }
    unavailable = true;
    console.warn("Capture coach unavailable — showing static fallback guide.");
    return null;
  })();
  return loadPromise;
}

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

// Score one factor: 1 inside the dead-zone, falling linearly to 0 at `worst`.
function factorScore(excess, worst) {
  if (excess <= 0) return 1;
  return Math.max(0, 1 - excess / worst);
}

/**
 * Analyze one video frame against the selected programme.
 * @param profileOpts {targetPercent:number, programme:string}
 * Returns null while the model loads, otherwise:
 * { present, score (0-100), ready, instruction, factors[], arrow, faceBox,
 *   target, angles:{roll,yaw,pitch}, headFrac }
 */
export function analyzeFrame(video, timestampMs, profileOpts = {}) {
  // Preview framing target: keep a little more room than the final crop so the
  // composer has headroom; clamp to sane webcam distances. Derived once here so
  // the live path and the fallback path share identical oval geometry.
  const { idealFrac, target } = framingTarget(profileOpts.targetPercent);

  // Coach model failed to load (offline, CDN blocked, GPU init failed…). Rather
  // than returning null — which makes the overlay disappear entirely and
  // silently contradicts the app's on-device / offline promise — return a
  // minimal metrics-shaped object. The app's existing renderer draws the target
  // oval (from `target`) and the instruction banner (from `instruction`); the
  // empty `factors`, `present:false` and non-numeric `score` keep it honest: no
  // score, no meters, no arrow, no auto-capture. `fallback:true` marks it.
  if (unavailable) {
    return {
      present: false,
      fallback: true,
      score: "—",
      ready: false,
      instruction: "Center your face in the oval — live scoring unavailable offline.",
      factors: [],
      arrow: null,
      target,
    };
  }

  if (!landmarker || !video || !video.videoWidth) return null;
  let result;
  try {
    result = landmarker.detectForVideo(video, timestampMs);
  } catch (error) {
    return null;
  }

  const faces = result.faceLandmarks;
  if (!faces || !faces.length) {
    return {
      present: false,
      score: 0,
      ready: false,
      instruction: "Step into frame — center your face",
      factors: [],
      arrow: null,
      target,
    };
  }

  const p = faces[0];
  const get = (name) => p[L[name]];

  const leftEye = get("leftEyeOuter");
  const rightEye = get("rightEyeOuter");
  const chin = get("chin");
  const forehead = get("forehead");
  const nose = get("nose");
  const eyeMid = { x: (leftEye.x + rightEye.x) / 2, y: (leftEye.y + rightEye.y) / 2 };
  const faceWidth = Math.abs(rightEye.x - leftEye.x) * 1.9;
  const faceH = Math.abs(chin.y - forehead.y);
  const headFrac = faceH * 1.5; // approx chin-to-crown as fraction of frame height
  const centerX = eyeMid.x;
  const centerY = (forehead.y + chin.y) / 2;

  const roll = (Math.atan2(rightEye.y - leftEye.y, rightEye.x - leftEye.x) * 180) / Math.PI;
  const yaw = ((nose.x - centerX) / Math.max(0.01, faceWidth)) * 100; // signed %
  const pitch = (nose.y - eyeMid.y) / Math.max(0.001, chin.y - eyeMid.y); // ~0.38 neutral
  const ear =
    (dist(get("leftEyeTop"), get("leftEyeBottom")) / Math.max(0.001, dist(leftEye, get("leftEyeInner"))) +
      dist(get("rightEyeTop"), get("rightEyeBottom")) / Math.max(0.001, dist(rightEye, get("rightEyeInner")))) /
    2;
  const mouthGap = (dist(get("mouthUpper"), get("mouthLower")) / Math.max(0.001, faceH)) * 100;

  const centerErr = Math.hypot((centerX - target.cx) * 1.2, (centerY - target.cy));
  const distErr = Math.abs(headFrac - idealFrac);
  const pitchErr = Math.abs(pitch - PITCH_NEUTRAL);

  // Weighted factors -> capture score. Weights sum to 100.
  const factors = [
    {
      id: "center", label: "Centered", weight: 10,
      s: factorScore(centerErr - 0.05, 0.25),
      hint: "Center your face in the frame",
    },
    {
      id: "distance", label: "Distance", weight: 18,
      s: factorScore(distErr - 0.05, 0.25),
      hint: headFrac < idealFrac ? "Move a little closer" : "Move back — too close distorts your face",
    },
    {
      id: "level", label: "Head level", weight: 16,
      s: factorScore(Math.abs(roll) - 2.0, 8),
      hint: `Straighten your head (${Math.abs(roll).toFixed(0)}°) — follow the arc`,
    },
    {
      id: "straight", label: "Facing camera", weight: 20,
      s: factorScore(Math.abs(yaw) - 3.0, 10),
      hint: "Turn your face toward the arrow",
    },
    {
      id: "pitch", label: "Chin level", weight: 11,
      s: factorScore(pitchErr - PITCH_BAND, 0.14),
      hint: pitch > PITCH_NEUTRAL ? "Raise your chin slightly" : "Lower your chin slightly",
    },
    {
      id: "eyes", label: "Eyes open", weight: 10,
      s: ear > 0.17 ? 1 : ear > 0.12 ? 0.5 : 0,
      hint: "Open your eyes normally",
    },
    {
      id: "neutral", label: "Neutral mouth", weight: 15,
      s: factorScore(mouthGap - 1.6, 3.5),
      hint: "Relax — neutral expression, mouth closed",
    },
  ];

  let score = 0;
  for (const f of factors) {
    f.ok = f.s >= 0.75;
    score += f.weight * f.s;
  }
  score = Math.round(score);

  // Primary instruction = the heaviest-losing factor.
  let worst = null;
  for (const f of factors) {
    const loss = f.weight * (1 - f.s);
    if (!worst || loss > worst.loss) worst = { f, loss };
  }
  const ready = score >= 88;
  const instruction = ready ? "Hold still…" : worst && worst.loss > 1.5 ? worst.f.hint : "Almost — hold steady";

  // Geometric arrow for the dominant ANGLE error (drawn by the app in display
  // space, so it is mirror-safe — the user just follows the arrow).
  let arrow = null;
  const rollLoss = factors[2].weight * (1 - factors[2].s);
  const yawLoss = factors[3].weight * (1 - factors[3].s);
  const pitchLoss = factors[4].weight * (1 - factors[4].s);
  const maxLoss = Math.max(rollLoss, yawLoss, pitchLoss);
  if (maxLoss > 1.5) {
    if (maxLoss === yawLoss) arrow = { kind: "turn", dir: Math.sign(nose.x - centerX) || 1 };
    else if (maxLoss === rollLoss) arrow = { kind: "rotate", dir: Math.sign(roll) || 1 };
    else arrow = { kind: "pitch", dir: pitch > PITCH_NEUTRAL ? -1 : 1 };
  }

  const faceBox = {
    x: Math.max(0, centerX - faceWidth / 2),
    y: Math.max(0, forehead.y - faceH * 0.2),
    w: Math.min(1, faceWidth),
    h: Math.min(1, faceH * 1.3),
  };

  return {
    present: true,
    score,
    ready,
    instruction,
    factors,
    arrow,
    faceBox,
    target,
    angles: { roll, yaw, pitch },
    headFrac,
    headCenter: { x: centerX, y: centerY },
  };
}
