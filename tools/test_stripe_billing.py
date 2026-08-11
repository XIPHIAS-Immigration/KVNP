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


class FakeStripeObject:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        if isinstance(key, int):
            raise KeyError(key)
        return self.data[key]

    def keys(self):
        return self.data.keys()

    def to_dict_recursive(self):
        return self.data


class FakeModernStripeObject(FakeStripeObject):
    """Matches Stripe SDK releases that expose to_dict() only."""

    to_dict_recursive = None

    def keys(self):
        raise AssertionError("Stripe object must be converted with to_dict()")

    def to_dict(self):
        return self.data


class FakePrice:
    @staticmethod
    def retrieve(price_id, **_options):
        assert price_id == "price_cad_monthly"
        return FakeModernStripeObject(
            {"id": price_id, "active": True, "currency": "cad", "recurring": {"interval": "month"}}
        )


class FakeCheckoutSession:
    last_params = None
    sessions = {}
    count = 0

    @classmethod
    def create(cls, **params):
        cls.last_params = params
        cls.count += 1
        session_id = f"cs_test_kvnp_{cls.count}"
        session = {
            "id": session_id,
            "url": f"https://checkout.stripe.test/{session_id}",
            "status": "open",
            "payment_status": "unpaid",
            "mode": "subscription",
            "metadata": params["metadata"],
            "livemode": False,
        }
        cls.sessions[session_id] = session
        return FakeStripeObject(session)

    @classmethod
    def retrieve(cls, session_id, **_options):
        return FakeStripeObject(cls.sessions[session_id])


class FakePortalSession:
    @staticmethod
    def create(**params):
        assert str(params["customer"]).startswith("cus_")
        return {"url": "https://billing.stripe.test/session"}


class FakeWebhook:
    @staticmethod
    def construct_event(payload, _signature, _secret):
        return FakeStripeObject(json.loads(payload))


class FakeSubscription:
    items = {}

    @classmethod
    def retrieve(cls, subscription_id, **_options):
        return FakeStripeObject(cls.items[subscription_id])


class FakeStripe:
    Price = FakePrice
    Webhook = FakeWebhook
    Subscription = FakeSubscription

    class checkout:
        Session = FakeCheckoutSession

    class billing_portal:
        Session = FakePortalSession


def subscription_payload(subscription_id, customer_id, metadata, status="active", with_invoice=False):
    payload = {
        "id": subscription_id,
        "customer": customer_id,
        "status": status,
        "cancel_at_period_end": False,
        "current_period_end": 2_000_000_000,
        "metadata": metadata,
        "items": {"data": [{"price": {"id": "price_cad_monthly", "currency": "cad"}}]},
    }
    if with_invoice:
        payload["latest_invoice"] = {
            "id": f"in_{subscription_id}",
            "customer": customer_id,
            "currency": "cad",
            "amount_paid": 500,
            "created": 1_999_000_000,
            "status": "paid",
            "paid": True,
            "parent": {"subscription_details": {"subscription": subscription_id}},
        }
    return payload


def checkout_completed_event(session):
    return {
        "id": f"evt_{session['id']}",
        "type": "checkout.session.completed",
        "data": {"object": session},
    }


def main():
    gateway = StripeGateway(stripe_module=FakeStripe)
    server.PAYMENT_MODE = "stripe"
    server.PAYMENT_GATEWAY = gateway
    server.COMMERCE_ENFORCED = True
    with TestClient(server.app) as client:
        assert client.get("/pricing").status_code == 200
        assert client.get("/activate").status_code == 200
        prepayment_signup = client.post(
            "/api/auth/signup",
            json={"email": "too.early@example.test", "name": "Too Early", "password": "correct-horse-42"},
        )
        assert prepayment_signup.status_code == 403
        assert prepayment_signup.json()["action"] == "/pricing"

        # Payment comes first: an anonymous visitor can open hosted Checkout.
        checkout = client.post("/api/billing/checkout", headers={"origin": "http://testserver"})
        assert checkout.status_code == 200, checkout.text
        checkout_url = checkout.json()["checkout"]["url"]
        session_id = checkout_url.rsplit("/", 1)[-1]
        params = FakeCheckoutSession.last_params
        assert params["mode"] == "subscription"
        assert params["line_items"] == [{"price": "price_cad_monthly", "quantity": 1}]
        assert "customer_email" not in params
        assert "client_reference_id" not in params
        assert "payment_method_types" not in params
        assert "automatic_tax" not in params
        assert params["metadata"]["kvnp_checkout_id"]
        assert params["idempotency_key"].startswith("kvnp-checkout-")
        assert client.cookies.get(server.CHECKOUT_CLAIM_COOKIE)

        # A success URL or pending Checkout cannot create an account or access.
        pending = client.get(f"/api/billing/activation?session_id={session_id}")
        assert pending.status_code == 200, pending.text
        assert pending.json()["paid"] is False
        assert client.get("/api/auth/me").json()["user"] is None

        # A verified webhook confirms payment and records the anonymous claim.
        claim_id = params["metadata"]["kvnp_checkout_id"]
        subscription_id = "sub_guest_kvnp"
        customer_id = "cus_guest_kvnp"
        metadata = {"kvnp_checkout_id": claim_id, "kvnp_product": "studio-membership"}
        FakeSubscription.items[subscription_id] = subscription_payload(
            subscription_id, customer_id, metadata, with_invoice=True
        )
        paid_session = FakeCheckoutSession.sessions[session_id]
        paid_session.update(
            {
                "status": "complete",
                "payment_status": "paid",
                "customer": customer_id,
                "subscription": subscription_id,
                "customer_details": {"email": "paid.customer@example.test"},
            }
        )
        event = checkout_completed_event(paid_session)
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

        with TestClient(server.app) as unrelated_browser:
            unbound = unrelated_browser.get(f"/api/billing/activation?session_id={session_id}")
            assert unbound.status_code == 404, "the Checkout Session ID alone must not claim a purchase"

        ready = client.get(f"/api/billing/activation?session_id={session_id}").json()
        assert ready["paid"] is True
        assert ready["existingAccount"] is False
        assert ready["email"].endswith("@example.test")

        # Account details are accepted only after the paid claim is verified.
        activated = client.post(
            "/api/billing/activate",
            json={"sessionId": session_id, "name": "Paid Customer", "password": "correct-horse-42"},
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["user"]["email"] == "paid.customer@example.test"
        assert client.cookies.get(server.CHECKOUT_CLAIM_COOKIE) is None

        account = client.get("/api/account/summary").json()
        assert account["subscription"]["active"] is True

        project = client.post(
            "/api/projects",
            headers={"x-kvnp-csrf": activated.json()["csrfToken"]},
            json={"profileId": "us-passport-print-2026-01", "countryCode": "US", "programmeLabel": "US passport"},
        ).json()["project"]
        allowed = client.post(
            "/api/downloads/authorize",
            headers={"x-kvnp-csrf": activated.json()["csrfToken"]},
            json={"projectId": project["id"], "fileKind": "prepared", "format": "image/jpeg"},
        )
        assert allowed.status_code == 200, allowed.text
        portal = client.post("/api/billing/portal", headers={"x-kvnp-csrf": activated.json()["csrfToken"]})
        assert portal.status_code == 200, portal.text

        # The paid claim is one-use and cannot be replayed after activation.
        replay = client.post(
            "/api/billing/activate",
            json={"sessionId": session_id, "name": "Attacker", "password": "another-password"},
        )
        assert replay.status_code == 409, replay.text

        # Paying with an existing account email requires that account's password.
        client.post("/api/auth/logout")
        server.platform.create_user(
            "returning.customer@example.test",
            "Returning Customer",
            server.PASSWORD_HASHER.hash("returning-password"),
        )
        returning_checkout = client.post("/api/billing/checkout", headers={"origin": "http://testserver"})
        returning_session_id = returning_checkout.json()["checkout"]["url"].rsplit("/", 1)[-1]
        returning_claim_id = FakeCheckoutSession.last_params["metadata"]["kvnp_checkout_id"]
        returning_subscription_id = "sub_returning_kvnp"
        returning_customer_id = "cus_returning_kvnp"
        returning_metadata = {
            "kvnp_checkout_id": returning_claim_id,
            "kvnp_product": "studio-membership",
        }
        FakeSubscription.items[returning_subscription_id] = subscription_payload(
            returning_subscription_id,
            returning_customer_id,
            returning_metadata,
            with_invoice=True,
        )
        returning_session = FakeCheckoutSession.sessions[returning_session_id]
        returning_session.update(
            {
                "status": "complete",
                "payment_status": "paid",
                "customer": returning_customer_id,
                "subscription": returning_subscription_id,
                "customer_details": {"email": "returning.customer@example.test"},
            }
        )
        returning_webhook = client.post(
            "/api/stripe/webhook",
            headers={"stripe-signature": "test-signature"},
            content=json.dumps(checkout_completed_event(returning_session)),
        )
        assert returning_webhook.status_code == 200, returning_webhook.text
        returning_ready = client.get(
            f"/api/billing/activation?session_id={returning_session_id}"
        ).json()
        assert returning_ready["existingAccount"] is True
        wrong_password = client.post(
            "/api/billing/activate",
            json={"sessionId": returning_session_id, "password": "wrong-password"},
        )
        assert wrong_password.status_code == 401
        returning_activated = client.post(
            "/api/billing/activate",
            json={"sessionId": returning_session_id, "password": "returning-password"},
        )
        assert returning_activated.status_code == 200, returning_activated.text
        assert returning_activated.json()["user"]["email"] == "returning.customer@example.test"

        # Existing account-first entry remains compatible for signed-in users.
        with TestClient(server.app) as signed_client:
            signed_user = server.platform.create_user(
                "signed.checkout@example.test",
                "Signed Checkout",
                server.PASSWORD_HASHER.hash("signed-password"),
            )
            signed_up = signed_client.post(
                "/api/auth/login",
                json={"email": "signed.checkout@example.test", "password": "signed-password"},
            )
            signed_checkout = signed_client.post(
                "/api/billing/checkout",
                headers={"x-kvnp-csrf": signed_up.json()["csrfToken"]},
            )
            assert signed_checkout.status_code == 200, signed_checkout.text
            signed_params = FakeCheckoutSession.last_params
            assert signed_params["customer_email"] == "signed.checkout@example.test"
            assert signed_params["client_reference_id"] == str(signed_user.id)
            assert signed_client.cookies.get(server.CHECKOUT_CLAIM_COOKIE) is None

        server.platform.promote_admin("paid.customer@example.test")
        client.post("/api/auth/logout")
        admin_login = client.post(
            "/api/auth/login",
            json={"email": "paid.customer@example.test", "password": "correct-horse-42"},
        )
        assert admin_login.status_code == 200, admin_login.text
        dashboard = client.get("/api/admin/dashboard").json()
        assert dashboard["metrics"]["activeSubscriptions"] == 2
        assert dashboard["metrics"]["stripePayments"] == 2
        assert dashboard["metrics"]["stripeRevenueMinor"] == 1000

    server.platform.ENGINE.dispose()
    TEMP_DATA.cleanup()
    print("Stripe payment-first billing tests passed.")


if __name__ == "__main__":
    main()
