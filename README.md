# KVNP Holdings Inc Passport Photo Studio

A Python-backed passport and visa photo preparation studio.

## Run locally

Serve the studio with npm:

```powershell
npm run dev
```

Then open:

```text
http://localhost:4173
```

No `npm install` is required. The script starts `server.py`, which serves the browser UI and runs the Python MediaPipe processor.

## Current scope

- accounts: sign up / sign in / guest, Argon2 passwords, opaque revocable sessions
- customer workspace with named applications, purchase history, entitlements,
  re-download status, and support enquiries
- role-protected operations portal with revenue, order, download, funnel, and
  enquiry reporting
- PostgreSQL-ready transactional product schema with one-time import of legacy
  SQLite users; local development falls back to `data/platform.db`
- payment-provider boundary plus a locked mock checkout for entitlement testing;
  Slice remains disabled until merchant UAT credentials are supplied
- premium app-shell UI (sidebar nav, top bar, login screen)
- image upload (multi-file batch queue)
- camera capture
- country and programme rule profiles
- Python MediaPipe Face Landmarker / FaceMesh processing
- Identity-preserving auto-correction: auto-straighten a tilted head and
  normalize exposure / white balance, with every applied correction disclosed
  in the result and report (geometry + tone only; the face is never altered)
- Layered background matting: BiRefNet Portrait for quality still-image alpha,
  optional MODNet for lighter CPU inference, and MediaPipe only as the fast
  fallback/live-guidance engine (see `docs/matting.md`)
- Honest matte diagnostics (stray islands, enclosed holes, shoulder coverage)
- Before/after comparison slider, draggable, on every generated photo
- Batch queue: upload several photos, step through them, per-job status dots
- Print sheets: tile the photo onto 4x6 / 5x7 / A4 / Letter with DPI + copies
  controls and cut guides (e.g. six 2x2 in photos on a 4x6) via `/api/print-sheet`
- Capture-quality gates measured on the ORIGINAL photo (corrections never mask a
  retake-worthy capture); strict "no alteration" programmes flag applied edits
- OpenCV contrib studio enhancement pipeline
- optional FSRCNN super-resolution refinement when the model is available
- automatic crop and head-position calculation
- clean background replacement
- white balance, denoise, color, contrast, and sharpness enhancement
- programme-specific JPEG compression targets
- manual head-position override
- pose, expression, quality, background, and file-size checks
- JPEG export
- JSON validation report

The first Python backend start downloads official MediaPipe model files into `models/` if they are missing. The checker compares images against published requirements encoded in `src/rules.js`. It does not claim official government approval.

## Tests

```powershell
python -m py_compile server.py        # backend syntax check
python tools/test_matting.py          # matting + diagnostics regression tests
python tools/test_corrections.py      # auto-correction (straighten / tone) tests
python tools/test_print_sheet.py      # print-sheet layout tests
python tools/test_platform.py         # accounts, orders, entitlements, admin
python tools/test_workflow.py         # staged browser workflow regressions
python tools/pipeline_smoketest.py    # run the full pipeline on sample portraits
```

`tools/pipeline_smoketest.py` writes generated photos and overlays to
`screenshots/smoketest/` so matte edges can be inspected by eye.

## Quality portrait matting

Docker Compose downloads and checksum-verifies the BiRefNet Portrait ONNX model
into the persistent `kvnp_models` volume before the app starts. The weight is
not committed to Git and is not re-downloaded after ordinary rebuilds. Set
`KVNP_QUALITY_MODEL=none` to keep a lightweight MediaPipe/MODNet-only install.
BiRefNet's official repository is MIT licensed; retain third-party notices and
review the exact weight provenance before a commercial release.


## Docker / AWS demo

Deployment files are included for a short EC2 demo:

- `requirements-base.txt` - shared Python runtime dependencies
- `requirements.txt` / `Dockerfile` - CPU ONNX Runtime deployment
- `requirements-gpu.txt` / `Dockerfile.gpu` - NVIDIA CUDA deployment
- `compose.yaml` - app + Caddy HTTPS reverse proxy
- `compose.gpu.yaml` - GPU override for the app service
- `compose.postgres.yaml` - PostgreSQL persistence override
- `Caddyfile` - automatic HTTPS for the configured domain
- `.env.example` - production environment template
- `docs/aws-ec2-demo.md` - EC2 + GoDaddy deployment runbook

For local Docker smoke testing:

```powershell
docker build -t kvnp-passport-studio .
docker run --rm -p 4173:4173 -e HOST=0.0.0.0 -e KVNP_SESSION_SECRET=dev-secret kvnp-passport-studio
```

For the AWS demo, follow `docs/aws-ec2-demo.md`.

On an NVIDIA host with the driver and NVIDIA Container Toolkit installed, run:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
docker compose -f compose.yaml -f compose.gpu.yaml exec -T app \
  python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

The provider check must include `CUDAExecutionProvider`; `/api/health` reports
the quality model inventory and the active provider after the first matte job.

For the production database, set `POSTGRES_PASSWORD` and
`KVNP_COOKIE_SECURE=true` in `.env`, then include the PostgreSQL override:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.postgres.yaml up -d --build
```

Create the administrator as an ordinary account first, then promote it from the
server shell. This prevents a public signup from claiming an administrator email:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml -f compose.postgres.yaml exec -T app \
  python tools/promote_admin.py admin@example.com
```

Commerce defaults to `disabled`, so deployment does not expose a fake checkout.
For local entitlement testing only, set `KVNP_PAYMENT_MODE=mock` and
`KVNP_ALLOW_MOCK_PAYMENTS=true`. Keep `KVNP_COMMERCE_ENFORCED=false` until a real
provider webhook can grant entitlements.

## Current starter programmes

- United States passport
- United States visa / DS-160
- United States diversity visa
- United Kingdom passport digital upload
- India passport ICAO upload
- India visa online / e-Visa
- Canada passport digital photo
- Canada temporary resident visa
- Australia passport
- France / Schengen visa

