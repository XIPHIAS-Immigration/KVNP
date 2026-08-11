"""Transactional product data for accounts, projects, commerce, and administration."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now_ts() -> int:
    return int(time.time())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str | None] = mapped_column(Text)
    legacy_pw_hash: Mapped[str | None] = mapped_column(String(128))
    legacy_pw_salt: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(24), default="customer", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_login_at: Mapped[int | None] = mapped_column(BigInteger)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    applicant_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    profile_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(12), default="", nullable=False, index=True)
    programme_label: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    result_status: Mapped[str | None] = mapped_column(String(32))
    summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), index=True)
    product_code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_at: Mapped[int | None] = mapped_column(BigInteger)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    raw_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), unique=True)
    product_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, index=True)
    granted_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int | None] = mapped_column(BigInteger)


class BillingCustomer(Base):
    __tablename__ = "billing_customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    price_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    current_period_end: Mapped[int | None] = mapped_column(BigInteger)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class BillingPayment(Base):
    __tablename__ = "billing_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_invoice_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProviderEvent(Base):
    __tablename__ = "provider_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    processed_at: Mapped[int | None] = mapped_column(BigInteger)


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    file_kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    warning_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), default="prepared", nullable=False)
    format: Mapped[str] = mapped_column(String(24), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    anonymous_id: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


class Enquiry(Base):
    __tablename__ = "enquiries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="new", nullable=False, index=True)
    admin_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AdminAudit(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)


Index("ix_orders_user_created", Order.user_id, Order.created_at)
Index("ix_projects_user_updated", Project.user_id, Project.updated_at)
Index("ix_downloads_project_created", Download.project_id, Download.created_at)
Index("ix_subscriptions_user_updated", Subscription.user_id, Subscription.updated_at)
Index("ix_billing_payments_user_updated", BillingPayment.user_id, BillingPayment.updated_at)


ENGINE = None
SessionLocal = None
DATABASE_URL = None


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def initialise(data_dir: Path) -> str:
    global ENGINE, SessionLocal, DATABASE_URL
    data_dir.mkdir(parents=True, exist_ok=True)
    default_url = f"sqlite:///{(data_dir / 'platform.db').as_posix()}"
    DATABASE_URL = _normalise_database_url(os.getenv("KVNP_DATABASE_URL", default_url).strip())
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ENGINE = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
    SessionLocal = sessionmaker(bind=ENGINE, expire_on_commit=False)
    Base.metadata.create_all(ENGINE)
    _import_legacy_users(data_dir / "kvnp.db")
    return "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite"


@contextmanager
def session_scope():
    if SessionLocal is None:
        raise RuntimeError("Product database is not initialised")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _import_legacy_users(legacy_path: Path) -> None:
    if not legacy_path.exists() or legacy_path.name == Path(str(DATABASE_URL)).name:
        return
    try:
        legacy = sqlite3.connect(str(legacy_path))
        legacy.row_factory = sqlite3.Row
        rows = legacy.execute("SELECT email, name, pw_hash, pw_salt, created_at FROM users").fetchall()
        legacy.close()
    except (sqlite3.Error, OSError):
        return
    with session_scope() as session:
        existing = set(session.scalars(select(User.email)).all())
        for row in rows:
            email = str(row["email"]).strip().lower()
            if email in existing:
                continue
            created = int(row["created_at"] or now_ts())
            session.add(
                User(
                    email=email,
                    name=row["name"],
                    legacy_pw_hash=row["pw_hash"],
                    legacy_pw_salt=row["pw_salt"],
                    role="customer",
                    status="active",
                    email_verified=False,
                    created_at=created,
                    updated_at=created,
                )
            )


def user_dict(user: User, include_private: bool = False) -> dict:
    result = {
        "id": user.id,
        "email": user.email,
        "name": user.name or user.email.split("@")[0],
        "role": user.role,
        "emailVerified": bool(user.email_verified),
        "createdAt": user.created_at,
    }
    if include_private:
        result.update({"status": user.status, "lastLoginAt": user.last_login_at})
    return result


def get_user(user_id: int) -> User | None:
    with session_scope() as session:
        return session.get(User, user_id)


def get_user_by_email(email: str) -> User | None:
    with session_scope() as session:
        return session.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(email: str, name: str | None, password_hash: str) -> User:
    timestamp = now_ts()
    user = User(
        email=email.strip().lower(),
        name=(name or "").strip() or None,
        password_hash=password_hash,
        role="customer",
        status="active",
        email_verified=False,
        created_at=timestamp,
        updated_at=timestamp,
    )
    try:
        with session_scope() as session:
            session.add(user)
            session.flush()
    except IntegrityError as error:
        raise ValueError("email_exists") from error
    return user


def promote_admin(email: str) -> User:
    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == email.strip().lower()))
        if not user:
            raise ValueError("user_not_found")
        user.role = "admin"
        user.updated_at = now_ts()
        session.flush()
        return user


def upgrade_legacy_password(user_id: int, password_hash: str) -> None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user:
            user.password_hash = password_hash
            user.legacy_pw_hash = None
            user.legacy_pw_salt = None
            user.updated_at = now_ts()


def touch_login(user_id: int) -> None:
    with session_scope() as session:
        user = session.get(User, user_id)
        if user:
            user.last_login_at = now_ts()
            user.updated_at = now_ts()


def _token_digest(token: str) -> str:
    secret = os.getenv("KVNP_SESSION_SECRET", "").encode("utf-8")
    if secret:
        return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_auth_session(user_id: int, ttl: int) -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    timestamp = now_ts()
    with session_scope() as session:
        session.add(
            AuthSession(
                id=str(uuid.uuid4()),
                user_id=user_id,
                token_hash=_token_digest(token),
                csrf_token=csrf,
                created_at=timestamp,
                expires_at=timestamp + ttl,
            )
        )
    return token, csrf


def resolve_auth_session(token: str | None) -> tuple[User, AuthSession] | None:
    if not token:
        return None
    token_hash = _token_digest(token)
    with session_scope() as session:
        auth_session = session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now_ts(),
            )
        )
        if not auth_session:
            return None
        user = session.get(User, auth_session.user_id)
        if not user or user.status != "active":
            return None
        return user, auth_session


def revoke_auth_session(token: str | None) -> None:
    if not token:
        return
    token_hash = _token_digest(token)
    with session_scope() as session:
        auth_session = session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = now_ts()


def subscription_dict(subscription: Subscription | None) -> dict:
    if not subscription:
        return {
            "status": "none",
            "active": False,
            "cancelAtPeriodEnd": False,
            "currentPeriodEnd": None,
            "provider": None,
        }
    return {
        "id": subscription.id,
        "status": subscription.status,
        "active": subscription.status in {"active", "trialing"},
        "cancelAtPeriodEnd": bool(subscription.cancel_at_period_end),
        "currentPeriodEnd": subscription.current_period_end,
        "provider": subscription.provider,
        "priceId": subscription.price_id,
        "currency": subscription.currency,
    }


def subscription_for_user(user_id: int) -> Subscription | None:
    with session_scope() as session:
        return session.scalar(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.updated_at.desc())
        )


def active_subscription(user_id: int) -> Subscription | None:
    with session_scope() as session:
        return session.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "trialing"]),
            )
            .order_by(Subscription.updated_at.desc())
        )


def billing_customer_for_user(user_id: int) -> BillingCustomer | None:
    with session_scope() as session:
        return session.scalar(select(BillingCustomer).where(BillingCustomer.user_id == user_id))


def resolve_billing_user(customer_id: str | None = None, supplied_user_id=None) -> int | None:
    with session_scope() as session:
        if supplied_user_id not in {None, ""}:
            try:
                user_id = int(supplied_user_id)
            except (TypeError, ValueError):
                user_id = 0
            if user_id and session.get(User, user_id):
                return user_id
        if customer_id:
            customer = session.scalar(
                select(BillingCustomer).where(BillingCustomer.provider_customer_id == str(customer_id))
            )
            if customer:
                return customer.user_id
    return None


def _stripe_price_data(payload: dict) -> tuple[str, str, int | None]:
    items = ((payload.get("items") or {}).get("data") or [])
    first_item = items[0] if items else {}
    price = first_item.get("price") or {}
    if isinstance(price, str):
        price = {"id": price}
    period_end = payload.get("current_period_end") or first_item.get("current_period_end")
    return (
        str(price.get("id") or "unknown")[:160],
        str(price.get("currency") or "CAD").upper()[:3],
        int(period_end) if period_end else None,
    )


def upsert_stripe_subscription(user_id: int, payload: dict) -> Subscription:
    provider_subscription_id = str(payload.get("id") or "")
    provider_customer_id = str(payload.get("customer") or "")
    if not provider_subscription_id.startswith("sub_") or not provider_customer_id.startswith("cus_"):
        raise ValueError("stripe_subscription_identifiers")
    price_id, currency, period_end = _stripe_price_data(payload)
    timestamp = now_ts()
    with session_scope() as session:
        if not session.get(User, user_id):
            raise ValueError("stripe_user")
        customer = session.scalar(select(BillingCustomer).where(BillingCustomer.user_id == user_id))
        if not customer:
            customer = BillingCustomer(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider="stripe",
                provider_customer_id=provider_customer_id,
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(customer)
        else:
            customer.provider_customer_id = provider_customer_id
            customer.updated_at = timestamp

        subscription = session.scalar(
            select(Subscription).where(
                Subscription.provider_subscription_id == provider_subscription_id
            )
        )
        if not subscription:
            subscription = Subscription(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider="stripe",
                provider_subscription_id=provider_subscription_id,
                provider_customer_id=provider_customer_id,
                price_id=price_id,
                status="incomplete",
                currency=currency,
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(subscription)
        subscription.user_id = user_id
        subscription.provider_customer_id = provider_customer_id
        subscription.price_id = price_id
        subscription.status = str(payload.get("status") or subscription.status)[:32]
        subscription.currency = currency
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = bool(payload.get("cancel_at_period_end"))
        subscription.updated_at = timestamp
        session.flush()
        return subscription


def billing_payment_dict(item: BillingPayment) -> dict:
    return {
        "id": item.id,
        "userId": item.user_id,
        "invoiceId": item.provider_invoice_id,
        "subscriptionId": item.provider_subscription_id,
        "status": item.status,
        "amountMinor": item.amount_minor,
        "currency": item.currency,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def upsert_stripe_invoice(user_id: int, payload: dict, status: str) -> BillingPayment:
    invoice_id = str(payload.get("id") or "")
    if not invoice_id.startswith("in_"):
        raise ValueError("stripe_invoice_identifier")
    subscription_id = payload.get("subscription")
    if not isinstance(subscription_id, str):
        parent = payload.get("parent") or {}
        details = parent.get("subscription_details") or {}
        subscription_id = details.get("subscription")
        if isinstance(subscription_id, dict):
            subscription_id = subscription_id.get("id")
    amount = payload.get("amount_paid") if status == "paid" else payload.get("amount_due")
    timestamp = now_ts()
    with session_scope() as session:
        item = session.scalar(
            select(BillingPayment).where(BillingPayment.provider_invoice_id == invoice_id)
        )
        if not item:
            item = BillingPayment(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider="stripe",
                provider_invoice_id=invoice_id,
                provider_subscription_id=str(subscription_id)[:160] if subscription_id else None,
                status=status[:32],
                amount_minor=max(0, int(amount or 0)),
                currency=str(payload.get("currency") or "CAD").upper()[:3],
                created_at=int(payload.get("created") or timestamp),
                updated_at=timestamp,
            )
            session.add(item)
        else:
            item.status = status[:32]
            item.amount_minor = max(0, int(amount or item.amount_minor or 0))
            item.currency = str(payload.get("currency") or item.currency or "CAD").upper()[:3]
            item.provider_subscription_id = str(subscription_id)[:160] if subscription_id else item.provider_subscription_id
            item.updated_at = timestamp
        session.flush()
        return item


def reserve_provider_event(provider: str, event_id: str, event_type: str) -> bool:
    timestamp = now_ts()
    with session_scope() as session:
        existing = session.scalar(
            select(ProviderEvent).where(ProviderEvent.provider_event_id == event_id)
        )
        if existing and existing.status in {"processing", "processed", "ignored"}:
            return False
        if existing:
            existing.status = "processing"
            existing.error = ""
            existing.processed_at = None
        else:
            session.add(
                ProviderEvent(
                    id=str(uuid.uuid4()),
                    provider=provider[:32],
                    provider_event_id=event_id[:160],
                    event_type=event_type[:96],
                    status="processing",
                    error="",
                    created_at=timestamp,
                )
            )
    return True


def finish_provider_event(event_id: str, status: str, error: str = "") -> None:
    if status not in {"processed", "ignored", "failed"}:
        raise ValueError("provider_event_status")
    with session_scope() as session:
        item = session.scalar(select(ProviderEvent).where(ProviderEvent.provider_event_id == event_id))
        if item:
            item.status = status
            item.error = error[:2000]
            item.processed_at = now_ts()


def project_dict(project: Project, entitlement: bool = False, artifact: bool = False) -> dict:
    return {
        "id": project.id,
        "applicantName": project.applicant_name,
        "profileId": project.profile_id,
        "countryCode": project.country_code,
        "programmeLabel": project.programme_label,
        "status": project.status,
        "resultStatus": project.result_status,
        "summary": _json_load(project.summary_json),
        "entitled": entitlement,
        "artifactAvailable": artifact,
        "createdAt": project.created_at,
        "updatedAt": project.updated_at,
    }


def save_project(user_id: int, payload: dict) -> Project:
    timestamp = now_ts()
    supplied_id = payload.get("id")
    try:
        project_id = str(uuid.UUID(str(supplied_id))) if supplied_id else str(uuid.uuid4())
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("project_id") from error
    with session_scope() as session:
        project = session.get(Project, project_id)
        if project and project.user_id != user_id:
            raise PermissionError("project_owner")
        if not project:
            project = Project(
                id=project_id,
                user_id=user_id,
                profile_id=str(payload.get("profileId") or "general-studio-square-2026-08")[:160],
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(project)
        project.applicant_name = str(payload.get("applicantName") or project.applicant_name or "")[:160]
        project.profile_id = str(payload.get("profileId") or project.profile_id)[:160]
        project.country_code = str(payload.get("countryCode") or project.country_code or "")[:12]
        project.programme_label = str(payload.get("programmeLabel") or project.programme_label or "")[:240]
        requested_status = str(payload.get("status") or "draft")
        if project.status == "paid":
            requested_status = "paid"
        elif requested_status not in {"draft", "prepared", "review"}:
            requested_status = "draft"
        project.status = requested_status
        project.result_status = str(payload.get("resultStatus") or project.result_status or "")[:32] or None
        project.summary_json = _json_dump(payload.get("summary") or {})
        project.updated_at = timestamp
        session.flush()
        return project


def list_projects(user_id: int, limit: int = 50) -> list[dict]:
    with session_scope() as session:
        projects = session.scalars(
            select(Project).where(Project.user_id == user_id).order_by(Project.updated_at.desc()).limit(limit)
        ).all()
        entitled_ids = set(
            session.scalars(
                select(Entitlement.project_id).where(
                    Entitlement.user_id == user_id,
                    Entitlement.status == "active",
                )
            ).all()
        )
        artifact_ids = set(
            session.scalars(
                select(Artifact.project_id).where(
                    Artifact.user_id == user_id,
                    Artifact.expires_at > now_ts(),
                )
            ).all()
        )
        membership = session.scalar(
            select(Subscription.id).where(
                Subscription.user_id == user_id,
                Subscription.status.in_(["active", "trialing"]),
            ).limit(1)
        )
        return [
            project_dict(project, bool(membership) or project.id in entitled_ids, project.id in artifact_ids)
            for project in projects
        ]


def get_owned_project(user_id: int, project_id: str) -> Project | None:
    with session_scope() as session:
        return session.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))


def create_order(user_id: int, project_id: str, amount_minor: int, currency: str, provider: str) -> Order:
    project = get_owned_project(user_id, project_id)
    if not project:
        raise PermissionError("project_owner")
    timestamp = now_ts()
    with session_scope() as session:
        existing = session.scalar(
            select(Order).where(
                Order.user_id == user_id,
                Order.project_id == project_id,
                Order.status.in_(["pending", "paid"]),
            ).order_by(Order.created_at.desc())
        )
        if existing:
            return existing
        order = Order(
            id=str(uuid.uuid4()),
            reference=f"KVNP-{uuid.uuid4().hex[:12].upper()}",
            user_id=user_id,
            project_id=project_id,
            product_code="application-pack",
            amount_minor=amount_minor,
            currency=currency,
            status="pending",
            provider=provider,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(order)
        session.flush()
        return order


def order_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "reference": order.reference,
        "projectId": order.project_id,
        "productCode": order.product_code,
        "amountMinor": order.amount_minor,
        "currency": order.currency,
        "status": order.status,
        "provider": order.provider,
        "createdAt": order.created_at,
        "paidAt": order.paid_at,
    }


def list_orders(user_id: int, limit: int = 50) -> list[dict]:
    with session_scope() as session:
        orders = session.scalars(
            select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)
        ).all()
        return [order_dict(order) for order in orders]


def complete_mock_order(user_id: int, order_id: str) -> Order:
    timestamp = now_ts()
    with session_scope() as session:
        order = session.scalar(select(Order).where(Order.id == order_id, Order.user_id == user_id))
        if not order:
            raise PermissionError("order_owner")
        if order.status == "paid":
            return order
        if order.status != "pending":
            raise ValueError("order_not_pending")
        order.status = "paid"
        order.paid_at = timestamp
        order.updated_at = timestamp
        order.provider_order_id = order.provider_order_id or f"mock-order-{order.id}"
        session.add(
            Payment(
                id=str(uuid.uuid4()),
                order_id=order.id,
                provider="mock",
                provider_payment_id=f"mock-payment-{order.id}",
                provider_event_id=f"mock-event-{order.id}",
                status="success",
                amount_minor=order.amount_minor,
                currency=order.currency,
                raw_json='{"mode":"development"}',
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        entitlement = session.scalar(select(Entitlement).where(Entitlement.project_id == order.project_id))
        if not entitlement:
            session.add(
                Entitlement(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    project_id=order.project_id,
                    order_id=order.id,
                    product_code=order.product_code,
                    status="active",
                    granted_at=timestamp,
                    expires_at=timestamp + (30 * 24 * 60 * 60),
                )
            )
        project = session.get(Project, order.project_id)
        if project:
            project.status = "paid"
            project.updated_at = timestamp
        artifact = session.scalar(select(Artifact).where(Artifact.project_id == order.project_id))
        if artifact:
            artifact.expires_at = timestamp + (30 * 24 * 60 * 60)
            artifact.updated_at = timestamp
        return order


def active_entitlement(user_id: int, project_id: str) -> Entitlement | None:
    with session_scope() as session:
        entitlement = session.scalar(
            select(Entitlement).where(
                Entitlement.user_id == user_id,
                Entitlement.project_id == project_id,
                Entitlement.status == "active",
            )
        )
        if entitlement and entitlement.expires_at and entitlement.expires_at < now_ts():
            return None
        return entitlement


def has_download_access(user_id: int, project_id: str) -> bool:
    return bool(active_subscription(user_id) or active_entitlement(user_id, project_id))


def register_artifact(user_id: int, project_id: str, storage_path: str, file_format: str, size: int) -> Artifact:
    if not get_owned_project(user_id, project_id):
        raise PermissionError("project_owner")
    timestamp = now_ts()
    with session_scope() as session:
        artifact = session.scalar(select(Artifact).where(Artifact.project_id == project_id))
        if not artifact:
            artifact = Artifact(
                id=str(uuid.uuid4()),
                user_id=user_id,
                project_id=project_id,
                kind="prepared",
                format=file_format[:24],
                storage_path=storage_path,
                bytes=size,
                created_at=timestamp,
                updated_at=timestamp,
                expires_at=timestamp + (24 * 60 * 60),
            )
            session.add(artifact)
        else:
            artifact.storage_path = storage_path
            artifact.format = file_format[:24]
            artifact.bytes = size
            artifact.updated_at = timestamp
            artifact.expires_at = timestamp + (24 * 60 * 60)
        session.flush()
        return artifact


def get_artifact(user_id: int, project_id: str) -> Artifact | None:
    with session_scope() as session:
        artifact = session.scalar(
            select(Artifact).where(
                Artifact.user_id == user_id,
                Artifact.project_id == project_id,
                Artifact.expires_at > now_ts(),
            )
        )
        return artifact


def remove_expired_artifacts(limit: int = 100) -> list[str]:
    paths = []
    with session_scope() as session:
        artifacts = session.scalars(
            select(Artifact).where(Artifact.expires_at <= now_ts()).limit(max(1, min(limit, 500)))
        ).all()
        for artifact in artifacts:
            paths.append(artifact.storage_path)
            session.delete(artifact)
    return paths


def extend_artifact_for_purchase(project_id: str) -> None:
    with session_scope() as session:
        artifact = session.scalar(select(Artifact).where(Artifact.project_id == project_id))
        if artifact:
            artifact.expires_at = now_ts() + (30 * 24 * 60 * 60)
            artifact.updated_at = now_ts()


def record_download(user_id: int, project_id: str, file_kind: str, file_format: str, size: int | None, warning: bool) -> Download:
    entitlement = active_entitlement(user_id, project_id)
    item = Download(
        id=str(uuid.uuid4()),
        user_id=user_id,
        project_id=project_id,
        order_id=entitlement.order_id if entitlement else None,
        file_kind=file_kind[:48],
        format=file_format[:24],
        bytes=size,
        warning_acknowledged=warning,
        created_at=now_ts(),
    )
    with session_scope() as session:
        session.add(item)
    return item


def record_event(name: str, user_id: int | None = None, project_id: str | None = None, anonymous_id: str | None = None, metadata: dict | None = None) -> None:
    allowed = {
        "landing_view",
        "studio_opened",
        "programme_selected",
        "photo_added",
        "processing_completed",
        "review_opened",
        "checkout_started",
        "payment_completed",
        "download_completed",
        "enquiry_created",
    }
    if name not in allowed:
        raise ValueError("event_name")
    with session_scope() as session:
        session.add(
            Event(
                id=str(uuid.uuid4()),
                name=name,
                user_id=user_id,
                project_id=project_id,
                anonymous_id=(anonymous_id or "")[:64] or None,
                metadata_json=_json_dump(metadata or {}),
                created_at=now_ts(),
            )
        )


def create_enquiry(user_id: int | None, name: str, email: str, subject: str, message: str) -> Enquiry:
    timestamp = now_ts()
    item = Enquiry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name.strip()[:160],
        email=email.strip().lower()[:320],
        subject=subject.strip()[:200],
        message=message.strip()[:5000],
        status="new",
        admin_note="",
        created_at=timestamp,
        updated_at=timestamp,
    )
    with session_scope() as session:
        session.add(item)
    return item


def admin_dashboard() -> dict:
    timestamp = now_ts()
    day = 24 * 60 * 60
    cutoff_30d = timestamp - (30 * day)
    cutoff_14d = timestamp - (14 * day)
    cutoff_7d = timestamp - (7 * day)
    cutoff_today = timestamp - day

    def visitor_key(row) -> str | None:
        if row.anonymous_id:
            return f"anonymous:{row.anonymous_id}"
        return None

    def event_detail(name: str, metadata: dict) -> str:
        if name == "programme_selected":
            return str(metadata.get("country") or metadata.get("profileId") or "Programme selected")[:80]
        if name == "processing_completed":
            return str(metadata.get("decision") or "Photo processed")[:80]
        if name == "download_completed":
            return str(metadata.get("fileKind") or "Prepared file")[:80]
        return ""

    with session_scope() as session:
        order_status = dict(session.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all())
        funnel = dict(session.execute(select(Event.name, func.count(Event.id)).group_by(Event.name)).all())
        revenue = session.scalar(select(func.coalesce(func.sum(Order.amount_minor), 0)).where(Order.status == "paid")) or 0
        recent_orders = session.scalars(select(Order).order_by(Order.created_at.desc()).limit(12)).all()
        recent_enquiries = session.scalars(select(Enquiry).order_by(Enquiry.created_at.desc()).limit(12)).all()
        recent_users = session.scalars(select(User).order_by(User.created_at.desc()).limit(100)).all()
        recent_subscriptions = session.scalars(
            select(Subscription).order_by(Subscription.updated_at.desc()).limit(50)
        ).all()
        recent_billing_payments = session.scalars(
            select(BillingPayment).order_by(BillingPayment.updated_at.desc()).limit(50)
        ).all()
        subscription_by_user = {}
        for subscription in recent_subscriptions:
            subscription_by_user.setdefault(subscription.user_id, subscription)
        project_counts = dict(session.execute(select(Project.user_id, func.count(Project.id)).group_by(Project.user_id)).all())
        download_counts = dict(session.execute(select(Download.user_id, func.count(Download.id)).group_by(Download.user_id)).all())
        traffic_rows = session.execute(
            select(Event.name, Event.user_id, Event.anonymous_id, Event.metadata_json, Event.created_at)
            .where(Event.created_at >= cutoff_30d)
            .order_by(Event.created_at.desc())
        ).all()
        all_unique_visitors = session.scalar(
            select(func.count(func.distinct(Event.anonymous_id))).where(Event.anonymous_id.is_not(None))
        ) or 0
        landing_views = session.scalar(select(func.count(Event.id)).where(Event.name == "landing_view")) or 0
        studio_sessions = session.scalar(select(func.count(Event.id)).where(Event.name == "studio_opened")) or 0
        registrations_7d = session.scalar(select(func.count(User.id)).where(User.created_at >= cutoff_7d)) or 0

        active_today = set()
        active_7d = set()
        active_30d = set()
        event_counts_30d = Counter()
        destinations = Counter()
        recent_activity = []
        daily = {}
        for offset in range(13, -1, -1):
            date_key = datetime.fromtimestamp(timestamp - (offset * day), tz=timezone.utc).strftime("%Y-%m-%d")
            daily[date_key] = {"visitors": set(), "landingViews": 0, "studioSessions": 0, "processed": 0}

        for row in traffic_rows:
            key = visitor_key(row)
            if key:
                active_30d.add(key)
                if row.created_at >= cutoff_7d:
                    active_7d.add(key)
                if row.created_at >= cutoff_today:
                    active_today.add(key)
            event_counts_30d[row.name] += 1
            metadata = _json_load(row.metadata_json)
            if row.name == "programme_selected" and metadata.get("country"):
                destinations[str(metadata["country"])[:12].upper()] += 1
            date_key = datetime.fromtimestamp(row.created_at, tz=timezone.utc).strftime("%Y-%m-%d")
            if row.created_at >= cutoff_14d and date_key in daily:
                if key:
                    daily[date_key]["visitors"].add(key)
                if row.name == "landing_view":
                    daily[date_key]["landingViews"] += 1
                elif row.name == "studio_opened":
                    daily[date_key]["studioSessions"] += 1
                elif row.name == "processing_completed":
                    daily[date_key]["processed"] += 1
            if len(recent_activity) < 20:
                recent_activity.append(
                    {
                        "name": row.name,
                        "actor": "Customer" if row.user_id else "Guest",
                        "detail": event_detail(row.name, metadata),
                        "createdAt": row.created_at,
                    }
                )

        stage_order = ["studio_opened", "photo_added", "processing_completed", "review_opened", "download_completed"]
        conversion_30d = []
        previous_count = None
        for name in stage_order:
            count = event_counts_30d.get(name, 0)
            rate = 100.0 if previous_count is None and count else (count / previous_count * 100.0 if previous_count else 0.0)
            conversion_30d.append({"name": name, "count": count, "fromPreviousPercent": round(rate, 1)})
            previous_count = count

        return {
            "metrics": {
                "users": session.scalar(select(func.count(User.id))) or 0,
                "projects": session.scalar(select(func.count(Project.id))) or 0,
                "paidOrders": order_status.get("paid", 0),
                "pendingOrders": order_status.get("pending", 0),
                "revenueMinor": int(revenue),
                "downloads": session.scalar(select(func.count(Download.id))) or 0,
                "openEnquiries": session.scalar(select(func.count(Enquiry.id)).where(Enquiry.status != "resolved")) or 0,
                "activeSubscriptions": session.scalar(
                    select(func.count(Subscription.id)).where(
                        Subscription.status.in_(["active", "trialing"])
                    )
                )
                or 0,
                "pastDueSubscriptions": session.scalar(
                    select(func.count(Subscription.id)).where(Subscription.status == "past_due")
                )
                or 0,
                "stripePayments": session.scalar(
                    select(func.count(BillingPayment.id)).where(BillingPayment.status == "paid")
                )
                or 0,
                "stripeRevenueMinor": int(
                    session.scalar(
                        select(func.coalesce(func.sum(BillingPayment.amount_minor), 0)).where(
                            BillingPayment.status == "paid",
                            BillingPayment.currency == "CAD",
                        )
                    )
                    or 0
                ),
            },
            "traffic": {
                "uniqueVisitors": int(all_unique_visitors),
                "activeToday": len(active_today),
                "active7d": len(active_7d),
                "active30d": len(active_30d),
                "landingViews": int(landing_views),
                "studioSessions": int(studio_sessions),
                "registrations7d": int(registrations_7d),
                "events30d": sum(event_counts_30d.values()),
                "daily": [
                    {
                        "date": date_key,
                        "visitors": len(values["visitors"]),
                        "landingViews": values["landingViews"],
                        "studioSessions": values["studioSessions"],
                        "processed": values["processed"],
                    }
                    for date_key, values in daily.items()
                ],
            },
            "conversion30d": conversion_30d,
            "destinations": [{"country": country, "selections": count} for country, count in destinations.most_common(8)],
            "recentActivity": recent_activity,
            "customers": [
                {
                    "id": item.id,
                    "name": item.name or "",
                    "email": item.email,
                    "role": item.role,
                    "status": item.status,
                    "emailVerified": bool(item.email_verified),
                    "projects": int(project_counts.get(item.id, 0)),
                    "downloads": int(download_counts.get(item.id, 0)),
                    "subscription": subscription_dict(subscription_by_user.get(item.id)),
                    "createdAt": item.created_at,
                    "lastLoginAt": item.last_login_at,
                }
                for item in recent_users
            ],
            "funnel": funnel,
            "orders": [order_dict(item) | {"userId": item.user_id} for item in recent_orders],
            "subscriptions": [subscription_dict(item) | {"userId": item.user_id} for item in recent_subscriptions],
            "billingPayments": [billing_payment_dict(item) for item in recent_billing_payments],
            "enquiries": [enquiry_dict(item) for item in recent_enquiries],
        }


def enquiry_dict(item: Enquiry) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "email": item.email,
        "subject": item.subject,
        "message": item.message,
        "status": item.status,
        "adminNote": item.admin_note,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def update_enquiry(admin_user_id: int, enquiry_id: str, status: str, note: str) -> Enquiry | None:
    if status not in {"new", "in_progress", "waiting", "resolved"}:
        raise ValueError("enquiry_status")
    with session_scope() as session:
        item = session.get(Enquiry, enquiry_id)
        if not item:
            return None
        item.status = status
        item.admin_note = note.strip()[:5000]
        item.updated_at = now_ts()
        session.add(
            AdminAudit(
                id=str(uuid.uuid4()),
                admin_user_id=admin_user_id,
                action="enquiry.updated",
                target_type="enquiry",
                target_id=enquiry_id,
                metadata_json=_json_dump({"status": status}),
                created_at=now_ts(),
            )
        )
        return item


def _json_dump(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)[:20000]


def _json_load(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}
