# Background matting

The studio estimates a per-pixel alpha matte, composites the original portrait
over the selected backdrop, then crops the result to the programme output size.
Background replacement is only offered as a submission file where the selected
programme permits it. Strict programmes may expose a watermarked preview only.

## Engines

1. **BiRefNet Portrait Matting (quality default).** Runs at 1024 x 1024 for
   final still-image alpha. It loads lazily and selects CUDA when ONNX Runtime
   exposes it, otherwise CPU.
2. **MODNet Portrait Matting (optional lighter fallback).** Used when
   `models/modnet.onnx` exists and BiRefNet is unavailable.
3. **MediaPipe Image Segmenter (bundled fallback).** A fast 256 x 256 selfie
   segmentation model used for live guidance and when neither matting model is
   available. Its mask is not treated as export-grade.

The quality checkpoint is a 1024 x 1024 portrait model. It materially improves
curls, ears, jaw edges, and shoulders over the old selfie mask, but an extremely
thin detached strand can still be missed. The UI must keep matte review visible
and recommend a retake when the edge audit is uncertain; it must never call a
model result flawless.

Set `KVNP_MATTING_ENGINE=birefnet|modnet|mediapipe|auto` to choose the preferred
engine. Every result and audit report records the engine that actually ran.

## Model-aware processing

- `keep_main_subject` selects the component containing the detected face and
  removes distant foreground islands. The BiRefNet path retains nearby detached
  curls and flyaway hair inside a bounded edge band.
- `refine_matte_edges` uses a guided filter only for coarse fallback masks.
- `refine_output_matte` may use a GrabCut trimap for coarse masks. BiRefNet's
  learned alpha bypasses this classification so translucent curls, ears and
  shoulder edges are not deleted after inference.
- `protect_head_and_neck` is a fallback guard for coarse masks. It is not drawn
  over a BiRefNet matte.
- `decontaminate_foreground` reduces the old backdrop colour carried by
  semi-transparent hair pixels before compositing.

## Diagnostics

`describe_mask` reports coverage, face coverage, soft-edge percentage, stray
islands, enclosed holes and shoulder coverage. An unavailable or unreliable
matte is surfaced as a warning or failure; it is never reported as a successful
background replacement.

## Installing BiRefNet

Docker Compose runs the verified model installer before the app:

```bash
docker compose run --rm model-init
docker compose up -d
```

The approximately 973 MB ONNX file lives in the persistent `kvnp_models`
volume and is verified against the checksum published by rembg. It is not
committed to Git and is not downloaded again after ordinary rebuilds. Set
`KVNP_QUALITY_MODEL=none` to skip it.

`KVNP_ONNX_PROVIDER=auto` prefers CUDA, then OpenVINO, then CPU.
`KVNP_ONNX_THREADS` bounds CPU inference threads. `/api/health` reports whether
the model is installed without eagerly loading the graph; the first background
job creates the session and logs the active execution provider.

Use `compose.gpu.yaml` on NVIDIA hosts. It swaps only the app image to the CUDA
runtime and requests one GPU; the model downloader and Caddy remain lightweight
CPU services. CPU is still a supported fallback, but measured inference on the
development machine is about 20-22 seconds per portrait.

BiRefNet's official repository is MIT licensed and the rembg converter is MIT
licensed. Retain their notices and review the exact model provenance before a
commercial release. MODNet's official repository publishes its code and models
under Apache 2.0.
