"""Additional PassportLens routes: team / invites, CRM, admin, marketing pages.

Registered from server.py with `register(app, globals())` so these handlers can
reuse the server's auth helpers without a circular import."""

from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

import kvnp_business as business
import kvnp_mail as mail
import kvnp_pages as pages
import kvnp_cities as cities
import kvnp_platform as platform


_LANDING_CACHE: dict = {}


def render_landing(root: Path, region: str, base_url: str) -> str:
    """Serve landing.html for Canada (default) or the US: flips the <span data-r>
    pairs server-side so search engines see region-specific copy, and sets
    lang / canonical / hreflang accordingly."""
    path = root / "landing.html"
    mtime = path.stat().st_mtime
    cached = _LANDING_CACHE.get("src")
    if not cached or cached[0] != mtime:
        cached = (mtime, path.read_text(encoding="utf-8"))
        _LANDING_CACHE["src"] = cached
    html_text = cached[1]
    region = "us" if region == "us" else "ca"
    other = "ca" if region == "us" else "us"
    # show this region's spans, hide the other's
    html_text = re.sub(r'<span data-r="%s" hidden>' % region, '<span data-r="%s">' % region, html_text)
    html_text = re.sub(r'<span data-r="%s">' % other, '<span data-r="%s" hidden>' % other, html_text)
    html_text = html_text.replace('<html lang="en-CA">', '<html lang="en-%s" data-region="%s">' % (region.upper(), region), 1)
    if region == "us":
        html_text = html_text.replace(
            "<title>PassportLens | Passport &amp; Visa Photo Software for Canada</title>",
            "<title>PassportLens | Passport &amp; Visa Photo Software for the United States</title>", 1)
        html_text = html_text.replace(
            "For individuals, photo studios, immigration consultants and pharmacies across Canada.",
            "For individuals, photo studios, immigration attorneys and pharmacies across the United States. US passport, DS-160 visa and diversity visa photos.", 1)
        html_text = html_text.replace('<link rel="canonical" href="https://passport.kvnp.ca/" />', '<link rel="canonical" href="https://passport.kvnp.ca/us" />', 1)
        html_text = html_text.replace('<meta property="og:url" content="https://passport.kvnp.ca/" />', '<meta property="og:url" content="https://passport.kvnp.ca/us" />', 1)
    # keep canonical/hreflang on the real public host
    if base_url and base_url != "https://passport.kvnp.ca":
        html_text = html_text.replace("https://passport.kvnp.ca", base_url)
    return html_text


def register(app, env: dict) -> None:
    ROOT: Path = env["ROOT"]
    ARTIFACT_DIR: Path = env["ARTIFACT_DIR"]
    require_identity = env["require_identity"]
    require_csrf = env["require_csrf"]
    require_admin = env["require_admin"]
    current_identity = env["current_identity"]
    authenticated_response = env["authenticated_response"]
    read_json_body_error = env["read_json_body_error"]
    normalise_email = env["normalise_email"]
    valid_email = env["valid_email"]
    public_url = env["public_url"]
    PASSWORD_HASHER = env["PASSWORD_HASHER"]
    PROFILE_REGISTRY: dict = env["PROFILE_REGISTRY"]
    SLUG_MAP = pages.build_slug_map(list(PROFILE_REGISTRY.values()))
    env["SLUG_MAP"] = SLUG_MAP

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    async def json_body(request: Request) -> dict:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body.")
        return body if isinstance(body, dict) else {}

    def require_org(identity, need_active: bool = True):
        org = business.org_for_user(identity[0].id)
        if not org:
            if identity[0].role == "admin":
                raise HTTPException(status_code=404, detail="Admins use the admin panel; no business is attached to this account.")
            raise HTTPException(status_code=403, detail="This feature needs a business plan (Silver, Gold or Platinum).")
        if need_active and not business.org_is_active(org):
            raise HTTPException(status_code=402, detail="Your business plan is not active. Renew it from your account.")
        return org

    def require_owner(identity):
        org = require_org(identity, need_active=False)
        if identity[0].org_role != "owner" and identity[0].role != "admin":
            raise HTTPException(status_code=403, detail="Only the business owner can manage the team.")
        return org

    def invite_url(request: Request, token: str) -> str:
        return f"{public_url(request)}/invite?token={token}"

    def int_or_none(value):
        if value in (None, ""):
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid number.")

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    @app.get("/crm")
    def crm_page():
        return FileResponse(ROOT / "crm.html")

    @app.get("/invite")
    def invite_page():
        return FileResponse(ROOT / "invite.html")

    @app.get("/receipt/{project_id}")
    def receipt_page(project_id: str):
        return FileResponse(ROOT / "receipt.html")

    @app.get("/studio-advanced")
    def studio_advanced_page(request: Request):
        identity = current_identity(request)
        if not identity or identity[0].role != "admin":
            return RedirectResponse("/app", status_code=302)
        return FileResponse(ROOT / "index.html")

    @app.get("/requirements")
    def requirements_index(request: Request):
        return Response(pages.render_requirements_index(SLUG_MAP, public_url(request)), media_type="text/html")

    @app.get("/requirements/{slug}")
    def requirements_page(slug: str, request: Request):
        profile = SLUG_MAP.get(slug)
        if not profile:
            # allow the raw profile id as well
            profile = PROFILE_REGISTRY.get(slug)
            if profile:
                for candidate, item in SLUG_MAP.items():
                    if item is profile:
                        return RedirectResponse(f"/requirements/{candidate}", status_code=301)
            raise HTTPException(status_code=404, detail="Unknown programme.")
        related = [
            (s, p)
            for s, p in SLUG_MAP.items()
            if p is not profile and (p.get("country") == profile.get("country") or p.get("category") == profile.get("category"))
        ][:6]
        return Response(pages.render_requirements(profile, slug, public_url(request), related), media_type="text/html")

    @app.get("/for/{slug}")
    def audience_page(slug: str, request: Request):
        html_text = pages.render_audience(slug, public_url(request))
        if not html_text:
            raise HTTPException(status_code=404, detail="Page not found.")
        return Response(html_text, media_type="text/html")

    @app.get("/passport-photos")
    def city_index(request: Request):
        return Response(cities.render_city_index(public_url(request)), media_type="text/html")

    @app.get("/passport-photos/{slug}")
    def city_page(slug: str, request: Request):
        html_text = cities.render_city(slug, public_url(request), SLUG_MAP)
        if not html_text:
            raise HTTPException(status_code=404, detail="Page not found.")
        return Response(html_text, media_type="text/html")

    @app.get("/sitemap.xml")
    def sitemap(request: Request):
        return Response(pages.sitemap_xml(public_url(request), SLUG_MAP), media_type="application/xml")

    @app.get("/robots.txt")
    def robots(request: Request):
        return Response(pages.robots_txt(public_url(request)), media_type="text/plain")

    @app.get("/api/demo")
    def demo_list():
        folder = ROOT / "assets" / "demo"
        files = sorted(p.name for p in folder.glob("*.jpg")) if folder.exists() else []
        return {"ok": True, "files": files}

    # ------------------------------------------------------------------
    # team / invites (Gold + Platinum owners; admins for any org)
    # ------------------------------------------------------------------
    @app.get("/api/team")
    def team_get(request: Request):
        identity = require_identity(request)
        org = require_org(identity, need_active=False)
        return {
            "ok": True,
            "org": business.org_dict(org, business.seats_used(org.id)),
            "active": business.org_is_active(org),
            "members": business.org_members(org.id),
            "invites": business.list_invites(org.id) if identity[0].org_role == "owner" else [],
            "canManage": identity[0].org_role == "owner" and org.plan in {"gold", "platinum"},
            "mailConfigured": mail.configured(),
        }

    @app.patch("/api/team")
    async def team_update(request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_owner(identity)
        body = await json_body(request)
        updated = business.update_org(org.id, name=body.get("name"))
        return {"ok": True, "org": business.org_dict(updated, business.seats_used(org.id))}

    @app.post("/api/team/invites")
    async def team_invite(request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_owner(identity)
        if org.plan not in {"gold", "platinum"}:
            raise HTTPException(status_code=403, detail="Staff logins are included with Gold and Platinum. Contact us to upgrade.")
        body = await json_body(request)
        email = normalise_email(body.get("email"))
        if not valid_email(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address.")
        try:
            invite, token = business.create_invite(org.id, email, "member", identity[0].id, str(body.get("name") or ""))
        except ValueError as error:
            messages = {
                "seat_limit": f"All {org.seat_limit} logins are in use. Remove a member or contact us for more.",
                "already_member": "That person is already in your team.",
                "member_elsewhere": "That email already belongs to another business on PassportLens.",
            }
            raise HTTPException(status_code=409, detail=messages.get(str(error), "Could not create the invite."))
        url = invite_url(request, token)
        sent = mail.send_invite(email, org.name, url, identity[0].name)
        platform.record_event("invite_sent", identity[0].id, metadata={"orgId": org.id, "inviteId": invite.id})
        return {"ok": True, "invite": business.invite_dict(invite), "inviteUrl": None if sent else url, "emailed": sent}

    @app.delete("/api/team/invites/{invite_id}")
    def team_invite_delete(invite_id: str, request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_owner(identity)
        if not business.delete_invite(org.id, invite_id):
            raise HTTPException(status_code=404, detail="Invite not found.")
        return {"ok": True}

    @app.delete("/api/team/members/{user_id}")
    def team_member_delete(user_id: int, request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_owner(identity)
        if not business.remove_member(org.id, user_id):
            raise HTTPException(status_code=404, detail="Member not found (the owner cannot be removed).")
        return {"ok": True}

    @app.get("/api/invites/{token}")
    def invite_lookup(token: str):
        found = business.invite_by_token(token)
        if not found:
            raise HTTPException(status_code=404, detail="This invitation is invalid or has expired.")
        invite, org = found
        existing = platform.get_user_by_email(invite.email)
        return {
            "ok": True,
            "email": invite.email,
            "name": invite.name,
            "orgName": org.name if org else "",
            "plan": org.plan if org else None,
            "existingAccount": bool(existing),
        }

    @app.post("/api/invites/{token}/accept")
    async def invite_accept(token: str, request: Request):
        body = await json_body(request)
        found = business.invite_by_token(token)
        if not found:
            raise HTTPException(status_code=404, detail="This invitation is invalid or has expired.")
        invite, org = found
        existing = platform.get_user_by_email(invite.email)
        password = str(body.get("password") or "")
        name = str(body.get("name") or "").strip()
        if existing:
            if not env["verify_user_password"](existing, password):
                raise HTTPException(status_code=401, detail="That email already has an account. Enter its existing password.")
            password_hash = None
        else:
            if len(password) < 8 or len(password) > 256:
                raise HTTPException(status_code=422, detail="Password must be 8 to 256 characters.")
            if len(name) < 2:
                raise HTTPException(status_code=422, detail="Enter your full name.")
            password_hash = PASSWORD_HASHER.hash(password)
        try:
            user = business.accept_invite(token, name, password_hash)
        except ValueError as error:
            raise HTTPException(status_code=409, detail={"member_elsewhere": "This account already belongs to another business."}.get(str(error), "Could not accept the invitation."))
        platform.touch_login(user.id)
        platform.record_event("invite_accepted", user.id, metadata={"orgId": org.id if org else None})
        return authenticated_response(user)

    # ------------------------------------------------------------------
    # CRM
    # ------------------------------------------------------------------
    @app.get("/api/crm/summary")
    def crm_summary(request: Request):
        identity = require_identity(request)
        org = require_org(identity)
        return {"ok": True, "org": business.org_dict(org, business.seats_used(org.id)), "summary": business.crm_summary(org.id), "recent": business.org_projects(org.id, limit=8)}

    @app.get("/api/crm/clients")
    def crm_clients(request: Request):
        identity = require_identity(request)
        org = require_org(identity)
        return {"ok": True, "clients": business.list_clients(org.id, str(request.query_params.get("q") or ""))}

    @app.post("/api/crm/clients")
    async def crm_client_create(request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_org(identity)
        body = await json_body(request)
        try:
            client = business.create_client(org.id, identity[0].id, str(body.get("name") or ""), str(body.get("phone") or ""), str(body.get("email") or ""), str(body.get("notes") or ""))
        except ValueError:
            raise HTTPException(status_code=422, detail="Enter the client's name.")
        return {"ok": True, "client": business.client_dict(client)}

    @app.get("/api/crm/clients/{client_id}")
    def crm_client_get(client_id: str, request: Request):
        identity = require_identity(request)
        org = require_org(identity)
        client = business.get_client(org.id, client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found.")
        photos = business.org_projects(org.id, client_id=client_id)
        revenue = sum(int(p["saleAmountMinor"] or 0) for p in photos)
        unpaid = sum(int(p["saleAmountMinor"] or 0) for p in photos if p["salePaid"] is False)
        return {"ok": True, "client": business.client_dict(client, len(photos), photos[0]["createdAt"] if photos else None, revenue, unpaid), "photos": photos}

    @app.patch("/api/crm/clients/{client_id}")
    async def crm_client_update(client_id: str, request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_org(identity)
        body = await json_body(request)
        client = business.update_client(org.id, client_id, name=body.get("name"), phone=body.get("phone"), email=body.get("email"), notes=body.get("notes"))
        if not client:
            raise HTTPException(status_code=404, detail="Client not found.")
        return {"ok": True, "client": business.client_dict(client)}

    @app.get("/api/crm/photos")
    def crm_photos(request: Request):
        identity = require_identity(request)
        org = require_org(identity)
        return {"ok": True, "photos": business.org_projects(org.id, client_id=request.query_params.get("client_id") or None)}

    @app.post("/api/crm/photos")
    async def crm_photo_save(request: Request):
        """Attach a studio project to a client (creating the client if needed)
        and record the sale."""
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_org(identity)
        body = await json_body(request)
        project_id = str(body.get("projectId") or "")
        project = platform.get_owned_project(identity[0].id, project_id)
        if not project and identity[0].role != "admin":
            existing = business.get_org_project(org.id, project_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Save the photo first, then attach it to a client.")
        client_id = body.get("clientId")
        new_client = body.get("newClient")
        if not client_id and isinstance(new_client, dict) and str(new_client.get("name") or "").strip():
            client = business.create_client(org.id, identity[0].id, str(new_client.get("name")), str(new_client.get("phone") or ""), str(new_client.get("email") or ""), str(new_client.get("notes") or ""))
            client_id = client.id
        amount = body.get("saleAmount")
        amount_minor = None if amount in (None, "") else int(round(float(amount) * 100))
        try:
            updated = business.attach_project(org.id, project_id, client_id if client_id is not None else None, amount_minor, str(body.get("currency") or "CAD"), body.get("salePaid"), body.get("verdict"))
        except ValueError:
            raise HTTPException(status_code=404, detail="Client not found.")
        if not updated:
            raise HTTPException(status_code=404, detail="Project not found.")
        platform.record_event("photo_saved_to_client", identity[0].id, project_id, metadata={"orgId": org.id, "clientId": client_id})
        photos = business.org_projects(org.id, limit=1)
        item = next((p for p in business.org_projects(org.id, client_id=client_id) if p["id"] == project_id), None) if client_id else None
        return {"ok": True, "photo": item or (photos[0] if photos else None), "clientId": client_id}

    @app.patch("/api/crm/photos/{project_id}")
    async def crm_photo_update(project_id: str, request: Request):
        identity = require_identity(request)
        require_csrf(request, identity)
        org = require_org(identity)
        body = await json_body(request)
        amount = body.get("saleAmount")
        amount_minor = None if amount in (None, "") else int(round(float(amount) * 100))
        try:
            updated = business.attach_project(org.id, project_id, body.get("clientId"), amount_minor, body.get("currency"), body.get("salePaid"), body.get("verdict"))
        except ValueError:
            raise HTTPException(status_code=404, detail="Client not found.")
        if not updated:
            raise HTTPException(status_code=404, detail="Photo not found.")
        return {"ok": True}

    @app.get("/api/crm/photos/{project_id}/file")
    def crm_photo_file(project_id: str, request: Request):
        identity = require_identity(request)
        org = require_org(identity)
        project = business.get_org_project(org.id, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Photo not found.")
        artifact = platform.get_artifact(project.user_id, project_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="This photo's file has expired (files are kept 30 days).")
        path = Path(artifact.storage_path).resolve()
        if ARTIFACT_DIR not in path.parents or not path.is_file():
            raise HTTPException(status_code=404, detail="File not available.")
        platform.record_download(project.user_id, project_id, "crm_redownload", artifact.format, artifact.bytes, False)
        return FileResponse(path, media_type=artifact.format, filename=f"passportlens-{project.profile_id}-{project_id[:8]}.jpg")

    @app.get("/api/crm/receipt/{project_id}")
    def crm_receipt(project_id: str, request: Request):
        identity = require_identity(request)
        org = require_org(identity, need_active=False)
        data = business.receipt_data(org.id, project_id)
        if not data:
            raise HTTPException(status_code=404, detail="Photo not found.")
        return {"ok": True, **data}

    @app.get("/api/crm/export.csv")
    def crm_export(request: Request):
        identity = require_identity(request)
        org = require_org(identity, need_active=False)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in business.export_rows(org.id):
            writer.writerow(row)
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="passportlens-{re.sub(r"[^a-z0-9]+", "-", org.name.lower())[:40]}.csv"'},
        )

    # ------------------------------------------------------------------
    # admin
    # ------------------------------------------------------------------
    @app.get("/api/admin/overview")
    def admin_overview(request: Request):
        require_admin(request)
        dashboard = platform.admin_dashboard()
        return {
            "ok": True,
            "stats": business.admin_overview(),
            "metrics": dashboard.get("metrics", {}),
            "traffic": dashboard.get("traffic", {}),
            "funnel": dashboard.get("funnel"),
            "destinations": dashboard.get("destinations", []),
            "recentActivity": dashboard.get("recentActivity", []),
            "organisations": business.list_orgs(),
            "users": business.list_users(),
            "enquiries": dashboard.get("enquiries", []),
            "subscriptions": dashboard.get("subscriptions", []),
            "billingPayments": dashboard.get("billingPayments", []),
            "mailConfigured": mail.configured(),
            "plans": business.PLANS,
        }

    @app.post("/api/admin/orgs")
    async def admin_org_create(request: Request):
        identity = require_admin(request, csrf=True)
        body = await json_body(request)
        plan = str(body.get("plan") or "gold")
        if plan not in business.PLANS:
            raise HTTPException(status_code=422, detail="Plan must be silver, gold or platinum.")
        name = str(body.get("name") or "").strip()
        if len(name) < 2:
            raise HTTPException(status_code=422, detail="Enter the business name.")
        owner_email = normalise_email(body.get("ownerEmail"))
        owner = platform.get_user_by_email(owner_email) if owner_email else None
        if owner and owner.org_id:
            raise HTTPException(status_code=409, detail="That email already belongs to another business.")
        org = business.create_org(
            name,
            plan,
            owner_user_id=owner.id if owner else None,
            seat_limit=int_or_none(body.get("seatLimit")),
            plan_source="manual",
            plan_status="active",
            notes=str(body.get("notes") or ""),
        )
        result = {"ok": True, "org": business.org_dict(org, business.seats_used(org.id)), "inviteUrl": None, "emailed": False}
        if owner_email and not owner:
            if not valid_email(owner_email):
                raise HTTPException(status_code=422, detail="Enter a valid owner email.")
            invite, token = business.create_invite(org.id, owner_email, "owner", identity[0].id, str(body.get("ownerName") or ""), enforce_seats=False)
            url = invite_url(request, token)
            sent = mail.send_invite(owner_email, org.name, url, "PassportLens")
            result.update({"inviteUrl": url if not sent else None, "emailed": sent, "invite": business.invite_dict(invite)})
        return result

    @app.get("/api/admin/orgs/{org_id}")
    def admin_org_get(org_id: str, request: Request):
        require_admin(request)
        org = business.get_org(org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Business not found.")
        owner = platform.get_user(org.owner_user_id) if org.owner_user_id else None
        return {
            "ok": True,
            "org": business.org_dict(org, business.seats_used(org.id), owner),
            "active": business.org_is_active(org),
            "members": business.org_members(org.id),
            "invites": business.list_invites(org.id),
            "photos": business.org_projects(org.id, limit=50),
            "summary": business.crm_summary(org.id),
        }

    @app.patch("/api/admin/orgs/{org_id}")
    async def admin_org_update(org_id: str, request: Request):
        require_admin(request, csrf=True)
        body = await json_body(request)
        org = business.update_org(
            org_id,
            name=body.get("name"),
            plan=body.get("plan"),
            plan_status=body.get("planStatus"),
            plan_source=body.get("planSource"),
            seat_limit=int_or_none(body.get("seatLimit")),
            notes=body.get("notes"),
        )
        if not org:
            raise HTTPException(status_code=404, detail="Business not found.")
        return {"ok": True, "org": business.org_dict(org, business.seats_used(org.id))}

    @app.post("/api/admin/orgs/{org_id}/invites")
    async def admin_org_invite(org_id: str, request: Request):
        identity = require_admin(request, csrf=True)
        org = business.get_org(org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Business not found.")
        body = await json_body(request)
        email = normalise_email(body.get("email"))
        if not valid_email(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address.")
        role = "owner" if body.get("role") == "owner" else "member"
        try:
            invite, token = business.create_invite(org.id, email, role, identity[0].id, str(body.get("name") or ""), enforce_seats=role != "owner")
        except ValueError as error:
            raise HTTPException(status_code=409, detail={"seat_limit": "All logins are in use for this business.", "already_member": "Already a member.", "member_elsewhere": "That email belongs to another business."}.get(str(error), "Could not create the invite."))
        url = invite_url(request, token)
        sent = mail.send_invite(email, org.name, url, "PassportLens")
        return {"ok": True, "invite": business.invite_dict(invite), "inviteUrl": url if not sent else None, "emailed": sent}

    @app.delete("/api/admin/orgs/{org_id}/invites/{invite_id}")
    def admin_org_invite_delete(org_id: str, invite_id: str, request: Request):
        require_admin(request, csrf=True)
        if not business.delete_invite(org_id, invite_id):
            raise HTTPException(status_code=404, detail="Invite not found.")
        return {"ok": True}

    @app.delete("/api/admin/orgs/{org_id}/members/{user_id}")
    def admin_org_member_delete(org_id: str, user_id: int, request: Request):
        require_admin(request, csrf=True)
        if not business.remove_member(org_id, user_id):
            raise HTTPException(status_code=404, detail="Member not found (owner cannot be removed).")
        return {"ok": True}

    @app.post("/api/admin/users/{user_id}/credits")
    async def admin_grant_credits(user_id: int, request: Request):
        identity = require_admin(request, csrf=True)
        body = await json_body(request)
        count = max(1, min(100, int(body.get("count") or 1)))
        user = platform.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        credit = business.grant_credit(user_id, f"admin-{identity[0].id}-{platform.now_ts()}", count)
        return {"ok": True, "credits": business.credits_remaining(user_id), "creditId": credit.id if credit else None}

    print(f"[kvnp] extra routes registered ({len(SLUG_MAP)} requirement pages)", file=sys.stderr, flush=True)
