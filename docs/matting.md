# Background matting

The studio replaces the background with a clean colour by estimating a per-pixel
alpha matte of the person, compositing the source over the target colour, then
cropping to the programme's output size.

## Engines (in priority order)

1. **MODNet Portrait Matting (optional, best edges).** Used automatically when
   `models/modnet.onnx` exists and `onnxruntime` is installed. Produces clean
   hair/shoulder edges from a single forward pass.
2. **MediaPipe Image Segmenter (default, bundled).** Apache-2.0 selfie
   segmenter. Always available; produces a coarser confidence mask that the
   pipeline then cleans and edge-refines.

Both engines run through the same post-processing so the output is consistent:

- **`keep_main_subject`** keeps the connected silhouette that the detected face
  actually sits in (falling back to the largest), and zeroes every other solid
  blob. Choosing by face — not just by area — means an inverted or weak matte
  whose largest blob is the *background* cannot silently erase the person. A
  small bounded edge-band dilation preserves the soft hair/shoulder alpha while
  still removing nearby coloured bleed.
- **`refine_matte_edges`** runs a guided filter (`cv2.ximgproc.guidedFilter`)
  using the source image as guide, aligning the alpha to real edges (hair,
  shoulders) instead of a blocky cutout. Falls back to a Gaussian feather if
  `ximgproc` is unavailable.

The cleanup, refinement, and diagnostics run at a capped working resolution
(`MATTE_WORK_MAX_SIDE`, 1280 px long side); only the final alpha is upsampled to
the source resolution for compositing, so a 12 MP phone photo stays fast.

## Honest matte diagnostics

`describe_mask` reports, and the "Background cleanup" check surfaces:

| field | meaning | warns when |
| --- | --- | --- |
| `coverage` | fraction of frame classified as person | < 0.12 or > 0.78 |
| `faceCoverage` | person coverage inside the face box | < 0.92 (fail < 0.82) |
| `softEdgePercent` | fraction of partially-transparent pixels | > 24 |
| `strayIslands` | disconnected person blobs after cleanup | > 0 |
| `holePercent` | background holes enclosed by the silhouette | > 0.8% |
| `shoulderCoverage` | person coverage in the lower-centre band (`null` if unmeasurable) | < 0.35 (clipped) |

These exist so the app does **not** mark a visibly broken matte (bleed, holes,
clipped shoulders) as `pass`. A very high `coverage` (> 0.97 of the whole frame)
is treated as an inverted/saturated matte and fails; a merely close-framed
subject is not penalised. When the matte engine is requested but produces
nothing, the cleanup check reports `mask unavailable` / the photo was **not**
background-replaced — never a benign "disabled".

## Enabling MODNet

MODNet pretrained weights are commonly released under a **non-commercial**
license (e.g. CC BY-NC-SA 4.0). They are intentionally **not** bundled or
auto-downloaded. To enable it, supply a MODNet ONNX export you are licensed to
use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch-modnet.ps1 -Url "<your-modnet-onnx-url>"
```

The expected ONNX contract: single image input `1x3xHxW`, RGB, normalized to
`[-1, 1]` (`(x/255 - 0.5) / 0.5`), single-channel alpha output in `[0, 1]`. The
backend resizes the input so the longer side is ~512 px (rounded to a multiple
of 32) for fast CPU inference, then upsamples the alpha to full resolution.

The loader also tolerates common export variations: channel-first or
channel-last outputs, and alpha emitted as raw logits or on a `[0, 255]` scale
(auto-normalized to `[0, 1]`).

After installing, restart the server. `/api/health` reports `"modnet": true`
only once the ONNX session has actually loaded and run — a present-but-broken
model reports `"modnet": false` (and `"error"` in the model inventory), with a
one-line reason logged to stderr, rather than falsely claiming MODNet is active
while every photo silently uses the MediaPipe fallback. When MODNet is genuinely
running, the pipeline panel shows **MODNet Portrait Matting** as the matting
engine, and each processed photo's matte stats name the engine that produced it.
