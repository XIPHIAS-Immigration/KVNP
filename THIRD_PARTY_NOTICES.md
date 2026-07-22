# Third-party notices & licensing

KVNP Passport Studio uses third-party models and libraries. **Before selling or
distributing this product, confirm each item below is cleared for commercial use
and reproduce its license/NOTICE as required.** This file is a starting checklist,
not legal advice.

## Models

| Component | Used for | License (verify) | Commercial-use note |
| --- | --- | --- | --- |
| MediaPipe Face Landmarker (`face_landmarker.task`) | face geometry | Apache-2.0 | Generally OK; keep Apache NOTICE |
| MediaPipe Selfie Segmenter (`selfie_segmenter.tflite`) | background matte | Apache-2.0 | Generally OK; keep Apache NOTICE |
| Real-ESRGAN NCNN (`realesrgan-ncnn-vulkan`, x4plus) | detail rescue | BSD-3 / MIT (code); **weights vary** | Verify the specific model weights' terms |
| FSRCNN (`FSRCNN_x2.pb`) | detail | check source | Verify origin/license before shipping |
| GFPGAN (`GFPGANv1.4.pth`) + facexlib weights | face restoration (rescue/"strong") | Apache-2.0 (code); **weights trained on FFHQ** | **Higher risk** — FFHQ/face-restoration weights may carry non-commercial/research terms. Audit before enabling in a paid build. |
| MODNet (`models/modnet.onnx`, optional) | portrait matting | **commonly non-commercial (CC BY-NC-SA)** | **Do NOT ship for commercial use** unless you have commercially-licensed weights. Not bundled; user-supplied only. |

## Assets / libraries

| Component | License | Note |
| --- | --- | --- |
| Inter font | SIL OFL 1.1 | OK to self-host & embed. Currently loaded from Google Fonts CDN — **self-host for offline + EU/GDPR** (hotlinking Google Fonts ships user IPs to Google). |
| FastAPI / Uvicorn / Starlette | MIT/BSD | OK |
| OpenCV (`opencv-contrib`) | Apache-2.0 | OK; some contrib/patented algos — verify none are used commercially-restricted |
| Pillow, NumPy, onnxruntime | permissive | OK |

## Test data

- `screenshots/eval/raw/*` are Pexels images used **only for local testing**. The
  Pexels license allows commercial use without attribution, but do **not** ship
  these as product assets/marketing without re-checking each image. They are dev
  fixtures, not part of the product.

## Action items before commercial release

- [ ] Confirm GFPGAN/facexlib weight terms; gate or remove the "strong"/Rescue path if non-commercial.
- [ ] Do not bundle MODNet weights; keep it user-supplied with the license warning.
- [ ] Self-host the Inter font; remove the Google Fonts `<link>`.
- [ ] Reproduce Apache-2.0 NOTICE files for MediaPipe/GFPGAN/OpenCV in the installer.
