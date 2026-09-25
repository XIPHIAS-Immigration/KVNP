"""Server-rendered marketing / SEO pages for PassportLens.

Everything here is plain HTML built from the authoritative rule registry
(data/profiles.json) so the requirement pages can never drift from what the
checker actually enforces. No template engine is needed."""

from __future__ import annotations

import html
import json
import re
from datetime import date

PRODUCT = "PassportLens"
STYLE_VERSION = "pl-4"

BACKGROUND_LABELS = {
    "white": "Plain white",
    "white_or_off_white": "White or off-white",
    "white_or_light": "White or light colour",
    "plain_light": "Plain light colour",
    "light_not_white": "Light colour (not pure white)",
}

AUDIENCES = {
    "photo-studios": {
        "title": "Passport photo software for photo studios",
        "kicker": "For photo studios",
        "heading": "Every passport and visa photo right, without memorising 35 rulebooks.",
        "intro": "PassportLens loads the exact size, head position, background and file limits for each programme, checks the shot in seconds and gives you a print sheet or digital file. Your clients get an accepted photo; you get a faster counter.",
        "points": [
            ("Rules built in", "Canadian passport, PR card, US visa, Indian OCI, Schengen and 30 more programmes with the issuing authority's published sizes and margins."),
            ("Plain verdicts", "\"Photo OK\" or \"Retake: eyes not looking at the camera\". Staff don't need to interpret numbers."),
            ("Print and digital", "4×6 and A4 print sheets with cut guides at the correct DPI, plus JPEG, PNG and PDF files sized for online uploads."),
            ("Client records", "Every photo is saved against a client with what you charged and whether it's paid. Export to CSV any time."),
        ],
        "cta": "Start Silver — CAD 100/month",
        "cta_href": "/pricing?plan=silver",
    },
    "immigration-consultants": {
        "title": "Passport photo checker for immigration consultants",
        "kicker": "For immigration consultants",
        "heading": "Stop losing weeks to rejected photos.",
        "intro": "A rejected photo restarts the clock on an application. PassportLens checks each client's photo against the programme's published requirements before it goes in, and keeps a record of what was submitted.",
        "points": [
            ("IRCC, USCIS, Passport Seva and more", "Programme profiles for Canadian PR cards, citizenship, TRVs, US DS-160, Indian OCI and e-Visa, UK and Schengen."),
            ("Check first, then fix", "The result tells your client plainly whether to retake. Where the programme allows it, the background is cleaned and the file resized."),
            ("Records for every file", "Clients, programmes, dates and the verdict are stored, so you can show what was checked if a question comes back."),
            ("Team logins", "Gold and Platinum plans give your staff their own logins under one business."),
        ],
        "cta": "See business plans",
        "cta_href": "/pricing",
    },
    "pharmacies": {
        "title": "Add a passport photo service to your pharmacy",
        "kicker": "For pharmacies",
        "heading": "A passport photo counter your staff can run on day one.",
        "intro": "Canadians already come to the pharmacy for passport photos. PassportLens turns any staff member into a compliant passport photographer: guided capture, instant checks and a print sheet, with the papers, printer and setup supplied on Gold and Platinum.",
        "points": [
            ("Guided capture", "The camera coach tells the customer to move closer, look at the lens or level their head before the photo is taken."),
            ("Every programme", "Passport Canada, PR card, citizenship, US, UK, India and 30 more, all with the correct sizes."),
            ("Hardware and papers", "Platinum includes the camera, lighting and printer; Gold includes the photo papers and materials with basic setup."),
            ("Sales tracking", "Each photo is logged with the amount charged, so the counter reconciles at the end of the day."),
        ],
        "cta": "Talk to us about Gold or Platinum",
        "cta_href": "/#contact",
    },
    "print-shops": {
        "title": "Passport photo software for print shops",
        "kicker": "For print shops",
        "heading": "Passport photos as a walk-in service, printed correctly every time.",
        "intro": "You already have the printer. PassportLens adds the rules: exact head size, plain background, correct DPI and a cut-guide sheet for 4×6 or A4 paper.",
        "points": [
            ("Correct print sheets", "Two, four or six photos per sheet with cut guides, stamped with the programme's DPI so the physical size is right."),
            ("Digital files too", "Customers applying online get a JPEG or PDF within the programme's size limits."),
            ("No training needed", "One verdict, plain reasons. Anyone at the counter can use it."),
            ("Unlimited photos", "Silver is a flat CAD 100 per month for one login; upgrade to Gold for staff logins."),
        ],
        "cta": "Start Silver — CAD 100/month",
        "cta_href": "/pricing?plan=silver",
    },
}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", value)


def programme_name(profile: dict) -> str:
    """'Passport photo (print)' -> 'passport'; 'Visa / DS-160' -> 'visa / DS-160'."""
    programme = re.sub(r"\(.*?\)", " ", str(profile.get("programme") or ""))
    programme = re.sub(r"\b(photo|photograph|checker)\b", " ", programme, flags=re.I)
    programme = re.sub(r"\s{2,}", " ", programme).strip(" -/")
    return programme or str(profile.get("document") or "photo")


def profile_slug(profile: dict) -> str:
    base = slugify(f"{profile.get('countryName') or profile.get('country')} {programme_name(profile)}")
    return base + "-photo"


def build_slug_map(profiles: list[dict]) -> dict[str, dict]:
    result = {}
    for profile in profiles:
        slug = profile_slug(profile)
        if slug in result:
            slug = f"{slug}-{slugify(profile['id'].split('-')[-2] if '-' in profile['id'] else profile['id'])}"
        result[slug] = profile
    return result


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _head(title: str, description: str, canonical: str, jsonld: list | None = None) -> str:
    ld = "".join(
        f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=False)}</script>' for item in (jsonld or [])
    )
    return f"""<!DOCTYPE html>
<html lang="en-CA">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description)}" />
  <meta name="theme-color" content="#351C15" />
  <link rel="icon" href="/assets/brand/favicon.svg" type="image/svg+xml" />
  <link rel="canonical" href="{_e(canonical)}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="{PRODUCT}" />
  <meta property="og:url" content="{_e(canonical)}" />
  <meta property="og:title" content="{_e(title)}" />
  <meta property="og:description" content="{_e(description)}" />
  <meta property="og:image" content="{_e(canonical.split('/')[0] + '//' + canonical.split('/')[2])}/assets/brand/og-image.jpg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="stylesheet" href="/src/theme.css?v={STYLE_VERSION}" />
  <link rel="stylesheet" href="/src/landing.css?v={STYLE_VERSION}" />
  <link rel="stylesheet" href="/src/pages.css?v={STYLE_VERSION}" />
  {ld}
</head>
<body>"""


# gold tile + brown lens: used on the dark nav and footer
_MARK = '<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="2" y="2" width="44" height="44" rx="12" fill="#FFB500"/><circle cx="24" cy="23" r="12.5" fill="none" stroke="#351C15" stroke-width="3.5"/><circle cx="24" cy="23" r="5" fill="#351C15"/><circle cx="29.5" cy="17.5" r="2" fill="#fff" opacity=".9"/><rect x="13" y="38" width="22" height="2.6" rx="1.3" fill="#351C15" opacity=".85"/></svg>'
_MARK_DARK = _MARK


def _nav() -> str:
    return f"""
  <header class="nav" id="nav">
    <div class="wrap nav-inner">
      <a class="brand on-dark" href="/" aria-label="{PRODUCT} home">{_MARK}<span class="brand-name">Passport<b>Lens</b></span></a>
      <nav class="nav-links" id="navLinks" aria-label="Primary">
        <a href="/#how">How it works</a>
        <a href="/requirements">Requirements</a>
        <a href="/#who">Who it's for</a>
        <a href="/pricing">Pricing</a>
        <a href="/#contact">Contact</a>
      </nav>
      <div class="nav-cta">
        <a class="nav-signin" href="/app">Sign in</a>
        <a class="btn sm" href="/pricing">Get started <span class="arw" aria-hidden="true">→</span></a>
        <button class="nav-toggle" id="navToggle" aria-label="Toggle menu" aria-expanded="false"><span></span><span></span><span></span></button>
      </div>
    </div>
  </header>
  <main>"""


def _footer() -> str:
    year = date.today().year
    return f"""
  </main>
  <footer class="foot">
    <div class="wrap">
      <div class="foot-grid">
        <div class="foot-brand">
          <a class="brand on-dark" href="/">{_MARK_DARK}<span class="brand-name">Passport<b>Lens</b></span></a>
          <p>Passport and visa photo software for individuals, studios, consultants and pharmacies across Canada and the United States.</p>
        </div>
        <nav class="foot-col" aria-label="Product"><h5>Product</h5><a href="/#how">How it works</a><a href="/pricing">Pricing</a><a href="/requirements">Photo requirements</a><a href="/passport-photos">Passport photos by city</a><a href="/app?guest">Free demo</a></nav>
        <nav class="foot-col" aria-label="Business"><h5>For business</h5><a href="/for/photo-studios">Photo studios</a><a href="/for/immigration-consultants">Immigration consultants</a><a href="/for/pharmacies">Pharmacies</a><a href="/for/print-shops">Print shops</a></nav>
        <nav class="foot-col" aria-label="Account"><h5>Account</h5><a href="/app">Sign in</a><a href="/account">My account</a><a href="/#faq">FAQ</a><a href="/#contact">Support</a></nav>
      </div>
      <div class="foot-fine">
        <p>Automated check only — {PRODUCT} is not a government service, is not affiliated with any passport or visa authority, and does not guarantee acceptance. The issuing authority makes the final decision.</p>
        <p class="credit">© {year} KVNP Holdings Inc. All rights reserved.</p>
      </div>
    </div>
  </footer>
  <script src="/src/vendor/anime.umd.min.js?v=4.5.0"></script>
  <script src="/src/landing.js?v={STYLE_VERSION}"></script>
</body>
</html>"""


def _mm(profile: dict) -> str:
    out = profile.get("output") or {}
    if out.get("printWidthMm") and out.get("printHeightMm"):
        return f"{out['printWidthMm']} × {out['printHeightMm']} mm"
    return "Digital only"


def _bytes(value) -> str:
    if not value:
        return ""
    value = int(value)
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / 1024:.0f} KB"


def _country_flag(code: str) -> str:
    code = (code or "").upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in code)


def render_requirements(profile: dict, slug: str, base_url: str, related: list[tuple[str, dict]]) -> str:
    country = profile.get("countryName") or profile.get("country")
    programme = programme_name(profile)
    programme = programme[0].lower() + programme[1:] if programme[:2].isupper() is False else programme
    title = f"{country} {programme} photo requirements ({date.today().year}) | {PRODUCT}"
    out = profile.get("output") or {}
    head = profile.get("head") or {}
    background = profile.get("background") or {}
    file_rules = profile.get("file") or {}
    description = (
        f"Official {country} {programme} photo size, head position, background and file rules, "
        f"with a free checker that tells you if your photo is OK. {out.get('widthPx')} × {out.get('heightPx')} px, {_mm(profile)}."
    )
    canonical = f"{base_url}/requirements/{slug}"
    requirements = profile.get("requirements") or []
    reviews = profile.get("reviewChecks") or []
    sources = profile.get("sources") or []
    formats = ", ".join(str(item).upper() for item in (file_rules.get("formats") or ["JPG"]))
    size_limit = " · ".join(
        part for part in (
            f"min {_bytes(file_rules.get('minBytes'))}" if file_rules.get("minBytes") else "",
            f"max {_bytes(file_rules.get('maxBytes'))}" if file_rules.get("maxBytes") else "",
        ) if part
    ) or "No published limit"
    head_text = ""
    if head.get("minMm") and head.get("maxMm"):
        head_text = f"{head['minMm']}–{head['maxMm']} mm from chin to top of head"
    elif head.get("minPercent") and head.get("maxPercent"):
        head_text = f"{head['minPercent']}–{head['maxPercent']}% of the photo height"
    rows = [
        ("Photo size (digital)", f"{out.get('widthPx')} × {out.get('heightPx')} pixels"),
        ("Photo size (print)", _mm(profile)),
        ("Head height", head_text or "Centred, natural size"),
        ("Background", BACKGROUND_LABELS.get(background.get("mode"), "Plain, even")),
        ("File format", formats),
        ("File size", size_limit),
        ("Delivery", profile.get("delivery") or ""),
        ("Rules last reviewed", profile.get("lastReviewed") or ""),
    ]
    table = "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows if v)
    req_list = "".join(f"<li>{_e(item)}</li>" for item in requirements)
    review_list = "".join(f"<li>{_e(str(item).capitalize())}</li>" for item in reviews)
    source_list = "".join(
        f'<li><a href="{_e(src.get("url"))}" rel="noopener nofollow" target="_blank">{_e(src.get("label") or src.get("url"))}</a></li>'
        for src in sources if isinstance(src, dict) and src.get("url")
    )
    related_html = "".join(
        f'<a class="rel" href="/requirements/{_e(s)}"><b>{_e(_country_flag(p.get("country")))} {_e(p.get("countryName"))}</b><span>{_e(p.get("programme"))}</span></a>'
        for s, p in related
    )
    faq = [
        (f"What size is a {country} {programme} photo?", f"{out.get('widthPx')} × {out.get('heightPx')} pixels for digital use{', ' + _mm(profile) + ' when printed' if out.get('printWidthMm') else ''}. {PRODUCT} crops and resizes to this automatically."),
        (f"What background does a {country} {programme} photo need?", f"{BACKGROUND_LABELS.get(background.get('mode'), 'A plain, even background')}. Where the programme permits it, {PRODUCT} replaces a busy background with a plain one; otherwise it tells you to retake against a plain wall."),
        ("Can I take it with my phone?", "Yes. Stand in front of a plain wall in even daylight, hold the phone at eye level and use the guided camera or upload the photo."),
        ("Will it be accepted?", f"{PRODUCT} checks the photo against these published requirements and tells you plainly whether it is OK. The final decision always belongs to the issuing authority."),
    ]
    faq_html = "".join(f"<details><summary>{_e(q)}</summary><p>{_e(a)}</p></details>" for q, a in faq)
    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Photo requirements", "item": f"{base_url}/requirements"},
                {"@type": "ListItem", "position": 2, "name": f"{country} {programme}", "item": canonical},
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq
            ],
        },
    ]
    return (
        _head(title, description, canonical, jsonld)
        + _nav()
        + f"""
    <section class="page-hero">
      <div class="wrap">
        <p class="crumbs"><a href="/">Home</a> › <a href="/requirements">Photo requirements</a> › {_e(country)}</p>
        <span class="kicker">{_e(_country_flag(profile.get('country')))} {_e(country)} · {_e(profile.get('category'))}</span>
        <h1>{_e(country)} {_e(programme)} photo requirements</h1>
        <p class="lead">{_e(description)}</p>
        <div class="hero-cta">
          <a class="btn lg" href="/app?programme={_e(profile.get('id'))}">Check my photo <span class="arw" aria-hidden="true">→</span></a>
          <a class="btn lg ghost" href="/pricing">Pricing</a>
        </div>
      </div>
    </section>
    <section class="page-body">
      <div class="wrap page-grid">
        <div>
          <h2>Specifications</h2>
          <table class="spec"><tbody>{table}</tbody></table>
          {'<h2>Published requirements</h2><ul class="ticks">' + req_list + '</ul>' if req_list else ''}
          {'<h2>What a person still checks</h2><p class="muted">These points cannot be measured reliably by software, so the result asks you to confirm them:</p><ul class="dots">' + review_list + '</ul>' if review_list else ''}
          <h2>How {PRODUCT} prepares it</h2>
          <ol class="steps-list">
            <li><b>Choose this programme</b> in the studio — the size, head position, background and file limits above load automatically.</li>
            <li><b>Add the photo</b> — upload or use the guided camera.</li>
            <li><b>Get the verdict</b> — "Photo OK", or the one plain reason to retake.</li>
            <li><b>Download</b> — a {formats} file at {out.get('widthPx')} × {out.get('heightPx')} px, or a print sheet for {_mm(profile) if out.get('printWidthMm') else 'your printer'}.</li>
          </ol>
          <h2>Common questions</h2>
          <div class="faq-list">{faq_html}</div>
          {'<h2>Official sources</h2><ul class="sources">' + source_list + '</ul>' if source_list else ''}
          <p class="fine">Requirements change. This page reflects the rules encoded in {PRODUCT} as of {_e(profile.get('lastReviewed') or date.today().isoformat())}. {PRODUCT} is not affiliated with any government; the issuing authority makes the final decision.</p>
        </div>
        <aside>
          <div class="side-card">
            <h3>Check your photo now</h3>
            <p>One photo for CAD 9.99, or unlimited photos for your business from CAD 100/month.</p>
            <a class="btn block" href="/app?programme={_e(profile.get('id'))}">Open the checker</a>
            <a class="btn ghost block" href="/app?guest">Try the free demo</a>
          </div>
          {'<div class="side-card"><h3>Related programmes</h3><div class="rel-list">' + related_html + '</div></div>' if related_html else ''}
        </aside>
      </div>
    </section>"""
        + _footer()
    )


def render_requirements_index(slug_map: dict[str, dict], base_url: str) -> str:
    title = f"Passport & visa photo requirements by country ({date.today().year}) | {PRODUCT}"
    description = "Exact photo size, head position, background and file rules for passports, visas, PR cards and ID photos in Canada, the US, the UK, India, Europe and Asia-Pacific — with a free checker."
    canonical = f"{base_url}/requirements"
    groups: dict[str, list[tuple[str, dict]]] = {}
    for slug, profile in slug_map.items():
        if profile.get("country") == "STUDIO":
            continue
        groups.setdefault(profile.get("countryName") or profile.get("country"), []).append((slug, profile))
    order = sorted(groups.keys(), key=lambda name: (name not in {"Canada", "United States", "India", "United Kingdom"}, name))
    cards = ""
    for name in order:
        items = groups[name]
        flag = _country_flag(items[0][1].get("country"))
        links = "".join(
            f'<a href="/requirements/{_e(slug)}">{_e(profile.get("programme"))} <span>{_e(str((profile.get("output") or {}).get("widthPx")))} × {_e(str((profile.get("output") or {}).get("heightPx")))} px</span></a>'
            for slug, profile in items
        )
        cards += f'<div class="prog-group req-group"><h3>{_e(flag)} {_e(name)}</h3><div class="req-links">{links}</div></div>'
    jsonld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": canonical}]
    return (
        _head(title, description, canonical, jsonld)
        + _nav()
        + f"""
    <section class="page-hero">
      <div class="wrap">
        <span class="kicker">Photo requirements</span>
        <h1>Passport &amp; visa photo requirements by country</h1>
        <p class="lead">{_e(description)}</p>
      </div>
    </section>
    <section class="page-body"><div class="wrap"><div class="prog-groups">{cards}</div></div></section>"""
        + _footer()
    )


def render_audience(slug: str, base_url: str) -> str | None:
    data = AUDIENCES.get(slug)
    if not data:
        return None
    canonical = f"{base_url}/for/{slug}"
    points = "".join(f'<div class="tcard"><h4>{_e(h)}</h4><p>{_e(p)}</p></div>' for h, p in data["points"])
    jsonld = [{"@context": "https://schema.org", "@type": "WebPage", "name": data["title"], "url": canonical}]
    return (
        _head(f"{data['title']} | {PRODUCT}", data["intro"], canonical, jsonld)
        + _nav()
        + f"""
    <section class="page-hero">
      <div class="wrap">
        <span class="kicker">{_e(data['kicker'])}</span>
        <h1>{_e(data['heading'])}</h1>
        <p class="lead">{_e(data['intro'])}</p>
        <div class="hero-cta">
          <a class="btn lg" href="{_e(data['cta_href'])}">{_e(data['cta'])} <span class="arw" aria-hidden="true">→</span></a>
          <a class="btn lg ghost" href="/app?guest">Try the free demo</a>
        </div>
      </div>
    </section>
    <section class="page-body"><div class="wrap"><div class="trust-grid">{points}</div>
      <div class="plan-note" style="margin-top:34px">See <a href="/pricing">plans and pricing</a> or <a href="/requirements">every supported programme</a>.</div>
    </div></section>"""
        + _footer()
    )


def sitemap_xml(base_url: str, slug_map: dict[str, dict]) -> str:
    today = date.today().isoformat()
    urls = [("/", "1.0", "weekly"), ("/us", "1.0", "weekly"), ("/pricing", "0.9", "monthly"), ("/requirements", "0.9", "weekly")]
    urls += [(f"/for/{slug}", "0.8", "monthly") for slug in AUDIENCES]
    urls += [(f"/requirements/{slug}", "0.8", "monthly") for slug, profile in slug_map.items() if profile.get("country") != "STUDIO"]
    import kvnp_cities  # local import: kvnp_cities imports this module

    urls += kvnp_cities.sitemap_paths()
    body = "".join(
        f"<url><loc>{_e(base_url + path)}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        for path, prio, freq in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


def robots_txt(base_url: str) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /admin",
            "Disallow: /account",
            "Disallow: /crm",
            "Disallow: /activate",
            "Disallow: /invite",
            "Disallow: /studio-advanced",
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        ]
    )
