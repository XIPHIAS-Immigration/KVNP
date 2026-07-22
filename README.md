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

- accounts: sign up / sign in / guest, local SQLite + signed session cookie
- premium app-shell UI (sidebar nav, top bar, login screen)
- image upload (multi-file batch queue)
- camera capture
- country and programme rule profiles
- Python MediaPipe Face Landmarker / FaceMesh processing
- Identity-preserving auto-correction: auto-straighten a tilted head and
  normalize exposure / white balance, with every applied correction disclosed
  in the result and report (geometry + tone only; the face is never altered)
- Layered background matting: optional MODNet portrait matting (ONNX) with an
  always-available MediaPipe segmenter fallback, single-subject cleanup, and
  guided-filter edge refinement for cleaner hair/shoulders (see `docs/matting.md`)
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
python tools/pipeline_smoketest.py    # run the full pipeline on sample portraits
```

`tools/pipeline_smoketest.py` writes generated photos and overlays to
`screenshots/smoketest/` so matte edges can be inspected by eye.

## Optional: MODNet matting

Higher-quality hair/shoulder edges are available by installing a MODNet ONNX
model. It is not bundled because MODNet pretrained weights are typically
non-commercial; review the license before using one in production. See
`docs/matting.md` and `scripts/fetch-modnet.ps1`.

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
