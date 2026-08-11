"""Stripe subscription regressions without contacting Stripe or charging a card."""

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEMP_DATA = tempfile.TemporaryDirectory(prefix="kvnp-stripe-")
os.environ["KVNP_DATA_DIR"] = TEMP_DATA.name
os.environ["KVNP_PAYMENT_MODE"] = "mock"
os.environ["KVNP_COMMERCE_ENFORCED"] = "true"
os.environ["STRIPE_RESTRICTED_KEY"] = "test-restricted-key-placeholder"
os.environ["STRIPE_WEBHOOK_SECRET"] = "test-webhook-secret-placeholder"
os.environ["STRIPE_PRICE_ID"] = "price_cad_monthly"
os.environ["STRIPE_CURRENCY"] = "CAD"

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from kvnp_payments import StripeGateway  # noqa: E402


class FakePrice:
    @staticmethod
    def retrieve(price_id, **_options):
        assert price_id == "price_cad_monthly"
        return {"id": price_id, "active": True, "currency": "cad", "recurring": {"interval": "month"}}


class FakeCheckoutSession:
    last_params = None

    @classmethod
    def create(cls, **params):
        cls.last_params = params
        return {"id": "cs_test_kvnp", "url": "https://checkout.stripe.test/session", "status": "open", "livemode": False}


class FakePortalSession:
    @staticmethod
    def create(**params):
        assert params["customer"] == "cus_kvnp_test"
        return {"url": "https://billing.stripe.test/session"}


class FakeWebhook:
    @staticmethod
    def construct_event(payload, _signature, _secret):
        return json.loads(payload)


class FakeSubscription:
    @staticmethod
    def retrieve(_subscription_id, **_options):
        return subscription_payload()


class FakeStripe:
    Price = FakePrice
    Webhook = FakeWebhook
    Subscription = FakeSubscription

    class checkout:
        Session = FakeCheckoutSession

    class billing_portal:
        Session = FakePortalSession


def subscription_payload(status="active"):
    return {
        "id": "sub_kvnp_test",
        "customer": "cus_kvnp_test",
        "status": status,
        "cancel_at_period_end": False,
        "current_period_end": 2_000_000_000,
        "metadata": {"kvnp_user_id": "1", "kvnp_product": "studio-membership"},
        "items": {"data": [{"price": {"id": "price_cad_monthly", "currency": "cad"}}]},
    }


def main():
    gateway = StripeGateway(stripe_module=FakeStripe)
    server.PAYMENT_MODE = "stripe"
    server.PAYMENT_GATEWAY = gateway
    server.COMMERCE_ENFORCED = True
    with TestClient(server.app) as client:
        assert client.get("/pricing").status_code == 200
        signup = client.post(
            "/api/auth/signup",
            json={"email": "subscriber@example.test", "name": "Subscriber", "password": "correct-horse-42"},
        )
        assert signup.status_code == 200, signup.text
        csrf = signup.json()["csrfToken"]
        project = client.post(
            "/api/projects",
            headers={"x-kvnp-csrf": csrf},
            json={"profileId": "us-passport-print-2026-01", "countryCode": "US", "programmeLabel": "US passport"},
        ).json()["project"]

        checkout = client.post("/api/billing/checkout", headers={"x-kvnp-csrf": csrf})
        assert checkout.status_code == 200, checkout.text
        assert checkout.json()["checkout"]["url"].startswith("https://checkout.stripe.test/")
        params = FakeCheckoutSession.last_params
        assert params["mode"] == "subscription"
        assert params["line_items"] == [{"price": "price_cad_monthly", "quantity": 1}]
        assert "payment_method_types" not in params
        assert "automatic_tax" not in params

        before = client.get("/api/account/summary").json()
        assert before["subscription"]["active"] is False, "success redirects must not grant access"
        blocked = client.post(
            "/api/downloads/authorize",
            headers={"x-kvnp-csrf": csrf},
            json={"projectId": project["id"], "fileKind": "prepared", "format": "image/jpeg"},
        )
        assert blocked.status_code == 402

        event = {
            "id": "evt_kvnp_subscription_active",
            "type": "customer.subscription.updated",
            "data": {"object": subscription_payload()},
        }
        webhook = client.post(
            "/api/stripe/webhook",
            headers={"stripe-signature": "test-signature"},
            content=json.dumps(event),
        )
        assert webhook.status_code == 200, webhook.text
        assert webhook.json()["handled"] is True
        duplicate = client.post(
            "/api/stripe/webhook",
            headers={"stripe-signature": "test-signature"},
            content=json.dumps(event),
        )
        assert duplicate.json()["duplicate"] is True

        invoice_event = {
            "id": "evt_kvnp_invoice_paid",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_kvnp_paid",
                    "customer": "cus_kvnp_test",
                    "currency": "cad",
                    "amount_paid": 1499,
                    "created": 1_999_000_000,
                    "parent": {"subscription_details": {"subscription": "sub_kvnp_test"}},
                }
            },
        }
        invoice_webhook = client.post(
            "/api/stripe/webhook",
            headers={"stripe-signature": "test-signature"},
            content=json.dumps(invoice_event),
        )
        assert invoice_webhook.status_code == 200, invoice_webhook.text

        after = client.get("/api/account/summary").json()
        assert after["subscription"]["active"] is True
        assert after["projects"][0]["entitled"] is True
        allowed = client.post(
            "/api/downloads/authorize",
            headers={"x-kvnp-csrf": csrf},
            json={"projectId": project["id"], "fileKind": "prepared", "format": "image/jpeg"},
        )
        assert allowed.status_code == 200, allowed.text

        portal = client.post("/api/billing/portal", headers={"x-kvnp-csrf": csrf})
        assert portal.status_code == 200, portal.text
        assert portal.json()["url"].startswith("https://billing.stripe.test/")

        server.platform.promote_admin("subscriber@example.test")
        dashboard = client.get("/api/admin/dashboard").json()
        assert dashboard["metrics"]["activeSubscriptions"] == 1
        assert dashboard["metrics"]["stripePayments"] == 1
        assert dashboard["metrics"]["stripeRevenueMinor"] == 1499
        assert dashboard["billingPayments"][0]["invoiceId"] == "in_kvnp_paid"

    server.platform.ENGINE.dispose()
    TEMP_DATA.cleanup()
    print("Stripe billing tests passed.")


if __name__ == "__main__":
    main()
