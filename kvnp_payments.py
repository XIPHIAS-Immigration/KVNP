"""Payment-provider boundary for KVNP subscriptions and legacy demo checkout."""

from __future__ import annotations

import os
import secrets
import string
from dataclasses import dataclass


STRIPE_API_VERSION = "2026-06-24.dahlia"


def stripe_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    converter = getattr(value, "to_dict_recursive", None)
    if callable(converter):
        converted = converter()
        if isinstance(converted, dict):
            return converted
    keys = getattr(value, "keys", None)
    if callable(keys):
        return {key: value[key] for key in keys()}
    raise TypeError(f"Unsupported Stripe response type: {type(value).__name__}")


@dataclass(frozen=True)
class CheckoutSession:
    provider: str
    status: str
    checkout_url: str | None = None
    provider_order_id: str | None = None
    development: bool = False


class PaymentGateway:
    name = "disabled"

    @property
    def configured(self) -> bool:
        return False

    def create_checkout(self, order: dict, return_url: str) -> CheckoutSession:
        raise RuntimeError("Online payments are not configured yet.")


class DisabledGateway(PaymentGateway):
    name = "disabled"


class MockGateway(PaymentGateway):
    name = "mock"

    @property
    def configured(self) -> bool:
        return True

    def create_checkout(self, order: dict, return_url: str) -> CheckoutSession:
        return CheckoutSession(
            provider=self.name,
            status="requires_demo_confirmation",
            checkout_url=None,
            provider_order_id=f"mock-order-{order['id']}",
            development=True,
        )


class StripeGateway(PaymentGateway):
    name = "stripe"

    def __init__(self, stripe_module=None):
        self.api_key = (
            os.getenv("STRIPE_RESTRICTED_KEY", "").strip()
            or os.getenv("STRIPE_SECRET_KEY", "").strip()
        )
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
        self.price_id = os.getenv("STRIPE_PRICE_ID", "").strip()
        self.currency = os.getenv("STRIPE_CURRENCY", "CAD").strip().lower() or "cad"
        suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))
        self.integration_identifier = (
            os.getenv("STRIPE_INTEGRATION_IDENTIFIER", "").strip() or f"kvnpweb-{suffix}"
        )
        self._stripe = stripe_module
        self._validated_price = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.webhook_secret and self.price_id)

    def _sdk(self):
        if self._stripe is None:
            try:
                import stripe
            except ImportError as error:
                raise RuntimeError("The Stripe SDK is not installed on this server.") from error
            self._stripe = stripe
        return self._stripe

    def _request_options(self) -> dict:
        return {"api_key": self.api_key, "stripe_version": STRIPE_API_VERSION}

    def validate_price(self) -> dict:
        if not self.api_key or not self.price_id:
            raise RuntimeError("Stripe sandbox credentials and STRIPE_PRICE_ID are not configured.")
        if self._validated_price is not None:
            return self._validated_price
        price = self._sdk().Price.retrieve(self.price_id, **self._request_options())
        price_data = stripe_dict(price)
        if not price_data.get("active"):
            raise RuntimeError("The configured Stripe Price is inactive.")
        if str(price_data.get("currency") or "").lower() != self.currency:
            raise RuntimeError(f"The configured Stripe Price must use {self.currency.upper()}.")
        if not price_data.get("recurring"):
            raise RuntimeError("The configured Stripe Price must be recurring.")
        self._validated_price = price_data
        return price_data

    def create_subscription_checkout(
        self,
        user: dict | None,
        success_url: str,
        cancel_url: str,
        checkout_id: str,
    ) -> CheckoutSession:
        self.validate_price()
        metadata = {"kvnp_checkout_id": checkout_id, "kvnp_product": "studio-membership"}
        params = {
            "mode": "subscription",
            "line_items": [{"price": self.price_id, "quantity": 1}],
            "metadata": metadata,
            "subscription_data": {"metadata": metadata},
            "success_url": success_url,
            "cancel_url": cancel_url,
            "integration_identifier": self.integration_identifier,
        }
        if user:
            metadata["kvnp_user_id"] = str(user["id"])
            params["customer_email"] = user["email"]
            params["client_reference_id"] = str(user["id"])
        session = self._sdk().checkout.Session.create(
            **params,
            idempotency_key=f"kvnp-checkout-{checkout_id}",
            **self._request_options(),
        )
        session_data = stripe_dict(session)
        return CheckoutSession(
            provider=self.name,
            status=str(session_data.get("status") or "open"),
            checkout_url=session_data.get("url"),
            provider_order_id=session_data.get("id"),
            development=not bool(session_data.get("livemode")),
        )

    def create_portal_session(self, customer_id: str, return_url: str) -> str:
        session = self._sdk().billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
            **self._request_options(),
        )
        return str(session["url"])

    def retrieve_subscription(self, subscription_id: str) -> dict:
        item = self._sdk().Subscription.retrieve(
            subscription_id,
            expand=["latest_invoice"],
            **self._request_options(),
        )
        return stripe_dict(item)

    def retrieve_checkout(self, session_id: str) -> dict:
        item = self._sdk().checkout.Session.retrieve(session_id, **self._request_options())
        return stripe_dict(item)

    def construct_event(self, payload: bytes, signature: str) -> dict:
        if not self.webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured.")
        return stripe_dict(self._sdk().Webhook.construct_event(payload, signature, self.webhook_secret))


class SliceGateway(PaymentGateway):
    name = "slice"

    def create_checkout(self, order: dict, return_url: str) -> CheckoutSession:
        raise RuntimeError(
            "Slice merchant credentials are not configured. The adapter boundary is ready for UAT onboarding."
        )


def gateway_for(mode: str) -> PaymentGateway:
    value = (mode or "disabled").strip().lower()
    if value == "mock":
        return MockGateway()
    if value == "stripe":
        return StripeGateway()
    if value == "slice":
        return SliceGateway()
    return DisabledGateway()
