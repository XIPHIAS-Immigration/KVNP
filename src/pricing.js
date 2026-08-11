const elements = {
  accountLink: document.querySelector("#account-link"),
  price: document.querySelector("#plan-price"),
  includes: document.querySelector("#plan-includes"),
  subscribe: document.querySelector("#subscribe-button"),
  portal: document.querySelector("#portal-button"),
  status: document.querySelector("#billing-status"),
};

const state = { user: null, csrf: null, commerce: null };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);

async function load() {
  const [commerceResponse, authResponse] = await Promise.all([
    fetch("/api/commerce/config", { credentials: "same-origin" }),
    fetch("/api/auth/me", { credentials: "same-origin" }),
  ]);
  state.commerce = await commerceResponse.json();
  const auth = await authResponse.json();
  state.user = auth.user || null;
  state.csrf = auth.csrfToken || null;
  render();
}

function render() {
  const product = state.commerce?.product || {};
  const subscription = state.commerce?.subscription || {};
  elements.price.textContent = product.priceLabel || "Price shown at checkout";
  elements.includes.innerHTML = (product.includes || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  elements.accountLink.textContent = state.user ? "My workspace" : "Sign in";
  elements.accountLink.href = state.user ? "/account" : "/app?auth=login&next=/pricing";

  if (subscription.active) {
    elements.subscribe.hidden = true;
    elements.portal.hidden = false;
    elements.status.textContent = subscription.cancelAtPeriodEnd ? "Active until the end of the current billing period." : "Your membership is active.";
    return;
  }
  elements.subscribe.hidden = false;
  elements.portal.hidden = true;
  elements.subscribe.disabled = false;
  elements.subscribe.textContent = state.user ? "Continue to secure checkout" : "Create account to subscribe";
  if (!state.commerce?.enabled) {
    elements.subscribe.disabled = true;
    elements.subscribe.textContent = "Checkout opening soon";
    elements.status.textContent = "Stripe sandbox configuration is not complete on this server.";
  }
  if (new URLSearchParams(location.search).get("checkout") === "cancelled") {
    elements.status.textContent = "Checkout was cancelled. Nothing was charged.";
  }
}

async function startCheckout() {
  if (!state.user) {
    location.href = "/app?auth=signup&next=/pricing";
    return;
  }
  elements.subscribe.disabled = true;
  elements.subscribe.textContent = "Opening Stripe...";
  elements.status.textContent = "";
  const response = await fetch("/api/billing/checkout", {
    method: "POST",
    credentials: "same-origin",
    headers: { "x-kvnp-csrf": state.csrf },
  });
  const data = await response.json();
  if (!response.ok || !data.checkout?.url) {
    elements.subscribe.disabled = false;
    elements.subscribe.textContent = "Continue to secure checkout";
    elements.status.textContent = data.error || data.detail || "Checkout could not start.";
    return;
  }
  location.href = data.checkout.url;
}

async function openPortal() {
  elements.portal.disabled = true;
  elements.status.textContent = "Opening billing...";
  const response = await fetch("/api/billing/portal", {
    method: "POST",
    credentials: "same-origin",
    headers: { "x-kvnp-csrf": state.csrf },
  });
  const data = await response.json();
  if (!response.ok || !data.url) {
    elements.portal.disabled = false;
    elements.status.textContent = data.error || data.detail || "Billing management could not open.";
    return;
  }
  location.href = data.url;
}

elements.subscribe.addEventListener("click", startCheckout);
elements.portal.addEventListener("click", openPortal);
load().catch(() => {
  elements.subscribe.disabled = true;
  elements.subscribe.textContent = "Checkout unavailable";
  elements.status.textContent = "Could not load billing configuration.";
});
