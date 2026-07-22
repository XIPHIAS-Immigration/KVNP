// Generated from data/profiles.json by tools/sync_rules.py.
// Edit the JSON registry, then run the sync command. Do not edit this array by hand.
export const RULE_PROFILES = [
  {
    "id": "us-passport-print-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "US State Dept: submit an original, unedited photo. The studio validates and formats the capture but does not alter pixels for this programme."
    },
    "label": "United States passport - print",
    "country": "US",
    "countryName": "United States",
    "programme": "Passport photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Print",
    "lastReviewed": "2026-06-07",
    "sources": [
      {
        "label": "U.S. State Department passport photos",
        "url": "https://travel.state.gov/en/passports/apply/help/photos.html"
      }
    ],
    "requirements": [
      "2 x 2 in / 51 x 51 mm color photo",
      "Head 25-35 mm from chin to top of head",
      "Plain white or off-white background",
      "Neutral expression, eyes open, no eyeglasses"
    ],
    "output": {
      "widthPx": 600,
      "heightPx": 600,
      "printWidthMm": 51,
      "printHeightMm": 51,
      "mime": "image/jpeg",
      "quality": 0.92
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 25,
      "maxMm": 35,
      "minPercent": 50,
      "maxPercent": 69,
      "targetPercent": 62,
      "topMarginPercent": 13,
      "eye": {
        "fromTopMinPercent": 31,
        "fromTopMaxPercent": 44,
        "targetFromTopPercent": 37.5,
        "note": "Eyes 28-35mm from bottom of a 51mm photo (State Dept)."
      }
    },
    "background": {
      "mode": "white_or_off_white",
      "minEdgeLuma": 190,
      "maxEdgeSaturation": 52,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "neutral expression",
      "eyes open",
      "mouth closed",
      "no face covering"
    ]
  },
  {
    "id": "us-visa-ds160-digital-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "US visa photos follow the original, unedited-photo standard. Retake lighting or background problems instead of correcting them digitally."
    },
    "label": "United States visa - DS-160 digital",
    "country": "US",
    "countryName": "United States",
    "programme": "Visa / DS-160",
    "category": "Visa",
    "document": "Visa",
    "delivery": "Digital",
    "lastReviewed": "2026-06-07",
    "sources": [
      {
        "label": "U.S. State Department visa photos",
        "url": "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html"
      }
    ],
    "requirements": [
      "Square digital image, usually 600 x 600 px or larger",
      "Printed equivalent is 2 x 2 in / 51 x 51 mm",
      "Head 22-35 mm or 50-69% of image height",
      "Plain white or off-white background"
    ],
    "output": {
      "widthPx": 600,
      "heightPx": 600,
      "printWidthMm": 51,
      "printHeightMm": 51,
      "mime": "image/jpeg",
      "quality": 0.9
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 22,
      "maxMm": 35,
      "minPercent": 50,
      "maxPercent": 69,
      "targetPercent": 62,
      "topMarginPercent": 12,
      "eye": {
        "fromTopMinPercent": 31,
        "fromTopMaxPercent": 44,
        "targetFromTopPercent": 37.5,
        "note": "Eyes 22-35mm from bottom of a 51mm photo (State Dept visa)."
      }
    },
    "background": {
      "mode": "white_or_off_white",
      "minEdgeLuma": 190,
      "maxEdgeSaturation": 52,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": 240000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 240000
    },
    "reviewChecks": [
      "neutral expression",
      "eyes open",
      "mouth closed",
      "no eyeglasses"
    ]
  },
  {
    "id": "us-dv-lottery-digital-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "DV programme rejects digitally retouched photos. The studio provides validation and required file formatting only."
    },
    "label": "United States diversity visa - digital",
    "country": "US",
    "countryName": "United States",
    "programme": "Diversity Visa / DV Lottery",
    "category": "Visa",
    "document": "Diversity Visa",
    "delivery": "Digital",
    "lastReviewed": "2026-06-07",
    "sources": [
      {
        "label": "U.S. State Department visa photo requirements",
        "url": "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html"
      }
    ],
    "requirements": [
      "Square JPEG digital photo",
      "Use the same composition standard as U.S. visa photos",
      "Head 50-69% of image height",
      "White or off-white background"
    ],
    "output": {
      "widthPx": 600,
      "heightPx": 600,
      "printWidthMm": 51,
      "printHeightMm": 51,
      "mime": "image/jpeg",
      "quality": 0.88
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 22,
      "maxMm": 35,
      "minPercent": 50,
      "maxPercent": 69,
      "targetPercent": 62,
      "topMarginPercent": 12,
      "eye": {
        "fromTopMinPercent": 31,
        "fromTopMaxPercent": 44,
        "targetFromTopPercent": 37.5,
        "note": "DV uses the U.S. visa composition: eyes 22-35mm from bottom of a 51mm photo."
      }
    },
    "background": {
      "mode": "white_or_off_white",
      "minEdgeLuma": 190,
      "maxEdgeSaturation": 52,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": 240000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 240000
    },
    "reviewChecks": [
      "recent photo",
      "neutral expression",
      "eyes open",
      "no digital retouching"
    ]
  },
  {
    "id": "uk-passport-digital-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "GOV.UK requires a true, unedited likeness. Capture defects must be retaken rather than digitally corrected."
    },
    "label": "United Kingdom passport - digital",
    "country": "GB",
    "countryName": "United Kingdom",
    "programme": "Passport digital upload",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Digital",
    "lastReviewed": "2026-06-23",
    "sources": [
      {
        "label": "GOV.UK digital passport photos",
        "url": "https://www.gov.uk/photos-for-passports"
      },
      {
        "label": "GOV.UK photo standards",
        "url": "https://www.gov.uk/government/publications/photographic-standards/photo-standards-accessible"
      }
    ],
    "requirements": [
      "Digital portrait with plain light background",
      "Face clear and centered",
      "Neutral expression, mouth closed, eyes open",
      "No editing that changes appearance"
    ],
    "output": {
      "widthPx": 900,
      "heightPx": 1125,
      "printWidthMm": null,
      "printHeightMm": null,
      "mime": "image/jpeg",
      "quality": 0.92
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 29,
      "maxMm": 34,
      "minPercent": 62,
      "maxPercent": 76,
      "targetPercent": 69,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 170,
      "maxEdgeSaturation": 70,
      "maxEdgeSpread": 50
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg",
        "png"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#f7f7f2",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "true likeness",
      "neutral expression",
      "plain background",
      "no digital retouching"
    ]
  },
  {
    "id": "india-passport-icao-upload-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Passport Seva ICAO guidance requires an unaltered photograph. The studio validates and formats; retake pose, lighting, or background defects."
    },
    "label": "India passport - ICAO upload",
    "country": "IN",
    "countryName": "India",
    "programme": "Passport ICAO upload",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Digital",
    "lastReviewed": "2026-06-07",
    "sources": [
      {
        "label": "Passport Seva ICAO photo guidelines",
        "url": "https://portal5.passportindia.gov.in/Online/pdf/Guidelines_for_ICAO_Compliant_Photographs_for_Passport_Applications.pdf"
      },
      {
        "label": "Passport Seva FAQ",
        "url": "https://www.passportindia.gov.in/psp/FaqServicesAvailable"
      }
    ],
    "requirements": [
      "ICAO-style front-facing portrait",
      "White background",
      "Face occupies most of the image",
      "Natural expression, eyes visible, no head tilt"
    ],
    "output": {
      "widthPx": 600,
      "heightPx": 600,
      "printWidthMm": 51,
      "printHeightMm": 51,
      "mime": "image/jpeg",
      "quality": 0.9
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 25,
      "maxMm": 35,
      "minPercent": 62,
      "maxPercent": 78,
      "targetPercent": 70,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 195,
      "maxEdgeSaturation": 45,
      "maxEdgeSpread": 38
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": 10000,
      "maxBytes": 250000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 250000
    },
    "reviewChecks": [
      "natural expression",
      "eyes visible",
      "no head tilt",
      "unaltered photo"
    ]
  },
  {
    "id": "india-visa-online-digital-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "India Visa Online specifies the required photo appearance but does not explicitly authorize software alteration. The studio validates and formats only unless the selected authority confirms edits are permitted."
    },
    "label": "India visa online - digital upload",
    "country": "IN",
    "countryName": "India",
    "programme": "Visa Online / e-Visa",
    "category": "Visa",
    "document": "Visa",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "India Visa Online instructions",
        "url": "https://indianvisaonline.gov.in/visa/instruction.html"
      },
      {
        "label": "India e-Visa upload guidance",
        "url": "https://indianvisaonline.gov.in/evisa/"
      }
    ],
    "requirements": [
      "Square color digital photo",
      "Plain light-coloured or white background",
      "Minimum 350 x 350 px",
      "Maximum file size 1 MB"
    ],
    "output": {
      "widthPx": 600,
      "heightPx": 600,
      "printWidthMm": 51,
      "printHeightMm": 51,
      "mime": "image/jpeg",
      "quality": 0.9
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 25,
      "maxMm": 35,
      "minPercent": 49,
      "maxPercent": 69,
      "targetPercent": 62,
      "topMarginPercent": 12
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 195,
      "maxEdgeSaturation": 45,
      "maxEdgeSpread": 38
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": 10000,
      "maxBytes": 1000000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 1000000
    },
    "reviewChecks": [
      "front view",
      "full face visible",
      "eyes open",
      "no shadows"
    ]
  },
  {
    "id": "canada-passport-print-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Canada: the photo must not be altered in any way, including filters, AI tools, brightness, sharpness, background changes, or head cropping. Validation only."
    },
    "label": "Canada passport - print",
    "country": "CA",
    "countryName": "Canada",
    "programme": "Passport photo (print)",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Print",
    "lastReviewed": "2026-06-23",
    "sources": [
      {
        "label": "Canada passport photo requirements",
        "url": "https://www.canada.ca/en/immigration-refugees-citizenship/services/canadian-passports/photos.html"
      }
    ],
    "requirements": [
      "TWO identical 50 x 70 mm printed photos",
      "Head 31-36 mm from chin to crown",
      "Taken/printed by a commercial photographer; home prints rejected",
      "Must NOT be altered or edited in any way (no filters, AI, or background editing)",
      "Plain white or light-coloured background"
    ],
    "output": {
      "widthPx": 1000,
      "heightPx": 1400,
      "printWidthMm": 50,
      "printHeightMm": 70,
      "mime": "image/jpeg",
      "quality": 0.95
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 31,
      "maxMm": 36,
      "minPercent": 44,
      "maxPercent": 51,
      "targetPercent": 47.5,
      "topMarginPercent": 13
    },
    "background": {
      "mode": "white_or_light",
      "minEdgeLuma": 180,
      "maxEdgeSaturation": 58,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "commercial photographer required",
      "unaltered photo",
      "two identical prints",
      "neutral expression"
    ]
  },
  {
    "id": "canada-trv-print-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "IRCC: digital photographs must not be altered in any way. The studio validates the original capture and applies required file formatting only."
    },
    "label": "Canada temporary resident visa - print",
    "country": "CA",
    "countryName": "Canada",
    "programme": "Temporary resident visa",
    "category": "Visa",
    "document": "Temporary Resident Visa",
    "delivery": "Print",
    "lastReviewed": "2026-06-07",
    "sources": [
      {
        "label": "Canada temporary resident visa photograph specifications",
        "url": "https://www.canada.ca/en/immigration-refugees-citizenship/services/application/application-forms-guides/temporary-resident-visa-application-photograph-specifications.html"
      }
    ],
    "requirements": [
      "35 x 45 mm photo",
      "Head 31-36 mm from chin to crown",
      "White or light-colored background",
      "Digital photographs must not be altered"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.92
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 31,
      "maxMm": 36,
      "minPercent": 69,
      "maxPercent": 80,
      "targetPercent": 74,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white_or_light",
      "minEdgeLuma": 180,
      "maxEdgeSaturation": 58,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "unaltered photo",
      "neutral expression",
      "eyes visible"
    ]
  },
  {
    "id": "australia-passport-print-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Australian Passport Office: the photo must not be digitally enhanced or altered. Retake capture defects instead of correcting them."
    },
    "label": "Australia passport - print",
    "country": "AU",
    "countryName": "Australia",
    "programme": "Passport photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Print",
    "lastReviewed": "2026-06-07",
    "sources": [
      {
        "label": "Australian Passport Office photo guidelines",
        "url": "https://www.passports.gov.au/PhotoGuidelines"
      }
    ],
    "requirements": [
      "35 x 45 mm photo",
      "Head 32-36 mm from chin to crown",
      "Plain white or light-gray background",
      "No retouching or alteration"
    ],
    "output": {
      "widthPx": 1400,
      "heightPx": 1800,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.92
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 32,
      "maxMm": 36,
      "minPercent": 71,
      "maxPercent": 80,
      "targetPercent": 75.5,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white_or_light",
      "minEdgeLuma": 180,
      "maxEdgeSaturation": 58,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#f7f7f2",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "no retouching",
      "edges of face visible",
      "no head tilt",
      "glossy print workflow"
    ]
  },
  {
    "id": "france-schengen-visa-print-2026-06",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "France-Visas requires a natural, plain light-coloured capture background. The studio validates and formats only unless the selected authority explicitly permits edits."
    },
    "label": "France / Schengen visa - print",
    "country": "FR",
    "countryName": "France",
    "programme": "Schengen visa",
    "category": "Visa",
    "document": "Visa",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "France-Visas photograph instructions",
        "url": "https://france-visas.gouv.fr/documents/d/france-visas/iso_iec_fv_visa_photograph_requirements_en"
      }
    ],
    "requirements": [
      "35 x 45 mm photo",
      "Face centered and front-facing",
      "Plain light background",
      "Neutral expression, mouth closed, eyes visible"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.92
    },
    "head": {
      "measure": "face_area_estimate",
      "minMm": null,
      "maxMm": null,
      "minPercent": 70,
      "maxPercent": 80,
      "targetPercent": 75,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 170,
      "maxEdgeSaturation": 70,
      "maxEdgeSpread": 50
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#f7f7f2",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "neutral expression",
      "mouth closed",
      "eyes visible",
      "no other person visible"
    ]
  },
  {
    "id": "netherlands-passport-id-print-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "The Dutch government requires a natural photograph unaltered by computer software. KVNP validates, crops and prepares the print file only."
    },
    "label": "Netherlands passport / ID - print",
    "country": "NL",
    "countryName": "Netherlands",
    "programme": "Passport or identity card",
    "category": "Passport",
    "document": "Passport / ID",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Government of the Netherlands photo requirements",
        "url": "https://www.government.nl/themes/justice-security-and-defence/identification-documents/requirements-for-photos"
      }
    ],
    "requirements": [
      "35 x 45 mm colour photo at a minimum 400 DPI",
      "Adult face length 26-30 mm from chin to crown",
      "Plain light grey, light blue or white background",
      "Forward-facing head, level eyes and straight shoulders"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 26,
      "maxMm": 30,
      "minPercent": 57.8,
      "maxPercent": 66.7,
      "targetPercent": 62.2,
      "topMarginPercent": 10
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 165,
      "maxEdgeSaturation": 85,
      "maxEdgeSpread": 45
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#e9edf1",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "natural likeness",
      "neutral expression",
      "mouth closed",
      "straight shoulders"
    ]
  },
  {
    "id": "ireland-passport-print-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Ireland does not accept digital enhancements or changes. KVNP validates and formats the original capture; photo defects require a retake."
    },
    "label": "Ireland passport - print",
    "country": "IE",
    "countryName": "Ireland",
    "programme": "Passport photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Ireland Department of Foreign Affairs photo guidelines",
        "url": "https://www.dfa.ie/irish-embassy/estonia/passports/top-passport-questions/photo-guidelines/"
      }
    ],
    "requirements": [
      "35 x 45 mm minimum; 38 x 50 mm maximum",
      "Face and top of shoulders fill 70-80% of the frame",
      "Plain light-coloured background without shadows",
      "Neutral expression, eyes open and mouth closed"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "face_area_estimate",
      "minMm": null,
      "maxMm": null,
      "minPercent": 70,
      "maxPercent": 80,
      "targetPercent": 75,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 170,
      "maxEdgeSaturation": 70,
      "maxEdgeSpread": 50
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#f7f7f2",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "neutral expression",
      "eyes open",
      "mouth closed",
      "no digital changes"
    ]
  },
  {
    "id": "ireland-visa-print-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Irish visa supporting photographs should remain natural. KVNP performs validation and print formatting only."
    },
    "label": "Ireland visa - print",
    "country": "IE",
    "countryName": "Ireland",
    "programme": "Entry visa supporting photo",
    "category": "Visa",
    "document": "Visa",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Ireland DFA online visa application guidance",
        "url": "https://www.dfa.ie/media/embassyitaly/ourservices/Information-on-completing-Online-Application---English.pdf"
      }
    ],
    "requirements": [
      "35 x 45 mm minimum; 38 x 50 mm maximum",
      "Face fills 70-80% of the photograph",
      "Plain white or light-grey background",
      "Front-facing neutral expression with eyes open"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "face_area_estimate",
      "minMm": null,
      "maxMm": null,
      "minPercent": 70,
      "maxPercent": 80,
      "targetPercent": 75,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white_or_light",
      "minEdgeLuma": 180,
      "maxEdgeSaturation": 58,
      "maxEdgeSpread": 48
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#f7f7f2",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "recent photo",
      "neutral expression",
      "mouth closed",
      "no hair over eyes"
    ]
  },
  {
    "id": "italy-passport-print-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "The Italian ICAO guidance expects a natural biometric capture. KVNP validates and formats without altering appearance."
    },
    "label": "Italy passport - print",
    "country": "IT",
    "countryName": "Italy",
    "programme": "Electronic passport photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Italian Ministry of Foreign Affairs ICAO photo guidance",
        "url": "https://www.esteri.it/en/servizi-opportunita/italiani-all-estero/documenti_di_viaggio/linee-guida-foto-icao/"
      }
    ],
    "requirements": [
      "35 x 45 mm colour photograph",
      "Face fills 70-80% of the photograph",
      "White, evenly lit background",
      "Front-facing neutral expression, eyes open and mouth closed"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "face_area_estimate",
      "minMm": null,
      "maxMm": null,
      "minPercent": 70,
      "maxPercent": 80,
      "targetPercent": 75,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 200,
      "maxEdgeSaturation": 45,
      "maxEdgeSpread": 38
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "recent photo",
      "natural skin tone",
      "neutral expression",
      "no face obstruction"
    ]
  },
  {
    "id": "japan-passport-print-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Japan's passport photograph must preserve the applicant's natural appearance. KVNP validates and formats only."
    },
    "label": "Japan passport - print",
    "country": "JP",
    "countryName": "Japan",
    "programme": "Passport photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Japan Ministry of Foreign Affairs passport photo standard",
        "url": "https://www.mofa.go.jp/mofaj/toko/passport/ic_photo.html"
      }
    ],
    "requirements": [
      "35 x 45 mm borderless photograph",
      "Head 32-36 mm from chin to top of head",
      "Approximately 4 mm space above the head",
      "Plain background, frontal pose and neutral expression"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 32,
      "maxMm": 36,
      "minPercent": 71.1,
      "maxPercent": 80,
      "targetPercent": 75.6,
      "topMarginPercent": 8.9
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 160,
      "maxEdgeSaturation": 80,
      "maxEdgeSpread": 48
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#f7f7f2",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "recent photo",
      "neutral expression",
      "plain background",
      "no face obstruction"
    ]
  },
  {
    "id": "singapore-passport-digital-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Singapore ICA permits resizing but says the photograph must not be altered or enhanced. KVNP therefore validates, crops and resizes only."
    },
    "label": "Singapore passport - digital",
    "country": "SG",
    "countryName": "Singapore",
    "programme": "Passport e-Service photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Singapore ICA photo guidelines",
        "url": "https://www.ica.gov.sg/photo-guidelines"
      }
    ],
    "requirements": [
      "Recommended online dimensions 400 x 514 px",
      "JPG, JPEG, HEIC, HEIF or PNG up to 8 MB",
      "White background and full frontal view",
      "Photograph must not be altered or enhanced"
    ],
    "output": {
      "widthPx": 400,
      "heightPx": 514,
      "printWidthMm": null,
      "printHeightMm": null,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "face_area_estimate",
      "minMm": null,
      "maxMm": null,
      "minPercent": 68,
      "maxPercent": 80,
      "targetPercent": 74,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 200,
      "maxEdgeSaturation": 45,
      "maxEdgeSpread": 38
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg",
        "png",
        "heic",
        "heif"
      ],
      "minBytes": null,
      "maxBytes": 8000000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 8000000
    },
    "reviewChecks": [
      "recent colour photo",
      "natural appearance",
      "eyes visible",
      "no digital enhancement"
    ]
  },
  {
    "id": "new-zealand-passport-digital-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "New Zealand requires a true image with no filters or digital alteration. KVNP performs compliance checks, crop and required file formatting only."
    },
    "label": "New Zealand passport - digital",
    "country": "NZ",
    "countryName": "New Zealand",
    "programme": "Passport online photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "New Zealand Passports photo requirements",
        "url": "https://www.passports.govt.nz/passport-photos"
      }
    ],
    "requirements": [
      "3:4 colour JPEG between 900 x 1200 and 4500 x 6000 px",
      "File size between 250 KB and 5 MB",
      "Head including hair no more than 80% of the frame",
      "Plain light background, clear head gap and upper chest visible"
    ],
    "output": {
      "widthPx": 900,
      "heightPx": 1200,
      "printWidthMm": null,
      "printHeightMm": null,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": null,
      "maxMm": null,
      "minPercent": 60,
      "maxPercent": 80,
      "targetPercent": 70,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 165,
      "maxEdgeSaturation": 75,
      "maxEdgeSpread": 48
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": 250000,
      "maxBytes": 5000000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#e9edf1",
      "enhanceOutput": false,
      "compressionTarget": 5000000
    },
    "reviewChecks": [
      "not a selfie",
      "neutral expression",
      "upper chest visible",
      "no filters or AI alteration"
    ]
  },
  {
    "id": "switzerland-passport-id-print-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Swiss identity photographs must represent the applicant naturally. KVNP validates, crops and formats the image without changing appearance or replacing the background."
    },
    "label": "Switzerland passport / ID - print",
    "country": "CH",
    "countryName": "Switzerland",
    "programme": "Passport and identity card photo",
    "category": "Passport",
    "document": "Passport / ID",
    "delivery": "Print",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Swiss Federal Police photo acceptance criteria",
        "url": "https://www.sem.admin.ch/dam/fedpol/en/data/pass-id/fotomustertafel.pdf.download.pdf/fotomustertafel.pdf"
      }
    ],
    "requirements": [
      "35 x 45 mm borderless photograph",
      "Face length from chin to crown between 29 and 34 mm",
      "Front-facing with straight shoulders and direct gaze",
      "Evenly lit face with a plain, uniform background"
    ],
    "output": {
      "widthPx": 826,
      "heightPx": 1063,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 29,
      "maxMm": 34,
      "minPercent": 64.4,
      "maxPercent": 75.6,
      "targetPercent": 70,
      "topMarginPercent": 7
    },
    "background": {
      "mode": "plain_light",
      "minEdgeLuma": 175,
      "maxEdgeSaturation": 65,
      "maxEdgeSpread": 42
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg",
        "png"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#e8ebed",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "recent photograph",
      "direct gaze",
      "neutral expression",
      "uniform background"
    ]
  },
  {
    "id": "china-visa-digital-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Chinese visa photographs must be recent and unaltered. KVNP validates the portrait and produces the required digital dimensions and file size without retouching it."
    },
    "label": "China visa - digital",
    "country": "CN",
    "countryName": "China",
    "programme": "Chinese visa application photo",
    "category": "Visa",
    "document": "Visa",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Chinese Embassy visa photo requirements",
        "url": "https://np.china-embassy.gov.cn/eng/News/202303/t20230314_11041189.htm"
      }
    ],
    "requirements": [
      "Digital photograph between 354 x 472 and 420 x 560 px",
      "JPEG file between 40 and 120 KB",
      "White or near-white background with no border",
      "Head length 28-33 mm on the 33 x 48 mm print specification"
    ],
    "output": {
      "widthPx": 354,
      "heightPx": 472,
      "printWidthMm": null,
      "printHeightMm": null,
      "mime": "image/jpeg",
      "quality": 0.92
    },
    "head": {
      "measure": "chin_to_top_of_head",
      "minMm": 28,
      "maxMm": 33,
      "minPercent": 58.3,
      "maxPercent": 68.8,
      "targetPercent": 63.5,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 205,
      "maxEdgeSaturation": 38,
      "maxEdgeSpread": 32
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": 40000,
      "maxBytes": 120000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 120000
    },
    "reviewChecks": [
      "taken within six months",
      "ears and eyes visible",
      "neutral expression",
      "unaltered appearance"
    ]
  },
  {
    "id": "hong-kong-passport-digital-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Hong Kong Immigration determines final photo acceptance. KVNP validates, crops and resizes the source while preserving the applicant's natural appearance."
    },
    "label": "Hong Kong passport - digital",
    "country": "HK",
    "countryName": "Hong Kong",
    "programme": "HKSAR passport online photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Hong Kong Immigration photo requirements",
        "url": "https://www.immd.gov.hk/eng/residents/immigration/traveldoc/photorequirements.html"
      }
    ],
    "requirements": [
      "40 x 50 mm physical proportion",
      "Digital-camera image at least 1200 x 1600 px and JPEG up to 5 MB",
      "Chin-to-crown length between 32 and 36 mm",
      "Plain white background, full frontal face and sufficient headroom"
    ],
    "output": {
      "widthPx": 1280,
      "heightPx": 1600,
      "printWidthMm": 40,
      "printHeightMm": 50,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 32,
      "maxMm": 36,
      "minPercent": 64,
      "maxPercent": 72,
      "targetPercent": 68,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 205,
      "maxEdgeSaturation": 38,
      "maxEdgeSpread": 32
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": 5000000
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": 5000000
    },
    "reviewChecks": [
      "clear facial features",
      "hair clear of eyes",
      "no flash reflection",
      "no shadows"
    ]
  },
  {
    "id": "south-korea-passport-digital-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Korean passport rules prohibit arbitrary correction, filters, AI processing and artificial background removal. KVNP therefore performs validation, crop and file formatting only."
    },
    "label": "South Korea passport - digital",
    "country": "KR",
    "countryName": "South Korea",
    "programme": "Online passport renewal photo",
    "category": "Passport",
    "document": "Passport",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Republic of Korea passport photo standards",
        "url": "https://passport.go.kr/home/kor/contents.do?menuPos=32"
      }
    ],
    "requirements": [
      "Recommended online dimensions 413 x 531 px",
      "35 x 45 mm proportion with head length between 32 and 36 mm",
      "Uniform white background and frontal upper-body portrait",
      "AI edits, filters and artificial background removal are prohibited"
    ],
    "output": {
      "widthPx": 413,
      "heightPx": 531,
      "printWidthMm": 35,
      "printHeightMm": 45,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 32,
      "maxMm": 36,
      "minPercent": 71.1,
      "maxPercent": 80,
      "targetPercent": 75.5,
      "topMarginPercent": 7
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 205,
      "maxEdgeSaturation": 38,
      "maxEdgeSpread": 32
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "taken within six months",
      "natural appearance",
      "mouth closed",
      "no artificial background removal"
    ]
  },
  {
    "id": "malaysia-evisa-digital-2026-07",
    "allowedEdits": {
      "straighten": false,
      "tone": false,
      "lighting": false,
      "background": false,
      "enhance": false,
      "rescue": false,
      "note": "Malaysia's eVISA guidance rejects cropped-out backgrounds, Photoshopped images and non-studio captures. KVNP validates and formats the original photo without replacing its background."
    },
    "label": "Malaysia eVISA - digital",
    "country": "MY",
    "countryName": "Malaysia",
    "programme": "Malaysia eVISA passport photo",
    "category": "Visa",
    "document": "eVISA",
    "delivery": "Digital",
    "lastReviewed": "2026-07-22",
    "sources": [
      {
        "label": "Malaysia Immigration eVISA photo FAQ",
        "url": "https://malaysiavisa.imi.gov.my/evisa/FAQ/PDF/FAQ/Support/FAQ_en.pdf?version=3.8.3"
      }
    ],
    "requirements": [
      "35 x 50 mm portrait proportion",
      "Pure white, shadow-free original background",
      "Face and body directed toward the camera, framed crown to shoulders",
      "Background cropping, Photoshopping and scanner-app images are not accepted"
    ],
    "output": {
      "widthPx": 827,
      "heightPx": 1181,
      "printWidthMm": 35,
      "printHeightMm": 50,
      "mime": "image/jpeg",
      "quality": 0.94
    },
    "head": {
      "measure": "chin_to_crown",
      "minMm": 25,
      "maxMm": 30,
      "minPercent": 50,
      "maxPercent": 60,
      "targetPercent": 55,
      "topMarginPercent": 8
    },
    "background": {
      "mode": "white",
      "minEdgeLuma": 210,
      "maxEdgeSaturation": 32,
      "maxEdgeSpread": 28
    },
    "file": {
      "formats": [
        "jpg",
        "jpeg"
      ],
      "minBytes": null,
      "maxBytes": null
    },
    "automation": {
      "backgroundReplacement": false,
      "backgroundColor": "#ffffff",
      "enhanceOutput": false,
      "compressionTarget": null
    },
    "reviewChecks": [
      "studio-captured original",
      "shoulders visible",
      "white background",
      "no digital alteration"
    ]
  }
];

export const COUNTRIES = Array.from(
  new Map(RULE_PROFILES.map((profile) => [profile.country, { code: profile.country, name: profile.countryName }])).values(),
).sort((a, b) => a.name.localeCompare(b.name));

export function getDefaultProfile() {
  return RULE_PROFILES[0];
}

export function getProfilesForCountry(countryCode) {
  return RULE_PROFILES.filter((profile) => profile.country === countryCode);
}
