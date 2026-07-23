import { COUNTRIES, RULE_PROFILES, getDefaultProfile, getProfilesForCountry } from "./rules.js?v=kvnp-studio-33";
import { initCoach, analyzeFrame, coachAvailable } from "./capture.js?v=kvnp-studio-33";

const elements = {
  fileInput: document.querySelector("#file-input"),
  countrySelect: document.querySelector("#country-select"),
  profileSelect: document.querySelector("#profile-select"),
  profileSummary: document.querySelector("#profile-summary"),
  requirementsList: document.querySelector("#requirements-list"),
  sourceLinks: document.querySelector("#source-links"),
  sourceMeta: document.querySelector("#source-meta"),
  sourceCanvas: document.querySelector("#source-canvas"),
  finalCanvas: document.querySelector("#final-canvas"),
  emptyState: document.querySelector("#empty-state"),
  cameraButton: document.querySelector("#camera-button"),
  captureButton: document.querySelector("#capture-button"),
  cameraFeed: document.querySelector("#camera-feed"),
  autoCapture: document.querySelector("#auto-capture"),
  centerX: document.querySelector("#center-x"),
  centerY: document.querySelector("#center-y"),
  headHeight: document.querySelector("#head-height"),
  measurements: document.querySelector("#measurements"),
  sourceQualityList: document.querySelector("#source-quality-list"),
  retakeGuidance: document.querySelector("#retake-guidance"),
  pipelineReport: document.querySelector("#pipeline-report"),
  decisionCard: document.querySelector("#decision-card"),
  resultSummary: document.querySelector("#result-summary"),
  overallStatus: document.querySelector("#overall-status"),
  checksList: document.querySelector("#checks-list"),
  downloadPhoto: document.querySelector("#download-photo"),
  downloadOriginal: document.querySelector("#download-original"),
  backgroundVariant: document.querySelector("#background-variant"),
  downloadReport: document.querySelector("#download-report"),
  autoFix: document.querySelector("#auto-fix"),
  sheetSize: document.querySelector("#sheet-size"),
  sheetDpi: document.querySelector("#sheet-dpi"),
  sheetCopies: document.querySelector("#sheet-copies"),
  printSheet: document.querySelector("#print-sheet"),
  compare: document.querySelector("#compare"),
  compareBefore: document.querySelector("#compare-before"),
  compareAfter: document.querySelector("#compare-after"),
  compareRange: document.querySelector("#compare-range"),
  compareDivider: document.querySelector("#compare-divider"),
  visionStatus: document.querySelector("#vision-status"),
  automationSummary: document.querySelector("#automation-summary"),
  rerunVision: document.querySelector("#rerun-vision"),
  backgroundReplace: document.querySelector("#background-replace"),
  enhanceOutput: document.querySelector("#enhance-output"),
  enhancementMode: document.querySelector("#enhancement-mode"),
  backgroundColor: document.querySelector("#background-color"),
  autoStraighten: document.querySelector("#auto-straighten"),
  autoTone: document.querySelector("#auto-tone"),
  autoLighting: document.querySelector("#auto-lighting"),
  backgroundCleanup: document.querySelector("#background-cleanup"),
  backgroundPolicyNote: document.querySelector("#background-policy-note"),
  correctionsCard: document.querySelector("#corrections-card"),
  queueStrip: document.querySelector("#queue-strip"),
  countryGate: document.querySelector("#country-gate"),
  gateConfirm: document.querySelector("#gate-confirm"),
  policyList: document.querySelector("#policy-list"),
  previewMode: document.querySelector("#preview-mode"),
  touchupToggle: document.querySelector("#touchup-toggle"),
  touchupBrush: document.querySelector("#touchup-brush"),
  touchupSize: document.querySelector("#touchup-size"),
  touchupReset: document.querySelector("#touchup-reset"),
  viewResult: document.querySelector("#view-result"),
  viewCompare: document.querySelector("#view-compare"),
  toggleGuides: document.querySelector("#toggle-guides"),
  zoomIn: document.querySelector("#zoom-in"),
  zoomOut: document.querySelector("#zoom-out"),
  zoomLabel: document.querySelector("#zoom-label"),
  adjustGrid: document.querySelector("#adjust-grid"),
  adjustReset: document.querySelector("#adjust-reset"),
  outputFormat: document.querySelector("#output-format"),
  outputScale: document.querySelector("#output-scale"),
  outputDpi: document.querySelector("#output-dpi"),
  outputQuality: document.querySelector("#output-quality"),
  qualityField: document.querySelector("#quality-field"),
  qualityVal: document.querySelector("#quality-val"),
  outputNote: document.querySelector("#output-note"),
  bgSwatches: document.querySelector("#bg-swatches"),
  presetSelect: document.querySelector("#preset-select"),
  presetSave: document.querySelector("#preset-save"),
  presetDelete: document.querySelector("#preset-delete"),
  uploadDropzone: document.querySelector("#upload-dropzone"),
  programmeOutput: document.querySelector("#programme-output"),
  programmeBackground: document.querySelector("#programme-background"),
  programmeReviewed: document.querySelector("#programme-reviewed"),
  catalogueCount: document.querySelector("#catalogue-count"),
  workflowSteps: Array.from(document.querySelectorAll("[data-workflow-step]")),
  wizardPanels: Array.from(document.querySelectorAll("[data-wizard-panel]")),
  wizardBackButtons: Array.from(document.querySelectorAll("[data-wizard-back]")),
  continuePrepare: document.querySelector("#continue-prepare"),
  continueReview: document.querySelector("#continue-review"),
  photoStepNote: document.querySelector("#photo-step-note"),
  reviewPreviewTabs: Array.from(document.querySelectorAll("[data-review-preview]")),
  reviewPreviewViews: Array.from(document.querySelectorAll("[data-review-preview-view]")),
  reviewPhotoImage: document.querySelector("#review-photo-image"),
  documentPreviewPhoto: document.querySelector("#document-preview-photo"),
  printPreviewCopies: Array.from(document.querySelectorAll(".print-preview-copy")),
  downloadAdvisory: document.querySelector("#download-advisory"),
  downloadWarningDialog: document.querySelector("#download-warning-dialog"),
  downloadWarningList: document.querySelector("#download-warning-list"),
  downloadWarningAck: document.querySelector("#download-warning-ack"),
  downloadAnywayConfirm: document.querySelector("#download-anyway-confirm"),
  reviewSourceQualityList: document.querySelector("#review-source-quality-list"),
  backgroundVariantDialog: document.querySelector("#background-variant-dialog"),
  backgroundVariantTitle: document.querySelector("#background-variant-title"),
  backgroundVariantCopy: document.querySelector("#background-variant-copy"),
  backgroundVariantPolicy: document.querySelector("#background-variant-policy"),
  backgroundVariantConfirm: document.querySelector("#background-variant-confirm"),
};

const ADJUST_CONTROLS = [
  { key: "brightness", label: "Brightness", min: -100, max: 100 },
  { key: "contrast", label: "Contrast", min: -100, max: 100 },
  { key: "saturation", label: "Saturation", min: -100, max: 100 },
  { key: "warmth", label: "Warmth", min: -100, max: 100 },
  { key: "tint", label: "Tint", min: -100, max: 100 },
  { key: "highlights", label: "Highlights", min: -100, max: 100 },
  { key: "shadows", label: "Shadows", min: -100, max: 100 },
  { key: "sharpness", label: "Sharpness", min: 0, max: 100 },
];

const BG_PRESETS = [
  { name: "White", color: "#ffffff" },
  { name: "Off-white", color: "#f7f7f2" },
  { name: "Light grey", color: "#e9edf1" },
  { name: "Pale blue", color: "#dfeaf6" },
  { name: "Cream", color: "#f3ece0" },
  { name: "Sky", color: "#cfe0f4" },
];

const adjustCanvas = document.createElement("canvas");
const adjustCtx = adjustCanvas.getContext("2d", { willReadFrequently: true });

const state = {
  profile: getDefaultProfile(),
  image: null,
  imageName: "",
  imageMeta: null,
  face: null,
  crop: null,
  checks: [],
  humanChecks: {},
  exportBlob: null,
  cameraStream: null,
  lastReport: null,
  visionStatus: { ready: false, failed: false, message: "Connecting to Python MediaPipe" },
  modelInventory: [],
  mediaPipeFace: null,
  segmentation: null,
  cleanedSourceCanvas: null,
  originalFile: null,
  backendResult: null,
  processedImage: null,
  sourceOverlayImage: null,
  serverChecks: [],
  sourceQuality: [],
  pipeline: null,
  decision: null,
  processingError: null,
  manualOverride: false,
  backgroundReplaced: true,
  enhanceOutput: true,
  enhancementMode: "ai-clean",
  backgroundColor: "#ffffff",
  autoStraighten: true,
  autoTone: true,
  autoLighting: true,
  backgroundCleanup: "balanced",
  corrections: [],
  policyClamped: [],
  effectiveEdits: {},
  manualTouchup: false,
  processing: false,
  beforeDataUrl: null,
  queue: [],
  activeJobId: null,
  touchUp: { active: false, dirty: false, painting: false, brush: 26 },
  coach: { metrics: null, lastAnalyze: 0, readySince: 0, captured: false, autoCapture: true },
  programmeConfirmed: false,
  adjust: { brightness: 0, contrast: 0, saturation: 0, warmth: 0, tint: 0, highlights: 0, shadows: 0, sharpness: 0 },
  guides: false,
  zoom: 1,
  resultView: "result",
  outputFormat: "image/jpeg",
  outputScale: 1,
  outputDpi: 300,
  outputQuality: 92,
  previewMode: false,
  wizardStep: 1,
  reviewPreviewMode: "photo",
  reviewPreviewUrl: null,
  downloadAcknowledged: false,
  backgroundVariantBusy: false,
};

let adjustBakeTimer = 0;
let reanalyzeTimer = 0;
let analyzeSeq = 0;

let scanRAF = 0;
let cameraRAF = 0;
let processSeq = 0;
let queueIdCounter = 0;

const sourceCtx = elements.sourceCanvas.getContext("2d");
const finalCtx = elements.finalCanvas.getContext("2d");

let analysisTimer = 0;
let serverTimer = 0;

function init() {
  populateCountrySelect();
  populateProgrammeSelect(state.profile.country);
  applyProfileAutomationDefaults();
  renderProfile();
  renderEmptyCanvas();
  renderVisionStatus();
  renderPipeline();
  renderDecision();
  buildAdjustControls();
  buildBgSwatches();
  refreshPresetList();
  bindEvents();
  bindCockpit();
  updateCountryGate();
  checkBackendHealth();
  renderSourceQuality();
  renderQueue();
  renderWorkflowProgress();
}

function bindEvents() {
  elements.fileInput.addEventListener("change", handleFileSelect);
  elements.countrySelect.addEventListener("change", handleCountryChange);
  elements.profileSelect.addEventListener("change", handleProfileChange);
  elements.cameraButton.addEventListener("click", toggleCamera);
  elements.captureButton.addEventListener("click", captureCameraFrame);
  elements.autoCapture.addEventListener("change", () => { state.coach.autoCapture = elements.autoCapture.checked; });
  elements.downloadPhoto.addEventListener("click", downloadPhoto);
  elements.downloadOriginal.addEventListener("click", downloadOriginal);
  elements.backgroundVariant.addEventListener("click", showBackgroundVariantDialog);
  elements.downloadReport.addEventListener("click", downloadReport);
  elements.autoFix.addEventListener("click", autoFix);
  elements.printSheet.addEventListener("click", generatePrintSheet);
  elements.compareRange.addEventListener("input", updateCompareSplit);
  elements.rerunVision.addEventListener("click", rerunVisionAnalysis);
  elements.backgroundReplace.addEventListener("change", handleRenderOptionChange);
  elements.enhanceOutput.addEventListener("change", handleRenderOptionChange);
  elements.enhancementMode.addEventListener("change", handleRenderOptionChange);
  elements.backgroundColor.addEventListener("input", handleRenderOptionChange);
  elements.autoStraighten.addEventListener("change", handleRenderOptionChange);
  elements.autoTone.addEventListener("change", handleRenderOptionChange);
  elements.autoLighting.addEventListener("change", handleRenderOptionChange);
  elements.previewMode.addEventListener("change", handlePreviewModeChange);
  elements.gateConfirm.addEventListener("click", confirmProgramme);
  elements.continuePrepare.addEventListener("click", () => setWizardStep(3));
  elements.continueReview.addEventListener("click", () => setWizardStep(4));
  elements.checksList.addEventListener("click", handleHumanCheckClick);
  elements.backgroundCleanup.addEventListener("change", handleRenderOptionChange);
  elements.touchupToggle.addEventListener("click", toggleTouchUp);
  elements.touchupReset.addEventListener("click", resetTouchUp);
  elements.touchupSize.addEventListener("input", () => {
    state.touchUp.brush = Number(elements.touchupSize.value);
  });
  bindTouchUpCanvas();

  for (const input of [elements.centerX, elements.centerY, elements.headHeight]) {
    input.addEventListener("input", handleManualChange);
  }

  for (const step of elements.workflowSteps) {
    step.addEventListener("click", () => {
      setWizardStep(Number(step.dataset.workflowStep));
    });
  }

  for (const button of elements.wizardBackButtons) {
    button.addEventListener("click", () => setWizardStep(Number(button.dataset.wizardBack), { force: true }));
  }

  for (const tab of elements.reviewPreviewTabs) {
    tab.addEventListener("click", () => setReviewPreview(tab.dataset.reviewPreview));
  }

  elements.downloadWarningAck.addEventListener("change", () => {
    elements.downloadAnywayConfirm.disabled = !elements.downloadWarningAck.checked;
  });
  elements.downloadAnywayConfirm.addEventListener("click", () => {
    if (!elements.downloadWarningAck.checked) return;
    state.downloadAcknowledged = true;
    elements.downloadWarningDialog.close();
    performPhotoDownload();
  });
  elements.downloadWarningDialog.addEventListener("close", resetDownloadWarningDialog);
  elements.backgroundVariantConfirm.addEventListener("click", downloadBackgroundVariant);

  if (elements.uploadDropzone) {
    for (const eventName of ["dragenter", "dragover"]) {
      elements.uploadDropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        if (state.programmeConfirmed) elements.uploadDropzone.classList.add("dragging");
      });
    }
    for (const eventName of ["dragleave", "drop"]) {
      elements.uploadDropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        elements.uploadDropzone.classList.remove("dragging");
      });
    }
    elements.uploadDropzone.addEventListener("drop", (event) => {
      if (!state.programmeConfirmed) return;
      const files = Array.from(event.dataTransfer?.files ?? []).filter((file) => file.type.startsWith("image/"));
      if (files.length) addFilesToQueue(files);
    });
  }
}

function populateCountrySelect() {
  elements.countrySelect.innerHTML = "";
  for (const country of COUNTRIES) {
    const option = document.createElement("option");
    option.value = country.code;
    option.textContent = country.name;
    elements.countrySelect.append(option);
  }
  elements.countrySelect.value = state.profile.country;
}

function populateProgrammeSelect(countryCode) {
  elements.profileSelect.innerHTML = "";
  const profiles = getProfilesForCountry(countryCode);
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = `${profile.programme} (${profile.delivery})`;
    elements.profileSelect.append(option);
  }

  if (!profiles.some((profile) => profile.id === state.profile.id)) {
    state.profile = profiles[0] ?? getDefaultProfile();
  }

  elements.profileSelect.value = state.profile.id;
}

async function handleFileSelect(event) {
  const files = Array.from(event.target.files ?? []);
  if (!files.length) return;
  addFilesToQueue(files);
  event.target.value = ""; // allow re-selecting the same file(s)
}

function addFilesToQueue(files) {
  let firstNewId = null;
  for (const file of files) {
    const id = `job-${queueIdCounter++}`;
    state.queue.push({
      id,
      file,
      name: file.name || "capture.jpg",
      thumbUrl: URL.createObjectURL(file),
      status: "pending",
    });
    if (!firstNewId) firstNewId = id;
  }
  renderQueue();
  if (firstNewId) selectJob(firstNewId);
}

async function selectJob(id) {
  const item = state.queue.find((job) => job.id === id);
  if (!item) return;
  state.activeJobId = id;
  renderQueue();
  await loadImageFile(item.file);
}

function clearQueue() {
  for (const item of state.queue) {
    URL.revokeObjectURL(item.thumbUrl);
  }
  state.queue = [];
  state.activeJobId = null;
  renderQueue();
}

function updateActiveJobStatus() {
  const item = state.queue.find((job) => job.id === state.activeJobId);
  if (!item) return;
  item.status = state.decision?.status ?? "pending";
  renderQueue();
}

function renderQueue() {
  if (!elements.queueStrip) return;
  updateQueueBadge();
  if (!state.queue.length) {
    elements.queueStrip.hidden = true;
    elements.queueStrip.innerHTML = "";
    return;
  }

  elements.queueStrip.hidden = false;
  const items = state.queue
    .map(
      (item) =>
        `<button class="queue-item status-${escapeHtml(item.status)} ${item.id === state.activeJobId ? "active" : ""}" data-id="${escapeHtml(
          item.id,
        )}" type="button" title="${escapeHtml(item.name)}"><img src="${item.thumbUrl}" alt="" /><span class="queue-dot"></span></button>`,
    )
    .join("");
  elements.queueStrip.innerHTML = `${items}<button class="queue-clear" data-action="clear" type="button">Clear</button>`;

  for (const button of elements.queueStrip.querySelectorAll(".queue-item")) {
    button.addEventListener("click", () => selectJob(button.dataset.id));
  }
  const clear = elements.queueStrip.querySelector('[data-action="clear"]');
  if (clear) clear.addEventListener("click", clearQueue);
}

function updateQueueBadge() {
  const badge = document.querySelector("#nav-queue-count");
  if (!badge) return;
  if (state.queue.length) {
    badge.textContent = String(state.queue.length);
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }
}

function handleProfileChange() {
  state.profile = RULE_PROFILES.find((profile) => profile.id === elements.profileSelect.value) ?? getDefaultProfile();
  state.programmeConfirmed = false;
  state.downloadAcknowledged = false;
  setWizardStep(1, { force: true, focus: false });
  state.previewMode = false;
  elements.previewMode.checked = false;
  applyProfileAutomationDefaults();
  renderProfile();
  renderVisionStatus();
  configureFinalCanvas();
  state.manualOverride = false;
  if (state.originalFile) {
    scheduleServerProcessing();
  } else {
    scheduleAnalysis();
  }
}

function handleCountryChange() {
  const profiles = getProfilesForCountry(elements.countrySelect.value);
  state.profile = profiles[0] ?? getDefaultProfile();
  state.programmeConfirmed = false;
  state.downloadAcknowledged = false;
  setWizardStep(1, { force: true, focus: false });
  state.previewMode = false;
  elements.previewMode.checked = false;
  populateProgrammeSelect(state.profile.country);
  applyProfileAutomationDefaults();
  renderProfile();
  renderVisionStatus();
  configureFinalCanvas();
  state.manualOverride = false;
  if (state.originalFile) {
    scheduleServerProcessing();
  } else {
    scheduleAnalysis();
  }
}

function handleManualChange() {
  if (!state.image || !state.face) return;

  state.downloadAcknowledged = false;
  state.face.centerX = (Number(elements.centerX.value) / 100) * state.image.naturalWidth;
  state.face.centerY = (Number(elements.centerY.value) / 100) * state.image.naturalHeight;
  state.face.headHeight = (Number(elements.headHeight.value) / 100) * state.image.naturalHeight;
  state.face.source = state.face.source.includes("python") ? "python-mediapipe-adjusted" : "manual";
  state.manualOverride = true;
  if (state.originalFile) {
    scheduleServerProcessing();
  } else {
    scheduleAnalysis();
  }
}

function handleRenderOptionChange() {
  state.downloadAcknowledged = false;
  state.backgroundReplaced = elements.backgroundReplace.checked;
  state.enhanceOutput = elements.enhanceOutput.checked;
  state.enhancementMode = elements.enhancementMode.value;
  state.backgroundColor = elements.backgroundColor.value;
  state.autoStraighten = elements.autoStraighten.checked;
  state.autoTone = elements.autoTone.checked;
  state.autoLighting = elements.autoLighting.checked;
  state.backgroundCleanup = elements.backgroundCleanup.value;
  if (state.originalFile) {
    scheduleServerProcessing();
  } else {
    scheduleAnalysis();
  }
}

function handlePreviewModeChange() {
  state.downloadAcknowledged = false;
  state.previewMode = elements.previewMode.checked;
  if (state.previewMode) {
    state.autoStraighten = true;
    state.autoTone = true;
    state.autoLighting = true;
    state.backgroundReplaced = true;
    state.enhanceOutput = true;
    state.enhancementMode = "natural";
    state.backgroundCleanup = "balanced";
    elements.autoStraighten.checked = true;
    elements.autoTone.checked = true;
    elements.autoLighting.checked = true;
    elements.backgroundReplace.checked = true;
    elements.enhanceOutput.checked = true;
    elements.enhancementMode.value = state.enhancementMode;
    elements.backgroundCleanup.value = state.backgroundCleanup;
    applyPolicyControlGate();
  } else {
    applyProfileAutomationDefaults();
  }
  renderPolicyList();
  updateOutputNote();
  if (state.originalFile) scheduleServerProcessing();
  else scheduleAnalysis();
}

function applyProfileAutomationDefaults() {
  const automation = state.profile.automation ?? {};
  state.backgroundReplaced = automation.backgroundReplacement !== false;
  state.enhanceOutput = automation.enhanceOutput !== false;
  state.enhancementMode = automation.enhancementMode ?? "ai-clean";
  state.backgroundColor = automation.backgroundColor ?? "#ffffff";
  state.backgroundCleanup = automation.backgroundCleanup ?? "balanced";
  state.outputFormat = state.profile.output?.mime ?? "image/jpeg";
  state.outputScale = 1;
  state.outputDpi = 300;
  state.outputQuality = Math.round((state.profile.output?.quality ?? 0.92) * 100);

  elements.backgroundReplace.checked = state.backgroundReplaced;
  elements.backgroundReplace.disabled = false;
  elements.enhanceOutput.checked = state.enhanceOutput;
  elements.enhanceOutput.disabled = false;
  elements.enhancementMode.value = state.enhancementMode;
  elements.enhancementMode.disabled = false;
  elements.backgroundColor.value = state.backgroundColor;
  elements.backgroundCleanup.value = state.backgroundCleanup;
  syncOutputControls();

  applyPolicyControlGate();
}

function applyPolicyControlGate() {
  // Submission mode follows programme policy. Editing preview can exercise the
  // pipeline because the server permanently watermarks that result.
  const allowed = state.profile.allowedEdits ?? {};
  const gates = [
    ["autoStraighten", "straighten"],
    ["autoTone", "tone"],
    ["autoLighting", "lighting"],
    ["backgroundReplace", "background"],
    ["enhanceOutput", "enhance"],
  ];
  for (const [el, key] of gates) {
    const banned = allowed[key] === false && !state.previewMode;
    elements[el].disabled = banned;
    if (banned) {
      elements[el].checked = false;
      elements[el].title = `Not permitted for ${state.profile.countryName} — ${state.profile.programme}`;
    } else {
      elements[el].title = "";
    }
  }
  if (!state.previewMode && allowed.straighten === false) state.autoStraighten = false;
  if (!state.previewMode && allowed.tone === false) state.autoTone = false;
  if (!state.previewMode && allowed.lighting === false) state.autoLighting = false;
  if (!state.previewMode && allowed.background === false) state.backgroundReplaced = false;
  if (!state.previewMode && allowed.enhance === false) state.enhanceOutput = false;
  // Generative "strong"/rescue restore is not offered in the UI (it would alter the
  // face). If a stale preset ever carries it, fall back to a non-generative mode.
  if (state.enhancementMode === "strong") {
    state.enhancementMode = "studio";
    elements.enhancementMode.value = "studio";
  }

  elements.enhancementMode.disabled = allowed.enhance === false && !state.previewMode;
  elements.backgroundCleanup.disabled = allowed.background === false && !state.previewMode;
  elements.backgroundColor.disabled = allowed.background === false && !state.previewMode;
  applyAdjustmentPolicyGate();

  // Touch-up paints over the background, so it is gated by the same background policy.
  applyTouchupGate();
  updateBackgroundPolicyNote();
}

function updateBackgroundPolicyNote() {
  if (!elements.backgroundPolicyNote || !state.profile) return;
  const required = describeBackground(state.profile.background?.mode ?? "plain light background");
  const banned = state.profile.allowedEdits?.background === false && !state.previewMode;
  elements.backgroundPolicyNote.className = `control-guidance ${state.previewMode ? "preview" : banned ? "locked" : "allowed"}`;
  if (state.previewMode) {
    elements.backgroundPolicyNote.textContent =
      `Editing Preview: background removal is available, but the result is permanently watermarked and is not a submission file. Required appearance: ${required}.`;
  } else if (banned) {
    elements.backgroundPolicyNote.textContent =
      `Required in the original capture: ${required}. Digital background removal is not permitted for this submission profile; retake against that background.`;
  } else {
    elements.backgroundPolicyNote.textContent =
      `Background replacement is available for this profile. Required appearance: ${required}.`;
  }
}

function syncOutputControls() {
  elements.outputFormat.value = state.outputFormat;
  elements.outputScale.value = String(state.outputScale);
  elements.outputDpi.value = String(state.outputDpi);
  elements.outputQuality.value = String(state.outputQuality);
  elements.qualityVal.textContent = String(state.outputQuality);
  if (elements.qualityField) elements.qualityField.hidden = state.outputFormat === "image/png";
  elements.outputDpi.disabled = state.outputFormat === "image/webp";
  updateOutputNote();
}

function updateOutputNote() {
  if (!elements.outputNote) return;
  if (state.previewMode) {
    elements.outputNote.classList.add("warning");
    elements.outputNote.textContent = "Watermarked editing preview. Switch back to Submission mode for the application file.";
    return;
  }
  const labels = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WebP",
    "application/pdf": "PDF",
  };
  const requiredMime = state.profile.output?.mime ?? "image/jpeg";
  const width = Number(state.profile.output?.widthPx ?? 0) * state.outputScale;
  const height = Number(state.profile.output?.heightPx ?? 0) * state.outputScale;
  const convenience = state.outputScale !== 1 || state.outputFormat !== requiredMime;
  elements.outputNote.classList.toggle("warning", convenience);
  elements.outputNote.textContent = convenience
    ? `Convenience export: ${width} x ${height}px ${labels[state.outputFormat] ?? "file"}. The portal may require ${state.profile.output.widthPx} x ${state.profile.output.heightPx}px ${labels[requiredMime] ?? "JPEG"}.`
    : `Submission export: ${width} x ${height}px ${labels[state.outputFormat] ?? "file"} at the programme's required canvas size.`;
}

function isValidationOnlyProfile() {
  const allowed = state.profile?.allowedEdits ?? {};
  return ["straighten", "tone", "lighting", "background", "enhance"].every((key) => allowed[key] === false);
}

function applyAdjustmentPolicyGate() {
  const validationOnly = isValidationOnlyProfile() && !state.previewMode;
  if (validationOnly) {
    for (const key of Object.keys(state.adjust)) state.adjust[key] = 0;
  }
  for (const input of elements.adjustGrid?.querySelectorAll("[data-adjust]") ?? []) {
    input.disabled = validationOnly;
    input.title = validationOnly ? `Pixel adjustments are not permitted for ${state.profile.countryName}` : "";
  }
  if (elements.adjustReset) elements.adjustReset.disabled = validationOnly;
  const manualDetails = document.querySelector(".manual-details");
  manualDetails?.classList.toggle("policy-locked", validationOnly);
  for (const input of manualDetails?.querySelectorAll("input") ?? []) input.disabled = validationOnly;
  if (validationOnly) state.manualOverride = false;
  if (elements.autoFix) elements.autoFix.textContent = validationOnly ? "Recheck photo" : "Prepare photo";
  syncAdjustControls();
}

function applyTouchupGate() {
  if (!elements.touchupToggle) return;
  const banned = state.profile?.allowedEdits?.background === false && !state.previewMode;
  if (banned) {
    elements.touchupToggle.disabled = true;
    elements.touchupToggle.title = `Not permitted for ${state.profile.countryName} — ${state.profile.programme}`;
  } else {
    elements.touchupToggle.title = "";
  }
}

function confirmProgramme() {
  state.programmeConfirmed = true;
  updateCountryGate();
  setWizardStep(2, { force: true });
}

function updateCountryGate() {
  const gated = !state.programmeConfirmed;
  if (elements.countryGate) elements.countryGate.hidden = !gated;
  // Source intake stays locked until the destination country is chosen.
  elements.fileInput.disabled = gated;
  elements.cameraButton.disabled = gated;
  document.querySelector('label[for="file-input"]')?.classList.toggle("btn-locked", gated);
  if (elements.gateConfirm && state.profile) {
    elements.gateConfirm.textContent = `Continue with ${state.profile.countryName} — ${state.profile.programme}`;
  }
}

function maxUnlockedWizardStep() {
  if (!state.programmeConfirmed) return 1;
  if (!state.image) return 2;
  if (state.processing || (!state.backendResult && !state.processingError && !state.exportBlob)) return 3;
  return 4;
}

function setWizardStep(step, { force = false, focus = true } = {}) {
  const requested = Math.max(1, Math.min(4, Number(step) || 1));
  const target = force ? requested : Math.min(requested, maxUnlockedWizardStep());
  state.wizardStep = target;
  renderWorkflowProgress();
  if (target === 4) updateReviewPreview();

  if (focus) {
    const panel = elements.wizardPanels.find((item) => Number(item.dataset.wizardPanel) === target);
    panel?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => panel?.querySelector("h3")?.focus({ preventScroll: true }), 260);
  }
}

function renderWorkflowProgress() {
  const maxUnlocked = maxUnlockedWizardStep();
  if (state.wizardStep > maxUnlocked) state.wizardStep = maxUnlocked;
  if (state.wizardStep < 1) state.wizardStep = 1;

  for (const panel of elements.wizardPanels) {
    const active = Number(panel.dataset.wizardPanel) === state.wizardStep;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  }

  for (const step of elements.workflowSteps) {
    const index = Number(step.dataset.workflowStep);
    const locked = index > maxUnlocked;
    step.classList.toggle("active", index === state.wizardStep);
    step.classList.toggle("complete", index < state.wizardStep);
    step.classList.toggle("locked", locked);
    step.disabled = locked;
    step.setAttribute("aria-current", index === state.wizardStep ? "step" : "false");
    step.setAttribute("aria-disabled", locked ? "true" : "false");
  }

  elements.continuePrepare.disabled = !state.image || state.processing;
  elements.continueReview.disabled = !state.image || state.processing;
  elements.photoStepNote.textContent = state.processing
    ? "Analyzing pose, crop, lighting and source quality..."
    : state.image
      ? "Photo loaded. Continue to inspect and prepare it."
      : "Upload or capture one photo to continue.";
}

const EDIT_LABELS = {
  straighten: "Straighten / crop",
  tone: "Exposure & colour",
  lighting: "Even face light / red-eye",
  background: "Background replace",
  enhance: "Photo enhancement",
  rescue: "AI face restoration",
};

function renderPolicyList() {
  if (!elements.policyList) return;
  const allowed = state.profile?.allowedEdits;
  if (!allowed) {
    elements.policyList.innerHTML = "";
    return;
  }
  const mode = state.previewMode
    ? `<div class="policy-mode preview"><strong>Editing preview active</strong><span>Identity-preserving cleanup tools are enabled. The result is watermarked and cannot be mistaken for a submission file.</span></div>`
    : isValidationOnlyProfile()
    ? `<div class="policy-mode validation"><strong>Submission mode: validation only</strong><span>This programme does not permit the listed pixel edits. We crop, size and check the original capture; defects require a retake.</span></div>`
    : `<div class="policy-mode assisted"><strong>Assisted editing</strong><span>Only the operations listed below can be applied.</span></div>`;
  const chips = Object.keys(EDIT_LABELS)
    .map((key) => {
      const ok = allowed[key] !== false || (state.previewMode && key !== "rescue");
      return `<span class="policy-chip ${ok ? "ok" : "no"}">${ok ? "✓" : "✗"} ${escapeHtml(EDIT_LABELS[key])}</span>`;
    })
    .join("");
  const note = allowed.note ? `<p class="policy-note">${escapeHtml(allowed.note)}</p>` : "";
  elements.policyList.innerHTML = mode + chips + note;
}

async function loadImageFile(file) {
  if (state.cameraStream) stopCamera(); // release the camera + its RAF loop first

  const imageUrl = URL.createObjectURL(file);
  const image = new Image();
  image.decoding = "async";

  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = reject;
    image.src = imageUrl;
  });

  state.image = image;
  state.imageName = file.name || "camera-capture.jpg";
  state.originalFile = file;
  state.downloadAcknowledged = false;
  state.imageMeta = {
    type: file.type || "image/jpeg",
    size: file.size,
    lastModified: file.lastModified || Date.now(),
  };
  state.exportBlob = null;
  state.mediaPipeFace = null;
  state.segmentation = null;
  state.cleanedSourceCanvas = null;
  state.backendResult = null;
  state.processedImage = null;
  state.sourceOverlayImage = null;
  state.serverChecks = [];
  state.sourceQuality = [];
  state.humanChecks = {};
  state.pipeline = null;
  state.decision = null;
  state.processingError = null;
  state.corrections = [];
  state.policyClamped = [];
  state.effectiveEdits = {};
  state.manualTouchup = false;
  state.beforeDataUrl = null;
  state.manualOverride = false;
  elements.downloadOriginal.disabled = false;
  updateReviewPreview();
  updateDownloadAdvisory();
  setResultView("result");
  setZoom(1);
  renderWorkflowProgress();

  configureDefaultFace();
  syncManualControls();
  renderSourceMeta();
  elements.emptyState.hidden = true;
  elements.cameraFeed.hidden = true;
  await processOnServer();
  syncManualControls();
  scheduleAnalysis();
}

function configureDefaultFace() {
  // Geometry must come from a successful detector result. Inventing a centered
  // fallback face makes non-portraits look measurable and is unsafe for export.
  state.face = null;
  state.crop = null;
}

async function rerunVisionAnalysis() {
  if (!state.originalFile) return;
  await processOnServer();
}

function scheduleServerProcessing() {
  window.clearTimeout(serverTimer);
  elements.automationSummary.textContent = "Preparing Python MediaPipe processing...";
  serverTimer = window.setTimeout(processOnServer, 180);
}

async function checkBackendHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.modelInventory = data.models ?? [];
    const matteEngine = data.modnet ? "MODNet matting" : "MediaPipe matting";
    state.visionStatus = {
      ready: true,
      failed: false,
      message: data.realEsrgan && data.gfpgan
        ? `${matteEngine} + Real-ESRGAN + GFPGAN ready`
        : data.realEsrgan
          ? `${matteEngine} + Real-ESRGAN ready`
        : data.processor === "python-mediapipe"
          ? `Python ${matteEngine} ready`
          : "Processor ready",
    };
  } catch (error) {
    state.modelInventory = [];
    state.visionStatus = {
      ready: false,
      failed: true,
      message: "Python backend unavailable. Run npm run dev.",
    };
  }
  renderVisionStatus();
  renderPipeline();
}

async function processOnServer() {
  if (!state.originalFile) return;

  // Sequence token: only the most recent request is allowed to write state or
  // touch the scan animation, so out-of-order responses can't show stale results.
  const seq = ++processSeq;

  elements.rerunVision.disabled = true;
  elements.automationSummary.textContent = "Running Python FaceMesh and background segmentation...";
  startScanAnimation();

  const form = new FormData();
  form.append("image", state.originalFile);
  form.append("profile", JSON.stringify(state.profile));
  form.append("options", JSON.stringify(getProcessingOptions()));

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      body: form,
    });
    const result = await response.json();
    if (seq !== processSeq) return; // a newer request superseded this one
    if (!response.ok || !result.ok) {
      throw new Error(result.error || `HTTP ${response.status}`);
    }

    state.backendResult = result;
    state.processingError = null;
    state.downloadAcknowledged = false;
    state.face = normalizeServerFace(result.face);
    state.crop = result.crop;
    state.serverChecks = result.checks ?? [];
    state.sourceQuality = result.sourceQuality ?? [];
    state.pipeline = result.pipeline ?? null;
    state.decision = result.decision ?? null;
    state.corrections = result.corrections ?? [];
    state.policyClamped = result.policyClamped ?? [];
    state.effectiveEdits = result.effectiveEdits ?? {};
    state.previewMode = Boolean(result.previewOnly);
    elements.previewMode.checked = state.previewMode;
    applyPolicyControlGate();
    state.beforeDataUrl = result.beforeDataUrl ?? null;
    state.checks = state.serverChecks;
    clearTouchUp();
    state.touchUp.serverFinalDataUrl = result.finalDataUrl;
    state.exportBlob = dataUrlToBlob(result.finalDataUrl);
    state.processedImage = await loadImageFromDataUrl(result.finalDataUrl);
    state.sourceOverlayImage = await loadImageFromDataUrl(result.overlayDataUrl);
    state.mediaPipeFace = null;
    state.segmentation = result.processor;
    state.visionStatus = { ready: true, failed: false, message: "Python MediaPipe ready" };
    stopScanAnimation();
    syncManualControls();
    runAnalysis();
    scheduleAdjustBake();
    updateActiveJobStatus();
  } catch (error) {
    if (seq !== processSeq) return; // superseded; let the newer request own the UI
    console.error(error);
    state.backendResult = null;
    state.face = null;
    state.crop = null;
    state.exportBlob = null;
    state.processedImage = null;
    state.sourceOverlayImage = null;
    state.corrections = [];
    state.effectiveEdits = {};
    state.beforeDataUrl = null;
    state.processingError = error.message || "The photo could not be analyzed.";
    state.downloadAcknowledged = false;
    state.sourceQuality = [
      qualityCheck("analysis_error", "Portrait analysis", "fail", state.processingError, "1 clear, unobstructed face"),
    ];
    state.serverChecks = [];
    state.checks = [];
    state.pipeline = {
      version: "analysis-failed",
      models: state.modelInventory ?? [],
      stages: [
        {
          id: "geometry",
          label: "Geometry",
          engine: "MediaPipe Face Landmarker",
          status: "fail",
          detail: state.processingError,
        },
      ],
    };
    state.decision = {
      status: "retake",
      title: "Retake required",
      message: state.processingError,
      failures: 1,
      warnings: 0,
      reviews: 0,
      actions: ["Use one unobstructed, front-facing person in even light"],
      pipelineVersion: "analysis-failed",
    };
    state.visionStatus = { ready: false, failed: true, message: error.message };
    elements.automationSummary.textContent = error.message;
    stopScanAnimation();
    scheduleAnalysis();
  } finally {
    if (seq === processSeq) {
      renderVisionStatus();
      renderWorkflowProgress();
      updateReviewPreview();
      updateDownloadAdvisory();
    }
  }
}

function getProcessingOptions() {
  const options = {
    backgroundReplaced: state.backgroundReplaced,
    enhanceOutput: state.enhanceOutput,
    enhancementMode: state.enhancementMode,
    backgroundColor: state.backgroundColor,
    autoStraighten: state.autoStraighten,
    autoTone: state.autoTone,
    autoLighting: state.autoLighting,
    backgroundCleanup: state.backgroundCleanup,
    previewMode: state.previewMode,
  };

  if (state.manualOverride && state.face) {
    options.manualFace = {
      centerX: state.face.centerX,
      centerY: state.face.centerY,
      headHeight: state.face.headHeight,
      faceWidth: state.face.faceWidth,
    };
  }

  return options;
}

function normalizeServerFace(face) {
  return {
    centerX: face.centerX,
    centerY: face.centerY,
    headHeight: face.headHeight,
    faceWidth: face.faceWidth,
    source: face.source,
    confidence: 0.96,
    faceCount: face.faceCount,
    rollDegrees: face.rollDegrees,
    yawProxy: face.yawProxy,
    pitchDegrees: face.pitchDegrees,
    pitchOffsetDegrees: face.pitchOffsetDegrees,
    gazeHorizontalPercent: face.gazeHorizontalPercent,
    gazeVerticalPercent: face.gazeVerticalPercent,
    gazeOffsetPercent: face.gazeOffsetPercent,
    mouthGapPercent: face.mouthGapPercent,
    eyeOpenness: face.eyeOpenness,
    expressionScore: 0,
    bounds: face.bounds,
  };
}

async function detectFaceIfAvailable(file) {
  if (!file || !("FaceDetector" in window)) return;

  try {
    const Detector = window.FaceDetector;
    const detector = new Detector({ fastMode: true, maxDetectedFaces: 1 });
    const bitmap = await createImageBitmap(file);
    const detections = await detector.detect(bitmap);
    bitmap.close?.();

    if (!detections.length) return;

    const box = detections[0].boundingBox;
    const estimatedHeadHeight = Math.min(state.image.naturalHeight, box.height * 1.42);
    state.face = {
      centerX: box.x + box.width / 2,
      centerY: box.y + box.height * 0.52,
      headHeight: estimatedHeadHeight,
      faceWidth: box.width,
      source: "native-face-detector",
      confidence: 0.65,
      faceCount: detections.length,
    };
  } catch (error) {
    console.warn("Face detection unavailable:", error);
  }
}

function renderVisionStatus() {
  const status = state.visionStatus ?? { ready: false, failed: true, message: "Backend unavailable" };
  if (status.ready) {
    elements.visionStatus.textContent = status.message || "Python MediaPipe ready";
    elements.visionStatus.className = "status-chip";
  } else if (status.failed) {
    elements.visionStatus.textContent = "Backend issue";
    elements.visionStatus.className = "status-chip warning-chip";
  } else {
    elements.visionStatus.textContent = "Connecting backend";
    elements.visionStatus.className = "status-chip loading-chip";
  }

  elements.rerunVision.disabled = !state.image;
  elements.autoFix.disabled = !state.originalFile || Boolean(state.processingError) || !state.face;

  if (!state.image) {
    elements.automationSummary.textContent = status.ready
      ? isValidationOnlyProfile()
        ? "Python MediaPipe is ready. Load a portrait to validate the original capture."
        : "Python MediaPipe is ready. Load a portrait for permitted corrections and validation."
      : status.message;
    return;
  }

  if (state.backendResult?.ok) {
    const background = state.backgroundReplaced ? "clean background on" : "clean background off";
    const enhancement = state.enhanceOutput ? `${state.enhancementMode} enhancement` : "enhancement off";
    elements.automationSummary.textContent = `${state.face.faceCount ?? 1} face found / ${background} / ${enhancement}`;
    return;
  }

  elements.automationSummary.textContent = status.failed
    ? status.message
    : "Waiting for Python processing.";
}

function syncManualControls() {
  if (!state.image || !state.face) return;
  elements.centerX.value = Math.round((state.face.centerX / state.image.naturalWidth) * 100);
  elements.centerY.value = Math.round((state.face.centerY / state.image.naturalHeight) * 100);
  elements.headHeight.value = Math.round((state.face.headHeight / state.image.naturalHeight) * 100);
}

function renderProfile() {
  const { profile } = state;
  const output = `${profile.output.widthPx} x ${profile.output.heightPx}px`;
  const head = profile.head.minMm
    ? `${profile.head.minMm}-${profile.head.maxMm}mm head`
    : `${profile.head.minPercent}-${profile.head.maxPercent}% head`;
  elements.countrySelect.value = profile.country;
  elements.profileSelect.value = profile.id;
  elements.profileSummary.textContent = `${profile.countryName} / ${profile.programme} / ${output} / ${head}`;
  const physical = profile.output.printWidthMm && profile.output.printHeightMm
    ? ` / ${profile.output.printWidthMm} x ${profile.output.printHeightMm} mm`
    : "";
  if (elements.programmeOutput) elements.programmeOutput.textContent = `${output}${physical}`;
  if (elements.programmeBackground) {
    elements.programmeBackground.textContent = describeBackground(profile.background?.mode ?? "plain_light");
  }
  if (elements.programmeReviewed) elements.programmeReviewed.textContent = profile.lastReviewed ?? "Review pending";
  if (elements.catalogueCount) elements.catalogueCount.textContent = `${RULE_PROFILES.length} programmes / ${COUNTRIES.length} countries`;
  elements.requirementsList.innerHTML = "";

  for (const requirement of profile.requirements ?? []) {
    const item = document.createElement("div");
    item.textContent = requirement;
    elements.requirementsList.append(item);
  }

  renderPolicyList();
  updateCountryGate();
  elements.sourceLinks.innerHTML = "";

  for (const source of profile.sources) {
    const link = document.createElement("a");
    link.href = source.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = source.label;
    elements.sourceLinks.append(link);
  }
}

function renderSourceMeta() {
  if (!state.image) {
    elements.sourceMeta.textContent = "No image loaded";
    return;
  }

  const size = state.imageMeta?.size ? `${formatBytes(state.imageMeta.size)} source` : "camera source";
  elements.sourceMeta.textContent = `${state.imageName} / ${state.image.naturalWidth} x ${state.image.naturalHeight}px / ${size}`;
}

function scheduleAnalysis() {
  window.clearTimeout(analysisTimer);
  analysisTimer = window.setTimeout(runAnalysis, 60);
}

async function runAnalysis() {
  if (!state.image) {
    renderEmptyCanvas();
    renderNoResult();
    return;
  }
  if (!state.face) {
    if (state.processingError) {
      renderProcessingFailure();
    } else {
      renderEmptyCanvas();
      renderNoResult();
    }
    return;
  }

  configureFinalCanvas();
  if (state.backendResult?.ok && state.processedImage) {
    renderSourceCanvas();
    renderFinalCanvas();
    state.checks = state.serverChecks;
    state.lastReport = buildReport();
    renderMeasurements();
    renderVisionStatus();
    renderSourceQuality();
    renderPipeline();
    renderDecision();
    renderCorrections();
    renderChecks();
    return;
  }

  state.crop = calculateCrop();
  state.cleanedSourceCanvas = buildCleanedSourceCanvas();
  renderSourceCanvas();
  renderFinalCanvas();
  state.exportBlob = await createExportBlob();
  state.sourceQuality = buildBrowserSourceQuality();
  state.checks = runChecks();
  state.pipeline = buildBrowserPipeline();
  state.decision = buildBrowserDecision();
  state.lastReport = buildReport();
  renderMeasurements();
  renderVisionStatus();
  renderSourceQuality();
  renderPipeline();
  renderDecision();
  renderCorrections();
  renderChecks();
}

function configureFinalCanvas() {
  elements.finalCanvas.width = state.profile.output.widthPx;
  elements.finalCanvas.height = state.profile.output.heightPx;
}

function calculateCrop() {
  const { image, face, profile } = state;
  const aspect = profile.output.widthPx / profile.output.heightPx;
  const targetHeadRatio = profile.head.targetPercent / 100;
  let cropHeight = face.headHeight / targetHeadRatio;
  let cropWidth = cropHeight * aspect;

  if (cropWidth > image.naturalWidth) {
    cropWidth = image.naturalWidth;
    cropHeight = cropWidth / aspect;
  }

  if (cropHeight > image.naturalHeight) {
    cropHeight = image.naturalHeight;
    cropWidth = cropHeight * aspect;
  }

  const headTop = face.centerY - face.headHeight / 2;
  let cropX = face.centerX - cropWidth / 2;
  let cropY = headTop - cropHeight * (profile.head.topMarginPercent / 100);

  cropX = clamp(cropX, 0, image.naturalWidth - cropWidth);
  cropY = clamp(cropY, 0, image.naturalHeight - cropHeight);

  return {
    x: cropX,
    y: cropY,
    width: cropWidth,
    height: cropHeight,
    aspect,
  };
}

function renderEmptyCanvas() {
  sourceCtx.clearRect(0, 0, elements.sourceCanvas.width, elements.sourceCanvas.height);
  sourceCtx.fillStyle = "#0f1620";
  sourceCtx.fillRect(0, 0, elements.sourceCanvas.width, elements.sourceCanvas.height);
  sourceCtx.strokeStyle = "#29405a";
  sourceCtx.lineWidth = 2;
  sourceCtx.strokeRect(40, 40, elements.sourceCanvas.width - 80, elements.sourceCanvas.height - 80);
}

function renderSourceCanvas() {
  const canvas = elements.sourceCanvas;
  if (state.sourceOverlayImage) {
    const fit = getContainFit(
      state.sourceOverlayImage.naturalWidth,
      state.sourceOverlayImage.naturalHeight,
      canvas.width,
      canvas.height,
    );
    sourceCtx.clearRect(0, 0, canvas.width, canvas.height);
    sourceCtx.fillStyle = "#eef2f7";
    sourceCtx.fillRect(0, 0, canvas.width, canvas.height);
    sourceCtx.drawImage(state.sourceOverlayImage, fit.x, fit.y, fit.width, fit.height);
    return;
  }

  const fit = getContainFit(state.image.naturalWidth, state.image.naturalHeight, canvas.width, canvas.height);
  sourceCtx.clearRect(0, 0, canvas.width, canvas.height);
  sourceCtx.fillStyle = "#0f1620";
  sourceCtx.fillRect(0, 0, canvas.width, canvas.height);
  sourceCtx.drawImage(state.image, fit.x, fit.y, fit.width, fit.height);

  sourceCtx.save();
  sourceCtx.fillStyle = "rgba(7, 13, 22, 0.42)";
  sourceCtx.fillRect(fit.x, fit.y, fit.width, fit.height);
  sourceCtx.fillStyle = state.processingError ? "#fecaca" : "#dbeafe";
  sourceCtx.font = "700 18px Segoe UI, sans-serif";
  sourceCtx.textAlign = "center";
  sourceCtx.fillText(state.processingError ? "Portrait analysis failed" : "Python FaceMesh processing...", canvas.width / 2, canvas.height / 2);
  sourceCtx.fillStyle = "#91a1b5";
  sourceCtx.font = "500 13px Segoe UI, sans-serif";
  sourceCtx.fillText(
    state.processingError ? state.processingError.slice(0, 100) : "The face-shaped contour will appear when processing completes.",
    canvas.width / 2,
    canvas.height / 2 + 28,
  );
  sourceCtx.restore();
}

function renderProcessingFailure() {
  configureFinalCanvas();
  renderSourceCanvas();
  finalCtx.clearRect(0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  finalCtx.fillStyle = "#0f1620";
  finalCtx.fillRect(0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  finalCtx.fillStyle = "#fecaca";
  finalCtx.font = "700 22px Segoe UI, sans-serif";
  finalCtx.textAlign = "center";
  finalCtx.fillText("No compliant output", elements.finalCanvas.width / 2, elements.finalCanvas.height / 2 - 10);
  finalCtx.fillStyle = "#91a1b5";
  finalCtx.font = "500 13px Segoe UI, sans-serif";
  finalCtx.fillText("Retake or choose a clear portrait.", elements.finalCanvas.width / 2, elements.finalCanvas.height / 2 + 20);
  state.lastReport = null;
  renderSourceQuality();
  renderPipeline();
  renderDecision();
  renderCorrections();
  renderChecks();
  elements.downloadPhoto.disabled = true;
  elements.downloadReport.disabled = true;
}

function renderFinalCanvas() {
  const { profile } = state;

  // Touch-up mode owns the canvas (the user is painting on it); don't redraw.
  if (state.touchUp.active) {
    elements.compare.hidden = true;
    elements.finalCanvas.hidden = false;
    return;
  }

  finalCtx.clearRect(0, 0, profile.output.widthPx, profile.output.heightPx);

  // Before/after compare view (only when a true "before" exists and selected).
  if (state.resultView === "compare" && state.processedImage && state.beforeDataUrl && state.backendResult?.finalDataUrl) {
    elements.compareAfter.src = state.backendResult.finalDataUrl;
    elements.compareBefore.src = state.beforeDataUrl;
    elements.compare.hidden = false;
    elements.finalCanvas.hidden = true;
    updateCompareSplit();
    return;
  }

  // Result view: the adjustable, guide-aware canvas.
  elements.compare.hidden = true;
  elements.finalCanvas.hidden = false;
  if (state.processedImage) {
    applyAdjustments();
    return;
  }

  finalCtx.fillStyle = "#0f1620";
  finalCtx.fillRect(0, 0, profile.output.widthPx, profile.output.heightPx);
  finalCtx.fillStyle = "#91a1b5";
  finalCtx.font = "700 22px Segoe UI, sans-serif";
  finalCtx.textAlign = "center";
  finalCtx.fillText("Waiting for Python output", profile.output.widthPx / 2, profile.output.heightPx / 2);
}

function updateCompareSplit() {
  const value = Number(elements.compareRange.value);
  elements.compare.style.setProperty("--split", `${value}%`);
}

function buildCleanedSourceCanvas() {
  if (!state.image) return null;

  const canvas = document.createElement("canvas");
  canvas.width = state.image.naturalWidth;
  canvas.height = state.image.naturalHeight;
  const ctx = canvas.getContext("2d");

  if (!state.backgroundReplaced || !state.segmentation?.canvas) {
    ctx.drawImage(state.image, 0, 0);
    return canvas;
  }

  ctx.fillStyle = state.backgroundColor;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.drawImage(state.segmentation.canvas, 0, 0, canvas.width, canvas.height);
  ctx.globalCompositeOperation = "source-in";
  ctx.drawImage(state.image, 0, 0);
  ctx.restore();

  return canvas;
}

function getHeadRect() {
  const { face } = state;
  const width = face.faceWidth || face.headHeight * 0.76;
  return {
    x: face.centerX - width / 2,
    y: face.centerY - face.headHeight / 2,
    width,
    height: face.headHeight,
  };
}

function drawLandmarks(fit) {
  const landmarks = state.mediaPipeFace?.landmarks;
  if (!landmarks?.length) return;

  sourceCtx.fillStyle = "rgba(14, 165, 233, 0.78)";
  const stride = Math.max(1, Math.floor(landmarks.length / 90));

  for (let index = 0; index < landmarks.length; index += stride) {
    const point = landmarks[index];
    sourceCtx.beginPath();
    sourceCtx.arc(fit.x + point.x * fit.scale, fit.y + point.y * fit.scale, 1.6, 0, Math.PI * 2);
    sourceCtx.fill();
  }
}

function runChecks() {
  const profile = state.profile;
  const crop = state.crop;
  const headPercent = getHeadPercent();
  const headMm = profile.output.printHeightMm ? (headPercent / 100) * profile.output.printHeightMm : null;
  const topMarginPercent = getTopMarginPercent();
  const centerOffsetPercent = Math.abs((state.face.centerX - (crop.x + crop.width / 2)) / crop.width) * 100;
  const imageQuality = analyzeImageQuality();
  const background = analyzeBackground();
  const fileCheck = analyzeFileSize();
  const checks = [];

  checks.push({
    id: "face_detection",
    label: "Face detection",
    status: getFaceDetectionStatus(),
    value: describeFaceDetection(),
    target: "1 clear face",
  });

  checks.push({
    id: "head_size",
    label: "Head size",
    status: inRange(headPercent, profile.head.minPercent, profile.head.maxPercent) ? "pass" : "fail",
    value: headMm ? `${headMm.toFixed(1)}mm (${headPercent.toFixed(1)}%)` : `${headPercent.toFixed(1)}%`,
    target: profile.head.minMm
      ? `${profile.head.minMm}-${profile.head.maxMm}mm`
      : `${profile.head.minPercent}-${profile.head.maxPercent}%`,
  });

  checks.push({
    id: "head_center",
    label: "Horizontal center",
    status: centerOffsetPercent <= 5 ? "pass" : centerOffsetPercent <= 8 ? "warning" : "fail",
    value: `${centerOffsetPercent.toFixed(1)}% offset`,
    target: "<= 5%",
  });

  checks.push({
    id: "top_margin",
    label: "Top margin",
    status: Math.abs(topMarginPercent - profile.head.topMarginPercent) <= 6 ? "pass" : "warning",
    value: `${topMarginPercent.toFixed(1)}%`,
    target: `${profile.head.topMarginPercent}% target`,
  });

  const shoulderRoom = 100 - topMarginPercent - headPercent;
  const targetShoulderRoom = 100 - profile.head.topMarginPercent - profile.head.targetPercent;
  const shoulderDelta = shoulderRoom - targetShoulderRoom;
  const shoulderStatus = shoulderRoom < 6
    ? "fail"
    : Math.abs(shoulderDelta) <= 8
    ? "pass"
    : Math.abs(shoulderDelta) <= 12
    ? "warning"
    : "fail";
  const shoulderNote = shoulderDelta > 8
    ? "too much upper body"
    : shoulderDelta < -8
    ? "shoulders too tight"
    : "balanced upper shoulders";
  checks.push({
    id: "shoulder_framing",
    label: "Shoulder framing",
    status: shoulderStatus,
    value: `${shoulderRoom.toFixed(1)}% below chin / ${shoulderNote}`,
    target: `about ${targetShoulderRoom.toFixed(0)}% / head and upper shoulders only`,
  });

  checks.push({
    id: "pose_roll",
    label: "Head tilt",
    status: getPoseStatus(Math.abs(state.face.rollDegrees ?? 0), 4, 7),
    value: `${Math.abs(state.face.rollDegrees ?? 0).toFixed(1)} deg`,
    target: "<= 4 deg",
  });

  checks.push({
    id: "pose_yaw",
    label: "Head direction",
    status: getPoseStatus(Math.abs(state.face.yawProxy ?? 0), 9, 14),
    value: `${Math.abs(state.face.yawProxy ?? 0).toFixed(1)}% nose offset`,
    target: "head facing camera",
  });

  if (state.face.gazeOffsetPercent != null) {
    checks.push({
      id: "eye_gaze",
      label: "Eye gaze",
      status: getPoseStatus(Math.abs(state.face.gazeOffsetPercent), 3, 4),
      value: `${Math.abs(state.face.gazeOffsetPercent).toFixed(1)}% iris offset`,
      target: "both eyes looking into camera",
    });
  }

  checks.push({
    id: "expression",
    label: "Expression / mouth",
    status: getExpressionStatus(),
    value: describeExpression(),
    target: "neutral, mouth closed",
  });

  checks.push({
    id: "background",
    label: "Background",
    status: background.status,
    value: background.value,
    target: describeBackground(profile.background.mode),
  });

  checks.push({
    id: "background_cleanup",
    label: "Background cleanup",
    status: getBackgroundCleanupStatus(),
    value: describeBackgroundCleanup(),
    target: state.backgroundReplaced ? "person mask applied" : "original background",
  });

  checks.push({
    id: "sharpness",
    label: "Sharpness",
    status: imageQuality.sharpness > 34 ? "pass" : imageQuality.sharpness > 22 ? "warning" : "fail",
    value: imageQuality.sharpness.toFixed(1),
    target: "> 34",
  });

  checks.push({
    id: "brightness",
    label: "Brightness",
    status: imageQuality.luma >= 80 && imageQuality.luma <= 220 ? "pass" : "warning",
    value: imageQuality.luma.toFixed(0),
    target: "80-220",
  });

  checks.push({
    id: "contrast",
    label: "Contrast",
    status: imageQuality.contrast >= 28 ? "pass" : "warning",
    value: imageQuality.contrast.toFixed(0),
    target: ">= 28",
  });

  checks.push({
    id: "output_size",
    label: "Output canvas",
    status: "pass",
    value: `${profile.output.widthPx} x ${profile.output.heightPx}px`,
    target: `${profile.output.widthPx} x ${profile.output.heightPx}px`,
  });

  if (fileCheck) {
    checks.push(fileCheck);
  }

  for (const item of profile.reviewChecks) {
    checks.push({
      id: `review_${item.replaceAll(" ", "_")}`,
      label: titleCase(item),
      status: "review",
      value: "Human check",
      target: "Required",
    });
  }

  return checks;
}

function getHeadPercent() {
  return (state.face.headHeight / state.crop.height) * 100;
}

function getTopMarginPercent() {
  const headTop = state.face.centerY - state.face.headHeight / 2;
  return ((headTop - state.crop.y) / state.crop.height) * 100;
}

function getShoulderRoomPercent() {
  return 100 - getTopMarginPercent() - getHeadPercent();
}

function getFaceDetectionStatus() {
  const source = state.face?.source ?? "";
  if (source.includes("mediapipe") && state.face.faceCount === 1) return "pass";
  if (source.includes("mediapipe") && state.face.faceCount > 1) return "fail";
  if (source.includes("native")) return "warning";
  return "fail";
}

function describeFaceDetection() {
  const source = state.face?.source ?? "manual";
  const count = state.face?.faceCount ?? 0;
  if (source.includes("mediapipe")) return `${count} face / MediaPipe landmarks`;
  if (source.includes("native")) return `${count || 1} face / native detector`;
  return "no verified face geometry";
}

function getPoseStatus(value, passMax, warningMax) {
  if (!state.face?.source?.includes("mediapipe")) return "review";
  if (value <= passMax) return "pass";
  if (value <= warningMax) return "warning";
  return "fail";
}

function getExpressionStatus() {
  if (!state.face?.source?.includes("mediapipe")) return "review";
  const mouthGap = state.face.mouthGapPercent ?? 0;
  const expression = state.face.expressionScore ?? 0;
  if (mouthGap <= 1.4 && expression <= 0.38) return "pass";
  if (mouthGap <= 2.4 && expression <= 0.55) return "warning";
  return "fail";
}

function describeExpression() {
  if (!state.face?.source?.includes("mediapipe")) return "manual review";
  return `mouth ${Number(state.face.mouthGapPercent ?? 0).toFixed(1)}% / expression ${Number(
    state.face.expressionScore ?? 0,
  ).toFixed(2)}`;
}

function getBackgroundCleanupStatus() {
  if (!state.backgroundReplaced) return "review";
  if (state.segmentation?.canvas) return "pass";
  return "warning";
}

function describeBackgroundCleanup() {
  if (!state.backgroundReplaced) return "disabled";
  if (state.segmentation?.canvas) {
    const coverage = state.segmentation.coverage ? `${Math.round(state.segmentation.coverage * 100)}% person mask` : "mask ready";
    return coverage;
  }
  return "no segmentation mask";
}

function analyzeImageQuality() {
  const sample = getSampledImageData(180);
  const data = sample.data;
  let lumaTotal = 0;
  let lumaSquared = 0;
  let edgeEnergy = 0;
  let pixels = 0;

  for (let y = 0; y < sample.height; y += 1) {
    for (let x = 0; x < sample.width; x += 1) {
      const index = (y * sample.width + x) * 4;
      const luma = getLuma(data[index], data[index + 1], data[index + 2]);
      lumaTotal += luma;
      lumaSquared += luma * luma;
      pixels += 1;

      if (x > 0 && y > 0) {
        const left = index - 4;
        const top = index - sample.width * 4;
        const leftLuma = getLuma(data[left], data[left + 1], data[left + 2]);
        const topLuma = getLuma(data[top], data[top + 1], data[top + 2]);
        edgeEnergy += Math.abs(luma - leftLuma) + Math.abs(luma - topLuma);
      }
    }
  }

  const luma = lumaTotal / pixels;
  const contrast = Math.sqrt(Math.max(0, lumaSquared / pixels - luma * luma));
  const sharpness = edgeEnergy / pixels;
  return { luma, contrast, sharpness };
}

function buildBrowserSourceQuality() {
  if (!state.image || !state.face) return [];
  const quality = analyzeImageElementQuality(state.image, 180);
  const sourceScale = Math.min(
    state.image.naturalWidth / Math.max(1, state.profile.output.widthPx),
    state.image.naturalHeight / Math.max(1, state.profile.output.heightPx),
  );
  const targetOutputHead = state.profile.output.heightPx * (state.profile.head.targetPercent / 100);
  const faceDetailRatio = state.face.headHeight / Math.max(1, targetOutputHead);
  const roll = Math.abs(state.face.rollDegrees ?? 0);
  const yaw = Math.abs(state.face.yawProxy ?? 0);
  const lightingStatus =
    quality.luma >= 70 && quality.luma <= 220 && quality.contrast >= 24
      ? "pass"
      : quality.luma >= 50 && quality.luma <= 238 && quality.contrast >= 16
        ? "warning"
        : "fail";
  const poseStatus = roll <= 4 && yaw <= 9 ? "pass" : roll <= 7 && yaw <= 14 ? "warning" : "fail";

  return [
    qualityCheck(
      "source_resolution",
      "Source resolution",
      inverseStatus(sourceScale, 1.15, 0.85),
      `${state.image.naturalWidth} x ${state.image.naturalHeight}px`,
      `>= ${state.profile.output.widthPx} x ${state.profile.output.heightPx}px with crop headroom`,
    ),
    qualityCheck(
      "source_face_pixels",
      "Face pixel detail",
      inverseStatus(faceDetailRatio, 0.95, 0.72),
      `${Math.round(state.face.headHeight)} px head / ${faceDetailRatio.toFixed(2)}x target`,
      "native detail before enlargement",
    ),
    qualityCheck("source_focus", "Input focus", inverseStatus(quality.sharpness, 24, 16), quality.sharpness.toFixed(1), "clear facial edges"),
    qualityCheck("source_lighting", "Input lighting", lightingStatus, `L ${quality.luma.toFixed(0)} / C ${quality.contrast.toFixed(0)}`, "even exposure and usable contrast"),
    qualityCheck("source_pose", "Capture pose", poseStatus, `${roll.toFixed(1)} deg tilt / ${yaw.toFixed(1)}% yaw`, "front-facing, level head"),
    qualityCheck("source_background_path", "Background path", state.backgroundReplaced ? "warning" : "review", state.backgroundReplaced ? "waiting for backend mask" : "replacement off", "matte-ready portrait"),
  ];
}

function buildBrowserPipeline() {
  const models = state.modelInventory?.length
    ? state.modelInventory
    : [
        { id: "mediapipe_face_landmarker", label: "MediaPipe Face Landmarker", stage: "geometry", status: "backend", weight: "" },
        { id: "mediapipe_selfie_segmenter", label: "MediaPipe Image Segmenter", stage: "matting", status: "backend", weight: "" },
        { id: "opencv", label: "OpenCV identity clean", stage: "enhancement", status: "backend", weight: "" },
      ];

  return {
    version: "browser-fallback",
    models,
    stages: [
      {
        id: "geometry",
        label: "Geometry",
        engine: "MediaPipe Face Landmarker",
        status: state.image ? getFaceDetectionStatus() : "review",
        detail: state.image ? describeFaceDetection() : "waiting for portrait",
      },
      {
        id: "matting",
        label: "Matting",
        engine: state.backgroundReplaced ? "MediaPipe Image Segmenter" : "disabled",
        status: state.image && state.backgroundReplaced ? "warning" : "review",
        detail: state.image ? (state.backgroundReplaced ? "waiting for backend matte" : "background replacement off") : "waiting for portrait",
      },
      {
        id: "enhancement",
        label: "Enhancement",
        engine: state.enhanceOutput ? state.enhancementMode : "disabled",
        status: state.enhanceOutput ? (state.enhancementMode === "strong" ? "warning" : "pass") : "review",
        detail: state.enhanceOutput
          ? state.enhancementMode === "strong"
            ? "rescue mode, verify likeness"
            : "bounded, identity-faithful cleanup"
          : isValidationOnlyProfile() && !state.previewMode
            ? "disabled by programme policy"
            : "disabled",
      },
      {
        id: "validation",
        label: "Validation",
        engine: "KVNP compliance rules",
        status: state.checks.some((item) => item.status === "fail") ? "fail" : "pass",
        detail: "geometry, background, quality, file, and human-review flags",
      },
    ],
  };
}

function buildBrowserDecision() {
  const allChecks = [...(state.sourceQuality ?? []), ...(state.checks ?? [])];
  const sourceFailures = (state.sourceQuality ?? []).filter((item) => item.status === "fail");
  const failures = allChecks.filter((item) => item.status === "fail");
  const warnings = allChecks.filter((item) => item.status === "warning");
  const reviews = (state.checks ?? []).filter((item) => item.status === "review");
  let status = "ready";
  let title = "Ready for export";
  let message = "Machine checks pass. Human-only requirements still need visual confirmation.";

  if (sourceFailures.length) {
    status = "retake";
    title = "Retake source photo";
    message = "The input does not have enough clean detail for a reliable passport output.";
  } else if (failures.length) {
    status = "fix";
    title = "Fix output before export";
    message = "The generated photo fails at least one machine compliance check.";
  } else if (warnings.length) {
    status = "review";
    title = "Review warnings";
    message = "The output is close, but warnings should be checked before submission.";
  }

  return {
    status,
    title,
    message,
    failures: failures.length,
    warnings: warnings.length,
    reviews: reviews.length,
    actions: getRetakeGuidance(sourceFailures, warnings) ? [getRetakeGuidance(sourceFailures, warnings)] : [],
    pipelineVersion: state.pipeline?.version ?? "browser-fallback",
  };
}

function analyzeImageElementQuality(image, maxSize) {
  const ratio = Math.min(1, maxSize / Math.max(image.naturalWidth, image.naturalHeight));
  const sampleCanvas = document.createElement("canvas");
  sampleCanvas.width = Math.max(1, Math.round(image.naturalWidth * ratio));
  sampleCanvas.height = Math.max(1, Math.round(image.naturalHeight * ratio));
  const sampleCtx = sampleCanvas.getContext("2d");
  sampleCtx.drawImage(image, 0, 0, sampleCanvas.width, sampleCanvas.height);
  const sample = sampleCtx.getImageData(0, 0, sampleCanvas.width, sampleCanvas.height);
  const data = sample.data;
  let lumaTotal = 0;
  let lumaSquared = 0;
  let edgeEnergy = 0;
  let pixels = 0;

  for (let y = 0; y < sample.height; y += 1) {
    for (let x = 0; x < sample.width; x += 1) {
      const index = (y * sample.width + x) * 4;
      const luma = getLuma(data[index], data[index + 1], data[index + 2]);
      lumaTotal += luma;
      lumaSquared += luma * luma;
      pixels += 1;

      if (x > 0 && y > 0) {
        const left = index - 4;
        const top = index - sample.width * 4;
        const leftLuma = getLuma(data[left], data[left + 1], data[left + 2]);
        const topLuma = getLuma(data[top], data[top + 1], data[top + 2]);
        edgeEnergy += Math.abs(luma - leftLuma) + Math.abs(luma - topLuma);
      }
    }
  }

  const luma = lumaTotal / Math.max(1, pixels);
  const contrast = Math.sqrt(Math.max(0, lumaSquared / Math.max(1, pixels) - luma * luma));
  const sharpness = edgeEnergy / Math.max(1, pixels);
  return { luma, contrast, sharpness };
}

function qualityCheck(id, label, status, value, target) {
  return { id, label, status, value: String(value), target: String(target) };
}

function inverseStatus(value, passMin, warningMin) {
  if (value >= passMin) return "pass";
  if (value >= warningMin) return "warning";
  return "fail";
}

function analyzeBackground() {
  const sample = getSampledImageData(180);
  const data = sample.data;
  const edge = Math.max(6, Math.floor(Math.min(sample.width, sample.height) * 0.09));
  const lumas = [];
  const saturations = [];

  for (let y = 0; y < sample.height; y += 1) {
    for (let x = 0; x < sample.width; x += 1) {
      const isEdge = x < edge || y < edge || x > sample.width - edge || y > sample.height - edge;
      if (!isEdge) continue;
      const index = (y * sample.width + x) * 4;
      const r = data[index];
      const g = data[index + 1];
      const b = data[index + 2];
      lumas.push(getLuma(r, g, b));
      saturations.push(getSaturation(r, g, b));
    }
  }

  const avgLuma = mean(lumas);
  const avgSaturation = mean(saturations);
  const spread = stdDev(lumas, avgLuma);
  const { minEdgeLuma, maxEdgeSaturation, maxEdgeSpread } = state.profile.background;
  let status = "pass";

  if (avgLuma < minEdgeLuma || avgSaturation > maxEdgeSaturation || spread > maxEdgeSpread) {
    status = "warning";
  }

  if (avgLuma < minEdgeLuma - 35 || avgSaturation > maxEdgeSaturation + 30 || spread > maxEdgeSpread + 25) {
    status = "fail";
  }

  return {
    status,
    value: `L ${avgLuma.toFixed(0)} / S ${avgSaturation.toFixed(0)} / spread ${spread.toFixed(0)}`,
  };
}

function analyzeFileSize() {
  const { file } = state.profile;
  if (!file.minBytes && !file.maxBytes) return null;
  const bytes = state.exportBlob?.size ?? 0;
  let status = "pass";

  if (file.minBytes && bytes < file.minBytes) status = "warning";
  if (file.maxBytes && bytes > file.maxBytes) status = "fail";

  const target = [
    file.minBytes ? `>= ${formatBytes(file.minBytes)}` : null,
    file.maxBytes ? `<= ${formatBytes(file.maxBytes)}` : null,
  ]
    .filter(Boolean)
    .join(" and ");

  return {
    id: "file_size",
    label: "File size",
    status,
    value: formatBytes(bytes),
    target,
  };
}

function getSampledImageData(maxSize) {
  const width = elements.finalCanvas.width;
  const height = elements.finalCanvas.height;
  const ratio = Math.min(1, maxSize / Math.max(width, height));
  const sampleCanvas = document.createElement("canvas");
  sampleCanvas.width = Math.max(1, Math.round(width * ratio));
  sampleCanvas.height = Math.max(1, Math.round(height * ratio));
  const sampleCtx = sampleCanvas.getContext("2d");
  sampleCtx.drawImage(elements.finalCanvas, 0, 0, sampleCanvas.width, sampleCanvas.height);
  return sampleCtx.getImageData(0, 0, sampleCanvas.width, sampleCanvas.height);
}

async function createExportBlob() {
  const { mime, quality } = state.profile.output;
  const maxBytes = state.profile.automation?.compressionTarget ?? state.profile.file.maxBytes;
  let currentQuality = quality;
  let blob = await canvasToBlob(elements.finalCanvas, mime, currentQuality);

  while (maxBytes && blob.size > maxBytes && currentQuality > 0.58) {
    currentQuality -= 0.06;
    blob = await canvasToBlob(elements.finalCanvas, mime, currentQuality);
  }

  return blob;
}

const REPORT_DISCLAIMER =
  "KVNP Passport Studio is an automated assistant, not a government service. It is " +
  "not affiliated with or endorsed by any passport/visa authority. Machine checks " +
  "estimate likely acceptance and do not guarantee it; some requirements can only be " +
  "confirmed by a human. The final decision rests with the issuing authority.";

function buildReport() {
  return {
    generatedAt: new Date().toISOString(),
    disclaimer: REPORT_DISCLAIMER,
    source: {
      name: state.imageName,
      width: state.image?.naturalWidth ?? null,
      height: state.image?.naturalHeight ?? null,
      type: state.imageMeta?.type ?? null,
      bytes: state.imageMeta?.size ?? null,
    },
    profile: {
      id: state.profile.id,
      label: state.profile.label,
      country: state.profile.country,
      countryName: state.profile.countryName,
      programme: state.profile.programme,
      category: state.profile.category,
      document: state.profile.document,
      delivery: state.profile.delivery,
      lastReviewed: state.profile.lastReviewed,
      requirements: state.profile.requirements,
      sources: state.profile.sources,
      automation: state.profile.automation,
    },
    face: {
      source: state.face?.source ?? null,
      centerX: round(state.face?.centerX),
      centerY: round(state.face?.centerY),
      headHeight: round(state.face?.headHeight),
      faceWidth: round(state.face?.faceWidth),
      faceCount: state.face?.faceCount ?? null,
      rollDegrees: round(state.face?.rollDegrees),
      yawProxy: round(state.face?.yawProxy),
      gazeHorizontalPercent: round(state.face?.gazeHorizontalPercent),
      gazeVerticalPercent: round(state.face?.gazeVerticalPercent),
      gazeOffsetPercent: round(state.face?.gazeOffsetPercent),
      mouthGapPercent: round(state.face?.mouthGapPercent),
      expressionScore: round(state.face?.expressionScore),
    },
    crop: {
      x: round(state.crop?.x),
      y: round(state.crop?.y),
      width: round(state.crop?.width),
      height: round(state.crop?.height),
    },
    output: {
      width: state.profile.output.widthPx,
      height: state.profile.output.heightPx,
      mime: state.profile.output.mime,
      bytes: state.exportBlob?.size ?? null,
      backgroundReplaced: state.effectiveEdits?.background === true,
      backgroundColor: state.backgroundColor,
      enhanced: state.effectiveEdits?.enhance === true,
      enhancementMode: state.enhancementMode,
    },
    effectiveEdits: state.effectiveEdits,
    policyClamped: state.policyClamped,
    sourceQuality: state.sourceQuality,
    decision: state.decision,
    pipeline: state.pipeline,
    corrections: state.manualTouchup
      ? [...(state.corrections ?? []), MANUAL_TOUCHUP_ENTRY]
      : state.corrections,
    manualTouchup: state.manualTouchup === true,
    checks: state.checks,
    humanChecks: (state.checks ?? [])
      .filter((check) => check.status === "review")
      .map((check) => ({
        label: check.label,
        decision:
          state.humanChecks[check.id] === "pass"
            ? "confirmed"
            : state.humanChecks[check.id] === "fail"
            ? "problem"
            : "unconfirmed",
      })),
  };
}

function renderMeasurements() {
  const headPercent = getHeadPercent();
  const headMm = state.profile.output.printHeightMm ? (headPercent / 100) * state.profile.output.printHeightMm : null;
  const source = describeMeasurementSource();
  const rows = [
    ["Face source", source],
    ["Head in frame", headMm ? `${headMm.toFixed(1)}mm / ${headPercent.toFixed(1)}%` : `${headPercent.toFixed(1)}%`],
    ["Top margin", `${getTopMarginPercent().toFixed(1)}%`],
    ["Shoulder room", `${getShoulderRoomPercent().toFixed(1)}% below chin`],
    ["Pose", describePoseMeasurement()],
    ["Background", describeBackgroundCleanup()],
    ["Input quality", describeQualitySummary()],
    ["Export file", state.exportBlob ? formatBytes(state.exportBlob.size) : "Pending"],
  ];

  elements.measurements.innerHTML = rows
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderSourceQuality() {
  if (!elements.sourceQualityList || !elements.retakeGuidance) return;

  const quality = state.sourceQuality ?? [];
  elements.sourceQualityList.innerHTML = "";
  if (elements.reviewSourceQualityList) elements.reviewSourceQualityList.innerHTML = "";

  if (!state.image) {
    elements.retakeGuidance.textContent = "Load a portrait to see whether the source is strong enough.";
    return;
  }

  if (!quality.length) {
    elements.retakeGuidance.textContent = "Waiting for Python quality analysis.";
    return;
  }

  const fails = quality.filter((item) => item.status === "fail");
  const warnings = quality.filter((item) => item.status === "warning");
  elements.retakeGuidance.textContent = getRetakeGuidance(fails, warnings);

  for (const item of quality) {
    const row = document.createElement("article");
    row.className = `quality-row ${item.status}`;
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.value)} / ${escapeHtml(item.target)}</span>
      </div>
      <span class="status-pill">${escapeHtml(item.status)}</span>
    `;
    elements.sourceQualityList.append(row);
    if (elements.reviewSourceQualityList) elements.reviewSourceQualityList.append(row.cloneNode(true));
  }
}

function getRetakeGuidance(fails, warnings) {
  const postureItems = [...fails, ...warnings].filter((item) =>
    ["source_head_pitch", "source_shoulder_level", "source_body_alignment"].includes(item.id),
  );
  if (postureItems.length) {
    const instructions = [];
    if (postureItems.some((item) => item.id === "source_head_pitch")) {
      instructions.push("put the lens at eye level and keep your chin neutral");
    }
    if (postureItems.some((item) => item.id === "source_shoulder_level")) {
      instructions.push("sit upright with both shoulders level and arms relaxed");
    }
    if (postureItems.some((item) => item.id === "source_body_alignment")) {
      instructions.push("center your head over your shoulders without leaning");
    }
    return `${fails.length ? "Retake recommended" : "Improve the pose"}: ${instructions.join("; ")}.`;
  }
  if (fails.some((item) => item.id === "source_face_pixels" || item.id === "source_focus")) {
    return "Retake closer to the camera with brighter light. The current face detail is too weak to rescue cleanly.";
  }
  if (fails.some((item) => item.id === "source_noise" || item.id === "source_lighting")) {
    return "Retake in brighter, even light. Enhancement can clean small issues, but this source will still look artificial.";
  }
  if (fails.length) {
    return "Retake recommended before export. The current source fails at least one capture-quality gate.";
  }
  if (warnings.length) {
    return "Usable with review. A better-lit, sharper source will produce a safer passport photo.";
  }
  return "Source is suitable for automated passport production.";
}

function describeQualitySummary() {
  const quality = state.sourceQuality ?? [];
  if (!quality.length) return "Pending";
  const fails = quality.filter((item) => item.status === "fail").length;
  const warnings = quality.filter((item) => item.status === "warning").length;
  if (fails) return `${fails} fail / retake`;
  if (warnings) return `${warnings} warning`;
  return "Ready";
}

function renderPipeline() {
  if (!elements.pipelineReport) return;
  const pipeline = state.pipeline ?? buildBrowserPipeline();
  const stages = pipeline.stages ?? [];
  elements.pipelineReport.innerHTML = "";

  for (const stage of stages) {
    const row = document.createElement("div");
    row.className = `pipeline-row ${stage.status ?? "review"}`;
    row.innerHTML = `
      <span>${escapeHtml(stage.label)}</span>
      <strong>${escapeHtml(stage.engine ?? "pending")}</strong>
      <small>${escapeHtml(stage.detail ?? "")}</small>
    `;
    elements.pipelineReport.append(row);
  }

  const modelRows = (pipeline.models ?? state.modelInventory ?? []).slice(0, 6);
  if (modelRows.length) {
    const models = document.createElement("div");
    models.className = "model-inventory";
    models.innerHTML = modelRows
      .map(
        (model) =>
          `<span class="${escapeHtml(model.status ?? "review")}">${escapeHtml(model.label)} <b>${escapeHtml(
            model.status ?? "unknown",
          )}</b></span>`,
      )
      .join("");
    elements.pipelineReport.append(models);
  }
}

function renderDecision() {
  if (!elements.decisionCard) return;
  const decision = state.decision ?? (state.image ? buildBrowserDecision() : null);
  renderWorkflowProgress();

  if (!decision) {
    elements.decisionCard.className = "decision-card pending";
    elements.decisionCard.innerHTML = "<strong>Waiting for image</strong><span>Load a portrait to generate a decision.</span>";
    return;
  }

  const { failCount, warningCount, unresolvedReviews } = computeLiveCounts();
  const ready = failCount === 0 && unresolvedReviews === 0 && warningCount === 0;
  const cardStatus = ready ? "ready" : decision.status;
  const title = ready ? "Ready to export" : decision.title;
  const message = ready
    ? "All machine checks pass and every human check is confirmed."
    : decision.message;
  const actions = ready
    ? ""
    : (decision.actions ?? []).map((action) => `<li>${escapeHtml(action)}</li>`).join("");

  elements.decisionCard.className = `decision-card ${escapeHtml(cardStatus)}`;
  elements.decisionCard.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <span>${escapeHtml(message)}</span>
    <small>${failCount} fail / ${warningCount} warning / ${unresolvedReviews} review</small>
    ${actions ? `<ul>${actions}</ul>` : ""}
  `;
}

const MANUAL_TOUCHUP_ENTRY = {
  id: "manual_touchup",
  label: "Manual background touch-up (operator)",
  detail: "Operator painted the background after automated processing; verify the face was not touched.",
};

function renderCorrections() {
  if (!elements.correctionsCard) return;
  const corrections = [...(state.corrections ?? [])];
  if (state.manualTouchup) corrections.push(MANUAL_TOUCHUP_ENTRY);

  if (!state.image) {
    elements.correctionsCard.hidden = true;
    elements.correctionsCard.innerHTML = "";
    return;
  }

  const effective = state.effectiveEdits ?? {};
  const audit = [
    {
      kind: "measured",
      label: "Face, gaze and framing",
      detail: "landmarks, eye direction, head level, crop and shoulder room measured; source pixels unchanged",
    },
    {
      kind: "measured",
      label: "Background and image quality",
      detail: "background uniformity, focus, grain, lighting and contrast measured; source pixels unchanged",
    },
    {
      kind: "formatted",
      label: "Programme output",
      detail: `cropped and resized to ${state.profile.output.widthPx} x ${state.profile.output.heightPx}px; face shape unchanged`,
    },
  ];

  for (const item of corrections) {
    audit.push({
      kind: "changed",
      label: item.label ?? item.id ?? "Correction",
      detail: item.detail ?? "pixel change applied",
    });
  }
  if (effective.background && !corrections.some((item) => item.id === "background")) {
    audit.push({
      kind: "changed",
      label: "Background replacement",
      detail: `person matte composited onto ${state.backgroundColor}; editing-preview watermark applied`,
    });
  }
  if (effective.enhance && !corrections.some((item) => item.id === "enhance")) {
    audit.push({
      kind: "changed",
      label: "Photo enhancement",
      detail: `${state.enhancementMode} identity-preserving cleanup applied`,
    });
  }
  const activeAdjustments = Object.entries(state.adjust ?? {}).filter(([, value]) => Number(value) !== 0);
  if (activeAdjustments.length) {
    audit.push({
      kind: "changed",
      label: "Browser image adjustments",
      detail: activeAdjustments.map(([key, value]) => `${titleCase(key)} ${Number(value) > 0 ? "+" : ""}${value}`).join(", "),
    });
  }

  const changedCount = audit.filter((item) => item.kind === "changed").length;
  if (!changedCount) {
    audit.push({
      kind: "unchanged",
      label: "No retouching applied",
      detail: "only output crop, sizing and encoding were produced",
    });
  }

  const unavailable = Object.keys(EDIT_LABELS).filter((key) => state.profile.allowedEdits?.[key] === false);
  if (unavailable.length) {
    audit.push({
      kind: "blocked",
      label: `Unavailable in ${state.profile.countryName} submission mode`,
      detail: unavailable.map((key) => EDIT_LABELS[key] ?? key).join(", "),
    });
  }

  const humanCount = (state.checks ?? []).filter((item) => item.status === "review").length;
  if (humanCount) {
    audit.push({
      kind: "human",
      label: `${humanCount} human confirmation${humanCount === 1 ? "" : "s"}`,
      detail: "not claimed as computer-verified; confirm in the compliance list",
    });
  }

  const items = audit
    .map(
      (item) => `
        <li class="audit-item ${escapeHtml(item.kind)}">
          <b class="audit-badge">${escapeHtml(item.kind)}</b>
          <div><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.detail)}</span></div>
        </li>`,
    )
    .join("");
  elements.correctionsCard.hidden = false;
  elements.correctionsCard.className = "corrections-card audit-card";
  elements.correctionsCard.innerHTML = `
    <div class="corrections-head">
      <strong>Processing audit</strong>
      <span>${changedCount} pixel edit${changedCount === 1 ? "" : "s"}</span>
    </div>
    <ul>${items}</ul>
    <small>Measured means software analysis only. Formatted means crop, size or encoding. Changed means pixels were modified. Blocked means the selected submission policy prevented that tool.</small>
  `;
}

const SCAN_PERIOD_MS = 1700;

function startScanAnimation() {
  // The camera preview owns the source canvas while live; don't fight it.
  if (!state.image || state.cameraStream) return;
  state.processing = true;
  renderWorkflowProgress();
  cancelAnimationFrame(scanRAF);
  scanRAF = requestAnimationFrame(drawScanFrame);
}

function stopScanAnimation() {
  state.processing = false;
  renderWorkflowProgress();
  cancelAnimationFrame(scanRAF);
  scanRAF = 0;
}

function drawScanFrame(timestamp) {
  if (!state.processing || !state.image) return;

  const canvas = elements.sourceCanvas;
  const fit = getContainFit(state.image.naturalWidth, state.image.naturalHeight, canvas.width, canvas.height);

  sourceCtx.clearRect(0, 0, canvas.width, canvas.height);
  sourceCtx.fillStyle = "#070b11";
  sourceCtx.fillRect(0, 0, canvas.width, canvas.height);
  sourceCtx.drawImage(state.image, fit.x, fit.y, fit.width, fit.height);

  // Dim the frame so the scanning band reads clearly.
  sourceCtx.fillStyle = "rgba(7, 11, 17, 0.34)";
  sourceCtx.fillRect(fit.x, fit.y, fit.width, fit.height);

  const phase = ((timestamp % SCAN_PERIOD_MS) / SCAN_PERIOD_MS);
  const scanY = fit.y + phase * fit.height;
  const bandHeight = Math.max(36, fit.height * 0.12);

  const gradient = sourceCtx.createLinearGradient(0, scanY - bandHeight, 0, scanY + bandHeight);
  gradient.addColorStop(0, "rgba(47, 184, 255, 0)");
  gradient.addColorStop(0.5, "rgba(47, 184, 255, 0.28)");
  gradient.addColorStop(1, "rgba(47, 184, 255, 0)");
  sourceCtx.fillStyle = gradient;
  sourceCtx.fillRect(fit.x, scanY - bandHeight, fit.width, bandHeight * 2);

  sourceCtx.strokeStyle = "rgba(120, 220, 255, 0.85)";
  sourceCtx.lineWidth = 2;
  sourceCtx.beginPath();
  sourceCtx.moveTo(fit.x, scanY);
  sourceCtx.lineTo(fit.x + fit.width, scanY);
  sourceCtx.stroke();

  drawScanReticle(fit, timestamp);

  sourceCtx.fillStyle = "#cfe9ff";
  sourceCtx.font = "700 15px Inter, Segoe UI, sans-serif";
  sourceCtx.textAlign = "center";
  sourceCtx.fillText("Analyzing and auto-correcting...", canvas.width / 2, fit.y + fit.height - 18);

  scanRAF = requestAnimationFrame(drawScanFrame);
}

function drawScanReticle(fit, timestamp) {
  const face = state.face;
  let cx = fit.x + fit.width / 2;
  let cy = fit.y + fit.height * 0.42;
  let size = Math.min(fit.width, fit.height) * 0.34;

  if (face && state.image) {
    const scaleX = fit.width / state.image.naturalWidth;
    const scaleY = fit.height / state.image.naturalHeight;
    cx = fit.x + face.centerX * scaleX;
    cy = fit.y + face.centerY * scaleY;
    size = (face.headHeight ?? size) * scaleY * 0.62;
  }

  const pulse = 0.5 + 0.5 * Math.sin(timestamp / 320);
  const half = size * (1 + pulse * 0.04);
  const corner = Math.max(14, size * 0.26);
  sourceCtx.strokeStyle = `rgba(48, 211, 139, ${0.55 + pulse * 0.4})`;
  sourceCtx.lineWidth = 3;

  const left = cx - half;
  const right = cx + half;
  const top = cy - half;
  const bottom = cy + half;
  const brackets = [
    [left, top, 1, 1],
    [right, top, -1, 1],
    [left, bottom, 1, -1],
    [right, bottom, -1, -1],
  ];
  for (const [x, y, dx, dy] of brackets) {
    sourceCtx.beginPath();
    sourceCtx.moveTo(x + dx * corner, y);
    sourceCtx.lineTo(x, y);
    sourceCtx.lineTo(x, y + dy * corner);
    sourceCtx.stroke();
  }
}

function describeMeasurementSource() {
  const source = state.face?.source ?? "";
  if (source === "python-mediapipe-facemesh") return "Python FaceMesh";
  if (source === "python-mediapipe-manual-override") return "Python adjusted";
  if (source === "python-mediapipe-adjusted") return "Python adjusted";
  if (source === "mediapipe-face-landmarks") return "Browser landmarks";
  if (source === "mediapipe-adjusted") return "Browser adjusted";
  if (source === "native-face-detector") return "Native detector";
  return "Manual fallback";
}

function describePoseMeasurement() {
  if (!state.face?.source?.includes("mediapipe")) return "Review manually";
  return `${Math.abs(state.face.rollDegrees ?? 0).toFixed(1)} deg tilt / ${Math.abs(state.face.yawProxy ?? 0).toFixed(
    1,
  )}% yaw`;
}

// A human-review check keeps its "review" status until the operator confirms (pass)
// or flags (fail) it. Its effective status is the operator's decision, if any.
function effectiveStatus(check) {
  return check.status === "review" && state.humanChecks[check.id]
    ? state.humanChecks[check.id]
    : check.status;
}

// Live tallies across source-quality + machine checks, honouring operator decisions,
// so renderChecks and renderDecision always agree on the numbers.
function computeLiveCounts() {
  const allMachineChecks = [...(state.sourceQuality ?? []), ...state.checks];
  const failCount = allMachineChecks.filter((check) => effectiveStatus(check) === "fail").length;
  const warningCount = allMachineChecks.filter((check) => effectiveStatus(check) === "warning").length;
  const unresolvedReviews = state.checks.filter(
    (check) => check.status === "review" && !state.humanChecks[check.id],
  ).length;
  return { failCount, warningCount, unresolvedReviews };
}

// Delegated handler for the tick/cross/reset controls on human-review rows.
function handleHumanCheckClick(event) {
  const passBtn = event.target.closest("[data-hc-pass]");
  const failBtn = event.target.closest("[data-hc-fail]");
  const resetBtn = event.target.closest("[data-hc-reset]");
  if (passBtn) {
    state.humanChecks[passBtn.dataset.hcPass] = "pass";
  } else if (failBtn) {
    state.humanChecks[failBtn.dataset.hcFail] = "fail";
  } else if (resetBtn) {
    delete state.humanChecks[resetBtn.dataset.hcReset];
  } else {
    return;
  }
  state.downloadAcknowledged = false;
  renderChecks();
  renderDecision();
}

function getDownloadIssues() {
  const issues = [];
  const seen = new Set();
  const allChecks = [...(state.sourceQuality ?? []), ...(state.checks ?? [])];

  for (const check of allChecks) {
    const status = effectiveStatus(check);
    if (!["fail", "warning", "review"].includes(status)) continue;
    const key = check.id || `${check.label}-${status}`;
    if (seen.has(key)) continue;
    seen.add(key);
    issues.push({
      status,
      label: check.label || "Photo check",
      detail: check.value || check.target || "Review before submission",
    });
  }

  if (state.processingError && !issues.some((issue) => issue.detail === state.processingError)) {
    issues.unshift({ status: "fail", label: "Photo preparation", detail: state.processingError });
  }
  return issues;
}

function renderChecks() {
  const { failCount, warningCount, unresolvedReviews } = computeLiveCounts();
  renderWorkflowProgress();
  const status = failCount
    ? "Needs retake"
    : unresolvedReviews
    ? "Confirm human checks"
    : warningCount
    ? "Check warnings"
    : "Looks ready";
  const className = failCount ? "fail" : unresolvedReviews ? "review" : warningCount ? "warning" : "pass";

  elements.resultSummary.textContent = `${state.profile.label} / ${state.profile.output.widthPx} x ${state.profile.output.heightPx}px${state.previewMode ? " / editing preview" : ""}`;
  elements.overallStatus.textContent = unresolvedReviews ? `${status} / ${unresolvedReviews} to confirm` : `${status}`;
  elements.overallStatus.className = `overall-status ${className}`;
  const preparedAvailable = Boolean(state.exportBlob && state.processedImage);
  const downloadIssues = getDownloadIssues();
  elements.downloadOriginal.disabled = !state.originalFile;
  elements.downloadPhoto.disabled = !preparedAvailable;
  elements.downloadPhoto.textContent = downloadIssues.length ? "Download with warnings" : "Download file";
  elements.printSheet.disabled = !preparedAvailable;
  elements.sheetSize.disabled = !preparedAvailable;
  elements.sheetDpi.disabled = !preparedAvailable;
  elements.sheetCopies.disabled = !preparedAvailable;
  // Touch-up needs a generated photo with a clean-background pass available.
  const hasPhoto = Boolean(state.processedImage && state.backendResult?.ok);
  const touchupBanned = state.profile?.allowedEdits?.background === false && !state.previewMode;
  elements.touchupToggle.disabled = !hasPhoto || touchupBanned;
  applyTouchupGate();
  elements.toggleGuides.disabled = !hasPhoto;
  elements.zoomIn.disabled = !hasPhoto;
  elements.zoomOut.disabled = !hasPhoto;
  elements.viewCompare.disabled = !(hasPhoto && state.beforeDataUrl);
  elements.downloadReport.disabled = !state.lastReport;
  renderBackgroundVariantControl();
  updateDownloadAdvisory(downloadIssues);
  updateReviewPreview();
  elements.checksList.innerHTML = "";

  for (const check of state.checks) {
    const row = document.createElement("article");
    const info = `
      <div>
        <strong>${escapeHtml(check.label)}</strong>
        <span>${escapeHtml(check.value)} / ${escapeHtml(check.target)}</span>
      </div>`;

    if (check.status === "review") {
      const decided = state.humanChecks[check.id];
      const eff = effectiveStatus(check);
      row.className = `check-row ${decided ? eff : "review"}`;
      const control = decided
        ? `<div class="human-confirm">
             <span class="status-pill">${escapeHtml(eff)}</span>
             <button class="hc-reset" type="button" data-hc-reset="${escapeHtml(check.id)}" title="Change" aria-label="Change decision for ${escapeHtml(check.label)}">↺</button>
           </div>`
        : `<div class="human-confirm">
             <button class="hc-btn hc-pass" type="button" data-hc-pass="${escapeHtml(check.id)}" title="Confirm OK" aria-label="Confirm ${escapeHtml(check.label)} is OK">✓</button>
             <button class="hc-btn hc-fail" type="button" data-hc-fail="${escapeHtml(check.id)}" title="Mark problem" aria-label="Mark ${escapeHtml(check.label)} as a problem">✗</button>
           </div>`;
      row.innerHTML = `${info}${control}`;
    } else {
      row.className = `check-row ${check.status}`;
      row.innerHTML = `${info}
      <span class="status-pill">${escapeHtml(check.status)}</span>
    `;
    }
    elements.checksList.append(row);
  }
}

function renderNoResult() {
  finalCtx.clearRect(0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  finalCtx.fillStyle = "#f8fafc";
  finalCtx.fillRect(0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  elements.resultSummary.textContent = "Waiting for an image.";
  elements.overallStatus.textContent = "Pending";
  elements.overallStatus.className = "overall-status pending";
  elements.checksList.innerHTML = "";
  state.sourceQuality = [];
  state.decision = null;
  state.pipeline = null;
  state.corrections = [];
  state.effectiveEdits = {};
  renderSourceQuality();
  renderDecision();
  renderPipeline();
  renderCorrections();
  elements.compare.hidden = true;
  elements.finalCanvas.hidden = false;
  elements.downloadOriginal.disabled = !state.originalFile;
  elements.downloadPhoto.disabled = true;
  elements.printSheet.disabled = true;
  elements.sheetSize.disabled = true;
  elements.sheetDpi.disabled = true;
  elements.sheetCopies.disabled = true;
  elements.downloadReport.disabled = true;
  renderBackgroundVariantControl();
  updateDownloadAdvisory();
  updateReviewPreview();
  renderWorkflowProgress();
}

function setReviewPreview(mode) {
  const next = ["photo", "document", "print"].includes(mode) ? mode : "photo";
  state.reviewPreviewMode = next;
  for (const tab of elements.reviewPreviewTabs) {
    const active = tab.dataset.reviewPreview === next;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const view of elements.reviewPreviewViews) {
    const active = view.dataset.reviewPreviewView === next;
    view.hidden = !active;
    view.classList.toggle("is-active", active);
  }
}

function updateReviewPreview() {
  if (state.reviewPreviewUrl) {
    URL.revokeObjectURL(state.reviewPreviewUrl);
    state.reviewPreviewUrl = null;
  }

  const blob = state.exportBlob;
  const targets = [elements.reviewPhotoImage, elements.documentPreviewPhoto, ...elements.printPreviewCopies];
  if (!blob) {
    for (const image of targets) {
      image.removeAttribute("src");
      image.hidden = true;
    }
    elements.reviewPhotoImage?.parentElement?.classList.add("is-empty");
    return;
  }

  state.reviewPreviewUrl = URL.createObjectURL(blob);
  for (const image of targets) {
    image.src = state.reviewPreviewUrl;
    image.hidden = false;
  }
  elements.reviewPhotoImage?.parentElement?.classList.remove("is-empty");
}

function updateDownloadAdvisory(issues = getDownloadIssues()) {
  if (!elements.downloadAdvisory) return;
  const strong = elements.downloadAdvisory.querySelector("strong");
  const detail = elements.downloadAdvisory.querySelector("span");
  let status = "pending";

  if (state.processing) {
    strong.textContent = "Preparing your photo";
    detail.textContent = "The original is already available. The prepared file will appear when analysis finishes.";
  } else if (!state.exportBlob) {
    status = state.originalFile ? "warning" : "pending";
    strong.textContent = state.originalFile ? "Prepared file unavailable" : "No prepared file yet";
    detail.textContent = state.originalFile
      ? "Download the original now or return to the photo step and try another image."
      : "Your original remains available after upload, even when preparation cannot finish.";
  } else if (issues.length) {
    status = "warning";
    strong.textContent = `${issues.length} issue${issues.length === 1 ? "" : "s"} to review`;
    detail.textContent = "A retake is recommended, but you can acknowledge the findings and download this file.";
  } else {
    status = "ready";
    strong.textContent = "Prepared file ready";
    detail.textContent = "No automated failure or warning is currently blocking the recommendation.";
  }

  elements.downloadAdvisory.className = `download-advisory ${status}`;
}

function resetDownloadWarningDialog() {
  elements.downloadWarningAck.checked = false;
  elements.downloadAnywayConfirm.disabled = true;
}

function showDownloadWarningDialog(issues) {
  elements.downloadWarningList.innerHTML = issues
    .map(
      (issue) =>
        `<li class="${escapeHtml(issue.status)}"><strong>${escapeHtml(issue.label)}</strong><span>${escapeHtml(
          issue.detail,
        )}</span></li>`,
    )
    .join("");
  resetDownloadWarningDialog();

  if (typeof elements.downloadWarningDialog.showModal === "function") {
    elements.downloadWarningDialog.showModal();
    return;
  }
  if (window.confirm("This photo has unresolved warnings. Download it anyway?")) {
    state.downloadAcknowledged = true;
    performPhotoDownload();
  }
}

async function toggleCamera() {
  if (state.cameraStream) {
    stopCamera();
    return;
  }

  // Re-entry guard: ignore rapid clicks while getUserMedia is still pending, so
  // two camera streams / RAF loops cannot stack on the same canvas.
  if (state.cameraStarting) return;
  state.cameraStarting = true;

  try {
    state.cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
      audio: false,
    });
    // A new image may have loaded while we awaited permission; abandon the stream.
    elements.cameraFeed.srcObject = state.cameraStream;
    await elements.cameraFeed.play();
    elements.cameraFeed.hidden = false;
    elements.emptyState.hidden = true;
    elements.captureButton.disabled = false;
    elements.cameraButton.textContent = "Stop";
    stopScanAnimation();
    cancelAnimationFrame(cameraRAF);
    state.coach.metrics = null;
    state.coach.captured = false;
    state.coach.readySince = 0;
    initCoach(); // lazy-load the live face model in the background
    renderCameraFrame();
  } catch (error) {
    elements.sourceMeta.textContent = "Camera unavailable";
    console.error(error);
  } finally {
    state.cameraStarting = false;
  }
}

function stopCamera() {
  cancelAnimationFrame(cameraRAF);
  cameraRAF = 0;
  state.coach.metrics = null;
  for (const track of state.cameraStream?.getTracks() ?? []) {
    track.stop();
  }
  state.cameraStream = null;
  elements.cameraFeed.hidden = true;
  elements.captureButton.disabled = true;
  elements.cameraButton.textContent = "Camera";
}

function renderCameraFrame() {
  if (!state.cameraStream) return;
  const canvas = elements.sourceCanvas;
  const video = elements.cameraFeed;
  const videoWidth = video.videoWidth || 1280;
  const videoHeight = video.videoHeight || 720;
  const fit = getContainFit(videoWidth, videoHeight, canvas.width, canvas.height);
  sourceCtx.clearRect(0, 0, canvas.width, canvas.height);
  sourceCtx.fillStyle = "#0d0e10";
  sourceCtx.fillRect(0, 0, canvas.width, canvas.height);
  // MIRRORED preview (what people expect from a selfie camera). The saved
  // photo is captured unmirrored, as passport photos must be.
  sourceCtx.save();
  sourceCtx.translate(fit.x + fit.width, fit.y);
  sourceCtx.scale(-1, 1);
  sourceCtx.drawImage(video, 0, 0, fit.width, fit.height);
  sourceCtx.restore();

  const now = performance.now();
  if (coachAvailable() && now - state.coach.lastAnalyze > 90) {
    state.coach.lastAnalyze = now;
    const metrics = analyzeFrame(video, now, {
      targetPercent: state.profile?.head?.targetPercent ?? 62,
      programme: state.profile?.label ?? "",
    });
    if (metrics) {
      if (metrics.present && metrics.faceBox) appendLightingFactors(metrics, fit);
      state.coach.metrics = metrics;
    }
  }
  if (state.coach.metrics) drawCoachOverlay(fit, state.coach.metrics, now);

  cameraRAF = requestAnimationFrame(renderCameraFrame);
}

// Map a normalized video x to display x (preview is mirrored).
function mirrorX(fit, nx) {
  return fit.x + (1 - nx) * fit.width;
}

function appendLightingFactors(metrics, fit) {
  // Sample the face region straight off the just-drawn (mirrored) preview and
  // judge brightness + evenness - lighting faults governments reject and that
  // MUST be fixed at capture (lamp/window), not in software.
  try {
    const box = metrics.faceBox;
    const bx = mirrorX(fit, box.x + box.w); // mirrored left edge
    const by = fit.y + box.y * fit.height;
    const bw = Math.max(8, box.w * fit.width);
    const bh = Math.max(8, box.h * fit.height);
    const img = sourceCtx.getImageData(Math.round(bx), Math.round(by), Math.round(bw), Math.round(bh));
    const data = img.data;
    let left = 0, right = 0, nL = 0, nR = 0;
    const w = img.width;
    for (let y = 0; y < img.height; y += 3) {
      for (let x = 0; x < w; x += 3) {
        const i = (y * w + x) * 4;
        const luma = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
        if (x < w / 2) { left += luma; nL += 1; } else { right += luma; nR += 1; }
      }
    }
    const lMean = left / Math.max(1, nL);
    const rMean = right / Math.max(1, nR);
    const mean = (lMean + rMean) / 2;
    const dark = mean < 70;
    const uneven = Math.abs(lMean - rMean) > 34;
    metrics.factors.push({ id: "light", label: "Bright enough", weight: 0, s: dark ? 0 : 1, ok: !dark, hint: "Too dark — face a window or add light" });
    metrics.factors.push({ id: "even", label: "Even light", weight: 0, s: uneven ? 0 : 1, ok: !uneven, hint: "Uneven light — turn toward the light source" });
    if (dark) metrics.score = Math.max(0, metrics.score - 14);
    if (uneven) metrics.score = Math.max(0, metrics.score - 9);
    if (metrics.score < 88) {
      metrics.ready = false;
      if (dark) metrics.instruction = "Too dark — face a window or add light";
      else if (uneven && metrics.instruction === "Hold still…") metrics.instruction = "Uneven light — turn toward the light source";
    }
  } catch (error) {
    /* getImageData can fail on tainted canvas; lighting factors just skip */
  }
}

function drawCoachOverlay(fit, metrics, now) {
  const ctx = sourceCtx;
  const target = metrics.target;
  const cx = fit.x + target.cx * fit.width; // target is centered: mirror-safe
  const cy = fit.y + target.cy * fit.height;
  const rx = target.halfW * fit.width;
  const ry = target.halfH * fit.height;
  const ready = metrics.ready;
  const stateColor = ready ? "#41d97d" : metrics.present ? "#f0b429" : "#8f8c84";

  // programme-specific target oval (sized from the selected country's head rule)
  ctx.save();
  ctx.setLineDash([10, 8]);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = stateColor;
  ctx.globalAlpha = 0.9;
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();

  // Show the measured geometry as well as the target oval. The eye line makes
  // roll immediately understandable; the head axis makes a tilted pose obvious.
  if (metrics.present && metrics.eyeLine && metrics.headAxis) {
    const level = metrics.factors?.find((factor) => factor.id === "level");
    const levelColor = (level?.s ?? 0) >= 0.75 ? "#41d97d" : (level?.s ?? 0) >= 0.4 ? "#f0b429" : "#e8442e";
    const eyeLeft = {
      x: mirrorX(fit, metrics.eyeLine.left.x),
      y: fit.y + metrics.eyeLine.left.y * fit.height,
    };
    const eyeRight = {
      x: mirrorX(fit, metrics.eyeLine.right.x),
      y: fit.y + metrics.eyeLine.right.y * fit.height,
    };
    const axisTop = {
      x: mirrorX(fit, metrics.headAxis.top.x),
      y: fit.y + metrics.headAxis.top.y * fit.height,
    };
    const axisBottom = {
      x: mirrorX(fit, metrics.headAxis.bottom.x),
      y: fit.y + metrics.headAxis.bottom.y * fit.height,
    };
    ctx.save();
    ctx.setLineDash([]);
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = levelColor;
    ctx.beginPath();
    ctx.moveTo(eyeLeft.x, eyeLeft.y);
    ctx.lineTo(eyeRight.x, eyeRight.y);
    ctx.moveTo(axisTop.x, axisTop.y);
    ctx.lineTo(axisBottom.x, axisBottom.y);
    ctx.stroke();
    ctx.fillStyle = levelColor;
    for (const point of [eyeLeft, eyeRight]) {
      ctx.beginPath();
      ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.font = "600 9px 'KVNP Mono', Consolas, monospace";
    ctx.textAlign = "center";
    ctx.fillText("EYE LINE / HEAD LEVEL", (eyeLeft.x + eyeRight.x) / 2, Math.min(eyeLeft.y, eyeRight.y) - 10);
    ctx.restore();
  }

  // factor meters (left column): label + mini bar, coloured by score
  if (metrics.factors?.length) {
    ctx.save();
    ctx.font = "600 11px 'KVNP Mono', Consolas, monospace";
    ctx.textAlign = "left";
    const px = fit.x + 14;
    let py = fit.y + 24;
    for (const f of metrics.factors) {
      const col = f.s >= 0.75 ? "#41d97d" : f.s >= 0.4 ? "#f0b429" : "#e8442e";
      ctx.fillStyle = "rgba(11,11,12,0.65)";
      ctx.fillRect(px - 6, py - 12, 150, 18);
      ctx.fillStyle = "rgba(236,233,226,0.92)";
      ctx.fillText(f.label.toUpperCase(), px, py);
      ctx.fillStyle = "rgba(255,255,255,0.16)";
      ctx.fillRect(px + 96, py - 8, 42, 5);
      ctx.fillStyle = col;
      ctx.fillRect(px + 96, py - 8, Math.max(2, 42 * f.s), 5);
      py += 21;
    }
    ctx.restore();
  }

  // CAPTURE SCORE (top-right, big mono)
  ctx.save();
  ctx.textAlign = "right";
  const sx = fit.x + fit.width - 16;
  ctx.fillStyle = "rgba(11,11,12,0.65)";
  ctx.fillRect(sx - 96, fit.y + 10, 96 + 6, 56);
  ctx.font = "600 30px 'KVNP Mono', Consolas, monospace";
  ctx.fillStyle = stateColor;
  ctx.fillText(String(metrics.score ?? 0), sx, fit.y + 44);
  ctx.font = "600 9px 'KVNP Mono', Consolas, monospace";
  ctx.fillStyle = "rgba(236,233,226,0.75)";
  ctx.fillText("CAPTURE SCORE / 100", sx, fit.y + 58);
  ctx.restore();

  // direction arrow for the dominant angle error (display space = mirror-safe:
  // the user simply moves the way the arrow points)
  if (metrics.arrow && metrics.present) {
    drawCoachArrow(ctx, fit, metrics, cx, cy, rx, ry);
  }

  // instruction banner
  ctx.save();
  ctx.textAlign = "center";
  const bannerY = fit.y + fit.height - 44;
  ctx.fillStyle = "rgba(11, 11, 12, 0.72)";
  ctx.fillRect(fit.x, bannerY - 20, fit.width, 42);
  ctx.fillStyle = ready ? "#41d97d" : "#ece9e2";
  ctx.font = "700 17px 'Space Grotesk', sans-serif";
  ctx.fillText(metrics.instruction, fit.x + fit.width / 2, bannerY + 7);
  ctx.font = "600 8.5px 'KVNP Mono', Consolas, monospace";
  ctx.fillStyle = "rgba(143,140,132,0.9)";
  ctx.fillText("PREVIEW MIRRORED — SAVED PHOTO IS TRUE ORIENTATION", fit.x + fit.width / 2, bannerY + 19);
  ctx.restore();

  // best-moment auto-capture: score must stay >= 88 for 800ms
  if (ready && state.coach.autoCapture && !state.coach.captured) {
    if (!state.coach.readySince) state.coach.readySince = now;
    const held = now - state.coach.readySince;
    ctx.save();
    ctx.strokeStyle = "#41d97d";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx, cy - ry - 26, 14, -Math.PI / 2, -Math.PI / 2 + (held / 800) * Math.PI * 2);
    ctx.stroke();
    ctx.restore();
    if (held >= 800) {
      state.coach.captured = true;
      captureCameraFrame();
    }
  } else if (!ready) {
    state.coach.readySince = 0;
  }
}

function drawCoachArrow(ctx, fit, metrics, cx, cy, rx, ry) {
  const face = metrics.headCenter ?? { x: 0.5, y: 0.42 };
  const fx = mirrorX(fit, face.x);
  const fy = fit.y + face.y * fit.height;
  ctx.save();
  ctx.strokeStyle = "#e8442e";
  ctx.fillStyle = "#e8442e";
  ctx.lineWidth = 3.5;
  const a = metrics.arrow;
  if (a.kind === "turn") {
    // horizontal arrow beside the head; mirrored display flips the sign
    const dir = -a.dir;
    const y = fy;
    const x1 = fx + dir * rx * 0.55;
    const x2 = fx + dir * (rx * 0.55 + 46);
    ctx.beginPath(); ctx.moveTo(x1, y); ctx.lineTo(x2, y); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x2 + dir * 10, y); ctx.lineTo(x2, y - 7); ctx.lineTo(x2, y + 7); ctx.closePath(); ctx.fill();
  } else if (a.kind === "rotate") {
    // arc above the head showing which way to tilt (mirror flips direction)
    const dir = -a.dir;
    const r = ry * 0.55;
    const start = -Math.PI / 2 - dir * 0.7;
    const end = -Math.PI / 2 + dir * 0.15;
    ctx.beginPath();
    ctx.arc(fx, fy, r, Math.min(start, end), Math.max(start, end));
    ctx.stroke();
    const tipA = dir > 0 ? Math.max(start, end) : Math.min(start, end);
    const tx = fx + r * Math.cos(tipA);
    const ty = fy + r * Math.sin(tipA);
    ctx.beginPath();
    ctx.moveTo(tx + dir * 9, ty - 4); ctx.lineTo(tx - dir * 3, ty - 9); ctx.lineTo(tx, ty + 6); ctx.closePath(); ctx.fill();
  } else if (a.kind === "pitch") {
    // vertical arrow beside the head: up = raise chin, down = lower chin
    const dir = a.dir; // +1 raise (arrow up), -1 lower (arrow down)
    const x = fx + rx * 0.85;
    const y1 = fy + (dir > 0 ? 24 : -24);
    const y2 = fy - (dir > 0 ? 24 : -24);
    ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y2); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y2 - dir * 10); ctx.lineTo(x - 7, y2); ctx.lineTo(x + 7, y2); ctx.closePath(); ctx.fill();
  }
  ctx.restore();
}

async function captureCameraFrame() {
  if (!state.cameraStream) return;

  // Burst capture: webcams motion-blur easily, so grab several frames and keep
  // the SHARPEST. This is frame selection, not editing - fully compliant.
  const video = elements.cameraFeed;
  const frames = [];
  for (let i = 0; i < 5; i += 1) {
    const shot = document.createElement("canvas");
    shot.width = video.videoWidth;
    shot.height = video.videoHeight;
    shot.getContext("2d").drawImage(video, 0, 0);
    frames.push(shot);
    if (i < 4) await new Promise((resolve) => setTimeout(resolve, 130));
    if (!state.cameraStream) return; // camera stopped mid-burst
  }

  let best = frames[0];
  let bestScore = -1;
  for (const shot of frames) {
    const score = frameSharpness(shot);
    if (score > bestScore) {
      bestScore = score;
      best = shot;
    }
  }

  const blob = await canvasToBlob(best, "image/jpeg", 0.95);
  const file = new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" });
  stopCamera();
  elements.automationSummary.textContent = "Captured the sharpest of 5 frames.";
  addFilesToQueue([file]);
}

function frameSharpness(canvas) {
  // Gradient energy on a small grayscale copy - fast per-frame sharpness rank.
  const w = 160;
  const h = Math.max(1, Math.round((canvas.height / canvas.width) * w));
  const small = document.createElement("canvas");
  small.width = w;
  small.height = h;
  const ctx = small.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(canvas, 0, 0, w, h);
  const data = ctx.getImageData(0, 0, w, h).data;
  let energy = 0;
  for (let y = 1; y < h - 1; y += 1) {
    for (let x = 1; x < w - 1; x += 1) {
      const i = (y * w + x) * 4;
      const l = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
      const r = data[i + 4] * 0.299 + data[i + 5] * 0.587 + data[i + 6] * 0.114;
      const d = data[i + w * 4] * 0.299 + data[i + w * 4 + 1] * 0.587 + data[i + w * 4 + 2] * 0.114;
      energy += Math.abs(l - r) + Math.abs(l - d);
    }
  }
  return energy;
}

function downloadPhoto() {
  if (!state.processedImage || !state.exportBlob) return;
  const issues = getDownloadIssues();
  if (issues.length && !state.downloadAcknowledged) {
    showDownloadWarningDialog(issues);
    return;
  }
  performPhotoDownload();
}

function downloadOriginal() {
  if (!state.originalFile) return;
  const originalName = state.originalFile.name || state.imageName || "original-photo.jpg";
  const dot = originalName.lastIndexOf(".");
  const base = dot > 0 ? originalName.slice(0, dot) : originalName;
  const typeExtensions = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };
  const extension = dot > 0 ? originalName.slice(dot + 1).toLowerCase() : typeExtensions[state.originalFile.type] || "jpg";
  downloadBlob(state.originalFile, `${slugify(base) || "photo"}-original.${extension}`);
}

function backgroundVariantIsSubmissionEligible() {
  return state.profile?.allowedEdits?.background !== false && !isValidationOnlyProfile();
}

function renderBackgroundVariantControl() {
  if (!elements.backgroundVariant) return;
  const eligible = backgroundVariantIsSubmissionEligible();
  elements.backgroundVariant.disabled = !state.originalFile || state.processing || state.backgroundVariantBusy;
  elements.backgroundVariant.textContent = state.backgroundVariantBusy
    ? "Creating..."
    : eligible
      ? "Clean-background file"
      : "Background preview";
  elements.backgroundVariant.title = eligible
    ? "Create a separate clean-background file using the selected programme colour"
    : "Create a watermarked background-removal preview; this programme does not permit a clean altered submission file";
}

function showBackgroundVariantDialog() {
  if (!state.originalFile || state.processing) return;
  const eligible = backgroundVariantIsSubmissionEligible();
  elements.backgroundVariantTitle.textContent = eligible
    ? "Create a clean-background version?"
    : "Create a watermarked background preview?";
  elements.backgroundVariantCopy.textContent = eligible
    ? "KVNP will isolate the person, preserve hair, ears and shoulders, and place the selected programme background behind them. The current prepared file will not be replaced."
    : "This programme does not permit digital background replacement in submission mode. KVNP can still generate a separately named, permanently watermarked preview so you can inspect the matte.";
  elements.backgroundVariantPolicy.className = `variant-policy ${eligible ? "allowed" : "blocked"}`;
  elements.backgroundVariantPolicy.innerHTML = eligible
    ? "<strong>Programme allows this processing path</strong><span>Acceptance is still decided by the issuing authority.</span>"
    : "<strong>Not a submission file</strong><span>The download will say EDITING PREVIEW - NOT FOR SUBMISSION.</span>";
  elements.backgroundVariantConfirm.textContent = eligible ? "Create and download" : "Create watermarked preview";
  elements.backgroundVariantDialog.showModal();
}

async function downloadBackgroundVariant() {
  if (!state.originalFile || state.backgroundVariantBusy) return;
  const eligible = backgroundVariantIsSubmissionEligible();
  state.backgroundVariantBusy = true;
  renderBackgroundVariantControl();
  elements.backgroundVariantConfirm.disabled = true;
  elements.backgroundVariantConfirm.textContent = "Creating...";

  try {
    const options = {
      ...getProcessingOptions(),
      previewMode: !eligible,
      backgroundReplaced: true,
      backgroundColor: state.backgroundColor || "#ffffff",
      backgroundCleanup: "strong",
      autoStraighten: false,
      autoTone: false,
      autoLighting: false,
      enhanceOutput: false,
      enhancementMode: "natural",
    };
    const form = new FormData();
    form.append("image", state.originalFile);
    form.append("profile", JSON.stringify(state.profile));
    form.append("options", JSON.stringify(options));
    const response = await fetch("/api/process", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`);

    const blob = dataUrlToBlob(result.finalDataUrl);
    const suffix = eligible ? "clean-background" : "background-preview-not-for-submission";
    downloadBlob(blob, `${slugify(state.profile.label)}-${suffix}-${Date.now()}.jpg`);
    elements.automationSummary.textContent = eligible
      ? "Separate clean-background file downloaded. The current review result was left unchanged."
      : "Watermarked background preview downloaded. It is not a submission file.";
    elements.backgroundVariantDialog.close();
  } catch (error) {
    console.error(error);
    elements.backgroundVariantCopy.textContent = `Background version failed: ${error.message}`;
  } finally {
    state.backgroundVariantBusy = false;
    elements.backgroundVariantConfirm.disabled = false;
    renderBackgroundVariantControl();
  }
}

async function performPhotoDownload() {
  if (!state.processedImage) return;
  const button = elements.downloadPhoto;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Preparing...";
  try {
    await bakeExport();
    if (!state.exportBlob) return;
    const spec = {
      format: state.outputFormat,
      scale: state.outputScale,
      dpi: state.outputDpi,
      quality: state.outputQuality,
    };
    const form = new FormData();
    form.append("image", state.exportBlob, "passport-photo.jpg");
    form.append("spec", JSON.stringify(spec));
    const response = await fetch("/api/export", { method: "POST", body: form });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.error || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const extensions = {
      "image/jpeg": "jpg",
      "image/png": "png",
      "image/webp": "webp",
      "application/pdf": "pdf",
    };
    const extension = extensions[state.outputFormat] ?? "jpg";
    const filename = `${slugify(state.profile.label)}${state.previewMode ? "-editing-preview" : ""}-${state.outputScale}x-${Date.now()}.${extension}`;
    downloadBlob(blob, filename);
    const width = response.headers.get("X-KVNP-Width") ?? "?";
    const height = response.headers.get("X-KVNP-Height") ?? "?";
    const engine = response.headers.get("X-KVNP-Upscale") ?? "none";
    elements.automationSummary.textContent = `Export ready: ${width} x ${height}px ${extension.toUpperCase()}${engine === "none" ? "" : ` / ${engine}`}.`;
  } catch (error) {
    console.error(error);
    elements.automationSummary.textContent = `Export failed: ${error.message}`;
  } finally {
    button.textContent = originalLabel;
    renderChecks();
  }
}

function downloadReport() {
  if (!state.lastReport) return;
  const blob = new Blob([JSON.stringify(state.lastReport, null, 2)], { type: "application/json" });
  downloadBlob(blob, `${slugify(state.profile.label)}-report-${Date.now()}.json`);
}

/* ============================================================
   Auto-fix: consider every check, then apply the best automatic
   corrections (server-side geometry/tone/background + client-side
   finishing) and report what still needs a human / retake.
   ============================================================ */
async function autoFix() {
  if (!state.originalFile || state.processingError || !state.face) return;
  const button = elements.autoFix;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Preparing…";
  elements.automationSummary.textContent = "Preparing the permitted corrections…";

  try {
    // 1) Decide corrective settings from the current findings.
    const allChecks = [...(state.sourceQuality ?? []), ...(state.checks ?? [])];
    const failing = (id) => allChecks.some((c) => c.id === id && c.status !== "pass" && c.status !== "review");
    const bgTrouble =
      failing("background_uniformity") || failing("background_cleanup") || failing("source_background_path");

    const lawful = state.profile.allowedEdits ?? {};
    state.autoStraighten = state.previewMode || lawful.straighten !== false;
    state.autoTone = state.previewMode || lawful.tone !== false;
    state.enhanceOutput = state.previewMode || lawful.enhance !== false;
    state.backgroundReplaced = state.previewMode || lawful.background !== false;
    state.backgroundCleanup = bgTrouble ? "strong" : state.backgroundCleanup === "balanced" ? "balanced" : state.backgroundCleanup;
    state.backgroundColor = state.profile.automation?.backgroundColor || "#ffffff";
    if (state.enhancementMode === "strong") state.enhancementMode = "natural";
    for (const key of Object.keys(state.adjust)) state.adjust[key] = 0;

    // Reflect into the controls — respect the same law-gating as the state above,
    // so a country-banned edit renders unchecked instead of a misleading enabled box.
    elements.autoStraighten.checked = state.autoStraighten;
    elements.autoTone.checked = state.autoTone;
    elements.enhanceOutput.checked = state.enhanceOutput;
    elements.backgroundReplace.checked = state.backgroundReplaced;
    elements.backgroundCleanup.value = state.backgroundCleanup;
    elements.backgroundColor.value = state.backgroundColor;
    elements.enhancementMode.value = state.enhancementMode;
    markActiveSwatch();
    syncAdjustControls();

    // 2) Re-run the server pipeline with the corrective settings.
    state.manualOverride = false;
    await processOnServer();

    // 3) Finishing pass: nudge tone metrics toward compliant from the new checks.
    const applied = applyToneAutoFix();
    syncAdjustControls();
    setResultView("result");
    applyAdjustments();
    // Re-analyze the adjusted output so the numbers reflect the fix (not the base).
    await reanalyzeOutput();

    // 4) Honest summary of what is fixed vs what still needs a human / retake.
    summarizeAutoFix(applied);
  } catch (error) {
    console.error(error);
    elements.automationSummary.textContent = `Preparation failed: ${error.message}`;
  } finally {
    button.textContent = label;
  button.disabled = !state.originalFile || Boolean(state.processingError) || !state.face;
  }
}

function applyToneAutoFix() {
  const get = (id) => state.checks.find((c) => c.id === id);
  const applied = [];

  const brightness = get("brightness");
  if (brightness) {
    const luma = parseFloat(brightness.value);
    if (Number.isFinite(luma)) {
      if (luma < 120) {
        state.adjust.brightness = Math.min(45, Math.round((135 - luma) * 0.7));
        applied.push("brightness");
      } else if (luma > 205) {
        state.adjust.brightness = Math.max(-45, Math.round((190 - luma) * 0.7));
        applied.push("brightness");
      }
    }
  }

  const contrast = get("contrast");
  if (contrast && contrast.status !== "pass") {
    const value = parseFloat(contrast.value);
    if (Number.isFinite(value) && value < 30) {
      state.adjust.contrast = Math.min(40, Math.round((32 - value) * 1.8));
      applied.push("contrast");
    }
  }

  const sharpness = get("sharpness");
  if (sharpness && sharpness.status !== "pass") {
    state.adjust.sharpness = 35;
    applied.push("sharpness");
  }

  return applied;
}

const HUMAN_ONLY = {
  face_direction: "turned head — face the camera",
  pose_yaw: "turned head — face the camera",
  eye_gaze: "eyes looking away - look directly into the lens",
  expression: "neutral expression / mouth closed",
  mouth: "close mouth / neutral expression",
  source_focus: "out of focus — retake sharper",
  source_face_pixels: "too low-res — retake closer",
  source_resolution: "source too small — use a higher-res photo",
  source_noise: "too grainy — retake in better light",
};

function summarizeAutoFix(applied) {
  const allChecks = [...(state.sourceQuality ?? []), ...(state.checks ?? [])];
  const blocking = allChecks.filter((c) => c.status === "fail");
  const fixedNote = applied.length ? ` Tone tuned: ${applied.join(", ")}.` : "";

  if (!blocking.length) {
    elements.automationSummary.textContent = `Preparation complete — ready to export.${fixedNote}`;
    return;
  }
  const reasons = [...new Set(blocking.map((c) => HUMAN_ONLY[c.id] || c.label))].slice(0, 3);
  elements.automationSummary.textContent = `Preparation applied what it can.${fixedNote} Still needs you: ${reasons.join("; ")}.`;
}

async function generatePrintSheet() {
  if (!state.processedImage) return;
  await bakeExport();
  if (!state.exportBlob) return;

  const button = elements.printSheet;
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Building...";

  try {
    const copies = parseInt(elements.sheetCopies.value, 10);
    const spec = {
      sheet: elements.sheetSize.value,
      dpi: parseInt(elements.sheetDpi.value, 10) || 300,
      photoWidthMm: state.profile.output.printWidthMm ?? null,
      photoHeightMm: state.profile.output.printHeightMm ?? null,
    };
    if (Number.isFinite(copies) && copies > 0) {
      spec.copies = copies;
    }
    const form = new FormData();
    form.append("image", state.exportBlob, "photo.jpg");
    form.append("spec", JSON.stringify(spec));

    const response = await fetch("/api/print-sheet", { method: "POST", body: form });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || `HTTP ${response.status}`);
    }

    const blob = dataUrlToBlob(result.sheetDataUrl);
    const layout = result.layout ?? {};
    downloadBlob(blob, `${slugify(state.profile.label)}-${layout.sheet ?? "sheet"}-${layout.copies ?? ""}up-${Date.now()}.jpg`);
    elements.automationSummary.textContent = `Print sheet ready: ${layout.copies ?? "?"} copies on ${layout.label ?? spec.sheet} at ${layout.dpi ?? 300} DPI.`;
  } catch (error) {
    console.error(error);
    elements.automationSummary.textContent = `Print sheet failed: ${error.message}`;
  } finally {
    button.textContent = label;
    button.disabled = !state.exportBlob;
  }
}

/* ---------- manual background touch-up ---------- */
function bindTouchUpCanvas() {
  const canvas = elements.finalCanvas;
  canvas.addEventListener("pointerdown", (event) => {
    if (!state.touchUp.active) return;
    event.preventDefault();
    state.touchUp.painting = true;
    canvas.setPointerCapture?.(event.pointerId);
    paintTouchUp(event);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (state.touchUp.active && state.touchUp.painting) paintTouchUp(event);
  });
  const stop = () => {
    state.touchUp.painting = false;
  };
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointercancel", stop);
  canvas.addEventListener("pointerleave", stop);
}

function paintTouchUp(event) {
  const canvas = elements.finalCanvas;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const x = (event.clientX - rect.left) * scaleX;
  const y = (event.clientY - rect.top) * scaleY;
  const radius = Math.max(4, state.touchUp.brush * scaleX);
  finalCtx.save();
  finalCtx.fillStyle = state.backgroundColor;
  finalCtx.beginPath();
  finalCtx.arc(x, y, radius, 0, Math.PI * 2);
  finalCtx.fill();
  finalCtx.restore();
  state.touchUp.dirty = true;
  state.manualTouchup = true;
}

function toggleTouchUp() {
  if (!state.processedImage || !state.backendResult?.ok) return;
  if (state.profile?.allowedEdits?.background === false && !state.previewMode) return;
  if (state.touchUp.active) {
    finishTouchUp();
    return;
  }
  state.touchUp.active = true;
  state.touchUp.dirty = false;
  configureFinalCanvas();
  finalCtx.clearRect(0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  finalCtx.drawImage(state.processedImage, 0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  elements.compare.hidden = true;
  elements.finalCanvas.hidden = false;
  elements.finalCanvas.classList.add("painting");
  elements.touchupBrush.hidden = false;
  elements.touchupReset.hidden = false;
  elements.touchupToggle.textContent = "Done";
  elements.automationSummary.textContent = "Touch-up: drag on the photo to paint over background spots.";
}

async function finishTouchUp() {
  state.touchUp.active = false;
  state.touchUp.painting = false;
  elements.finalCanvas.classList.remove("painting");
  elements.touchupBrush.hidden = true;
  elements.touchupReset.hidden = true;
  elements.touchupToggle.textContent = "Clean background";

  if (state.touchUp.dirty) {
    state.downloadAcknowledged = false;
    const mime = state.profile.output.mime || "image/jpeg";
    const quality = state.profile.output.quality ?? 0.92;
    const dataUrl = elements.finalCanvas.toDataURL(mime, quality);
    state.exportBlob = dataUrlToBlob(dataUrl);
    state.processedImage = await loadImageFromDataUrl(dataUrl);
    if (state.backendResult) state.backendResult.finalDataUrl = dataUrl;
    state.lastReport = buildReport();
    elements.automationSummary.textContent = "Touch-up applied to the exported photo.";
    renderCorrections();
    scheduleReanalyze();
  }
  renderFinalCanvas();
  renderChecks();
}

async function resetTouchUp() {
  const base = state.touchUp.serverFinalDataUrl;
  if (!base) return;
  state.touchUp.dirty = false;
  state.downloadAcknowledged = false;
  state.manualTouchup = false;
  state.exportBlob = dataUrlToBlob(base);
  state.processedImage = await loadImageFromDataUrl(base);
  if (state.backendResult) state.backendResult.finalDataUrl = base;
  if (state.touchUp.active) {
    finalCtx.clearRect(0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
    finalCtx.drawImage(state.processedImage, 0, 0, elements.finalCanvas.width, elements.finalCanvas.height);
  } else {
    renderFinalCanvas();
  }
  elements.automationSummary.textContent = "Touch-up reset to the generated photo.";
  state.lastReport = buildReport();
  renderCorrections();
}

function clearTouchUp() {
  state.touchUp.active = false;
  state.touchUp.painting = false;
  state.touchUp.dirty = false;
  state.manualTouchup = false;
  if (elements.finalCanvas) elements.finalCanvas.classList.remove("painting");
  if (elements.touchupBrush) elements.touchupBrush.hidden = true;
  if (elements.touchupReset) elements.touchupReset.hidden = true;
  if (elements.touchupToggle) elements.touchupToggle.textContent = "Clean background";
}

/* ============================================================
   Cockpit: live adjustments, guides, zoom, presets, output
   ============================================================ */
function bindCockpit() {
  elements.viewResult.addEventListener("click", () => setResultView("result"));
  elements.viewCompare.addEventListener("click", () => setResultView("compare"));
  elements.toggleGuides.addEventListener("click", toggleGuides);
  elements.zoomIn.addEventListener("click", () => setZoom(state.zoom + 0.25));
  elements.zoomOut.addEventListener("click", () => setZoom(state.zoom - 0.25));
  elements.adjustReset.addEventListener("click", (event) => {
    event.preventDefault();
    resetAdjustments();
  });
  elements.outputFormat.addEventListener("change", () => {
    state.downloadAcknowledged = false;
    state.outputFormat = elements.outputFormat.value;
    syncOutputControls();
  });
  elements.outputScale.addEventListener("change", () => {
    state.downloadAcknowledged = false;
    state.outputScale = Number(elements.outputScale.value) === 2 ? 2 : 1;
    updateOutputNote();
  });
  elements.outputDpi.addEventListener("change", () => {
    state.downloadAcknowledged = false;
    state.outputDpi = Number(elements.outputDpi.value) === 600 ? 600 : 300;
    updateOutputNote();
  });
  elements.outputQuality.addEventListener("input", () => {
    state.downloadAcknowledged = false;
    state.outputQuality = Number(elements.outputQuality.value);
    elements.qualityVal.textContent = String(state.outputQuality);
    scheduleReanalyze();
  });
  elements.presetSave.addEventListener("click", savePreset);
  elements.presetDelete.addEventListener("click", deletePreset);
  elements.presetSelect.addEventListener("change", () => applyPreset(elements.presetSelect.value));
}

function buildAdjustControls() {
  elements.adjustGrid.innerHTML = ADJUST_CONTROLS.map(
    (control) => `
      <div class="adjust-row">
        <div class="adjust-head">
          <span>${control.label}</span>
          <span class="adjust-val" data-val="${control.key}">${state.adjust[control.key]}</span>
        </div>
        <input type="range" data-adjust="${control.key}" min="${control.min}" max="${control.max}" value="${state.adjust[control.key]}" />
      </div>`,
  ).join("");

  for (const input of elements.adjustGrid.querySelectorAll("[data-adjust]")) {
    input.addEventListener("input", () => {
      state.downloadAcknowledged = false;
      const key = input.dataset.adjust;
      state.adjust[key] = Number(input.value);
      elements.adjustGrid.querySelector(`[data-val="${key}"]`).textContent = input.value;
      if (state.resultView !== "result") setResultView("result");
      else applyAdjustments();
      renderCorrections();
      scheduleReanalyze();
    });
  }
  applyAdjustmentPolicyGate();
}

function syncAdjustControls() {
  for (const input of elements.adjustGrid.querySelectorAll("[data-adjust]")) {
    const key = input.dataset.adjust;
    input.value = state.adjust[key];
    elements.adjustGrid.querySelector(`[data-val="${key}"]`).textContent = String(state.adjust[key]);
  }
}

function resetAdjustments() {
  for (const key of Object.keys(state.adjust)) state.adjust[key] = 0;
  syncAdjustControls();
  applyAdjustments();
  renderCorrections();
  scheduleReanalyze();
}

function adjustmentsActive() {
  return Object.values(state.adjust).some((value) => value !== 0);
}

function applyAdjustments() {
  if (!state.processedImage || state.touchUp.active) return;
  const width = state.profile.output.widthPx;
  const height = state.profile.output.heightPx;
  adjustCanvas.width = width;
  adjustCanvas.height = height;
  adjustCtx.clearRect(0, 0, width, height);
  adjustCtx.drawImage(state.processedImage, 0, 0, width, height);

  if (adjustmentsActive() && (!isValidationOnlyProfile() || state.previewMode)) {
    const image = adjustCtx.getImageData(0, 0, width, height);
    applyTone(image.data, state.adjust);
    adjustCtx.putImageData(image, 0, 0);
    if (state.adjust.sharpness > 0) applySharpen(adjustCtx, width, height, state.adjust.sharpness / 100);
  }

  configureFinalCanvas();
  finalCtx.clearRect(0, 0, width, height);
  finalCtx.drawImage(adjustCanvas, 0, 0, width, height);
  if (state.guides) drawGuides(finalCtx, width, height);
}

function applyTone(data, adjust) {
  const brightness = adjust.brightness * 1.5; // -150..150
  const c = adjust.contrast;
  const contrastF = (259 * (c * 2.55 + 255)) / (255 * (259 - c * 2.55));
  const sat = 1 + adjust.saturation / 100;
  const warmth = adjust.warmth * 0.6;
  const tint = adjust.tint * 0.6;
  const hi = adjust.highlights / 100;
  const sh = adjust.shadows / 100;

  for (let i = 0; i < data.length; i += 4) {
    let r = data[i];
    let g = data[i + 1];
    let b = data[i + 2];

    // tone-zone lift: shadows affect darks, highlights affect brights
    const luma0 = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 255;
    const shadowW = (1 - luma0) * (1 - luma0);
    const highW = luma0 * luma0;
    const zone = sh * 70 * shadowW + hi * 70 * highW;

    r += brightness + warmth + zone;
    g += brightness + tint + zone;
    b += brightness - warmth + zone;

    r = contrastF * (r - 128) + 128;
    g = contrastF * (g - 128) + 128;
    b = contrastF * (b - 128) + 128;

    if (sat !== 1) {
      const luma = r * 0.2126 + g * 0.7152 + b * 0.0722;
      r = luma + (r - luma) * sat;
      g = luma + (g - luma) * sat;
      b = luma + (b - luma) * sat;
    }

    data[i] = clamp255(r);
    data[i + 1] = clamp255(g);
    data[i + 2] = clamp255(b);
  }
}

function applySharpen(ctx, width, height, amount) {
  const src = ctx.getImageData(0, 0, width, height);
  const out = ctx.createImageData(width, height);
  const s = src.data;
  const d = out.data;
  const k = amount * 0.8;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const idx = (y * width + x) * 4;
      for (let c = 0; c < 3; c += 1) {
        const center = s[idx + c];
        if (x === 0 || y === 0 || x === width - 1 || y === height - 1) {
          d[idx + c] = center;
          continue;
        }
        const neighbors =
          s[idx - 4 + c] + s[idx + 4 + c] + s[idx - width * 4 + c] + s[idx + width * 4 + c];
        d[idx + c] = clamp255(center + k * (center * 4 - neighbors));
      }
      d[idx + 3] = s[idx + 3];
    }
  }
  ctx.putImageData(out, 0, 0);
}

function clamp255(value) {
  return value < 0 ? 0 : value > 255 ? 255 : value;
}

function scheduleAdjustBake() {
  window.clearTimeout(adjustBakeTimer);
  adjustBakeTimer = window.setTimeout(bakeExport, 180);
}

async function bakeExport() {
  if (!state.processedImage) return;
  // Bake the adjusted (guide-free) result into the downloadable blob.
  const width = state.profile.output.widthPx;
  const height = state.profile.output.heightPx;
  adjustCanvas.width = width;
  adjustCanvas.height = height;
  adjustCtx.clearRect(0, 0, width, height);
  adjustCtx.drawImage(state.processedImage, 0, 0, width, height);
  if (adjustmentsActive()) {
    const image = adjustCtx.getImageData(0, 0, width, height);
    applyTone(image.data, state.adjust);
    adjustCtx.putImageData(image, 0, 0);
    if (state.adjust.sharpness > 0) applySharpen(adjustCtx, width, height, state.adjust.sharpness / 100);
  }
  const complianceMime = state.profile.output?.mime ?? "image/jpeg";
  const quality = complianceMime === "image/png" ? undefined : state.outputQuality / 100;
  state.exportBlob = await canvasToBlob(adjustCanvas, complianceMime, quality);
  updateReviewPreview();
  updateDownloadAdvisory();
}

/* ---------- live re-analysis: keep the numbers honest as the photo changes ---------- */
function scheduleReanalyze() {
  if (!state.processedImage || !state.backendResult?.ok) return;
  setAnalyzingHint(true);
  window.clearTimeout(reanalyzeTimer);
  reanalyzeTimer = window.setTimeout(reanalyzeOutput, 320);
}

async function reanalyzeOutput() {
  if (!state.processedImage || !state.backendResult?.ok) return;
  const seq = ++analyzeSeq;
  await bakeExport(); // refresh the adjusted (guide-free) output blob
  if (seq !== analyzeSeq || !state.exportBlob) return;

  try {
    const form = new FormData();
    form.append("image", state.exportBlob, "out.jpg");
    form.append("profile", JSON.stringify(state.profile));
    form.append(
      "options",
      JSON.stringify({ backgroundReplaced: state.effectiveEdits?.background === true, outputBytes: state.exportBlob.size }),
    );
    const response = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await response.json();
    if (seq !== analyzeSeq) return;
    if (!response.ok || !data.ok) return;

    const updated = data.checks || {};
    state.checks = state.checks.map((c) => updated[c.id] || c);
    state.serverChecks = state.checks;
    state.decision = recomputeDecisionFromChecks();
    state.lastReport = buildReport();
    renderChecks();
    renderDecision();
    renderCorrections();
  } catch (error) {
    console.warn("reanalyze failed", error);
  } finally {
    if (seq === analyzeSeq) setAnalyzingHint(false);
  }
}

function setAnalyzingHint(active) {
  if (!elements.overallStatus) return;
  elements.overallStatus.classList.toggle("analyzing", active);
}

function recomputeDecisionFromChecks() {
  const sourceQuality = state.sourceQuality ?? [];
  const checks = state.checks ?? [];
  const all = [...sourceQuality, ...checks];
  const failItems = all.filter((c) => c.status === "fail");
  const warnItems = all.filter((c) => c.status === "warning");
  const reviewItems = checks.filter((c) => c.status === "review");
  const sourceFailures = sourceQuality.filter((c) => c.status === "fail");
  const policyWarnings = checks.filter((c) => c.id === "edit_policy" && c.status === "warning");

  let status = "ready";
  let title = "Ready for export";
  let message = "Machine checks pass. Human-only requirements still need visual confirmation.";
  if (sourceFailures.length) {
    status = "retake";
    title = "Retake source photo";
    message = "The input does not have enough clean detail for a reliable passport output.";
  } else if (failItems.length) {
    status = "fix";
    title = "Fix output before export";
    message = "The generated photo fails at least one machine compliance check.";
  } else if (policyWarnings.length) {
    status = "policy_review";
    title = "Policy review required";
    message = "The photo is technically formed, but the selected programme may reject digital alteration or AI restoration.";
  } else if (warnItems.length) {
    status = "review";
    title = "Review warnings";
    message = "The output is close, but the marked warnings should be checked before submission.";
  }

  const actions = [];
  if (status === "retake") actions.push("Use a sharper source", "Face the camera directly", "Use brighter even light");
  if (checks.some((c) => c.id === "background_cleanup" && c.status !== "pass")) actions.push("Review hair and shoulder edges");
  if (checks.some((c) => c.id === "shoulder_framing" && c.status !== "pass")) {
    actions.push("Keep only the head and upper shoulders; avoid excess torso");
  }
  if (policyWarnings.length) actions.push("Use crop/background only if the government allows edited photos");
  if (reviewItems.length) actions.push("Confirm human-only checks before submission");

  return {
    status,
    title,
    message,
    failures: failItems.length,
    warnings: warnItems.length,
    reviews: reviewItems.length,
    actions: actions.slice(0, 5),
    pipelineVersion: state.pipeline?.version ?? "live",
  };
}

function setResultView(view) {
  state.resultView = view;
  elements.viewResult.classList.toggle("active", view === "result");
  elements.viewCompare.classList.toggle("active", view === "compare");
  renderFinalCanvas();
}

function toggleGuides() {
  state.guides = !state.guides;
  elements.toggleGuides.classList.toggle("is-on", state.guides);
  if (state.resultView !== "result") setResultView("result");
  else renderFinalCanvas();
}

function drawGuides(ctx, width, height) {
  const head = state.profile.head ?? {};
  const targetPercent = (head.targetPercent ?? 60) / 100;
  const topMargin = (head.topMarginPercent ?? 10) / 100;
  const headHeight = height * targetPercent;
  const headTop = height * topMargin;
  const headBottom = headTop + headHeight;
  const eyeLine = headTop + headHeight * 0.42;

  ctx.save();
  ctx.lineWidth = Math.max(1, width / 600);
  ctx.strokeStyle = "rgba(91, 140, 255, 0.85)";
  ctx.setLineDash([width / 60, width / 90]);
  // crown / chin lines
  ctx.beginPath();
  ctx.moveTo(0, headTop);
  ctx.lineTo(width, headTop);
  ctx.moveTo(0, headBottom);
  ctx.lineTo(width, headBottom);
  ctx.stroke();
  // eye line
  ctx.strokeStyle = "rgba(52, 211, 153, 0.85)";
  ctx.beginPath();
  ctx.moveTo(0, eyeLine);
  ctx.lineTo(width, eyeLine);
  ctx.stroke();
  // center
  ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
  ctx.beginPath();
  ctx.moveTo(width / 2, 0);
  ctx.lineTo(width / 2, height);
  ctx.stroke();
  ctx.restore();
}

function setZoom(value) {
  state.zoom = Math.max(1, Math.min(3, Math.round(value * 100) / 100));
  elements.zoomLabel.textContent = `${Math.round(state.zoom * 100)}%`;
  const scale = `scale(${state.zoom})`;
  elements.finalCanvas.style.transform = scale;
  elements.finalCanvas.style.transformOrigin = "top left";
  elements.compare.style.transform = scale;
  elements.compare.style.transformOrigin = "top left";
}

function buildBgSwatches() {
  elements.bgSwatches.innerHTML = BG_PRESETS.map(
    (preset) =>
      `<button class="bg-swatch" type="button" data-color="${preset.color}" title="${preset.name}" style="background:${preset.color}"></button>`,
  ).join("");
  for (const swatch of elements.bgSwatches.querySelectorAll(".bg-swatch")) {
    swatch.addEventListener("click", () => {
      const color = swatch.dataset.color;
      state.backgroundColor = color;
      elements.backgroundColor.value = color;
      markActiveSwatch();
      handleRenderOptionChange();
    });
  }
  markActiveSwatch();
}

function markActiveSwatch() {
  for (const swatch of elements.bgSwatches.querySelectorAll(".bg-swatch")) {
    swatch.classList.toggle("active", swatch.dataset.color.toLowerCase() === state.backgroundColor.toLowerCase());
  }
}

/* ---- presets (localStorage) ---- */
const PRESET_KEY = "kvnp.presets";

function loadPresets() {
  try {
    return JSON.parse(localStorage.getItem(PRESET_KEY) || "{}");
  } catch (error) {
    return {};
  }
}

function refreshPresetList(selected = "") {
  const presets = loadPresets();
  const names = Object.keys(presets).sort();
  elements.presetSelect.innerHTML =
    `<option value="">Presets…</option>` +
    names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  elements.presetSelect.value = selected;
}

function currentSettings() {
  return {
    backgroundReplaced: state.backgroundReplaced,
    enhanceOutput: state.enhanceOutput,
    enhancementMode: state.enhancementMode,
    backgroundColor: state.backgroundColor,
    backgroundCleanup: state.backgroundCleanup,
    autoStraighten: state.autoStraighten,
    autoTone: state.autoTone,
    autoLighting: state.autoLighting,
    adjust: { ...state.adjust },
    outputFormat: state.outputFormat,
    outputScale: state.outputScale,
    outputDpi: state.outputDpi,
    outputQuality: state.outputQuality,
  };
}

function savePreset() {
  const name = window.prompt("Save current settings as preset:", "My preset");
  if (!name) return;
  const presets = loadPresets();
  presets[name] = currentSettings();
  localStorage.setItem(PRESET_KEY, JSON.stringify(presets));
  refreshPresetList(name);
  elements.automationSummary.textContent = `Preset "${name}" saved.`;
}

function deletePreset() {
  const name = elements.presetSelect.value;
  if (!name) return;
  const presets = loadPresets();
  delete presets[name];
  localStorage.setItem(PRESET_KEY, JSON.stringify(presets));
  refreshPresetList();
}

function applyPreset(name) {
  if (!name) return;
  const preset = loadPresets()[name];
  if (!preset) return;

  state.backgroundReplaced = preset.backgroundReplaced ?? true;
  state.enhanceOutput = preset.enhanceOutput ?? true;
  state.enhancementMode = preset.enhancementMode ?? "ai-clean";
  state.backgroundColor = preset.backgroundColor ?? "#ffffff";
  state.backgroundCleanup = preset.backgroundCleanup ?? "balanced";
  state.autoStraighten = preset.autoStraighten ?? true;
  state.autoTone = preset.autoTone ?? true;
  state.outputFormat = preset.outputFormat ?? "image/jpeg";
  state.outputScale = preset.outputScale === 2 ? 2 : 1;
  state.outputDpi = preset.outputDpi === 600 ? 600 : 300;
  state.outputQuality = preset.outputQuality ?? 92;
  Object.assign(state.adjust, { brightness: 0, contrast: 0, saturation: 0, warmth: 0, tint: 0, highlights: 0, shadows: 0, sharpness: 0 }, preset.adjust ?? {});

  elements.backgroundReplace.checked = state.backgroundReplaced;
  elements.enhanceOutput.checked = state.enhanceOutput;
  elements.enhancementMode.value = state.enhancementMode;
  elements.backgroundColor.value = state.backgroundColor;
  elements.backgroundCleanup.value = state.backgroundCleanup;
  elements.autoStraighten.checked = state.autoStraighten;
  elements.autoTone.checked = state.autoTone;
  state.autoLighting = preset.autoLighting !== false;
  elements.autoLighting.checked = state.autoLighting;
  syncOutputControls();
  syncAdjustControls();
  markActiveSwatch();

  if (state.originalFile) scheduleServerProcessing();
  else applyAdjustments();
  elements.automationSummary.textContent = `Preset "${name}" applied.`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function loadImageFromDataUrl(dataUrl) {
  const image = new Image();
  image.decoding = "async";
  return new Promise((resolve, reject) => {
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = dataUrl;
  });
}

function dataUrlToBlob(dataUrl) {
  const [header, payload] = dataUrl.split(",");
  const mime = header.match(/data:(.*?);/)?.[1] ?? "image/jpeg";
  const binary = atob(payload);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mime });
}

function canvasToBlob(canvas, mime, quality) {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), mime, quality);
  });
}

function getContainFit(sourceWidth, sourceHeight, targetWidth, targetHeight) {
  const scale = Math.min(targetWidth / sourceWidth, targetHeight / sourceHeight);
  const width = sourceWidth * scale;
  const height = sourceHeight * scale;
  return {
    x: (targetWidth - width) / 2,
    y: (targetHeight - height) / 2,
    width,
    height,
    scale,
  };
}

function mapRect(rect, fit) {
  return {
    x: fit.x + rect.x * fit.scale,
    y: fit.y + rect.y * fit.scale,
    width: rect.width * fit.scale,
    height: rect.height * fit.scale,
  };
}

function getLuma(r, g, b) {
  return r * 0.2126 + g * 0.7152 + b * 0.0722;
}

function getSaturation(r, g, b) {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  return max === 0 ? 0 : ((max - min) / max) * 100;
}

function mean(values) {
  return values.reduce((total, value) => total + value, 0) / Math.max(1, values.length);
}

function stdDev(values, average) {
  const variance = values.reduce((total, value) => total + (value - average) ** 2, 0) / Math.max(1, values.length);
  return Math.sqrt(variance);
}

function inRange(value, min, max) {
  return value >= min && value <= max;
}

function clamp(value, min, max) {
  if (max < min) return min;
  return Math.min(Math.max(value, min), max);
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "n/a";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function titleCase(value) {
  return value.replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1));
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function round(value) {
  return typeof value === "number" ? Math.round(value * 100) / 100 : null;
}

function describeBackground(mode) {
  const labels = {
    white: "plain white",
    white_or_off_white: "plain white or off-white",
    plain_light: "plain light-coloured",
    white_or_light: "plain white or light-coloured",
    light_gray_or_white: "plain white or light gray",
  };
  return labels[mode] ?? String(mode).replaceAll("_", " ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/* ============================================================
   Auth + app-shell bootstrap
   ============================================================ */
const authEls = {
  authView: document.querySelector("#auth-view"),
  appView: document.querySelector("#app-view"),
  form: document.querySelector("#auth-form"),
  title: document.querySelector("#auth-title"),
  subtitle: document.querySelector("#auth-subtitle"),
  nameField: document.querySelector("#auth-name-field"),
  name: document.querySelector("#auth-name"),
  email: document.querySelector("#auth-email"),
  password: document.querySelector("#auth-password"),
  error: document.querySelector("#auth-error"),
  submit: document.querySelector("#auth-submit"),
  switchText: document.querySelector("#auth-switch-text"),
  switchBtn: document.querySelector("#auth-switch-btn"),
  guest: document.querySelector("#auth-guest"),
  logout: document.querySelector("#logout-btn"),
  accountAvatar: document.querySelector("#account-avatar"),
  accountName: document.querySelector("#account-name"),
  accountEmail: document.querySelector("#account-email"),
  navItems: document.querySelectorAll(".nav-item"),
};

const authState = { mode: "login" };

function showAuthView() {
  authEls.appView.hidden = true;
  authEls.authView.hidden = false;
}

function showAppView() {
  authEls.authView.hidden = true;
  authEls.appView.hidden = false;
}

function setAuthMode(mode) {
  authState.mode = mode;
  const signup = mode === "signup";
  authEls.title.textContent = signup ? "Create your account" : "Welcome back";
  authEls.subtitle.textContent = signup
    ? "Start preparing compliant passport photos."
    : "Sign in to your studio workspace.";
  authEls.submit.textContent = signup ? "Create account" : "Sign in";
  authEls.nameField.hidden = !signup;
  authEls.switchText.textContent = signup ? "Already have an account?" : "New to KVNP Studio?";
  authEls.switchBtn.textContent = signup ? "Sign in" : "Create an account";
  authEls.password.autocomplete = signup ? "new-password" : "current-password";
  hideAuthError();
}

function showAuthError(message) {
  authEls.error.textContent = message;
  authEls.error.hidden = false;
}

function hideAuthError() {
  authEls.error.hidden = true;
  authEls.error.textContent = "";
}

function applyAccount(user) {
  if (user) {
    const label = user.name || user.email;
    authEls.accountName.textContent = label;
    authEls.accountEmail.textContent = user.email;
    authEls.accountAvatar.textContent = (label[0] || "U").toUpperCase();
    authEls.logout.style.display = "";
  } else {
    authEls.accountName.textContent = "Guest";
    authEls.accountEmail.textContent = "local session";
    authEls.accountAvatar.textContent = "G";
    authEls.logout.style.display = "none";
  }
}

async function submitAuth(event) {
  event.preventDefault();
  hideAuthError();
  const endpoint = authState.mode === "signup" ? "/api/auth/signup" : "/api/auth/login";
  const payload = {
    email: authEls.email.value.trim(),
    password: authEls.password.value,
  };
  if (authState.mode === "signup") payload.name = authEls.name.value.trim();

  authEls.submit.disabled = true;
  const labelText = authEls.submit.textContent;
  authEls.submit.textContent = "Please wait...";
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    applyAccount(data.user);
    showAppView();
  } catch (error) {
    showAuthError(error.message);
  } finally {
    authEls.submit.disabled = false;
    authEls.submit.textContent = labelText;
  }
}

async function logout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (error) {
    console.warn(error);
  }
  applyAccount(null);
  setAuthMode("login");
  authEls.form.reset();
  showAuthView();
}

function continueAsGuest() {
  applyAccount(null);
  showAppView();
}

function bindNav() {
  for (const item of authEls.navItems) {
    item.addEventListener("click", () => {
      for (const other of authEls.navItems) other.classList.toggle("active", other === item);
      const target = item.dataset.nav;
      const anchor =
        target === "queue"
          ? elements.queueStrip
          : target === "checks"
            ? document.querySelector(".result-card")
            : document.querySelector(".source-card");
      anchor?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}

async function bootAuth() {
  authEls.form.addEventListener("submit", submitAuth);
  authEls.switchBtn.addEventListener("click", () => setAuthMode(authState.mode === "login" ? "signup" : "login"));
  authEls.guest.addEventListener("click", continueAsGuest);
  authEls.logout.addEventListener("click", logout);
  setAuthMode("login");
  bindNav();

  // Quick local entry without an account (e.g. http://127.0.0.1:4173/?guest)
  if (new URLSearchParams(location.search).has("guest")) {
    continueAsGuest();
    return;
  }

  try {
    const response = await fetch("/api/auth/me");
    const data = await response.json();
    if (data.ok && data.user) {
      applyAccount(data.user);
      showAppView();
      return;
    }
  } catch (error) {
    console.warn("auth check failed", error);
  }
  applyAccount(null);
  showAuthView();
}

init();
bootAuth();
