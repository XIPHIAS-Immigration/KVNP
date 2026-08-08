"""Payment-provider boundary. Slice is intentionally connected after merchant onboarding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutSession:
    provider: str
    status: str
    checkout_url: str | None = None
    provider_order_id: str | None = None
    development: bool = False


class PaymentGateway:
    name = "disabled"

    def create_checkout(self, order: dict, return_url: str) -> CheckoutSession:
        raise RuntimeError("Online payments are not configured yet.")


class DisabledGateway(PaymentGateway):
    name = "disabled"


class MockGateway(PaymentGateway):
    name = "mock"

    def create_checkout(self, order: dict, return_url: str) -> CheckoutSession:
        return CheckoutSession(
            provider=self.name,
            status="requires_demo_confirmation",
            checkout_url=None,
            provider_order_id=f"mock-order-{order['id']}",
            development=True,
        )


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
    if value == "slice":
        return SliceGateway()
    return DisabledGateway()
