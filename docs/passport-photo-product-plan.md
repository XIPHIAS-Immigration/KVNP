# Passport Photo Compliance Software Plan

## Working thesis

Passport and visa photo requirements are usually published by government agencies or official visa portals, but they are not "open source" in the software sense. The public material gives us enough to build a serious compliance assistant: size, aspect ratio, face position, background, lighting, expression, file format, print requirements, and country-specific exceptions.

The acceptance engines used by governments, consulates, booths, and application portals are usually not public. Our product should therefore position itself as a compliance checker and preparation tool, with a money-back policy for rejections caused by photo-format issues rather than a blanket guarantee.

## Product goal

Build a low-cost tool that helps users create passport, visa, OCI, and identity-document photos that are likely to pass official checks.

The first version should:

- accept a camera capture or uploaded image
- let the user choose country, document type, and delivery format
- validate face position, quality, background, pose, expression, and file constraints
- guide the user to retake the photo when editing would violate rules
- export compliant digital files and printable sheets
- preserve source evidence and metadata needed for refund/review workflows

## Source model

Each country/document rule must be backed by an official source URL and a last-reviewed date. Requirements change, and similar documents in the same country can differ.

Rule sources should be classified as:

- `official_government`: government passport, immigration, embassy, or consulate source
- `official_vendor_or_partner`: authorized post office, photo booth network, VFS-style application partner, or visa center
- `standards_body`: ICAO or ISO standard reference
- `secondary_reference`: commercial guide, blog, or user report; allowed only as a pointer, not as a rule source

We should avoid scraping blindly. For MVP countries, manually encode rules from official pages, keep links, and add a review workflow.

## Initial countries and documents

Start with high-demand, high-documentation targets:

- United States passport photo
- United Kingdom digital passport photo
- India passport or passport-service photo flows
- Canada passport photo
- Australia passport photo
- Schengen visa photo, starting with one official member-state source such as France or Germany

India needs special care because many adult passport applicants are photographed at PSK/POPSK locations, while minors and certain forms may need carried photos. We should model the exact use case, not just "India passport" as one universal rule.

## MVP scope

Version 0.1 should prove the core workflow:

1. Upload or capture an image.
2. Select a rule profile.
3. Detect face landmarks.
4. Compute crop and head placement.
5. Validate deterministic requirements.
6. Show pass/fail checks with actionable retake guidance.
7. Export a compliant image when allowed.
8. Store a local audit report for support/refunds.

MVP should not promise full acceptance. It should say whether the image appears to meet the selected published requirements.

## What can be automated

Strong candidates:

- face and landmark detection
- head bounding box estimation
- eye-line alignment
- crop and resize
- background color/texture/shadow checks
- blur and sharpness estimation
- exposure and contrast checks
- image dimensions, DPI metadata, file type, file size
- printable sheet layout

Medium-confidence candidates:

- neutral expression
- mouth open/closed
- head tilt/yaw/pitch
- glasses glare
- face occlusion
- skin tone naturalness
- hair covering eyes or face edges

Human-review candidates:

- religious or medical head-covering exceptions
- infant/toddler exceptions
- disability accommodations
- borderline shadows
- subjective "true likeness" concerns
- possible digital manipulation concerns

## Editing policy

Government rules often restrict alteration. Our software should prefer guided retake over aggressive editing.

Allowed by default:

- crop
- resize
- rotate slightly for alignment
- compress to target file size
- produce print layouts

Conditionally allowed, depending on rule profile:

- background replacement
- brightness/contrast normalization
- shadow reduction outside face

Avoid:

- face retouching
- skin smoothing
- changing facial features
- AI-generated face reconstruction
- changing hair, eyes, scars, moles, wrinkles, or identity-relevant details

When a country says "unaltered" or rejects AI/photo-editing tools, the profile should disable background replacement and enhancement. Canada and Australia are especially strict on alteration language.

## Refund policy concept

Offer a narrow, credible guarantee:

"If your photo is rejected specifically because of a photo-format or composition issue that our checker marked as passing, we refund the photo-preparation fee."

Exclude:

- application rejection unrelated to the photo
- user submitted a different image
- user edited the exported image
- rejection caused by age/recency issues we cannot verify
- country-specific subjective exceptions
- rules changed after export
- users selecting the wrong country/document profile

Require:

- original uploaded photo
- exported file ID
- selected rule profile and version
- rejection notice screenshot or text
- application authority/date

## Technical architecture

Recommended stack for the first build:

- Frontend: Next.js or Vite React
- Image pipeline: OpenCV.js for browser-side checks, or Python/OpenCV for server-side processing
- Face landmarks: MediaPipe Face Detection / Face Mesh for initial version
- Rules engine: typed JSON profiles validated by schema
- Storage: local filesystem first, later S3-compatible object storage
- Audit/report: JSON result plus human-readable PDF/HTML report

Longer term:

- add server-side validation for consistent results
- support offline kiosk mode
- add a reviewer dashboard
- build an API for studios, agents, and travel-service businesses
- add country-rule review reminders
- add A/B capture guidance from rejection data

## Rule profile shape

Each rule profile should be data-first:

```json
{
  "id": "us-passport-photo-v2026-06",
  "country": "US",
  "document": "passport",
  "delivery": ["print", "digital"],
  "sourceUrls": [],
  "lastReviewed": "2026-06-03",
  "canvas": {
    "widthMm": 51,
    "heightMm": 51,
    "aspectRatio": 1
  },
  "head": {
    "measure": "chin_to_top_of_head",
    "minMm": 25,
    "maxMm": 35,
    "centered": true
  },
  "background": {
    "allowed": ["white", "off-white"],
    "plain": true,
    "shadowFree": true
  },
  "pose": {
    "facingCamera": true,
    "neutralExpression": true,
    "eyesOpen": true,
    "mouthClosed": true
  },
  "file": {
    "formats": ["jpg", "jpeg"],
    "minPixels": null,
    "maxBytes": null
  },
  "editing": {
    "crop": true,
    "resize": true,
    "backgroundReplacement": "profile_specific",
    "faceRetouching": false
  }
}
```

## Validation result shape

The checker should return both machine-readable and user-facing results:

```json
{
  "profileId": "us-passport-photo-v2026-06",
  "status": "pass_with_warnings",
  "checks": [
    {
      "id": "head_size",
      "status": "pass",
      "measured": "31.4mm",
      "required": "25-35mm"
    },
    {
      "id": "background_shadow",
      "status": "warning",
      "message": "Possible shadow near right shoulder."
    }
  ],
  "exportAllowed": true
}
```

## UX principles

The product must guide capture before fixing the image.

Good capture guidance:

- move closer/farther
- stand farther from the wall
- remove glasses
- face the camera
- close mouth
- improve lighting
- choose a different background
- retake if image is blurred

The UI should show a live outline for face/head placement, but avoid implying official approval. Use plain labels such as "Likely to meet published rules" and "Needs retake."

## Business model

Possible paths:

- free open-source core validator
- paid hosted exports
- paid country/document rule packs
- studio/kiosk licensing
- API for visa agencies and travel businesses
- white-label version for local photo shops
- human review upsell for high-value applications

The strongest wedge is not replacing photographers everywhere. It is helping users avoid repeated rejections and helping small shops/studios produce correct photos cheaply.

## Compliance and privacy

This is sensitive biometric-adjacent data. Treat face photos as private by default.

Baseline privacy decisions:

- process locally in browser when possible
- avoid storing photos unless the user chooses export/support
- delete temporary files automatically
- store only audit metadata needed for refund/support
- encrypt stored originals if a review workflow exists
- do not train models on user photos without explicit opt-in
- show a clear privacy notice before upload

## First implementation milestones

Milestone 1: Research-backed rules

- create rule schema
- add US, UK, India, Canada, Australia starter profiles
- add source URL and last-reviewed fields
- write unit tests for profile validity

Milestone 2: Image analysis prototype

- detect face and landmarks
- estimate chin, eye line, top-of-head/crown
- calculate suggested crop
- check blur, dimensions, and file type
- produce validation report

Milestone 3: User workflow

- upload/camera input
- country/document selector
- live preview and crop overlay
- pass/fail checklist
- export digital image

Milestone 4: Print/export

- print sheet templates
- DPI-aware output
- PDF export
- file-size compression targets

Milestone 5: Guarantee support

- export IDs
- immutable rule/profile version
- audit report
- rejection/refund intake form

## Open questions

- Should the first product be a browser-only tool, a desktop app, or a web app with server-side processing?
- Are we targeting Indian users first, or global expat/visa users?
- Do we want open-source core plus paid hosted service, or fully proprietary software?
- Should background replacement be disabled by default until we confirm each country's policy?
- Should we include human review from day one for paid exports?

## Immediate next step

Build a small prototype around one rule profile first. The United States printed passport photo is a good starting case because the published requirements are clear, measurable, and common. After that, add India and UK, because they will force us to model different workflow realities instead of assuming every country behaves the same.
