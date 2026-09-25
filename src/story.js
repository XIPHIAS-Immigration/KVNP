/* PassportLens — 3D story ("The making of a passport photo").
 *
 * One WebGL scene inside the dark stage. The intro plays on load (the phone
 * assembles, the flash fires); after that, scroll through the pinned story
 * section scrubs the chapters: Scan → Clean → Rules → Ready.
 *
 * Tiers: "full" (bloom, sharper), "lite" (weak GPU / phone), "none" (no
 * WebGL → the page shows 2D poster frames instead; see home.css).
 */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const story = document.getElementById("story");
const stage = document.getElementById("stage");
const canvas = document.getElementById("stage-canvas");
const docEl = document.documentElement;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const A = window.anime;
const SNAP = new URLSearchParams(location.search).has("snap");

/* ------------------------------------------------------------------ */
/* helpers                                                             */
/* ------------------------------------------------------------------ */
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (p, a, b) => clamp((p - a) / (b - a));
const ease = (t) => t * t * (3 - 2 * t); // smoothstep
const easeOut = (t) => 1 - Math.pow(1 - t, 3);
const bell = (t) => Math.sin(Math.PI * clamp(t)); // 0 → 1 → 0

/* chapter boundaries along the pinned section (0..1) */
const CH = { hero: [0, 0.1], scan: [0.1, 0.32], clean: [0.32, 0.52], rules: [0.52, 0.74], ready: [0.74, 1] };

function detectTier() {
  const q = new URLSearchParams(location.search).get("tier");
  if (q === "full" || q === "lite" || q === "none") return q;
  let gl = null;
  try { gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl"); } catch (e) {}
  if (!gl) return "none";
  let renderer = "";
  try {
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    renderer = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)) : "";
  } catch (e) {}
  const software = /swiftshader|llvmpipe|basic render|software/i.test(renderer);
  const small = matchMedia("(max-width: 820px)").matches;
  const weak = (navigator.hardwareConcurrency || 8) <= 4 || (navigator.deviceMemory || 8) <= 4;
  return software || small || weak ? "lite" : "full";
}

function loadTexture(url) {
  return new Promise((resolve) => {
    new THREE.TextureLoader().load(url, (t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; resolve(t); }, undefined, () => resolve(null));
  });
}
function loadImage(url) {
  return new Promise((resolve) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = () => resolve(null); img.src = url; });
}
function canvasTexture(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function drawCover(ctx, img, x, y, w, h) {
  const s = Math.max(w / img.width, h / img.height);
  const sw = w / s, sh = h / s;
  ctx.drawImage(img, (img.width - sw) / 2, (img.height - sh) * 0.3, sw, sh, x, y, w, h);
}

const GOLD = new THREE.Color("#FFB500");
const GOLD_SOFT = new THREE.Color("#FFD27A");

/* ------------------------------------------------------------------ */
/* boot                                                                */
/* ------------------------------------------------------------------ */
const tier = story && stage && canvas ? detectTier() : "none";
docEl.dataset.tier = tier;
function fallback() { docEl.dataset.tier = "none"; dispatchEvent(new CustomEvent("pl:fallback")); }
if (tier !== "none") boot().catch((err) => { console.warn("3D story disabled", err); fallback(); });
else if (story) fallback();

async function boot() {
  const full = tier === "full";
  const region = docEl.getAttribute("data-region") === "us" ? "us" : "ca";

  /* ---------- renderer ---------- */
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: full, alpha: false, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, full ? 1.75 : 1.25));
  renderer.setClearColor(0x120a07, 1);
  renderer.toneMapping = THREE.NoToneMapping;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 60);
  camera.position.set(0, 0.15, 8.2);

  /* ---------- assets ---------- */
  const [texOrig, texMatte, texFinal, meshData, imgFinal, imgOrig] = await Promise.all([
    loadTexture("/assets/landing/hero-original.jpg"),
    loadTexture("/assets/landing/hero-matte.png"),
    loadTexture("/assets/landing/hero-final.jpg"),
    fetch("/assets/landing/face-mesh.json").then((r) => r.json()).catch(() => null),
    loadImage("/assets/landing/hero-final.jpg"),
    loadImage("/assets/landing/hero-original.jpg"),
  ]);
  if (texMatte) texMatte.colorSpace = THREE.NoColorSpace;
  const flagCodes = region === "us" ? ["ca", "in", "gb", "us"] : ["us", "in", "gb", "ca"];
  const flagImgs = await Promise.all(flagCodes.map((c) => loadImage(`/assets/flags/${c}.svg`)));

  /* ---------- lights ---------- */
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const key = new THREE.DirectionalLight(0xffe2b0, 1.6);
  key.position.set(3, 4, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xffb500, 1.4);
  rim.position.set(-4, 1.5, -3);
  scene.add(rim);
  const flash = new THREE.PointLight(0xffffff, 0, 12, 1.5);
  flash.position.set(0, 0.6, 2.5);
  scene.add(flash);

  /* ---------- backdrop: glow, plinth, dust ---------- */
  const glowTex = canvasTexture(512, 512, (ctx, w, h) => {
    const g = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
    g.addColorStop(0, "rgba(255,181,0,0.26)");
    g.addColorStop(0.3, "rgba(255,150,0,0.06)");
    g.addColorStop(1, "rgba(255,120,0,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  });
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(9, 9), new THREE.MeshBasicMaterial({ map: glowTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
  glow.position.set(0.6, 0.4, -5);
  scene.add(glow);

  const floorTex = canvasTexture(1024, 1024, (ctx, w, h) => {
    const cx = w / 2, cy = h / 2;
    ctx.strokeStyle = "rgba(255,181,0,0.20)";
    ctx.lineWidth = 2;
    for (let r = 60; r < w / 2; r += 60) { ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke(); }
    ctx.strokeStyle = "rgba(255,181,0,0.10)";
    for (let a = 0; a < 24; a++) {
      const t = (a / 24) * Math.PI * 2;
      ctx.beginPath(); ctx.moveTo(cx + Math.cos(t) * 60, cy + Math.sin(t) * 60); ctx.lineTo(cx + Math.cos(t) * w / 2, cy + Math.sin(t) * h / 2); ctx.stroke();
    }
    const fade = ctx.createRadialGradient(cx, cy, w * 0.1, cx, cy, w / 2);
    fade.addColorStop(0, "rgba(0,0,0,0)"); fade.addColorStop(1, "rgba(18,10,7,1)");
    ctx.globalCompositeOperation = "destination-out";
    const m = ctx.createRadialGradient(cx, cy, w * 0.25, cx, cy, w / 2);
    m.addColorStop(0, "rgba(0,0,0,0)"); m.addColorStop(1, "rgba(0,0,0,1)");
    ctx.fillStyle = m; ctx.fillRect(0, 0, w, h);
  });
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.MeshBasicMaterial({ map: floorTex, transparent: true, depthWrite: false, toneMapped: false }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -2.05;
  scene.add(floor);

  const plinth = new THREE.Group();
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(1.55, 1.68, 0.14, 96), new THREE.MeshPhysicalMaterial({ color: 0x1b110c, metalness: 0.5, roughness: 0.35, clearcoat: 0.6 }));
  plinth.add(disc);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.57, 0.014, 12, 160), new THREE.MeshBasicMaterial({ color: GOLD, toneMapped: false }));
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.085;
  plinth.add(ring);
  plinth.position.set(0, -2.0, -0.4);
  scene.add(plinth);

  const DUST = full ? 420 : 160;
  const dustGeo = new THREE.BufferGeometry();
  const dustPos = new Float32Array(DUST * 3);
  const dustSeed = new Float32Array(DUST);
  for (let i = 0; i < DUST; i++) {
    dustPos[i * 3] = (Math.random() - 0.5) * 12;
    dustPos[i * 3 + 1] = (Math.random() - 0.5) * 7;
    dustPos[i * 3 + 2] = -4 + Math.random() * 6;
    dustSeed[i] = Math.random() * 100;
  }
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPos, 3));
  const dotTex = canvasTexture(64, 64, (ctx) => {
    const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.3, "rgba(255,220,150,0.8)"); g.addColorStop(1, "rgba(255,180,0,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, 64, 64);
  });
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({ size: 0.045, map: dotTex, transparent: true, opacity: 0.55, depthWrite: false, blending: THREE.AdditiveBlending, color: GOLD_SOFT, toneMapped: false }));
  scene.add(dust);

  /* ---------- phone (assembles from parts) ---------- */
  const phone = new THREE.Group();
  scene.add(phone);
  const PW = 1.5, PH = 3.05;
  const bodyMat = new THREE.MeshPhysicalMaterial({ color: 0x1d1512, metalness: 0.75, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.2 });
  const frameMat = new THREE.MeshPhysicalMaterial({ color: 0xd9a441, metalness: 1, roughness: 0.25, emissive: 0x3a2400, emissiveIntensity: 0.4 });
  const glassMat = new THREE.MeshPhysicalMaterial({ color: 0x050505, metalness: 0.2, roughness: 0.05, clearcoat: 1 });

  const screenCanvas = document.createElement("canvas");
  screenCanvas.width = 512; screenCanvas.height = 1040;
  const screenCtx = screenCanvas.getContext("2d");
  const screenTex = new THREE.CanvasTexture(screenCanvas);
  screenTex.colorSpace = THREE.SRGBColorSpace;
  let screenState = "";
  function paintScreen(state) {
    if (state === screenState) return;
    screenState = state;
    const ctx = screenCtx, w = 512, h = 1040;
    ctx.fillStyle = "#0b0706"; ctx.fillRect(0, 0, w, h);
    if (state === "off") { screenTex.needsUpdate = true; return; }
    if (imgOrig) drawCover(ctx, imgOrig, 0, 90, w, 860);
    // viewfinder UI
    ctx.fillStyle = "rgba(11,7,6,0.85)"; ctx.fillRect(0, 0, w, 90); ctx.fillRect(0, 950, w, 90);
    ctx.strokeStyle = state === "captured" ? "#3ddc84" : "#FFB500";
    ctx.lineWidth = 5; ctx.setLineDash(state === "captured" ? [] : [18, 12]);
    ctx.beginPath(); ctx.ellipse(w / 2, 400, 150, 200, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 6; ctx.strokeStyle = "#FFB500";
    const bx = 60, by = 130, bw = w - 120, bh = 780, L = 50;
    [[bx, by, 1, 1], [bx + bw, by, -1, 1], [bx, by + bh, 1, -1], [bx + bw, by + bh, -1, -1]].forEach(([x, y, sx, sy]) => {
      ctx.beginPath(); ctx.moveTo(x, y + sy * L); ctx.lineTo(x, y); ctx.lineTo(x + sx * L, y); ctx.stroke();
    });
    ctx.fillStyle = "#fff"; ctx.font = "600 30px Inter, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(state === "captured" ? "✓ Captured" : "Hold still · look at the lens", w / 2, 58);
    ctx.beginPath(); ctx.arc(w / 2, 995, 34, 0, Math.PI * 2); ctx.fillStyle = state === "captured" ? "#3ddc84" : "#fff"; ctx.fill();
    ctx.beginPath(); ctx.arc(w / 2, 995, 42, 0, Math.PI * 2); ctx.strokeStyle = "#fff"; ctx.lineWidth = 4; ctx.stroke();
    screenTex.needsUpdate = true;
  }
  paintScreen("off");

  const parts = [];
  function part(mesh, from, at) { if (at) mesh.position.set(at[0], at[1], at[2]); phone.add(mesh); parts.push({ mesh, to: mesh.position.clone(), toRot: mesh.rotation.clone(), from }); return mesh; }
  const back = part(new THREE.Mesh(new RoundedBoxGeometry(PW, PH, 0.1, 5, 0.2), bodyMat), { p: [0, -0.6, -1.8], r: [0.5, 0.9, 0.2] }, [0, 0, -0.03]);
  const bezel = part(new THREE.Mesh(new RoundedBoxGeometry(PW + 0.05, PH + 0.05, 0.06, 5, 0.22), frameMat), { p: [-2.6, 0.4, 0.4], r: [0, -0.8, 0.5] });
  const screen = part(new THREE.Mesh(new THREE.PlaneGeometry(PW - 0.12, PH - 0.14), new THREE.MeshBasicMaterial({ map: screenTex, toneMapped: false })), { p: [2.4, 1.2, 1.4], r: [-0.4, 0.7, -0.3] }, [0, 0, 0.056]);
  const glass = part(new THREE.Mesh(new RoundedBoxGeometry(PW - 0.02, PH - 0.02, 0.02, 4, 0.2), new THREE.MeshPhysicalMaterial({ color: 0xffffff, transmission: 0, transparent: true, opacity: 0.08, roughness: 0, clearcoat: 1 })), { p: [0.2, 2.6, 1.8], r: [0.9, 0, 0] }, [0, 0, 0.066]);
  const bump = part(new THREE.Mesh(new RoundedBoxGeometry(0.62, 0.62, 0.08, 4, 0.12), bodyMat), { p: [2.2, -1.6, -1.2], r: [0, 1.2, 0.8] }, [-0.36, 1.08, -0.11]);
  const lensGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.06, 32);
  [[-0.49, 1.2], [-0.23, 1.2], [-0.49, 0.95]].forEach(([x, y], i) => {
    const lens = new THREE.Group();
    const l = new THREE.Mesh(lensGeo, glassMat);
    l.rotation.x = Math.PI / 2;
    const r = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.012, 8, 32), frameMat);
    lens.add(l, r);
    lens.position.set(x, y, -0.17);
    part(lens, { p: [-1.8 + i * 1.3, -2.2, -0.6], r: [0, 0, 2] });
  });
  const button = part(new THREE.Mesh(new RoundedBoxGeometry(0.04, 0.42, 0.06, 2, 0.02), frameMat), { p: [2.8, 0.6, 0], r: [0, 0, 1.4] }, [PW / 2 + 0.04, 0.6, 0]);

  phone.position.set(0.15, 0.05, 0);
  phone.rotation.set(0.05, -0.32, 0.02);

  /* ---------- the photo (dissolving background shader) ---------- */
  const PWP = 1.8, PHP = 2.4;
  const photoMat = new THREE.ShaderMaterial({
    transparent: true,
    toneMapped: false,
    uniforms: {
      uOrig: { value: texOrig },
      uMatte: { value: texMatte },
      uClean: { value: 0 },
      uLight: { value: 0 },
      uScaleX: { value: 1 },
      uOpacity: { value: 0 },
      uEdge: { value: GOLD },
      uTime: { value: 0 },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uOrig; uniform sampler2D uMatte;
      uniform float uClean; uniform float uLight; uniform float uScaleX; uniform float uOpacity; uniform float uTime;
      uniform vec3 uEdge;
      varying vec2 vUv;
      float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float noise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.0-2.0*f);
        return mix(mix(hash(i),hash(i+vec2(1,0)),u.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x), u.y); }
      void main() {
        vec2 uv = vec2(0.5 + (vUv.x - 0.5) * uScaleX, vUv.y);
        bool inside = uv.x >= 0.0 && uv.x <= 1.0;
        vec3 col = inside ? texture2D(uOrig, uv).rgb : vec3(1.0);
        float matte = inside ? texture2D(uMatte, uv).r : 0.0;
        // light balance: gentle lift of shadows on the person
        col = mix(col, pow(col, vec3(0.86)) * 1.04, uLight * matte);
        // background dissolve with a travelling noise front
        float n = noise(uv * 9.0) * 0.55 + noise(uv * 23.0) * 0.3 + (1.0 - uv.y) * 0.25;
        float front = uClean * 1.25 - 0.1;
        float gone = smoothstep(n - 0.03, n + 0.03, front);
        float edge = (smoothstep(n - 0.09, n, front) - smoothstep(n, n + 0.09, front)) * (1.0 - matte);
        vec3 bg = mix(col, vec3(1.0), gone);
        col = mix(bg, col, matte);
        col += uEdge * edge * 1.6 * (1.0 - step(0.999, uClean));
        gl_FragColor = vec4(col * 0.93, uOpacity);
        #include <colorspace_fragment>
      }`,
  });
  const photoRig = new THREE.Group(); // position / tilt / scale in the world
  scene.add(photoRig);
  const photo = new THREE.Mesh(new THREE.PlaneGeometry(PWP, PHP), photoMat);
  photoRig.add(photo);
  // thin white card border behind the photo
  const card = new THREE.Mesh(new THREE.PlaneGeometry(PWP + 0.12, PHP + 0.12), new THREE.MeshBasicMaterial({ color: 0xededed, transparent: true, opacity: 0, toneMapped: false }));
  card.position.z = -0.005;
  card.renderOrder = 1;
  photo.renderOrder = 2;
  photoRig.add(card);

  /* frame outline (gold) around the programme's crop */
  const frameGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-0.5, -0.5, 0), new THREE.Vector3(0.5, -0.5, 0), new THREE.Vector3(0.5, 0.5, 0), new THREE.Vector3(-0.5, 0.5, 0), new THREE.Vector3(-0.5, -0.5, 0),
  ]);
  const frameLine = new THREE.Line(frameGeo, new THREE.LineBasicMaterial({ color: GOLD, transparent: true, opacity: 0, toneMapped: false }));
  frameLine.position.z = 0.02;
  frameLine.renderOrder = 7;
  photoRig.add(frameLine);

  /* face mesh from the real landmarks */
  const meshGroup = new THREE.Group();
  photoRig.add(meshGroup);
  let meshPoints = null, meshLines = null, POINTS = 0, EDGES = 0;
  const faceInfo = meshData ? meshData.face : { cx: 0.5, cy: 0.42, headTop: 0.18, chin: 0.66 };
  if (meshData) {
    const pts = meshData.points;
    POINTS = pts.length;
    const pos = new Float32Array(POINTS * 3);
    pts.forEach(([x, y, z], i) => { pos[i * 3] = (x - 0.5) * PWP; pos[i * 3 + 1] = (0.5 - y) * PHP; pos[i * 3 + 2] = 0.02 - z * PWP * 0.5; });
    const pg = new THREE.BufferGeometry();
    pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    // order points top → bottom so the mesh "draws" down the face
    const order = pts.map((p, i) => [p[1], i]).sort((a, b) => a[0] - b[0]).map((p) => p[1]);
    pg.setIndex(order);
    meshPoints = new THREE.Points(pg, new THREE.PointsMaterial({ size: full ? 0.05 : 0.06, map: dotTex, color: GOLD, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    const edges = meshData.edges;
    EDGES = edges.length;
    const epos = new Float32Array(EDGES * 6);
    edges.sort((a, b) => Math.min(pts[a[0]][1], pts[a[1]][1]) - Math.min(pts[b[0]][1], pts[b[1]][1]));
    edges.forEach(([a, b], i) => { epos.set(pos.subarray(a * 3, a * 3 + 3), i * 6); epos.set(pos.subarray(b * 3, b * 3 + 3), i * 6 + 3); });
    const eg = new THREE.BufferGeometry();
    eg.setAttribute("position", new THREE.BufferAttribute(epos, 3));
    meshLines = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: GOLD_SOFT, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    meshLines.renderOrder = 5;
    meshPoints.renderOrder = 6;
    meshGroup.add(meshLines, meshPoints);
  }

  /* measuring guides: eye line, centre line, head-height bracket */
  const guideMat = new THREE.LineBasicMaterial({ color: GOLD, transparent: true, opacity: 0, toneMapped: false });
  function guide(points) { const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map((p) => new THREE.Vector3(p[0], p[1], 0.04))), guideMat); l.renderOrder = 7; photoRig.add(l); return l; }
  const eyeY = (0.5 - (faceInfo.headTop + (faceInfo.chin - faceInfo.headTop) * 0.47)) * PHP;
  const topY = (0.5 - faceInfo.headTop) * PHP, chinY = (0.5 - faceInfo.chin) * PHP;
  const cxW = (faceInfo.cx - 0.5) * PWP;
  const eyeLine = guide([[-PWP * 0.42, eyeY], [PWP * 0.42, eyeY]]);
  const centreLine = guide([[cxW, PHP * 0.46], [cxW, -PHP * 0.46]]);
  const bx = PWP * 0.43;
  const bracket = guide([[bx - 0.08, topY], [bx, topY], [bx, chinY], [bx - 0.08, chinY]]);
  const guides = [eyeLine, centreLine, bracket];

  /* scan beam */
  const beamTex = canvasTexture(8, 256, (ctx, w, h) => {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, "rgba(255,181,0,0)"); g.addColorStop(0.5, "rgba(255,200,60,0.95)"); g.addColorStop(1, "rgba(255,181,0,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  });
  const beam = new THREE.Mesh(new THREE.PlaneGeometry(PWP * 1.1, 0.22), new THREE.MeshBasicMaterial({ map: beamTex, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
  beam.position.z = 0.05;
  beam.renderOrder = 8;
  photoRig.add(beam);

  /* ---------- flags (Rules chapter) ---------- */
  const flagGroup = new THREE.Group();
  scene.add(flagGroup);
  const flagCards = flagImgs.map((img, i) => {
    const tex = canvasTexture(320, 240, (ctx, w, h) => {
      ctx.save(); roundRect(ctx, 0, 0, w, h, 26); ctx.clip();
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h);
      if (img) ctx.drawImage(img, 10, 10, w - 20, h - 20);
      ctx.restore();
      ctx.strokeStyle = "rgba(255,255,255,0.9)"; ctx.lineWidth = 8; roundRect(ctx, 4, 4, w - 8, h - 8, 24); ctx.stroke();
    });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(0.72, 0.54), new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0, toneMapped: false }));
    flagGroup.add(m);
    return m;
  });
  // programme crops (width / height) and head bracket share for each flag
  const SPECS = { ca: { aspect: 50 / 70, label: "Canada · 50 × 70 mm" }, us: { aspect: 1, label: "United States · 2 × 2 in" }, in: { aspect: 1, label: "India OCI · 51 × 51 mm" }, gb: { aspect: 35 / 45, label: "United Kingdom · 35 × 45 mm" } };
  const flagSpecs = flagCodes.map((c) => SPECS[c]);

  /* ---------- passport booklet + printer (Ready chapter) ---------- */
  const booklet = new THREE.Group();
  scene.add(booklet);
  const BW = 1.9, BH = 2.6;
  const coverTex = canvasTexture(512, 700, (ctx, w, h) => {
    ctx.fillStyle = "#3a1a12"; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(255,181,0,0.35)"; ctx.lineWidth = 3; ctx.strokeRect(24, 24, w - 48, h - 48);
    ctx.fillStyle = "#FFB500"; ctx.textAlign = "center";
    ctx.font = "800 44px Manrope, sans-serif"; ctx.fillText("PASSPORT", w / 2, 150);
    ctx.font = "600 22px Inter, sans-serif"; ctx.fillText("SPECIMEN · PASSPORTLENS", w / 2, 190);
    ctx.lineWidth = 6; ctx.strokeStyle = "#FFB500";
    ctx.beginPath(); ctx.arc(w / 2, 380, 110, 0, Math.PI * 2); ctx.stroke();
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.ellipse(w / 2, 380, 50, 110, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(w / 2 - 110, 380); ctx.lineTo(w / 2 + 110, 380); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(w / 2 - 95, 325); ctx.lineTo(w / 2 + 95, 325); ctx.moveTo(w / 2 - 95, 435); ctx.lineTo(w / 2 + 95, 435); ctx.stroke();
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(w / 2 - 34, 600, 68, 44, 8) : ctx.rect(w / 2 - 34, 600, 68, 44); ctx.stroke();
  });
  const pageTex = canvasTexture(512, 700, (ctx, w, h) => {
    ctx.fillStyle = "#fbf6ea"; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(122,85,0,0.10)"; ctx.lineWidth = 1.2;
    for (let i = 0; i < 60; i++) { ctx.beginPath(); ctx.ellipse(w / 2, h / 2, 40 + i * 6, 20 + i * 9, i * 0.05, 0, Math.PI * 2); ctx.stroke(); }
    // photo slot + placeholder text lines (not a real document layout)
    ctx.strokeStyle = "rgba(53,28,21,0.35)"; ctx.lineWidth = 2; ctx.strokeRect(46, 160, 190, 262);
    ctx.fillStyle = "rgba(53,28,21,0.55)";
    for (let i = 0; i < 7; i++) { ctx.fillRect(268, 170 + i * 38, 90 + ((i * 37) % 110), 10); ctx.fillStyle = "rgba(53,28,21,0.25)"; ctx.fillRect(268, 186 + i * 38, 170, 6); ctx.fillStyle = "rgba(53,28,21,0.55)"; }
    ctx.font = "600 20px ui-monospace, monospace"; ctx.fillStyle = "rgba(53,28,21,0.55)";
    ctx.fillText("SPECIMEN<<PASSPORTLENS<<<<<<<<<<<<", 40, 620);
    ctx.fillText("0000000<0XXX0000000X0000000<<<<<<<0", 40, 652);
  });
  const backCover = new THREE.Mesh(new RoundedBoxGeometry(BW, BH, 0.05, 3, 0.05), new THREE.MeshPhysicalMaterial({ color: 0x3a1a12, roughness: 0.6, clearcoat: 0.3 }));
  backCover.position.set(BW / 2, 0, -0.03);
  const dataPage = new THREE.Mesh(new THREE.PlaneGeometry(BW - 0.08, BH - 0.08), new THREE.MeshBasicMaterial({ map: pageTex, toneMapped: false }));
  dataPage.position.set(BW / 2, 0, 0.001);
  booklet.add(backCover, dataPage);
  const coverPivot = new THREE.Group(); // hinge on the spine (x = 0)
  booklet.add(coverPivot);
  const frontCover = new THREE.Mesh(new RoundedBoxGeometry(BW, BH, 0.05, 3, 0.05), [
    new THREE.MeshPhysicalMaterial({ color: 0x3a1a12, roughness: 0.6 }), new THREE.MeshPhysicalMaterial({ color: 0x3a1a12, roughness: 0.6 }),
    new THREE.MeshPhysicalMaterial({ color: 0x3a1a12, roughness: 0.6 }), new THREE.MeshPhysicalMaterial({ color: 0x3a1a12, roughness: 0.6 }),
    new THREE.MeshPhysicalMaterial({ map: coverTex, roughness: 0.55, clearcoat: 0.4 }), new THREE.MeshPhysicalMaterial({ color: 0xf3ead4, roughness: 0.9 }),
  ]);
  frontCover.position.set(BW / 2, 0, 0.04);
  coverPivot.add(frontCover);
  // photo slot position on the data page (booklet space): matches the canvas slot
  const SLOT = { x: ((46 + 95) / 512) * BW - 0.04, y: (0.5 - (160 + 131) / 700) * BH, w: (190 / 512) * BW * 0.96 };

  const stampTex = canvasTexture(400, 400, (ctx, w, h) => {
    ctx.translate(w / 2, h / 2); ctx.rotate(-0.22);
    ctx.strokeStyle = "#3ddc84"; ctx.fillStyle = "#3ddc84";
    ctx.lineWidth = 12; ctx.beginPath(); ctx.arc(0, 0, 170, 0, Math.PI * 2); ctx.stroke();
    ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(0, 0, 140, 0, Math.PI * 2); ctx.stroke();
    ctx.textAlign = "center"; ctx.font = "800 64px Manrope, sans-serif"; ctx.fillText("PHOTO OK", 0, 20);
    ctx.font = "700 26px Inter, sans-serif"; ctx.fillText("✓ READY TO SUBMIT", 0, 70);
    ctx.font = "700 22px Inter, sans-serif"; ctx.fillText("PASSPORTLENS", 0, -60);
  });
  const stamp = new THREE.Mesh(new THREE.PlaneGeometry(1.35, 1.35), new THREE.MeshBasicMaterial({ map: stampTex, transparent: true, opacity: 0, depthWrite: false, toneMapped: false }));
  booklet.add(stamp);

  const printer = new THREE.Group();
  scene.add(printer);
  const pBody = new THREE.Mesh(new RoundedBoxGeometry(2.1, 0.9, 1.3, 5, 0.16), new THREE.MeshPhysicalMaterial({ color: 0x241611, metalness: 0.4, roughness: 0.35, clearcoat: 0.8 }));
  const pSlot = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.05, 0.06), new THREE.MeshBasicMaterial({ color: 0x000000 }));
  pSlot.position.set(0, 0.15, 0.66);
  const pLed = new THREE.Mesh(new THREE.CircleGeometry(0.045, 20), new THREE.MeshBasicMaterial({ color: 0x3ddc84, toneMapped: false }));
  pLed.position.set(0.82, -0.22, 0.66);
  const pStrip = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.03, 0.02), new THREE.MeshBasicMaterial({ color: GOLD, toneMapped: false }));
  pStrip.position.set(0, -0.42, 0.66);
  printer.add(pBody, pSlot, pLed, pStrip);
  const sheetTex = canvasTexture(600, 400, (ctx, w, h) => {
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(0,0,0,0.25)"; ctx.setLineDash([6, 6]); ctx.lineWidth = 2;
    const pw = 150, ph = 210;
    [[70, 95], [250, 95], [430, 95]].slice(0, 2).forEach(([x, y]) => {
      if (imgFinal) drawCover(ctx, imgFinal, x, y, pw, ph); else { ctx.fillStyle = "#ddd"; ctx.fillRect(x, y, pw, ph); }
      ctx.strokeRect(x - 8, y - 8, pw + 16, ph + 16);
    });
    ctx.setLineDash([]); ctx.fillStyle = "#351C15"; ctx.font = "700 20px Inter, sans-serif";
    ctx.fillText("4 × 6 in · 300 DPI · cut guides", 430, 360);
    ctx.fillStyle = "#1F8A4C"; ctx.font = "800 26px Manrope, sans-serif"; ctx.fillText("✓ Photo OK", 440, 140);
  });
  const sheet = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.0), new THREE.MeshBasicMaterial({ map: sheetTex, transparent: true, opacity: 0, toneMapped: false }));
  printer.add(sheet);

  // Bloom was tried and lifted the whole stage to muddy brown; the glow comes
  // from additive sprites instead, which is also cheaper on every device.
  const composer = null;

  /* ---------- sizing ---------- */
  let W = 1, H = 1;
  function resize() {
    const r = stage.getBoundingClientRect();
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    renderer.setSize(W, H, false);
    if (composer) composer.setSize(W, H);
    camera.aspect = W / H;
    // keep the story framed on tall/narrow stages
    camera.fov = W / H < 0.9 ? 34 + (0.9 - W / H) * 20 : 32;
    camera.updateProjectionMatrix();
  }
  resize();
  new ResizeObserver(resize).observe(stage);

  /* ---------- intro (time based) ---------- */
  const intro = { t: reduceMotion ? 1 : 0 };
  function startIntro() {
    if (reduceMotion || !A || !A.animate) { intro.t = 1; return; }
    A.animate(intro, { t: [0, 1], duration: 3600, ease: "linear" });
  }

  /* ---------- scroll progress ---------- */
  let target = 0, prog = 0;
  function readScroll() {
    const r = story.getBoundingClientRect();
    const total = r.height - innerHeight;
    target = clamp(-r.top / Math.max(1, total));
  }
  addEventListener("scroll", readScroll, { passive: true });
  readScroll();
  prog = target;

  let mx = 0, my = 0, pmx = 0, pmy = 0;
  addEventListener("pointermove", (e) => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; }, { passive: true });

  /* ---------- per-frame choreography ---------- */
  const tmpV = new THREE.Vector3();
  const slotWorld = new THREE.Vector3();
  const bus = window.PL_STORY = { progress: 0, chapter: 0, specIndex: 0, tilt: 8, tier, intro };

  function update(time) {
    const t = time / 1000;
    prog += (target - prog) * (reduceMotion || SNAP ? 1 : 0.12);
    const p = prog;
    bus.progress = p;

    const it = intro.t;
    // ---- intro: parts fly together, phone turns, screen wakes, flash
    const assemble = easeOut(seg(it, 0, 0.55));
    parts.forEach((pt, i) => {
      const k = easeOut(seg(it, i * 0.035, 0.42 + i * 0.035));
      pt.mesh.position.set(lerp(pt.to.x + pt.from.p[0], pt.to.x, k), lerp(pt.to.y + pt.from.p[1], pt.to.y, k), lerp(pt.to.z + pt.from.p[2], pt.to.z, k));
      pt.mesh.rotation.set(lerp(pt.from.r[0], pt.toRot.x, k), lerp(pt.from.r[1], pt.toRot.y, k), lerp(pt.from.r[2], pt.toRot.z, k));
    });
    const turn = ease(seg(it, 0.45, 0.7));
    paintScreen(it < 0.6 ? "off" : it < 0.82 ? "live" : "captured");
    const f = seg(it, 0.8, 0.95);
    flash.intensity = bell(f) * 40;
    stage.style.setProperty("--flash", String(bell(f) * 0.85));

    // ---- hero → scan: phone steps back, the photo comes forward
    const out = ease(seg(p, 0.07, 0.19));
    const idle = reduceMotion ? 0 : Math.sin(t * 0.9) * 0.06;
    phone.visible = out < 0.999;
    phone.position.set(lerp(0.15, -2.6, out), lerp(0.05, -0.2, out) + idle * (1 - out), lerp(0, -2.2, out));
    phone.rotation.set(0.05 + (1 - assemble) * 0.3, lerp(-0.32 + (1 - turn) * Math.PI, -0.9, out) + idle * 0.3, 0.02);
    phone.scale.setScalar(lerp(1, 0.7, out));

    // ---- photo rig base placement
    const photoIn = ease(seg(p, 0.08, 0.2));
    const tScan = seg(p, CH.scan[0], CH.scan[1]);
    const tClean = seg(p, CH.clean[0], CH.clean[1]);
    const tRules = seg(p, CH.rules[0], CH.rules[1]);
    const tReady = seg(p, CH.ready[0], CH.ready[1]);

    let px = lerp(0.15, 0, photoIn), py = lerp(0.05, 0.05, photoIn), pz = lerp(0.06, 0.4, photoIn);
    let ps = lerp(0.72, 1, photoIn);
    let tilt = lerp(0, 0.14, photoIn) * (1 - ease(seg(tScan, 0.35, 0.75)));
    bus.tilt = Math.round((tilt / 0.14) * 8);
    photoMat.uniforms.uOpacity.value = photoIn;
    card.material.opacity = photoIn * ease(seg(tClean, 0.6, 1));

    // scan
    const drawPts = ease(seg(tScan, 0.05, 0.45));
    const drawEdges = ease(seg(tScan, 0.18, 0.62));
    const meshFade = 1 - ease(seg(tClean, 0.0, 0.35));
    if (meshPoints) {
      meshPoints.geometry.setDrawRange(0, Math.floor(POINTS * drawPts));
      meshPoints.material.opacity = 0.95 * meshFade * (tScan > 0 ? 1 : 0);
      meshLines.geometry.setDrawRange(0, Math.floor(EDGES * drawEdges) * 2);
      meshLines.material.opacity = 0.55 * meshFade * (tScan > 0 ? 1 : 0);
    }
    beam.material.opacity = bell(seg(tScan, 0.0, 0.55)) * 0.9;
    beam.position.y = lerp(PHP * 0.5, -PHP * 0.5, seg(tScan, 0.0, 0.55));
    const gShow = ease(seg(tScan, 0.55, 0.9)) * (1 - ease(seg(tReady, 0.05, 0.2)));
    guideMat.opacity = gShow * (tRules > 0 ? 0.55 : 0.95);
    guides.forEach((g, i) => { g.scale.x = i === 1 ? 1 : lerp(0.001, 1, ease(seg(tScan, 0.55 + i * 0.08, 0.85 + i * 0.05))); });

    // clean
    photoMat.uniforms.uClean.value = ease(seg(tClean, 0.08, 0.85));
    photoMat.uniforms.uLight.value = ease(seg(tClean, 0.5, 1));

    // rules: step through four programmes, re-crop the frame
    const flagsIn = ease(seg(tRules, 0, 0.12)) * (1 - ease(seg(tReady, 0.0, 0.12)));
    const a = clamp(seg(tRules, 0.1, 0.92) * 3, 0, 3); // 0..3 continuous
    const idx = Math.round(a);
    bus.specIndex = idx;
    let aspect = flagSpecs[0].aspect;
    { const i0 = Math.floor(a), i1 = Math.min(3, i0 + 1), k = ease(a - i0); aspect = lerp(flagSpecs[i0].aspect, flagSpecs[i1].aspect, k); }
    const crop = tRules > 0 ? aspect / (PWP / PHP) : 1; // relative width
    const scaleX = lerp(1, crop, ease(seg(tRules, 0.02, 0.14)));
    photo.scale.x = scaleX;
    card.scale.x = scaleX;
    photoMat.uniforms.uScaleX.value = scaleX;
    frameLine.scale.set(PWP * scaleX + 0.02, PHP + 0.02, 1);
    frameLine.material.opacity = flagsIn;
    flagCards.forEach((m, i) => {
      const prox = clamp(1 - Math.abs(i - a));
      m.material.opacity = flagsIn * (0.35 + 0.65 * prox);
      m.position.set(1.18 + PWP * 0.5 * (scaleX - 1) * 0.6 - prox * 0.1, 0.95 - i * 0.62, 0.5 + prox * 0.2);
      m.scale.setScalar(0.78 + prox * 0.34);
      m.rotation.y = -0.25 + prox * 0.25;
    });
    flagGroup.visible = flagsIn > 0.001;
    px -= flagsIn * 0.6;

    // ready: booklet opens, photo slides into the slot, cover closes, stamp, printer
    const bookIn = ease(seg(tReady, 0.0, 0.2));
    const toSlot = ease(seg(tReady, 0.12, 0.34));
    const close = ease(seg(tReady, 0.36, 0.56));
    const stampT = seg(tReady, 0.56, 0.68);
    const printIn = ease(seg(tReady, 0.68, 0.82));
    const sheetOut = ease(seg(tReady, 0.8, 0.98));
    booklet.visible = bookIn > 0.001;
    const bookX = lerp(0, -0.95, printIn), bookS = lerp(lerp(0.62, 0.82, close), 0.55, printIn);
    booklet.position.set(bookX + lerp(0, -BW / 2, close) * bookS, lerp(-3.4, 0.1, bookIn) + lerp(0, 0.35, printIn), lerp(-1, 0, bookIn));
    booklet.scale.setScalar(bookS * lerp(0.9, 1, bookIn));
    booklet.rotation.set(lerp(-0.5, -0.12, bookIn), lerp(0.3, 0.12, bookIn) + close * 0.18, 0);
    coverPivot.rotation.y = lerp(-Math.PI + 0.02, 0, close);
    stamp.position.set(BW / 2, -0.05, 0.1);
    stamp.material.opacity = ease(stampT);
    stamp.scale.setScalar(lerp(2.4, 1, easeOut(stampT)));
    stamp.visible = stampT > 0;

    if (tReady > 0) {
      booklet.updateMatrixWorld(true);
      slotWorld.set(SLOT.x, SLOT.y, 0.02).applyMatrix4(booklet.matrixWorld);
      const slotScale = (SLOT.w / (PWP * scaleX)) * booklet.scale.x;
      px = lerp(px, slotWorld.x, toSlot);
      py = lerp(py, slotWorld.y, toSlot);
      pz = lerp(pz, slotWorld.z, toSlot);
      ps = lerp(ps, slotScale, toSlot);
      tilt = lerp(tilt, 0, toSlot);
    }
    // once the cover closes the photo is inside the booklet
    photoRig.visible = !(close > 0.55);
    photoRig.position.set(px, py + (reduceMotion ? 0 : Math.sin(t * 0.8) * 0.03 * (1 - toSlot)), pz);
    photoRig.rotation.set(tReady > 0 ? booklet.rotation.x * toSlot : 0, (tReady > 0 ? booklet.rotation.y * toSlot : 0) + (1 - toSlot) * (pmx * -0.12), tilt);
    photoRig.scale.setScalar(ps);

    printer.visible = printIn > 0.001;
    printer.position.set(lerp(3.2, 0.95, printIn), lerp(-2.6, -1.05, printIn), 0.3);
    printer.scale.setScalar(0.72);
    printer.rotation.set(0.18, -0.35, 0);
    sheet.material.opacity = sheetOut > 0 ? 1 : 0;
    sheet.position.set(0, lerp(0.1, 0.85, sheetOut), lerp(0.4, 0.95, sheetOut));
    sheet.rotation.x = lerp(-1.35, -0.35, sheetOut);
    pLed.material.color.set(sheetOut > 0 && sheetOut < 1 ? (Math.sin(t * 12) > 0 ? 0xffb500 : 0x3ddc84) : 0x3ddc84);

    // stage props
    plinth.position.y = lerp(-2.0, -2.4, bookIn);
    ring.material.color.copy(GOLD).multiplyScalar(0.7 + 0.3 * Math.sin(t * 1.6));
    const d = dustGeo.attributes.position.array;
    if (!reduceMotion) for (let i = 0; i < DUST; i++) { d[i * 3 + 1] += 0.0025 + Math.sin(t + dustSeed[i]) * 0.001; if (d[i * 3 + 1] > 3.5) d[i * 3 + 1] = -3.5; }
    dustGeo.attributes.position.needsUpdate = true;
    photoMat.uniforms.uTime.value = t;

    // camera: gentle parallax + chapter dolly
    pmx += (mx - pmx) * 0.05; pmy += (my - pmy) * 0.05;
    const dolly = lerp(8.2, 7.4, bell(tScan)) + lerp(0, 0.6, printIn);
    camera.position.set(pmx * 0.5, 0.75 - pmy * 0.3, dolly);
    camera.lookAt(tmpV.set(0, -0.15, 0));

    // chapter index for the captions / HUD
    const chapter = p < 0.09 ? 0 : p < CH.clean[0] ? 1 : p < CH.rules[0] ? 2 : p < CH.ready[0] ? 3 : 4;
    if (chapter !== bus.chapter) { bus.chapter = chapter; dispatchEvent(new CustomEvent("pl:chapter", { detail: chapter })); }
    dispatchEvent(new CustomEvent("pl:frame", { detail: bus }));
  }

  /* ---------- loop (only while the stage is on screen) ---------- */
  let visible = true, running = false;
  new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; if (visible) start(); }, { rootMargin: "100px" }).observe(stage);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) start(); });
  function frame(time) {
    if (!visible || document.hidden) { running = false; return; }
    update(time);
    if (composer) composer.render(); else renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  function start() { if (!running) { running = true; requestAnimationFrame(frame); } }

  docEl.classList.add("stage-ready");
  startIntro();
  start();
  dispatchEvent(new CustomEvent("pl:chapter", { detail: 0 }));
}
