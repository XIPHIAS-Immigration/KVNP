"""City landing pages for local search ("passport photos Toronto" and so on).

Each page has its own programme mix and local note so it is useful on its
own, not a copy of the others with the city name swapped. No street
addresses are listed: PassportLens is online software, not a shop in the city.
"""

from __future__ import annotations

from datetime import date

import kvnp_pages as pages
from kvnp_pages import PRODUCT, _e, _footer, _head, _mm, _nav

# programme slugs (from kvnp_pages.build_slug_map)
CA_CORE = ["canada-passport-photo", "canada-permanent-resident-card-photo", "canada-citizenship-grant-photo", "canada-temporary-resident-visa-photo"]
US_CORE = ["united-states-passport-photo", "united-states-visa-ds-160-photo", "united-states-diversity-visa-dv-lottery-photo"]
INDIA = ["india-oci-card-application-photo", "india-passport-icao-upload-photo", "india-visa-online-e-visa-photo"]
EAST_ASIA = ["china-chinese-visa-application-photo", "hong-kong-hksar-passport-online-photo", "south-korea-online-passport-renewal-photo"]
EUROPE = ["united-kingdom-passport-digital-upload-photo", "france-schengen-visa-photo", "ireland-passport-photo", "italy-electronic-passport-photo"]

CITIES = {
    # ---------------- Canada ----------------
    "toronto": {
        "name": "Toronto", "region": "Ontario", "country": "CA",
        "note": "Toronto is Canada's busiest city for new passports, PR cards and citizenship applications, and one of its most international, so one family often needs photos for two or three different countries.",
        "programmes": CA_CORE + INDIA[:2] + ["china-chinese-visa-application-photo", "united-kingdom-passport-digital-upload-photo", "italy-electronic-passport-photo"],
    },
    "montreal": {
        "name": "Montreal", "region": "Quebec", "country": "CA",
        "note": "In Montreal, Canadian passport and citizenship photos sit alongside French and Schengen visa photos for travel to Europe. The size rules differ, and so does the head size.",
        "programmes": CA_CORE + ["france-schengen-visa-photo", "italy-electronic-passport-photo", "belgium-passport-photo"],
    },
    "vancouver": {
        "name": "Vancouver", "region": "British Columbia", "country": "CA",
        "note": "Vancouver families often renew Hong Kong, Korean or Chinese documents as well as Canadian ones. Those programmes use digital uploads with their own pixel and file-size limits.",
        "programmes": CA_CORE + EAST_ASIA + ["india-oci-card-application-photo"],
    },
    "calgary": {
        "name": "Calgary", "region": "Alberta", "country": "CA",
        "note": "Calgary has many newcomers moving from temporary status to PR and then citizenship, and each step needs a photo to a different specification.",
        "programmes": CA_CORE + ["india-oci-card-application-photo", "united-kingdom-passport-digital-upload-photo", "united-states-visa-ds-160-photo"],
    },
    "edmonton": {
        "name": "Edmonton", "region": "Alberta", "country": "CA",
        "note": "Edmonton applicants often need a Canadian passport photo for travel and a US DS-160 photo for cross-border visits. They look alike but are not the same size.",
        "programmes": CA_CORE + ["united-states-visa-ds-160-photo", "india-oci-card-application-photo", "united-kingdom-passport-digital-upload-photo"],
    },
    "ottawa": {
        "name": "Ottawa", "region": "Ontario", "country": "CA",
        "note": "Ottawa sees a lot of official and diplomatic travel, where Canadian passport photos and visa photos for other countries are needed on short notice.",
        "programmes": CA_CORE + ["france-schengen-visa-photo", "china-chinese-visa-application-photo", "india-visa-online-e-visa-photo"],
    },
    "winnipeg": {
        "name": "Winnipeg", "region": "Manitoba", "country": "CA",
        "note": "Manitoba's provincial nominee stream brings many newcomers through Winnipeg, so PR card and citizenship photos are some of the most common requests here.",
        "programmes": CA_CORE + ["india-oci-card-application-photo", "india-passport-icao-upload-photo", "united-kingdom-passport-digital-upload-photo"],
    },
    "mississauga": {
        "name": "Mississauga", "region": "Ontario", "country": "CA",
        "note": "Mississauga households regularly juggle Canadian, Indian and other passport renewals. Getting each photo right the first time saves a second trip.",
        "programmes": CA_CORE + INDIA + ["united-arab-emirates-passport-renewal-photo"],
    },
    "brampton": {
        "name": "Brampton", "region": "Ontario", "country": "CA",
        "note": "Brampton has one of Canada's largest Indian-Canadian communities, so OCI card and Indian passport photos are asked for almost as often as Canadian ones.",
        "programmes": INDIA + CA_CORE,
    },
    "surrey": {
        "name": "Surrey", "region": "British Columbia", "country": "CA",
        "note": "Surrey families often apply for Canadian citizenship and an Indian OCI card around the same time. The two photos have different sizes and backgrounds.",
        "programmes": CA_CORE + INDIA,
    },
    # ---------------- United States ----------------
    "new-york": {
        "name": "New York City", "region": "New York", "country": "US",
        "note": "New York handles more US passport applications than almost anywhere, and many New Yorkers also need visa or passport photos for a second country.",
        "programmes": US_CORE + ["india-oci-card-application-photo", "china-chinese-visa-application-photo", "united-kingdom-passport-digital-upload-photo", "ireland-passport-photo", "italy-electronic-passport-photo"],
    },
    "los-angeles": {
        "name": "Los Angeles", "region": "California", "country": "US",
        "note": "Los Angeles has large Korean, Chinese and Indian communities, so Korean passport renewals and Chinese visa photos are common next to US passports.",
        "programmes": US_CORE + EAST_ASIA + ["india-oci-card-application-photo"],
    },
    "chicago": {
        "name": "Chicago", "region": "Illinois", "country": "US",
        "note": "Chicago applicants often combine a US passport photo with an Irish, Polish or Indian document photo. Each has its own head-size rule.",
        "programmes": US_CORE + ["ireland-passport-photo", "poland-passport-photo", "india-oci-card-application-photo", "united-kingdom-passport-digital-upload-photo"],
    },
    "houston": {
        "name": "Houston", "region": "Texas", "country": "US",
        "note": "Houston's energy and medical sectors send people abroad often, so US passports and visa photos for India, the UAE and Europe are frequent requests.",
        "programmes": US_CORE + ["india-oci-card-application-photo", "united-arab-emirates-passport-renewal-photo", "france-schengen-visa-photo", "china-chinese-visa-application-photo"],
    },
    "phoenix": {
        "name": "Phoenix", "region": "Arizona", "country": "US",
        "note": "In Phoenix most requests are US passport photos for first-time applicants and families, plus visa photos for travel and study abroad.",
        "programmes": US_CORE + ["canada-temporary-resident-visa-photo", "united-kingdom-passport-digital-upload-photo", "india-oci-card-application-photo"],
    },
    "philadelphia": {
        "name": "Philadelphia", "region": "Pennsylvania", "country": "US",
        "note": "Philadelphia's universities bring international students who need visa photos, alongside local families renewing US passports.",
        "programmes": US_CORE + ["india-visa-online-e-visa-photo", "china-chinese-visa-application-photo", "italy-electronic-passport-photo", "ireland-passport-photo"],
    },
    "san-antonio": {
        "name": "San Antonio", "region": "Texas", "country": "US",
        "note": "San Antonio's military families often need US passport photos in a hurry for overseas postings, and correct first time matters when the timeline is tight.",
        "programmes": US_CORE + ["japan-passport-photo", "south-korea-online-passport-renewal-photo", "germany-secure-biometric-capture-photo"],
    },
    "san-diego": {
        "name": "San Diego", "region": "California", "country": "US",
        "note": "San Diego applicants often need US passport photos for cross-border travel, and many also need photos for Asian and European passports and visas.",
        "programmes": US_CORE + ["japan-passport-photo", "china-chinese-visa-application-photo", "australia-passport-photo", "united-kingdom-passport-digital-upload-photo"],
    },
    "dallas": {
        "name": "Dallas", "region": "Texas", "country": "US",
        "note": "Dallas–Fort Worth has one of the fastest-growing Indian-American communities, so OCI and Indian passport photos are asked for nearly as often as US passports.",
        "programmes": US_CORE + INDIA + ["united-arab-emirates-passport-renewal-photo"],
    },
    "san-jose": {
        "name": "San Jose", "region": "California", "country": "US",
        "note": "Silicon Valley's international workforce means San Jose sees many OCI, Chinese visa and Korean passport photos next to US passport renewals.",
        "programmes": US_CORE + ["india-oci-card-application-photo", "india-passport-icao-upload-photo", "china-chinese-visa-application-photo", "south-korea-online-passport-renewal-photo", "hong-kong-hksar-passport-online-photo"],
    },
}

PRICE = {"CA": ("CAD 9.99", "CAD 100"), "US": ("USD 7.99", "USD 75")}


def _submit_note(city: dict) -> str:
    name = city["name"]
    if city["country"] == "CA":
        return (
            f"Canadian passport applications from {name} go through Service Canada, either at a passport office or a Service Canada Centre, or by mail. "
            "PR card, citizenship and visa photos go to IRCC, printed or uploaded as the application form asks. "
            "PassportLens prepares the photo to the programme's size. For printed Canadian passport photos, the back must still be completed as Passport Canada requires."
        )
    return (
        f"US passport applications in {name} are accepted at passport acceptance facilities (many post offices, libraries and county clerk offices), "
        "or renewals can be sent by mail, or online where eligible. DS-160 and DV Lottery photos are uploaded digitally, so the file size and pixel limits matter as much as the framing."
    )


def render_city(slug: str, base_url: str, slug_map: dict[str, dict]) -> str | None:
    city = CITIES.get(slug)
    if not city:
        return None
    name, region, country = city["name"], city["region"], city["country"]
    single, silver = PRICE[country]
    canonical = f"{base_url}/passport-photos/{slug}"
    year = date.today().year
    title = f"Passport photos in {name}, {region}: checked online ({year}) | {PRODUCT}"
    description = (
        f"Make a passport or visa photo in {name} from your phone and have it checked against the official rules. "
        f"{'Canadian passport, PR card and citizenship' if country == 'CA' else 'US passport, DS-160 and DV Lottery'} photos plus 30+ other programmes. {single} per photo."
    )

    cards = []
    for prog_slug in city["programmes"]:
        profile = slug_map.get(prog_slug)
        if not profile:
            continue
        label = f"{profile.get('countryName') or profile.get('country')} {pages.programme_name(profile)}"
        cards.append(
            f'<a class="rel" href="/requirements/{_e(prog_slug)}"><b>{_e(label)}</b><span>{_e(_mm(profile))}</span></a>'
        )
    others = [(s, c) for s, c in CITIES.items() if s != slug and c["country"] == country]
    nearby = " · ".join(f'<a href="/passport-photos/{_e(s)}">{_e(c["name"])}</a>' for s, c in others)

    faqs = [
        (
            f"How much is a passport photo in {name} with {PRODUCT}?",
            f"One checked photo costs {single}, and you can download it as a file or a print sheet. Businesses in {name} can take unlimited photos on Silver for {silver} a month.",
        ),
        (
            f"Can I take my passport photo at home in {name}?",
            "Yes, if the programme allows it. Stand in front of a plain, light wall with even light from the front and have someone take the photo from about 1.2 metres away, with the camera at eye level. "
            f"{PRODUCT} checks the result and tells you plainly if you need to retake it.",
        ),
        (
            "Is acceptance guaranteed?",
            f"No tool can guarantee it, because the issuing authority makes the final decision. {PRODUCT} checks every measurable rule it publishes (size, head position, background, file limits) so avoidable mistakes are caught before you submit.",
        ),
    ]
    faq_html = "".join(f"<details class=\"faq-item\"><summary>{_e(q)}</summary><p>{_e(a)}</p></details>" for q, a in faqs)
    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": f"Passport photo checking in {name}",
            "serviceType": "Passport and visa photo preparation",
            "provider": {"@type": "Organization", "name": PRODUCT, "url": base_url + "/"},
            "areaServed": {"@type": "City", "name": name, "containedInPlace": {"@type": "State" if country == "US" else "AdministrativeArea", "name": region}},
            "offers": {"@type": "Offer", "price": single.split()[1], "priceCurrency": single.split()[0]},
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs],
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Passport photos by city", "item": f"{base_url}/passport-photos"},
                {"@type": "ListItem", "position": 2, "name": name, "item": canonical},
            ],
        },
    ]
    head = _head(title, description, canonical, jsonld)
    if country == "US":
        head = head.replace('<html lang="en-CA">', '<html lang="en-US">', 1)
    home = "/us" if country == "US" else "/"
    cur = "&cur=usd" if country == "US" else ""
    return (
        head
        + _nav()
        + f"""
    <section class="page-hero">
      <div class="wrap">
        <div class="crumbs"><a href="{home}">Home</a> › <a href="/passport-photos">Passport photos by city</a> › {_e(name)}</div>
        <span class="kicker">{_e(name)}, {_e(region)}</span>
        <h1>Passport photos in {_e(name)}, checked before you submit.</h1>
        <p class="lead">{_e(city['note'])}</p>
        <div class="hero-cta">
          <a class="btn lg" href="/pricing?plan=single{cur}">Make my photo · {_e(single)} <span class="arw" aria-hidden="true">→</span></a>
          <a class="btn lg ghost" href="/app?guest">Try the free demo</a>
        </div>
      </div>
    </section>
    <section class="page-body"><div class="wrap">
      <div class="page-grid">
        <div>
          <h2>Photos people in {_e(name)} ask for most</h2>
          <p class="muted" style="margin:8px 0 18px">Each one has its own size, head position and background rule. Open one to see the exact requirements.</p>
          <div class="rel-list city-programmes">{''.join(cards)}</div>

          <h2 style="margin-top:40px">How it works</h2>
          <div class="trust-grid city-steps" style="margin-top:18px">
            <div class="tcard"><h4>1. Pick the programme</h4><p>Choose the passport, visa or ID you are applying for. The official rules load automatically.</p></div>
            <div class="tcard"><h4>2. Take or upload a photo</h4><p>A phone photo against a plain wall is enough. Light and tilt are corrected automatically; the face is never altered.</p></div>
            <div class="tcard"><h4>3. Get a plain answer</h4><p>"Photo OK", or exactly what to change. Download the file or a 4×6 print sheet.</p></div>
          </div>

          <h2 style="margin-top:40px">Submitting your application from {_e(name)}</h2>
          <p style="margin-top:12px">{_e(_submit_note(city))}</p>

          <h2 style="margin-top:40px">Questions</h2>
          <div class="faq-list" style="margin-top:14px">{faq_html}</div>
        </div>
        <aside>
          <div class="side-card">
            <h4>For {_e(name)} businesses</h4>
            <p class="muted small" style="margin:8px 0 14px">Photo studios, pharmacies, print shops and immigration consultants in {_e(name)} can run a passport photo counter with {PRODUCT}: unlimited photos, client records and print sheets.</p>
            <a class="btn block" href="/pricing?plan=silver{cur}">Silver · {_e(silver)}/month</a>
            <a class="btn ghost block" style="margin-top:10px" href="/for/photo-studios">See business plans</a>
          </div>
        </aside>
      </div>
      <div class="plan-note" style="margin-top:34px">Other cities: {nearby}.</div>
    </div></section>"""
        + _footer()
    )


def render_city_index(base_url: str) -> str:
    canonical = f"{base_url}/passport-photos"
    title = f"Passport photos by city: Canada and the United States | {PRODUCT}"
    description = "Online passport and visa photos, checked against the official rules, for Toronto, Montreal, Vancouver, Calgary, New York, Los Angeles, Chicago, Houston and more."

    def block(country, heading):
        links = "".join(
            f'<a class="rel" href="/passport-photos/{_e(s)}"><b>{_e(c["name"])}</b><span>{_e(c["region"])}</span></a>'
            for s, c in CITIES.items()
            if c["country"] == country
        )
        return f'<h2 style="margin-top:28px">{heading}</h2><div class="rel-list city-index" style="margin-top:14px">{links}</div>'

    jsonld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": canonical}]
    return (
        _head(title, description, canonical, jsonld)
        + _nav()
        + f"""
    <section class="page-hero">
      <div class="wrap">
        <span class="kicker">Passport photos by city</span>
        <h1>Passport and visa photos, wherever you are applying from.</h1>
        <p class="lead">{_e(description)}</p>
      </div>
    </section>
    <section class="page-body"><div class="wrap">
      {block("CA", "Canada")}
      {block("US", "United States")}
    </div></section>"""
        + _footer()
    )


def sitemap_paths() -> list[tuple[str, str, str]]:
    return [("/passport-photos", "0.7", "monthly")] + [(f"/passport-photos/{s}", "0.7", "monthly") for s in CITIES]
