/* PassportLens — simplified 5-step studio.
   Programme → Photo → Result → Adjust → Download.
   Talks to the same Python engine as the advanced studio; shows people a plain
   verdict and keeps the technical detail for admins. */

import { RULE_PROFILES } from "./rules.js?v=pl-3";
import { DEMO_PORTRAITS } from "./demo-library.js?v=pl-3";
import { initCoach, analyzeFrame, coachAvailable } from "./capture.js?v=pl-3";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  user: null,
  plan: null,
  csrf: null,
  guest: false,
  step: 1,
  profile: null,
  sourceBlob: null,      // File/Blob for uploads and camera captures
  sourceName: "",
  demoName: "",          // demo sample file name (guests)
  sourceUrl: "",         // object URL for the original preview
  result: null,
  options: { backgroundReplaced: true, backgroundColor: null, backgroundCleanup: "balanced", brightness: 0, manualFace: null },
  projectId: null,
  artifactSaved: false,
  clients: [],
  camera: { stream: null, raf: 0, lastAnalyze: 0, metrics: null },
  busy: false,
};

const FLAGS = (code) => {
  code = String(code || "").toUpperCase();
  if (code.length !== 2 || !/^[A-Z]{2}$/.test(code)) return "🌐";
  return String.fromCodePoint(...[...code].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
};

const BACKGROUND_CHOICES = {
  white: ["#ffffff"],
  white_or_off_white: ["#ffffff", "#f7f7f2", "#f4f4f0"],
  white_or_light: ["#ffffff", "#f4f6f8", "#e9edf1", "#dfe6ee"],
  plain_light: ["#f7f7f2", "#f2f2f0", "#e9edf1", "#e8ebed", "#dfe6ee"],
  light_not_white: ["#e9edf1", "#e3e8ef", "#dfe6ee", "#d9e2ec"],
};

/* Plain-English reasons for every technical check id. */
const REASONS = {
  source_resolution: "The photo's resolution is low — use a larger, sharper photo.",
  source_face_pixels: "The face is small in the photo — move closer or use a higher-resolution photo.",
  source_focus: "The photo is blurry — hold the camera steady and refocus on the face.",
  source_noise: "The photo is grainy — use more light.",
  source_lighting: "The lighting is uneven or too dark/bright — use soft, even light from the front.",
  source_pose: "The head is tilted or turned — face the camera straight on with the head level.",
  source_head_pitch: "The camera is not at eye level — hold it level with the eyes and keep the chin neutral.",
  source_shoulder_level: "The shoulders are not level — sit upright.",
  source_body_alignment: "The body is leaning — centre the head over the shoulders.",
  source_background_path: "The background is not plain enough — stand in front of a plain, light wall.",
  face_detection: "One clear face is needed — face the camera with nothing covering the face.",
  face_outline: "The outline of the head is unclear — keep hair away from the face and use a plain wall.",
  head_size: "The head size is out of range — move closer or further from the camera.",
  head_center: "The face is not centred in the frame.",
  top_margin: "There is too little or too much space above the head.",
  shoulder_framing: "Show the head and the top of the shoulders only.",
  head_tilt: "The head is tilted — keep it level.",
  face_direction: "The face is turned — look straight at the camera.",
  mouth: "The mouth is open — close the mouth with a neutral expression.",
  eyes_open: "The eyes are not fully open.",
  eye_gaze: "The eyes are not looking at the camera.",
  glasses_glare: "There is glare on the glasses — remove them or change the light.",
  background_cleanup: "The background edges around hair or shoulders need a look — try a plainer wall or the Strong clean-up.",
  background_uniformity: "The background is not even — use a plain wall or the clean background option.",
  grain: "The image is grainy — use more light.",
  sharpness: "The image is not sharp enough.",
  brightness: "The photo is too dark or too bright.",
  contrast: "The photo lacks contrast.",
  output_size: "The output size does not match the programme.",
};

const HUMAN_LABELS = {
  review_commercial_photographer_required: "This programme expects a professional photographer to take the photo",
  review_unaltered_photo: "The photo must not be altered in ways the authority forbids",
  review_two_identical_prints: "Print two identical copies if applying by post",
  review_neutral_expression: "Neutral expression, mouth closed",
};

/* ------------------------------------------------------------------ */
/* boot                                                                */
/* ------------------------------------------------------------------ */
async function boot() {
  bindGlobal();
  const params = new URLSearchParams(location.search);
  try {
    const me = await fetch("/api/auth/me", { credentials: "same-origin" }).then((r) => r.json());
    state.commerceMode = me.commerceMode || "disabled";
    if (me.ok && me.user) {
      state.user = me.user;
      state.plan = me.plan;
      state.csrf = me.csrfToken;
    }
  } catch (error) {
    console.warn("auth check failed", error);
  }
  if (!state.user && params.has("guest")) state.guest = true;
  if (state.commerceMode === "disabled") $("#dev-signup-link").hidden = false;
  renderChrome();
  if (!state.user && !state.guest) {
    showAuth();
  } else {
    showStudio();
    renderProgrammes();
    if (params.get("programme")) {
      const profile = RULE_PROFILES.find((item) => item.id === params.get("programme"));
      if (profile) selectProgramme(profile);
    }
  }
}

function renderChrome() {
  const signedIn = !!state.user;
  $("#signout-btn").hidden = !signedIn;
  $("#signin-link").hidden = signedIn || !state.guest;
  $("[data-nav-account]").hidden = !signedIn;
  $("[data-nav-admin]").hidden = !(state.plan && state.plan.isAdmin);
  $("[data-nav-advanced]").hidden = !(state.plan && state.plan.isAdmin);
  $("[data-nav-crm]").hidden = !(state.plan && state.plan.crm && !state.plan.isAdmin);
  const badge = $("#plan-badge");
  if (signedIn && state.plan) {
    badge.hidden = false;
    if (state.plan.isAdmin) badge.textContent = "Admin";
    else if (state.plan.org) badge.textContent = `${state.plan.org.planLabel}${state.plan.orgActive ? "" : " · inactive"}`;
    else if (state.plan.subscriptionActive) badge.textContent = "Silver";
    else if (state.plan.credits > 0) badge.textContent = `${state.plan.credits} photo credit${state.plan.credits === 1 ? "" : "s"}`;
    else badge.textContent = "No plan";
  } else if (state.guest) {
    badge.hidden = false;
    badge.textContent = "Demo";
  } else {
    badge.hidden = true;
  }
  $("#guest-notice").hidden = !state.guest;
  const planNotice = $("#plan-notice");
  if (signedIn && state.plan && !state.plan.canProcess) {
    planNotice.hidden = false;
    planNotice.innerHTML = `Your account has no active plan or photo credit. <a href="/pricing">Choose a plan</a> to make photos with your own pictures. You can still try the sample portraits below.`;
  } else {
    planNotice.hidden = true;
  }
  $("#demo-library").hidden = !(state.guest || (signedIn && state.plan && !state.plan.canProcess));
  $("#photo-options").hidden = state.guest;
  $("#capture-tips").hidden = state.guest;
  $("#tech-panel").hidden = !(state.plan && state.plan.isAdmin);
  $("#save-client-card").hidden = !(state.plan && state.plan.crm && !state.plan.isAdmin);
}

function showAuth() {
  $("#auth-view").hidden = false;
  $("#studio-view").hidden = true;
}

function showStudio() {
  $("#auth-view").hidden = true;
  $("#studio-view").hidden = false;
}

function bindGlobal() {
  $("#signin-form").addEventListener("submit", signIn);
  $("#signup-form").addEventListener("submit", signUp);
  $("#dev-signup-toggle").addEventListener("click", (e) => { e.preventDefault(); $("#signin-form").hidden = true; $("#signup-form").hidden = false; });
  $("#dev-signin-toggle").addEventListener("click", (e) => { e.preventDefault(); $("#signup-form").hidden = true; $("#signin-form").hidden = false; });
  $("#demo-btn").addEventListener("click", () => {
    state.guest = true;
    history.replaceState(null, "", "/app?guest");
    renderChrome();
    showStudio();
    renderProgrammes();
  });
  $("#signin-link").addEventListener("click", (event) => {
    event.preventDefault();
    state.guest = false;
    history.replaceState(null, "", "/app");
    showAuth();
  });
  $("#signout-btn").addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
    location.href = "/";
  });
  $$("[data-go]").forEach((el) => el.addEventListener("click", () => goStep(Number(el.dataset.go))));
  $("#prog-search").addEventListener("input", () => renderProgrammes($("#prog-search").value));

  // upload
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  fileInput.addEventListener("change", () => fileInput.files[0] && useFile(fileInput.files[0]));
  ["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.remove("over"); }));
  dropzone.addEventListener("drop", (e) => { const file = e.dataTransfer.files && e.dataTransfer.files[0]; if (file) useFile(file); });

  // camera
  $("#camera-open").addEventListener("click", openCamera);
  $("#camera-close").addEventListener("click", closeCamera);
  $("#camera-shoot").addEventListener("click", shootCamera);

  // adjust
  $("#bg-replace").addEventListener("change", () => { state.options.backgroundReplaced = $("#bg-replace").checked; });
  $$("#bg-strength button").forEach((btn) => btn.addEventListener("click", () => {
    $$("#bg-strength button").forEach((b) => b.classList.toggle("on", b === btn));
    state.options.backgroundCleanup = btn.dataset.value;
  }));
  $("#brightness").addEventListener("input", () => {
    state.options.brightness = Number($("#brightness").value);
    $("#brightness-value").textContent = (state.options.brightness > 0 ? "+" : "") + state.options.brightness;
  });
  $$("[data-nudge]").forEach((btn) => btn.addEventListener("click", () => nudge(btn.dataset.nudge)));
  $("#adjust-apply").addEventListener("click", () => runProcess({ stay: 4 }));
  $("#adjust-reset").addEventListener("click", () => { resetOptions(); renderAdjustControls(); runProcess({ stay: 4 }); });

  // download
  $$("[data-export]").forEach((btn) => btn.addEventListener("click", () => exportFile(btn.dataset.export)));
  $("#sheet-btn").addEventListener("click", printSheet);
  $("#save-client-form").addEventListener("submit", saveToClient);
  $("#new-photo").addEventListener("click", () => { resetPhoto(); goStep(2); });
  $("#retake-btn").addEventListener("click", resetPhoto);

  bindCompare();
}

async function signIn(event) {
  event.preventDefault();
  const form = event.target;
  const error = $("#signin-error");
  error.hidden = true;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: form.email.value.trim(), password: form.password.value }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || data.detail || "Sign-in failed.");
    const params = new URLSearchParams(location.search);
    params.delete("guest");
    location.href = "/app" + (params.toString() ? "?" + params.toString() : "");
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
  }
}

async function signUp(event) {
  event.preventDefault();
  const form = event.target;
  const error = $("#signup-error");
  error.hidden = true;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const response = await fetch("/api/auth/signup", {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: form.name.value.trim(), email: form.email.value.trim(), password: form.password.value }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || data.detail || "Could not create the account.");
    location.href = "/app";
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/* steps                                                               */
/* ------------------------------------------------------------------ */
function goStep(step, force = false) {
  if (!force) {
    if (step === state.step) return;
    if (step > 2 && !state.result) { toast("Add a photo first."); return; }
    if (step === 2 && !state.profile) { toast("Choose a programme first."); return; }
  }
  if (state.step === 2 && step !== 2) closeCamera();
  state.step = step;
  $$(".step-panel").forEach((panel) => { panel.hidden = Number(panel.dataset.step) !== step; });
  refreshStepper();
  if (step === 4) renderAdjustControls();
  if (step === 5) prepareDownload();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function refreshStepper() {
  $$("#stepper li").forEach((li) => {
    const n = Number(li.dataset.go);
    li.classList.toggle("active", n === state.step);
    li.classList.toggle("done", n !== state.step && ((n <= 1 && !!state.profile) || (n <= 2 && (!!state.sourceBlob || !!state.demoName)) || (n <= 5 && !!state.result)));
  });
}

/* ---------- step 1 ---------- */
function renderProgrammes(query = "") {
  const q = query.trim().toLowerCase();
  const host = $("#prog-groups");
  const groups = new Map();
  for (const profile of RULE_PROFILES) {
    const hay = `${profile.countryName} ${profile.country} ${profile.programme} ${profile.category} ${profile.document} ${profile.label}`.toLowerCase();
    if (q && !hay.includes(q)) continue;
    const key = profile.country === "STUDIO" ? "zzz" : profile.countryName;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(profile);
  }
  const priority = ["Canada", "United States", "India", "United Kingdom"];
  const keys = [...groups.keys()].sort((a, b) => {
    const pa = priority.indexOf(a), pb = priority.indexOf(b);
    if (pa !== -1 || pb !== -1) return (pa === -1 ? 99 : pa) - (pb === -1 ? 99 : pb);
    return a.localeCompare(b);
  });
  host.innerHTML = keys.map((key) => {
    const items = groups.get(key);
    const first = items[0];
    const title = key === "zzz" ? "General studio portrait" : `${FLAGS(first.country)} ${first.countryName}`;
    return `<div class="prog-country"><h2>${title}</h2><div class="prog-cards">${items.map((p) => programmeCard(p)).join("")}</div></div>`;
  }).join("") || `<p class="empty">No programme matches "${escapeHtml(query)}". <a href="/#contact">Ask us to add it.</a></p>`;
  $$(".prog-card", host).forEach((btn) => btn.addEventListener("click", () => {
    const profile = RULE_PROFILES.find((item) => item.id === btn.dataset.id);
    if (profile) selectProgramme(profile);
  }));
}

function programmeCard(profile) {
  const out = profile.output || {};
  const size = out.printWidthMm ? `${out.printWidthMm} × ${out.printHeightMm} mm` : `${out.widthPx} × ${out.heightPx} px`;
  const on = state.profile && state.profile.id === profile.id ? "on" : "";
  return `<button type="button" class="prog-card ${on}" data-id="${escapeHtml(profile.id)}"><b>${escapeHtml(profile.programme)}</b><span>${escapeHtml(size)} · ${escapeHtml(profile.delivery || "")}</span><span class="badge info tag">${escapeHtml(profile.category || "")}</span></button>`;
}

function selectProgramme(profile) {
  state.profile = profile;
  resetOptions();
  resetPhoto();
  $$(".prog-card").forEach((btn) => btn.classList.toggle("on", btn.dataset.id === profile.id));
  const out = profile.output || {};
  $("#selected-programme-line").innerHTML = `${FLAGS(profile.country)} <b>${escapeHtml(profile.countryName)} — ${escapeHtml(profile.programme)}</b> · ${out.printWidthMm ? `${out.printWidthMm} × ${out.printHeightMm} mm` : `${out.widthPx} × ${out.heightPx} px`}${profile.requirements && profile.requirements.length ? `<br><span class="muted small">${escapeHtml(profile.requirements.slice(0, 3).join(" · "))}</span>` : ""}`;
  renderDemoLibrary();
  trackEvent("programme_selected", { profileId: profile.id });
  goStep(2);
}

function resetOptions() {
  state.options = {
    backgroundReplaced: true,
    backgroundColor: (state.profile && state.profile.automation && state.profile.automation.backgroundColor) || "#ffffff",
    backgroundCleanup: "balanced",
    brightness: 0,
    manualFace: null,
  };
}

function resetPhoto() {
  state.sourceBlob = null;
  state.sourceName = "";
  state.demoName = "";
  if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
  state.sourceUrl = "";
  state.result = null;
  state.projectId = null;
  state.artifactSaved = false;
  state.options.manualFace = null;
  $("#result-view").hidden = true;
  refreshStepper();
}

/* ---------- step 2 ---------- */
function useFile(file) {
  if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) { toast("Please choose an image file.", "bad"); return; }
  if (file.size > 25 * 1024 * 1024) { toast("The photo is larger than 25 MB.", "bad"); return; }
  state.sourceBlob = file;
  state.sourceName = file.name;
  state.demoName = "";
  if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
  state.sourceUrl = URL.createObjectURL(file);
  state.options.manualFace = null;
  trackEvent("photo_added", { source: "upload" });
  runProcess();
}

function renderDemoLibrary() {
  const grid = $("#demo-grid");
  grid.innerHTML = DEMO_PORTRAITS.map((item) => `<button type="button" class="demo-card" data-path="${escapeHtml(item.path)}"><img src="/${escapeHtml(item.path)}" alt="${escapeHtml(item.title)}" loading="lazy" /><span>${escapeHtml(item.title)}</span></button>`).join("");
  $$(".demo-card", grid).forEach((btn) => btn.addEventListener("click", () => {
    const path = btn.dataset.path;
    state.demoName = path.split("/").pop();
    state.sourceBlob = null;
    state.sourceName = state.demoName;
    if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
    state.sourceUrl = "/" + path;
    state.options.manualFace = null;
    trackEvent("photo_added", { source: "demo" });
    runProcess();
  }));
}

/* camera */
async function openCamera() {
  const panel = $("#camera-panel");
  panel.hidden = false;
  $("#camera-instruction").textContent = "Starting camera…";
  try {
    state.camera.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1920 }, height: { ideal: 1440 } }, audio: false });
    const video = $("#camera-video");
    video.srcObject = state.camera.stream;
    await video.play();
    initCoach();
    loopCamera();
  } catch (error) {
    $("#camera-instruction").textContent = "Camera not available. Allow camera access or upload a photo instead.";
  }
}

function closeCamera() {
  cancelAnimationFrame(state.camera.raf);
  if (state.camera.stream) state.camera.stream.getTracks().forEach((track) => track.stop());
  state.camera.stream = null;
  $("#camera-panel").hidden = true;
}

function loopCamera() {
  const video = $("#camera-video");
  const canvas = $("#camera-overlay");
  const ctx = canvas.getContext("2d");
  const tick = () => {
    if (!state.camera.stream) return;
    if (video.videoWidth && (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight)) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }
    const now = performance.now();
    let metrics = state.camera.metrics;
    if (video.videoWidth && now - state.camera.lastAnalyze > 120) {
      state.camera.lastAnalyze = now;
      const targetPercent = state.profile && state.profile.head ? state.profile.head.targetPercent : 62;
      metrics = coachAvailable() ? analyzeFrame(video, now, { targetPercent, programme: state.profile ? state.profile.label : "" }) : null;
      state.camera.metrics = metrics;
    }
    drawGuide(ctx, canvas.width, canvas.height, metrics);
    const instruction = $("#camera-instruction");
    instruction.textContent = metrics ? metrics.instruction : "Center your face in the oval, then take the photo.";
    instruction.classList.toggle("ready", !!(metrics && metrics.ready));
    state.camera.raf = requestAnimationFrame(tick);
  };
  state.camera.raf = requestAnimationFrame(tick);
}

function drawGuide(ctx, width, height, metrics) {
  if (!width || !height) return;
  ctx.clearRect(0, 0, width, height);
  const target = (metrics && metrics.target) || { cx: 0.5, cy: 0.44, halfW: 0.2, halfH: 0.36 };
  ctx.save();
  ctx.setLineDash([12, 8]);
  ctx.lineWidth = 3;
  ctx.strokeStyle = metrics && metrics.ready ? "#41d97d" : "#FFB500";
  ctx.beginPath();
  ctx.ellipse(target.cx * width, target.cy * height, target.halfW * width, target.halfH * height, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function shootCamera() {
  const video = $("#camera-video");
  if (!video.videoWidth) { toast("Camera is still starting.", "bad"); return; }
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  canvas.toBlob((blob) => {
    if (!blob) return;
    closeCamera();
    const file = new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" });
    trackEvent("photo_added", { source: "camera" });
    useFile(file);
  }, "image/jpeg", 0.95);
}

/* ---------- processing ---------- */
function buildOptions() {
  const options = {
    backgroundReplaced: state.options.backgroundReplaced,
    backgroundColor: state.options.backgroundColor,
    backgroundCleanup: state.options.backgroundCleanup,
    brightness: state.options.brightness,
    autoCorrect: true,
    autoStraighten: true,
    autoTone: true,
    autoLighting: true,
    enhanceOutput: false,
  };
  if (state.options.manualFace) options.manualFace = state.options.manualFace;
  return options;
}

async function runProcess({ stay } = {}) {
  if (!state.profile || (!state.sourceBlob && !state.demoName)) return;
  if (state.busy) return;
  state.busy = true;
  const stayOnAdjust = stay === 4 && state.step === 4;
  if (!stayOnAdjust) {
    goStep(3, true);
    $("#processing").hidden = false;
    $("#result-view").hidden = true;
  } else {
    $("#adjust-busy").hidden = false;
  }
  const form = new FormData();
  if (state.demoName) form.append("demo", state.demoName);
  else form.append("image", state.sourceBlob, state.sourceName || "photo.jpg");
  form.append("profile", JSON.stringify({ id: state.profile.id }));
  form.append("options", JSON.stringify(buildOptions()));
  try {
    const response = await fetch("/api/process", { method: "POST", body: form, credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      const message = data.error || data.detail || "Processing failed.";
      if (response.status === 401 || response.status === 402) {
        toast(message, "bad");
        if (!state.user) showAuth();
      }
      throw new Error(message);
    }
    state.result = data;
    state.artifactSaved = false;
    renderResult(data);
    refreshStepper();
    if (stayOnAdjust) $("#adjust-img").src = data.finalDataUrl;
  } catch (error) {
    if (!stayOnAdjust) goStep(2, true);
    toast(error.message, "bad");
  } finally {
    state.busy = false;
    $("#processing").hidden = true;
    $("#adjust-busy").hidden = true;
  }
}

/* ---------- step 3 ---------- */
function renderResult(data) {
  $("#result-view").hidden = false;
  const decision = data.decision || {};
  const verdict = $("#verdict");
  const icon = $("#verdict-icon");
  const failing = [...(data.sourceQuality || []), ...(data.checks || [])].filter((c) => c.status === "fail");
  const warnings = [...(data.sourceQuality || []), ...(data.checks || [])].filter((c) => c.status === "warning");
  const humans = (data.checks || []).filter((c) => c.status === "review" && /^review_/.test(c.id));
  let level = "ok", title = "Photo OK", message = "The photo meets the programme's measurable rules. Download it, or adjust the background first.";
  let reasons = [];
  if (decision.status === "retake" || decision.status === "fix" || failing.length) {
    level = "bad";
    title = decision.status === "fix" ? "Not OK yet" : "Please retake the photo";
    message = decision.status === "fix" ? "One thing needs fixing before this photo can be used." : "Something in the original photo can't be corrected safely. Here's what to change:";
    reasons = failing.map(plainReason).filter(Boolean);
    if (!reasons.length) reasons = [decision.message || "The photo needs a retake."];
  } else if (warnings.length || decision.status === "review" || decision.status === "policy_review") {
    level = "warn";
    title = "Almost — please check";
    message = "The photo is usable, but look at the points below before you submit it.";
    reasons = warnings.map(plainReason).filter(Boolean);
  }
  verdict.className = `verdict card ${level}`;
  icon.textContent = level === "ok" ? "✓" : level === "warn" ? "!" : "✕";
  $("#verdict-title").textContent = title;
  $("#verdict-message").textContent = message;
  const list = $("#verdict-reasons");
  list.innerHTML = uniq(reasons).slice(0, 4).map((r) => `<li>${escapeHtml(r)}</li>`).join("");
  list.hidden = !reasons.length;
  const confirmBox = $("#verdict-confirm");
  const confirmList = $("#verdict-confirm-list");
  const humanItems = humans.map((c) => HUMAN_LABELS[c.id] || c.label).filter(Boolean);
  confirmBox.hidden = !humanItems.length || level === "bad";
  confirmList.innerHTML = humanItems.map((t) => `<li>${escapeHtml(t)}</li>`).join("");

  $("#before-img").src = data.beforeDataUrl || state.sourceUrl;
  $("#after-img").src = data.finalDataUrl;
  const out = state.profile.output || {};
  $("#ba").style.setProperty("--ratio", `${out.widthPx} / ${out.heightPx}`);
  $("#result-size").textContent = `${out.widthPx} × ${out.heightPx} px · ${formatBytes(data.outputBytes)}`;
  resetCompare();

  const edits = data.effectiveEdits || {};
  const applied = [];
  if (edits.background) applied.push("background cleaned");
  if (edits.straighten) applied.push("straightened");
  if (edits.tone) applied.push("exposure balanced");
  if (edits.lighting) applied.push("lighting evened");
  if ((data.corrections || []).some((c) => c.id === "brightness")) applied.push("brightness adjusted");
  $("#edits-note").textContent = applied.length ? `Applied: ${applied.join(", ")}. The face itself was not changed.` : "Only cropped and resized. The face itself was not changed.";
  const downloadButton = $("#to-download");
  downloadButton.disabled = false;
  downloadButton.innerHTML = level === "bad" ? 'Download anyway <span class="arw" aria-hidden="true">→</span>' : 'Download <span class="arw" aria-hidden="true">→</span>';

  if (state.plan && state.plan.isAdmin) renderTech(data);
}

function plainReason(check) {
  const text = REASONS[check.id];
  if (!text) return null;
  if (check.id === "source_background_path" && state.result && state.result.effectiveEdits && state.result.effectiveEdits.background) {
    return "The background could not be cleaned reliably around the hair or shoulders — try a plainer wall.";
  }
  return text;
}

function renderTech(data) {
  const rows = (items) => items.map((c) => `<tr><td>${escapeHtml(c.id)}</td><td>${escapeHtml(c.label)}</td><td class="st ${escapeHtml(c.status)}">${escapeHtml(c.status)}</td><td>${escapeHtml(c.value ?? "")}</td><td>${escapeHtml(c.required ?? "")}</td></tr>`).join("");
  const head = `<tr><th>id</th><th>check</th><th>status</th><th>value</th><th>target</th></tr>`;
  const matte = data.matte || {};
  const face = data.face || {};
  $("#tech-body").innerHTML = `
    <h4>Decision</h4><pre>${escapeHtml(JSON.stringify(data.decision, null, 1))}</pre>
    <h4>Source quality (original capture)</h4><table>${head}${rows(data.sourceQuality || [])}</table>
    <h4>Output checks</h4><table>${head}${rows(data.checks || [])}</table>
    <h4>Corrections</h4><pre>${escapeHtml((data.corrections || []).map((c) => `${c.id}: ${c.detail || c.label}`).join("\n") || "none")}</pre>
    <h4>Matte</h4><pre>${escapeHtml(`${matte.engine || ""} · coverage ${matte.coverage} · face ${matte.faceCoverage} · soft edge ${matte.softEdgePercent}% · islands ${matte.strayIslands} · holes ${matte.holePercent}% · ${matte.message || ""}`)}</pre>
    <h4>Face</h4><pre>${escapeHtml(`head ${face.headHeight} px · roll ${face.rollDegrees}° · yaw ${face.yawProxy}% · pitch ${face.pitchOffsetDegrees}° · gaze ${face.gazeOffsetPercent}% · eyes ${face.eyeOpenness} · mouth ${face.mouthGapPercent}% · source ${face.headSource || face.source}`)}</pre>
    <h4>Pipeline</h4><pre>${escapeHtml((data.pipeline && data.pipeline.stages || []).map((s) => `${s.label}: ${s.engine} (${s.status})`).join("\n"))}</pre>
    <h4>Policy</h4><pre>${escapeHtml(`allowed ${JSON.stringify(data.allowedEdits)}\nclamped ${JSON.stringify(data.policyClamped)}\neffective ${JSON.stringify(data.effectiveEdits)}`)}</pre>
    <p class="muted">Source ${data.source && data.source.width} × ${data.source && data.source.height} px · output ${formatBytes(data.outputBytes)} · <a href="/studio-advanced">open in the advanced studio</a></p>`;
}

/* before/after slider */
function bindCompare() {
  const ba = $("#ba"), after = $("#after-img"), handle = $("#ba-handle");
  let dragging = false;
  const setPos = (clientX) => {
    const r = ba.getBoundingClientRect();
    const p = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
    after.style.clipPath = `inset(0 0 0 ${(p * 100).toFixed(1)}%)`;
    handle.style.left = `${(p * 100).toFixed(1)}%`;
  };
  handle.addEventListener("pointerdown", (e) => { dragging = true; try { handle.setPointerCapture(e.pointerId); } catch (err) {} e.preventDefault(); });
  window.addEventListener("pointermove", (e) => { if (dragging) setPos(e.clientX); });
  window.addEventListener("pointerup", () => { dragging = false; });
  ba.addEventListener("pointerdown", (e) => { if (e.target !== handle && !handle.contains(e.target)) setPos(e.clientX); });
}
function resetCompare() {
  $("#after-img").style.clipPath = "inset(0 0 0 50%)";
  $("#ba-handle").style.left = "50%";
}

/* ---------- step 4 ---------- */
function renderAdjustControls() {
  if (!state.result) return;
  $("#adjust-img").src = state.result.finalDataUrl;
  const caution = $("#adjust-caution");
  const edits = state.profile.allowedEdits || {};
  caution.hidden = edits.background !== false;
  if (edits.background === false) caution.textContent = `Note: ${state.profile.countryName}'s published rules say the photo must not be digitally altered. Cleaning the background is your choice; when in doubt, retake against a plain wall.`;
  $("#bg-replace").checked = state.options.backgroundReplaced;
  const mode = (state.profile.background && state.profile.background.mode) || "white_or_off_white";
  const choices = BACKGROUND_CHOICES[mode] || BACKGROUND_CHOICES.white_or_off_white;
  if (!choices.includes(state.options.backgroundColor)) choices.unshift(state.options.backgroundColor);
  $("#bg-swatches").innerHTML = choices.map((hex) => `<button type="button" class="swatch ${hex === state.options.backgroundColor ? "on" : ""}" data-hex="${hex}" style="background:${hex}" title="${hex}" aria-label="Background ${hex}"></button>`).join("");
  $$("#bg-swatches .swatch").forEach((btn) => btn.addEventListener("click", () => {
    state.options.backgroundColor = btn.dataset.hex;
    $$("#bg-swatches .swatch").forEach((b) => b.classList.toggle("on", b === btn));
  }));
  $$("#bg-strength button").forEach((b) => b.classList.toggle("on", b.dataset.value === state.options.backgroundCleanup));
  $("#brightness").value = state.options.brightness;
  $("#brightness-value").textContent = (state.options.brightness > 0 ? "+" : "") + state.options.brightness;
}

function nudge(direction) {
  if (!state.result) return;
  const face = state.options.manualFace || {
    centerX: state.result.face.centerX,
    centerY: state.result.face.centerY,
    headHeight: state.result.face.headHeight,
    faceWidth: state.result.face.faceWidth,
  };
  const stepPx = Math.max(4, state.result.face.headHeight * 0.03);
  if (direction === "up") face.centerY -= stepPx;
  if (direction === "down") face.centerY += stepPx;
  if (direction === "left") face.centerX -= stepPx;
  if (direction === "right") face.centerX += stepPx;
  if (direction === "bigger") face.headHeight *= 1.04;
  if (direction === "smaller") face.headHeight *= 0.96;
  state.options.manualFace = face;
  runProcess({ stay: 4 });
}

/* ---------- step 5 ---------- */
function prepareDownload() {
  if (!state.result) return;
  $("#final-img").src = state.result.finalDataUrl;
  const out = state.profile.output || {};
  $("#final-caption").textContent = `${state.profile.countryName} — ${state.profile.programme} · ${out.widthPx} × ${out.heightPx} px${out.printWidthMm ? ` · ${out.printWidthMm} × ${out.printHeightMm} mm` : ""}`;
  const locked = $("#download-locked");
  const access = state.result.access || {};
  if (!state.user) {
    locked.hidden = false;
    locked.innerHTML = `Downloads are for members and photo buyers. <a href="/pricing">Buy one photo for CAD 9.99</a> or a business plan, then upload your own photo.`;
    $("#download-line").textContent = "This is a demo result on a sample portrait.";
  } else if (!access.canDownload) {
    locked.hidden = false;
    locked.innerHTML = `Your account has no active plan or photo credit. <a href="/pricing">Choose a plan</a> to download.`;
    $("#download-line").textContent = "";
  } else {
    locked.hidden = true;
    const credits = state.plan && !state.plan.unlimited ? ` You have ${state.plan.credits} photo credit${state.plan.credits === 1 ? "" : "s"}; the first download of this photo uses one.` : "";
    $("#download-line").textContent = `Files are kept for 30 days in your account.${credits}`;
    loadClients();
  }
  $("#sheet-copies").value = out.printWidthMm && out.printWidthMm <= 40 ? 6 : 4;
  $$("[data-export], #sheet-btn").forEach((btn) => { btn.disabled = !(state.user && access.canDownload); });
}

async function ensureProject() {
  if (!state.user || !state.result) return null;
  if (state.projectId && state.artifactSaved) return state.projectId;
  const summary = { decision: state.result.decision, outputBytes: state.result.outputBytes, edits: state.result.effectiveEdits };
  const payload = {
    id: state.projectId || undefined,
    profileId: state.profile.id,
    countryCode: state.profile.country,
    programmeLabel: `${state.profile.countryName} — ${state.profile.programme}`,
    status: "prepared",
    resultStatus: (state.result.decision || {}).status,
    summary,
  };
  const response = await fetch("/api/projects", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json", "x-kvnp-csrf": state.csrf }, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || data.detail || "Could not save the photo.");
  state.projectId = data.project.id;
  if (!state.artifactSaved) {
    const form = new FormData();
    form.append("image", dataUrlToBlob(state.result.finalDataUrl), "prepared.jpg");
    const up = await fetch(`/api/projects/${state.projectId}/artifact`, { method: "POST", credentials: "same-origin", headers: { "x-kvnp-csrf": state.csrf }, body: form });
    if (up.ok) state.artifactSaved = true;
  }
  return state.projectId;
}

async function authorize(fileKind, format, bytes) {
  const projectId = await ensureProject();
  const response = await fetch("/api/downloads/authorize", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json", "x-kvnp-csrf": state.csrf }, body: JSON.stringify({ projectId, fileKind, format, bytes }) });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || data.detail || "Download not allowed.");
  if (typeof data.credits === "number" && state.plan) { state.plan.credits = data.credits; renderChrome(); }
  return true;
}

async function exportFile(format) {
  if (!state.result) return;
  const button = $(`[data-export="${format}"]`);
  button.disabled = true;
  try {
    await authorize("prepared", format, state.result.outputBytes);
    const out = state.profile.output || {};
    const dpi = out.printWidthMm ? Math.round(out.widthPx / (out.printWidthMm / 25.4)) : 300;
    const form = new FormData();
    form.append("image", dataUrlToBlob(state.result.finalDataUrl), "photo.jpg");
    form.append("spec", JSON.stringify({ format, scale: 1, quality: 92, dpi }));
    const response = await fetch("/api/export", { method: "POST", body: form, credentials: "same-origin" });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || data.detail || "Export failed."); }
    const blob = await response.blob();
    downloadBlob(blob, `passportlens-${slug(state.profile.id)}.${format}`);
    trackEvent("download_completed", { format });
    toast("Downloaded.", "ok");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    button.disabled = false;
  }
}

async function printSheet() {
  if (!state.result) return;
  const button = $("#sheet-btn");
  button.disabled = true;
  try {
    await authorize("print_sheet", "jpg", state.result.outputBytes);
    const out = state.profile.output || {};
    const form = new FormData();
    form.append("image", dataUrlToBlob(state.result.finalDataUrl), "photo.jpg");
    form.append("spec", JSON.stringify({ sheet: $("#sheet-size").value, copies: Number($("#sheet-copies").value) || 4, dpi: 300, photoWidthMm: out.printWidthMm || null, photoHeightMm: out.printHeightMm || null }));
    const response = await fetch("/api/print-sheet", { method: "POST", body: form, credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || data.detail || "Print sheet failed.");
    downloadBlob(dataUrlToBlob(data.sheetDataUrl), `passportlens-print-${$("#sheet-size").value}.jpg`);
    trackEvent("download_completed", { format: "print-sheet" });
    toast(`Print sheet ready (${data.layout.copies} copies).`, "ok");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    button.disabled = false;
  }
}

async function loadClients() {
  if (!state.plan || !state.plan.crm || state.plan.isAdmin) return;
  try {
    const data = await fetch("/api/crm/clients", { credentials: "same-origin" }).then((r) => r.json());
    if (data.ok) {
      state.clients = data.clients;
      $("#client-list").innerHTML = data.clients.map((c) => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.phone || c.email || "")}</option>`).join("");
    }
  } catch (error) {}
}

async function saveToClient(event) {
  event.preventDefault();
  const msg = $("#save-client-msg");
  msg.className = "form-msg";
  const name = $("#client-name").value.trim();
  if (!name) { msg.className = "form-msg bad"; msg.textContent = "Enter the client's name."; return; }
  msg.textContent = "Saving…";
  try {
    const projectId = await ensureProject();
    const existing = state.clients.find((c) => c.name.toLowerCase() === name.toLowerCase());
    const amount = $("#sale-amount").value;
    const body = {
      projectId,
      clientId: existing ? existing.id : null,
      newClient: existing ? null : { name, phone: $("#client-phone").value, email: $("#client-email").value },
      saleAmount: amount === "" ? null : Number(amount),
      salePaid: $("#sale-paid").value === "true",
      verdict: (state.result.decision || {}).status,
      currency: "CAD",
    };
    const response = await fetch("/api/crm/photos", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json", "x-kvnp-csrf": state.csrf }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || data.detail || "Could not save.");
    msg.className = "form-msg ok";
    msg.innerHTML = `Saved to ${escapeHtml(name)}. <a href="/crm">Open Clients</a>`;
    loadClients();
  } catch (error) {
    msg.className = "form-msg bad";
    msg.textContent = error.message;
  }
}

/* ------------------------------------------------------------------ */
/* utilities                                                           */
/* ------------------------------------------------------------------ */
function trackEvent(name, metadata = {}) {
  let anonymousId = "";
  try {
    anonymousId = localStorage.getItem("kvnp-anonymous-id") || crypto.randomUUID();
    localStorage.setItem("kvnp-anonymous-id", anonymousId);
  } catch (error) {}
  fetch("/api/events", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ name, anonymousId, projectId: state.projectId, metadata }) }).catch(() => {});
}

function dataUrlToBlob(dataUrl) {
  const [meta, base64] = dataUrl.split(",");
  const mime = (meta.match(/data:([^;]+)/) || [])[1] || "image/jpeg";
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function formatBytes(bytes) {
  if (!bytes) return "";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

function slug(value) { return String(value).replace(/-20\d\d-\d\d$/, ""); }
function uniq(items) { return [...new Set(items)]; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

let toastTimer = 0;
function toast(message, kind = "") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast ${kind}`;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3800);
}

boot();
