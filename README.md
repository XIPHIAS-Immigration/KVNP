# PassportLens

Passport and visa photo software for Canada: 35+ programmes with the issuing
authority's published rules built in, a plain "Photo OK / Retake" verdict, clean
background and print sheets, plus a small CRM for the businesses that use it.
Built and operated by KVNP Holdings Inc.

## Run locally

```powershell
npm run dev          # starts server.py on http://localhost:4173
```

No `npm install` is needed. Python 3.11+ with the packages in
`requirements.txt` must be installed. The first start downloads the small
MediaPipe models into `models/`. Copy `.env.example` to `.env` to change
settings; without a `.env` the app runs with payments disabled, which lets you
create accounts directly from `/api/auth/signup` for testing.

## Pages

| Path | What it is |
|------|------------|
| `/` and `/us` | Marketing landing page for Canada / the United States (UPS-style brown+gold theme, anime.js motion) |
| `/app` | The 5-step studio: programme → photo → result → adjust → download |
| `/app?guest` | Free demo on bundled sample portraits (no uploads, no downloads) |
| `/pricing` | Plans: One photo CAD 9.99 / USD 7.99, Silver CAD 100 (USD 75)/mo or CAD 999 (USD 749)/yr, Gold, Platinum — CAD/USD toggle |
| `/activate` | After Stripe Checkout: choose a password, account is created |
| `/account` | Plan, billing portal, team logins, recent photos |
| `/crm` | Clients & photos for business plans: sales, paid/unpaid, receipts, CSV |
| `/admin` | Operations: businesses (create Gold/Platinum + invite owner), users, enquiries, traffic |
| `/studio-advanced` | The full technical studio (admins only) |
| `/requirements`, `/requirements/<slug>` | SEO pages generated from the rules |
| `/for/<audience>` | SEO pages for studios, consultants, pharmacies, print shops |
| `/sitemap.xml`, `/robots.txt` | For search engines |

## Plans and access

- **One photo** (individual): Stripe one-time payment → 1 photo credit. The first
  download of a photo uses the credit; that photo can be re-downloaded for 30 days.
- **Silver**: Stripe subscription (monthly/yearly). A one-login business is created
  automatically; unlimited photos and the CRM.
- **Gold / Platinum**: sold by contact form. Create the business in `/admin`, which
  emails the owner an invitation. Owners invite staff (10 logins for Gold,
  unlimited for Platinum).
- The photo engine (`/api/process`) requires a signed-in account with an active
  plan or a credit; guests can only run the bundled demo portraits.
- Every programme allows background clean-up, brightness and straightening
  (the face is never altered). Set `KVNP_STRICT_POLICY=true` to restore the
  old per-country validation-only locks.

## Code map

- `server.py` — FastAPI app: photo pipeline (MediaPipe + OpenCV + optional BiRefNet), auth, Stripe, downloads.
- `kvnp_platform.py` — database models and queries (SQLite locally, PostgreSQL in production).
- `kvnp_business.py` — organisations, seats, invites, photo credits, CRM.
- `kvnp_routes.py` — team, CRM, admin and SEO page routes.
- `kvnp_payments.py` — Stripe gateway (Silver monthly/yearly, single photo, optional Stripe Tax).
- `kvnp_mail.py` — SMTP email (enquiry alerts, invitations, welcome).
- `kvnp_pages.py` — server-rendered requirement and audience pages.
- `src/rules.js` ↔ `data/profiles.json` — the programme rules (keep in sync with `tools/sync_rules.py`).
- `studio.html` + `src/studio.js` — the simple studio; `index.html` + `src/app.js` — the advanced studio.
- `src/theme.css` — the design system (navy + gold); `src/landing.css`, `src/portal.css`, `src/studio.css`, `src/pages.css`.

## Tests

```powershell
python -m py_compile server.py kvnp_platform.py kvnp_business.py kvnp_routes.py kvnp_payments.py kvnp_mail.py kvnp_pages.py
python tools/test_matting.py
python tools/test_corrections.py
python tools/test_print_sheet.py
python tools/test_platform.py
```

## Deploy

See `docs/aws-ec2-demo.md` (Docker Compose on EC2, CPU or GPU) and
`docs/stripe-billing.md` (Stripe prices, webhook, tax). Set the email variables
in `.env` (AWS SES SMTP credentials work) so the contact form and invitations
are delivered.

Create the first administrator by signing up normally, then promoting from the
server shell:

```bash
python tools/promote_admin.py you@example.com
```
