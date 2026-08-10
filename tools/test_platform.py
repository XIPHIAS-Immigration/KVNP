"""End-to-end regressions for accounts, projects, commerce, and administration."""

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEMP_DATA = tempfile.TemporaryDirectory(prefix="kvnp-platform-")
os.environ["KVNP_DATA_DIR"] = TEMP_DATA.name
os.environ["KVNP_PAYMENT_MODE"] = "mock"
os.environ["KVNP_ALLOW_MOCK_PAYMENTS"] = "true"
os.environ["KVNP_COMMERCE_ENFORCED"] = "true"
os.environ["KVNP_APPLICATION_PRICE_MINOR"] = "19900"

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402


PASS = "  ok"


def signup(client, email="admin@kvnp.test", name="Admin User"):
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "name": name, "password": "correct-horse-42"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["csrfToken"]
    return data


def save_project(client, csrf):
    response = client.post(
        "/api/projects",
        headers={"x-kvnp-csrf": csrf},
        json={
            "applicantName": "Example Applicant",
            "profileId": "us-passport-print-2026-01",
            "countryCode": "US",
            "programmeLabel": "United States passport",
            "status": "prepared",
            "resultStatus": "review",
            "summary": {"warnings": 1, "output": "600x600"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["project"]


def test_paid_application_lifecycle():
    with TestClient(server.app) as client:
        auth = signup(client)
        assert auth["user"]["role"] == "customer"
        server.platform.promote_admin("admin@kvnp.test")
        promoted = client.get("/api/auth/me").json()
        assert promoted["user"]["role"] == "admin"
        project = save_project(client, auth["csrfToken"])
        sample = server.np.full((180, 140, 3), 225, dtype=server.np.uint8)
        encoded_ok, encoded = server.cv2.imencode(".jpg", sample)
        assert encoded_ok
        artifact = client.post(
            f"/api/projects/{project['id']}/artifact",
            headers={"x-kvnp-csrf": auth["csrfToken"]},
            files={"image": ("prepared.jpg", encoded.tobytes(), "image/jpeg")},
        )
        assert artifact.status_code == 200, artifact.text

        checkout = client.post(
            "/api/checkout/start",
            headers={"x-kvnp-csrf": auth["csrfToken"]},
            json={"projectId": project["id"], "amountMinor": 1},
        )
        assert checkout.status_code == 200, checkout.text
        order = checkout.json()["order"]
        assert order["amountMinor"] == 19900, "client must not control price"
        assert order["status"] == "pending"

        blocked_client = TestClient(server.app)
        blocked = blocked_client.post(
            "/api/downloads/authorize",
            json={"projectId": project["id"], "fileKind": "prepared", "format": "image/jpeg"},
        )
        assert blocked.status_code == 401
        blocked_client.close()

        paid = client.post(
            "/api/checkout/mock/complete",
            headers={"x-kvnp-csrf": auth["csrfToken"]},
            json={"orderId": order["id"]},
        )
        assert paid.status_code == 200, paid.text
        assert paid.json()["entitled"] is True

        download = client.post(
            "/api/downloads/authorize",
            headers={"x-kvnp-csrf": auth["csrfToken"]},
            json={
                "projectId": project["id"],
                "fileKind": "prepared",
                "format": "image/jpeg",
                "bytes": 45000,
                "warningAcknowledged": True,
            },
        )
        assert download.status_code == 200, download.text
        assert download.json()["entitled"] is True
        saved = client.get(f"/api/projects/{project['id']}/artifact")
        assert saved.status_code == 200, saved.text
        assert saved.headers["content-type"].startswith("image/jpeg")
    print("test_paid_application_lifecycle", PASS)


def test_enquiry_and_admin_dashboard():
    with TestClient(server.app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "admin@kvnp.test", "password": "correct-horse-42"},
        )
        assert login.status_code == 200, login.text
        csrf = login.json()["csrfToken"]
        enquiry = client.post(
            "/api/enquiries",
            json={
                "name": "Example Applicant",
                "email": "applicant@example.test",
                "subject": "Download question",
                "message": "I need help choosing the correct PDF output.",
            },
        )
        assert enquiry.status_code == 200, enquiry.text
        for name, metadata in [
            ("landing_view", {}),
            ("studio_opened", {}),
            ("programme_selected", {"country": "US", "profileId": "us-passport-print-2026-01"}),
            ("photo_added", {"bytes": 42000}),
            ("processing_completed", {"decision": "review"}),
            ("review_opened", {}),
        ]:
            event = client.post(
                "/api/events",
                json={"name": name, "anonymousId": "test-visitor-1", "metadata": metadata},
            )
            assert event.status_code == 200, event.text

        dashboard = client.get("/api/admin/dashboard")
        assert dashboard.status_code == 200, dashboard.text
        data = dashboard.json()
        assert data["metrics"]["users"] == 1
        assert data["metrics"]["paidOrders"] == 1
        assert data["metrics"]["downloads"] == 2
        assert data["metrics"]["openEnquiries"] == 1
        assert data["traffic"]["uniqueVisitors"] == 1
        assert data["traffic"]["active7d"] == 1
        assert data["traffic"]["landingViews"] == 1
        assert data["traffic"]["studioSessions"] == 1
        assert len(data["traffic"]["daily"]) == 14
        assert data["destinations"][0] == {"country": "US", "selections": 1}
        assert data["conversion30d"][0]["name"] == "studio_opened"
        assert data["recentActivity"]
        assert data["customers"][0]["name"] == "Admin User"
        assert data["customers"][0]["email"] == "admin@kvnp.test"
        assert data["customers"][0]["role"] == "admin"
        assert data["customers"][0]["projects"] == 1
        assert data["customers"][0]["downloads"] == 2

        enquiry_id = data["enquiries"][0]["id"]
        update = client.patch(
            f"/api/admin/enquiries/{enquiry_id}",
            headers={"x-kvnp-csrf": csrf},
            json={"status": "resolved", "adminNote": "Sent output guidance."},
        )
        assert update.status_code == 200, update.text
        assert update.json()["enquiry"]["status"] == "resolved"
    print("test_enquiry_and_admin_dashboard", PASS)


def test_customer_cannot_open_admin():
    with TestClient(server.app) as client:
        signup(client, "customer@example.test", "Customer")
        response = client.get("/api/admin/dashboard")
        assert response.status_code == 403
    print("test_customer_cannot_open_admin", PASS)


def main():
    try:
        test_paid_application_lifecycle()
        test_enquiry_and_admin_dashboard()
        test_customer_cannot_open_admin()
        print("\nAll 3 platform tests passed.")
    finally:
        server.platform.ENGINE.dispose()
        TEMP_DATA.cleanup()


if __name__ == "__main__":
    main()
