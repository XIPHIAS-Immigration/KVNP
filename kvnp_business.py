"""Business layer for PassportLens: organisations (plans + seats), invites,
single-photo credits, and the per-business CRM (clients, photos, sales).

Uses the same SQLAlchemy Base / session as kvnp_platform so everything lives in
one database. Import this module BEFORE kvnp_platform.initialise() so the new
tables are created, then call ensure_schema() once to add columns that were
introduced after the original tables were created."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, func, inspect, select, text
from sqlalchemy.orm import Mapped, mapped_column

import kvnp_platform as platform
from kvnp_platform import (
    Artifact,
    Base,
    Download,
    Project,
    Subscription,
    User,
    _json_load,
    now_ts,
    session_scope,
)

PLANS = {
    "silver": {"label": "Silver", "seatLimit": 1, "source": "stripe"},
    "gold": {"label": "Gold", "seatLimit": 10, "source": "manual"},
    "platinum": {"label": "Platinum", "seatLimit": 0, "source": "manual"},  # 0 = unlimited
}
INVITE_TTL = 7 * 24 * 60 * 60
CREDIT_TTL = 180 * 24 * 60 * 60


# ============================================================
# Models
# ============================================================
class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    plan: Mapped[str] = mapped_column(String(24), default="silver", nullable=False, index=True)
    plan_status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, index=True)
    plan_source: Mapped[str] = mapped_column(String(24), default="stripe", nullable=False)
    seat_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    invited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    accepted_at: Mapped[int | None] = mapped_column(BigInteger)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PhotoCredit(Base):
    __tablename__ = "photo_credits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    remaining: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


# ============================================================
# Schema upkeep (columns added after the original tables existed)
# ============================================================
_ADDED_COLUMNS = {
    "users": {"org_id": "VARCHAR(36)", "org_role": "VARCHAR(16)"},
    "projects": {
        "org_id": "VARCHAR(36)",
        "client_id": "VARCHAR(36)",
        "credit_id": "VARCHAR(36)",
        "verdict": "VARCHAR(32)",
        "sale_amount_minor": "INTEGER",
        "sale_currency": "VARCHAR(3)",
        "sale_paid": "BOOLEAN",
    },
    "checkout_claims": {"provider_payment_id": "VARCHAR(160)", "product": "VARCHAR(32)"},
    "enquiries": {"business": "VARCHAR(160)", "phone": "VARCHAR(40)", "tier": "VARCHAR(32)"},
}


def ensure_schema(engine) -> list[str]:
    """Add any missing columns to tables that already existed. Safe to run on
    every start; SQLite and PostgreSQL both accept the simple ADD COLUMN form."""
    added = []
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    added.append(f"{table}.{name}")
    return added


# ============================================================
# Organisations / plans / seats
# ============================================================
def org_dict(org: Organisation | None, seats_used: int | None = None, owner: User | None = None) -> dict | None:
    if not org:
        return None
    plan = PLANS.get(org.plan, PLANS["silver"])
    return {
        "id": org.id,
        "name": org.name,
        "plan": org.plan,
        "planLabel": plan["label"],
        "planStatus": org.plan_status,
        "planSource": org.plan_source,
        "seatLimit": org.seat_limit,
        "seatsUsed": seats_used,
        "ownerUserId": org.owner_user_id,
        "ownerEmail": owner.email if owner else None,
        "notes": org.notes,
        "createdAt": org.created_at,
        "updatedAt": org.updated_at,
    }


def get_org(org_id: str | None) -> Organisation | None:
    if not org_id:
        return None
    with session_scope() as session:
        return session.get(Organisation, org_id)


def org_for_user(user_id: int) -> Organisation | None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if not user or not user.org_id:
            return None
        return session.get(Organisation, user.org_id)


def seats_used(org_id: str) -> int:
    with session_scope() as session:
        return int(session.scalar(select(func.count(User.id)).where(User.org_id == org_id)) or 0)


def create_org(
    name: str,
    plan: str,
    owner_user_id: int | None = None,
    seat_limit: int | None = None,
    plan_source: str | None = None,
    plan_status: str = "active",
    notes: str = "",
) -> Organisation:
    plan = plan if plan in PLANS else "silver"
    defaults = PLANS[plan]
    timestamp = now_ts()
    org = Organisation(
        id=str(uuid.uuid4()),
        name=(name or "").strip()[:160] or "Business",
        plan=plan,
        plan_status=plan_status if plan_status in {"active", "inactive"} else "active",
        plan_source=plan_source or defaults["source"],
        seat_limit=defaults["seatLimit"] if seat_limit is None else max(0, int(seat_limit)),
        owner_user_id=owner_user_id,
        notes=(notes or "")[:2000],
        created_at=timestamp,
        updated_at=timestamp,
    )
    with session_scope() as session:
        session.add(org)
        if owner_user_id:
            owner = session.get(User, owner_user_id)
            if owner:
                owner.org_id = org.id
                owner.org_role = "owner"
                owner.updated_at = timestamp
        session.flush()
    return org


def update_org(org_id: str, **fields) -> Organisation | None:
    with session_scope() as session:
        org = session.get(Organisation, org_id)
        if not org:
            return None
        if "name" in fields and fields["name"]:
            org.name = str(fields["name"]).strip()[:160]
        if "plan" in fields and fields["plan"] in PLANS:
            org.plan = fields["plan"]
        if "plan_status" in fields and fields["plan_status"] in {"active", "inactive"}:
            org.plan_status = fields["plan_status"]
        if "plan_source" in fields and fields["plan_source"] in {"stripe", "manual"}:
            org.plan_source = fields["plan_source"]
        if "seat_limit" in fields and fields["seat_limit"] is not None:
            org.seat_limit = max(0, int(fields["seat_limit"]))
        if "notes" in fields and fields["notes"] is not None:
            org.notes = str(fields["notes"])[:2000]
        org.updated_at = now_ts()
        session.flush()
        return org


def ensure_silver_org(user_id: int) -> Organisation:
    """Every paying Silver subscriber gets a one-seat business of their own."""
    existing = org_for_user(user_id)
    if existing:
        return existing
    with session_scope() as session:
        user = session.get(User, user_id)
        label = (user.name or user.email.split("@")[0]) if user else "My studio"
    return create_org(f"{label}", "silver", owner_user_id=user_id, plan_source="stripe")


def org_members(org_id: str) -> list[dict]:
    with session_scope() as session:
        users = session.scalars(select(User).where(User.org_id == org_id).order_by(User.created_at)).all()
        return [
            {**platform.user_dict(user, include_private=True), "orgRole": user.org_role or "member"}
            for user in users
        ]


def remove_member(org_id: str, user_id: int) -> bool:
    with session_scope() as session:
        user = session.get(User, user_id)
        org = session.get(Organisation, org_id)
        if not user or not org or user.org_id != org_id or org.owner_user_id == user_id:
            return False
        user.org_id = None
        user.org_role = None
        user.updated_at = now_ts()
        return True


def _owner_subscription_active(session, org: Organisation) -> bool:
    if not org.owner_user_id:
        return False
    return bool(
        session.scalar(
            select(Subscription.id)
            .where(Subscription.user_id == org.owner_user_id, Subscription.status.in_(["active", "trialing"]))
            .limit(1)
        )
    )


def org_is_active(org: Organisation | None) -> bool:
    if not org or org.plan_status != "active":
        return False
    if org.plan_source == "manual":
        return True
    with session_scope() as session:
        return _owner_subscription_active(session, org)


def plan_for_user(user_id: int) -> dict:
    """Everything the UI needs to know about what this user may do."""
    with session_scope() as session:
        user = session.get(User, user_id)
        org = session.get(Organisation, user.org_id) if user and user.org_id else None
        own_subscription = bool(
            session.scalar(
                select(Subscription.id)
                .where(Subscription.user_id == user_id, Subscription.status.in_(["active", "trialing"]))
                .limit(1)
            )
        )
        credits = int(
            session.scalar(
                select(func.coalesce(func.sum(PhotoCredit.remaining), 0)).where(
                    PhotoCredit.user_id == user_id, PhotoCredit.expires_at > now_ts()
                )
            )
            or 0
        )
        seats = int(session.scalar(select(func.count(User.id)).where(User.org_id == org.id)) or 0) if org else 0
        org_active = False
        if org and org.plan_status == "active":
            org_active = org.plan_source == "manual" or _owner_subscription_active(session, org)
        is_admin = bool(user and user.role == "admin")
    return {
        "isAdmin": is_admin,
        "org": org_dict(org, seats) if org else None,
        "orgRole": (user.org_role if user else None),
        "orgActive": org_active,
        "subscriptionActive": own_subscription,
        "credits": credits,
        "unlimited": bool(is_admin or org_active or own_subscription),
        "canProcess": bool(is_admin or org_active or own_subscription or credits > 0),
        "canManageTeam": bool(org and user and user.org_role == "owner" and org.plan in {"gold", "platinum"}),
        "crm": bool(org and org_active) or is_admin,
    }


def list_orgs() -> list[dict]:
    with session_scope() as session:
        orgs = session.scalars(select(Organisation).order_by(Organisation.created_at.desc())).all()
        month_start = int(datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
        seat_rows = session.execute(select(User.org_id, func.count(User.id)).group_by(User.org_id)).all()
        seats = {row[0]: row[1] for row in seat_rows}
        total_rows = session.execute(select(Project.org_id, func.count(Project.id)).group_by(Project.org_id)).all()
        totals = {row[0]: row[1] for row in total_rows}
        month_rows = session.execute(
            select(Project.org_id, func.count(Project.id)).where(Project.created_at >= month_start).group_by(Project.org_id)
        ).all()
        months = {row[0]: row[1] for row in month_rows}
        pending = session.execute(
            select(Invite.org_id, func.count(Invite.id))
            .where(Invite.accepted_at.is_(None), Invite.expires_at > now_ts())
            .group_by(Invite.org_id)
        ).all()
        pending_map = {row[0]: row[1] for row in pending}
        result = []
        for org in orgs:
            owner = session.get(User, org.owner_user_id) if org.owner_user_id else None
            item = org_dict(org, seats.get(org.id, 0), owner)
            item.update(
                {
                    "active": org.plan_status == "active" and (org.plan_source == "manual" or _owner_subscription_active(session, org)),
                    "photosTotal": totals.get(org.id, 0),
                    "photosThisMonth": months.get(org.id, 0),
                    "pendingInvites": pending_map.get(org.id, 0),
                }
            )
            result.append(item)
        return result


# ============================================================
# Invites
# ============================================================
def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_dict(invite: Invite) -> dict:
    return {
        "id": invite.id,
        "orgId": invite.org_id,
        "email": invite.email,
        "name": invite.name,
        "role": invite.role,
        "createdAt": invite.created_at,
        "expiresAt": invite.expires_at,
        "acceptedAt": invite.accepted_at,
        "expired": invite.expires_at <= now_ts() and not invite.accepted_at,
    }


def create_invite(org_id: str, email: str, role: str, invited_by: int | None, name: str = "", enforce_seats: bool = True) -> tuple[Invite, str]:
    email = platform.normalise_checkout_email(email)
    if not email:
        raise ValueError("invalid_email")
    with session_scope() as session:
        org = session.get(Organisation, org_id)
        if not org:
            raise ValueError("org")
        existing_user = session.scalar(select(User).where(User.email == email))
        if existing_user and existing_user.org_id == org_id:
            raise ValueError("already_member")
        if existing_user and existing_user.org_id and existing_user.org_id != org_id:
            raise ValueError("member_elsewhere")
        if enforce_seats and org.seat_limit:
            used = int(session.scalar(select(func.count(User.id)).where(User.org_id == org_id)) or 0)
            pending = int(
                session.scalar(
                    select(func.count(Invite.id)).where(
                        Invite.org_id == org_id, Invite.accepted_at.is_(None), Invite.expires_at > now_ts()
                    )
                )
                or 0
            )
            if used + pending >= org.seat_limit:
                raise ValueError("seat_limit")
        # one live invite per email per org
        for stale in session.scalars(
            select(Invite).where(Invite.org_id == org_id, Invite.email == email, Invite.accepted_at.is_(None))
        ).all():
            session.delete(stale)
        token = secrets.token_urlsafe(32)
        timestamp = now_ts()
        invite = Invite(
            id=str(uuid.uuid4()),
            org_id=org_id,
            email=email,
            name=(name or "").strip()[:160],
            role="owner" if role == "owner" else "member",
            token_hash=_digest(token),
            invited_by=invited_by,
            created_at=timestamp,
            expires_at=timestamp + INVITE_TTL,
        )
        session.add(invite)
        session.flush()
        return invite, token


def list_invites(org_id: str) -> list[dict]:
    with session_scope() as session:
        invites = session.scalars(
            select(Invite).where(Invite.org_id == org_id, Invite.accepted_at.is_(None)).order_by(Invite.created_at.desc())
        ).all()
        return [invite_dict(item) for item in invites]


def delete_invite(org_id: str, invite_id: str) -> bool:
    with session_scope() as session:
        invite = session.get(Invite, invite_id)
        if not invite or invite.org_id != org_id or invite.accepted_at:
            return False
        session.delete(invite)
        return True


def invite_by_token(token: str | None) -> tuple[Invite, Organisation] | None:
    if not token:
        return None
    with session_scope() as session:
        invite = session.scalar(select(Invite).where(Invite.token_hash == _digest(token)))
        if not invite or invite.accepted_at or invite.expires_at <= now_ts():
            return None
        org = session.get(Organisation, invite.org_id)
        return invite, org


def accept_invite(token: str, name: str, password_hash: str | None) -> User:
    """Create the user (or attach an existing one) and put them in the org."""
    with session_scope() as session:
        invite = session.scalar(select(Invite).where(Invite.token_hash == _digest(token)))
        if not invite or invite.accepted_at or invite.expires_at <= now_ts():
            raise ValueError("invite")
        org = session.get(Organisation, invite.org_id)
        if not org:
            raise ValueError("org")
        timestamp = now_ts()
        user = session.scalar(select(User).where(User.email == invite.email))
        if not user:
            if not password_hash:
                raise ValueError("password")
            user = User(
                email=invite.email,
                name=(name or invite.name or invite.email.split("@")[0]).strip()[:160],
                password_hash=password_hash,
                role="customer",
                status="active",
                email_verified=True,
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(user)
            session.flush()
        elif user.org_id and user.org_id != org.id:
            raise ValueError("member_elsewhere")
        user.org_id = org.id
        user.org_role = invite.role
        user.updated_at = timestamp
        if invite.role == "owner" and not org.owner_user_id:
            org.owner_user_id = user.id
            org.updated_at = timestamp
        invite.accepted_at = timestamp
        session.flush()
        session.refresh(user)
        return user


# ============================================================
# Single-photo credits
# ============================================================
def grant_credit(user_id: int, source: str, count: int = 1) -> PhotoCredit | None:
    """Idempotent on `source` (a Stripe session / payment id)."""
    with session_scope() as session:
        existing = session.scalar(select(PhotoCredit).where(PhotoCredit.source == source[:160]))
        if existing:
            return existing
        timestamp = now_ts()
        credit = PhotoCredit(
            id=str(uuid.uuid4()),
            user_id=user_id,
            remaining=max(1, int(count)),
            total=max(1, int(count)),
            source=source[:160],
            created_at=timestamp,
            expires_at=timestamp + CREDIT_TTL,
        )
        session.add(credit)
        session.flush()
        return credit


def credits_remaining(user_id: int) -> int:
    with session_scope() as session:
        return int(
            session.scalar(
                select(func.coalesce(func.sum(PhotoCredit.remaining), 0)).where(
                    PhotoCredit.user_id == user_id, PhotoCredit.expires_at > now_ts()
                )
            )
            or 0
        )


def consume_credit_for_project(user_id: int, project_id: str) -> bool:
    """Spend one credit on a project (once). Returns True if the project is now covered."""
    with session_scope() as session:
        project = session.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
        if not project:
            return False
        if project.credit_id:
            return True
        credit = session.scalar(
            select(PhotoCredit)
            .where(PhotoCredit.user_id == user_id, PhotoCredit.remaining > 0, PhotoCredit.expires_at > now_ts())
            .order_by(PhotoCredit.expires_at)
        )
        if not credit:
            return False
        credit.remaining -= 1
        project.credit_id = credit.id
        project.updated_at = now_ts()
        return True


def project_covered_by_credit(user_id: int, project_id: str) -> bool:
    with session_scope() as session:
        project = session.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
        return bool(project and project.credit_id)


# ============================================================
# CRM: clients and photos
# ============================================================
def client_dict(client: Client, photo_count: int = 0, last_photo_at: int | None = None, revenue_minor: int = 0, unpaid_minor: int = 0) -> dict:
    return {
        "id": client.id,
        "orgId": client.org_id,
        "name": client.name,
        "phone": client.phone,
        "email": client.email,
        "notes": client.notes,
        "photoCount": photo_count,
        "lastPhotoAt": last_photo_at,
        "revenueMinor": revenue_minor,
        "unpaidMinor": unpaid_minor,
        "createdAt": client.created_at,
        "updatedAt": client.updated_at,
    }


def create_client(org_id: str, created_by: int | None, name: str, phone: str = "", email: str = "", notes: str = "") -> Client:
    name = (name or "").strip()
    if len(name) < 1:
        raise ValueError("name")
    timestamp = now_ts()
    client = Client(
        id=str(uuid.uuid4()),
        org_id=org_id,
        name=name[:160],
        phone=(phone or "").strip()[:40],
        email=(email or "").strip().lower()[:320],
        notes=(notes or "").strip()[:4000],
        created_by=created_by,
        created_at=timestamp,
        updated_at=timestamp,
    )
    with session_scope() as session:
        session.add(client)
        session.flush()
    return client


def update_client(org_id: str, client_id: str, **fields) -> Client | None:
    with session_scope() as session:
        client = session.get(Client, client_id)
        if not client or client.org_id != org_id:
            return None
        if fields.get("name") is not None and str(fields["name"]).strip():
            client.name = str(fields["name"]).strip()[:160]
        for key, limit in (("phone", 40), ("email", 320), ("notes", 4000)):
            if fields.get(key) is not None:
                value = str(fields[key]).strip()[:limit]
                setattr(client, key, value.lower() if key == "email" else value)
        client.updated_at = now_ts()
        session.flush()
        return client


def get_client(org_id: str, client_id: str) -> Client | None:
    with session_scope() as session:
        client = session.get(Client, client_id)
        return client if client and client.org_id == org_id else None


def _client_stats(session, org_id: str) -> dict:
    rows = session.execute(
        select(
            Project.client_id,
            func.count(Project.id),
            func.max(Project.created_at),
            func.coalesce(func.sum(Project.sale_amount_minor), 0),
        )
        .where(Project.org_id == org_id, Project.client_id.isnot(None))
        .group_by(Project.client_id)
    ).all()
    unpaid_rows = session.execute(
        select(Project.client_id, func.coalesce(func.sum(Project.sale_amount_minor), 0))
        .where(Project.org_id == org_id, Project.client_id.isnot(None), Project.sale_paid.is_(False))
        .group_by(Project.client_id)
    ).all()
    unpaid = {row[0]: int(row[1] or 0) for row in unpaid_rows}
    return {row[0]: (int(row[1]), row[2], int(row[3] or 0), unpaid.get(row[0], 0)) for row in rows}


def list_clients(org_id: str, query: str = "", limit: int = 200) -> list[dict]:
    query = (query or "").strip().lower()
    with session_scope() as session:
        statement = select(Client).where(Client.org_id == org_id)
        if query:
            like = f"%{query}%"
            statement = statement.where(
                func.lower(Client.name).like(like) | func.lower(Client.email).like(like) | Client.phone.like(like)
            )
        clients = session.scalars(statement.order_by(Client.updated_at.desc()).limit(limit)).all()
        stats = _client_stats(session, org_id)
        return [client_dict(client, *stats.get(client.id, (0, None, 0, 0))) for client in clients]


def crm_project_dict(project: Project, artifact_available: bool, client: Client | None = None) -> dict:
    summary = _json_load(project.summary_json)
    return {
        "id": project.id,
        "clientId": project.client_id,
        "clientName": client.name if client else (project.applicant_name or ""),
        "applicantName": project.applicant_name,
        "profileId": project.profile_id,
        "countryCode": project.country_code,
        "programmeLabel": project.programme_label,
        "verdict": project.verdict or project.result_status,
        "status": project.status,
        "saleAmountMinor": project.sale_amount_minor,
        "saleCurrency": project.sale_currency or "CAD",
        "salePaid": project.sale_paid,
        "artifactAvailable": artifact_available,
        "summary": summary,
        "createdAt": project.created_at,
        "updatedAt": project.updated_at,
        "userId": project.user_id,
    }


def org_projects(org_id: str, client_id: str | None = None, limit: int = 200) -> list[dict]:
    with session_scope() as session:
        statement = select(Project).where(Project.org_id == org_id)
        if client_id:
            statement = statement.where(Project.client_id == client_id)
        projects = session.scalars(statement.order_by(Project.created_at.desc()).limit(limit)).all()
        ids = [project.id for project in projects]
        artifacts = set(
            session.scalars(select(Artifact.project_id).where(Artifact.project_id.in_(ids), Artifact.expires_at > now_ts())).all()
        ) if ids else set()
        client_ids = {project.client_id for project in projects if project.client_id}
        clients = {
            client.id: client
            for client in session.scalars(select(Client).where(Client.id.in_(client_ids))).all()
        } if client_ids else {}
        return [crm_project_dict(project, project.id in artifacts, clients.get(project.client_id)) for project in projects]


def get_org_project(org_id: str, project_id: str) -> Project | None:
    with session_scope() as session:
        project = session.get(Project, project_id)
        return project if project and project.org_id == org_id else None


def attach_project(org_id: str, project_id: str, client_id: str | None, sale_amount_minor: int | None, sale_currency: str | None, sale_paid: bool | None, verdict: str | None) -> Project | None:
    with session_scope() as session:
        project = session.get(Project, project_id)
        if not project:
            return None
        if project.org_id and project.org_id != org_id:
            return None
        project.org_id = org_id
        if client_id is not None:
            if client_id == "":
                project.client_id = None
            else:
                client = session.get(Client, client_id)
                if not client or client.org_id != org_id:
                    raise ValueError("client")
                project.client_id = client_id
                if not project.applicant_name:
                    project.applicant_name = client.name[:160]
        if sale_amount_minor is not None:
            project.sale_amount_minor = max(0, int(sale_amount_minor))
        if sale_currency:
            project.sale_currency = str(sale_currency).upper()[:3]
        if sale_paid is not None:
            project.sale_paid = bool(sale_paid)
        if verdict:
            project.verdict = str(verdict)[:32]
        project.updated_at = now_ts()
        session.flush()
        return project


def crm_summary(org_id: str) -> dict:
    now = datetime.now(timezone.utc)
    month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    with session_scope() as session:
        total = int(session.scalar(select(func.count(Project.id)).where(Project.org_id == org_id)) or 0)
        this_month = int(
            session.scalar(select(func.count(Project.id)).where(Project.org_id == org_id, Project.created_at >= month_start)) or 0
        )
        clients = int(session.scalar(select(func.count(Client.id)).where(Client.org_id == org_id)) or 0)
        revenue_month = int(
            session.scalar(
                select(func.coalesce(func.sum(Project.sale_amount_minor), 0)).where(
                    Project.org_id == org_id, Project.created_at >= month_start, Project.sale_paid.is_(True)
                )
            )
            or 0
        )
        unpaid = int(
            session.scalar(
                select(func.coalesce(func.sum(Project.sale_amount_minor), 0)).where(
                    Project.org_id == org_id, Project.sale_paid.is_(False)
                )
            )
            or 0
        )
        unpaid_count = int(
            session.scalar(select(func.count(Project.id)).where(Project.org_id == org_id, Project.sale_paid.is_(False))) or 0
        )
        last = session.scalar(select(func.max(Project.created_at)).where(Project.org_id == org_id))
        # last 6 months histogram
        months = []
        for offset in range(5, -1, -1):
            year = now.year
            month = now.month - offset
            while month <= 0:
                month += 12
                year -= 1
            start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1
            end = int(datetime(next_year, next_month, 1, tzinfo=timezone.utc).timestamp())
            count = int(
                session.scalar(
                    select(func.count(Project.id)).where(
                        Project.org_id == org_id, Project.created_at >= start, Project.created_at < end
                    )
                )
                or 0
            )
            months.append({"label": datetime(year, month, 1).strftime("%b"), "count": count})
        by_programme = session.execute(
            select(Project.programme_label, func.count(Project.id))
            .where(Project.org_id == org_id)
            .group_by(Project.programme_label)
            .order_by(func.count(Project.id).desc())
            .limit(6)
        ).all()
    return {
        "photosTotal": total,
        "photosThisMonth": this_month,
        "clients": clients,
        "revenueThisMonthMinor": revenue_month,
        "unpaidMinor": unpaid,
        "unpaidCount": unpaid_count,
        "lastActivityAt": last,
        "months": months,
        "topProgrammes": [{"label": row[0] or "Unknown", "count": row[1]} for row in by_programme],
    }


def export_rows(org_id: str) -> list[list]:
    rows = [["date", "client", "phone", "email", "programme", "verdict", "amount", "currency", "paid", "project_id"]]
    with session_scope() as session:
        projects = session.scalars(select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())).all()
        clients = {client.id: client for client in session.scalars(select(Client).where(Client.org_id == org_id)).all()}
        for project in projects:
            client = clients.get(project.client_id)
            amount = "" if project.sale_amount_minor is None else f"{project.sale_amount_minor / 100:.2f}"
            rows.append(
                [
                    datetime.fromtimestamp(project.created_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
                    client.name if client else project.applicant_name,
                    client.phone if client else "",
                    client.email if client else "",
                    project.programme_label,
                    project.verdict or project.result_status or "",
                    amount,
                    project.sale_currency or "CAD",
                    "" if project.sale_paid is None else ("yes" if project.sale_paid else "no"),
                    project.id,
                ]
            )
    return rows


def receipt_data(org_id: str, project_id: str) -> dict | None:
    with session_scope() as session:
        project = session.get(Project, project_id)
        if not project or project.org_id != org_id:
            return None
        org = session.get(Organisation, org_id)
        client = session.get(Client, project.client_id) if project.client_id else None
        return {
            "project": crm_project_dict(project, False, client),
            "client": client_dict(client) if client else None,
            "org": org_dict(org),
        }


def admin_overview() -> dict:
    now = datetime.now(timezone.utc)
    month_start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    with session_scope() as session:
        users = int(session.scalar(select(func.count(User.id))) or 0)
        orgs = int(session.scalar(select(func.count(Organisation.id))) or 0)
        photos_total = int(session.scalar(select(func.count(Project.id))) or 0)
        photos_month = int(session.scalar(select(func.count(Project.id)).where(Project.created_at >= month_start)) or 0)
        credits = int(session.scalar(select(func.coalesce(func.sum(PhotoCredit.remaining), 0))) or 0)
        subs = int(session.scalar(select(func.count(Subscription.id)).where(Subscription.status.in_(["active", "trialing"]))) or 0)
        downloads_month = int(session.scalar(select(func.count(Download.id)).where(Download.created_at >= month_start)) or 0)
    return {
        "users": users,
        "organisations": orgs,
        "activeSubscriptions": subs,
        "photosTotal": photos_total,
        "photosThisMonth": photos_month,
        "downloadsThisMonth": downloads_month,
        "creditsOutstanding": credits,
    }


def list_users(limit: int = 300) -> list[dict]:
    with session_scope() as session:
        users = session.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all()
        orgs = {org.id: org for org in session.scalars(select(Organisation)).all()}
        result = []
        for user in users:
            item = platform.user_dict(user, include_private=True)
            org = orgs.get(user.org_id) if user.org_id else None
            item.update({"orgId": user.org_id, "orgName": org.name if org else None, "orgRole": user.org_role, "plan": org.plan if org else None})
            result.append(item)
        return result
