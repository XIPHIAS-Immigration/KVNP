const state = { user: null, csrf: null, projects: [], orders: [], subscription: null };

const money = (minor, currency = "CAD") => new Intl.NumberFormat("en-CA", { style: "currency", currency }).format((minor || 0) / 100);
const date = (value) => value ? new Date(value * 1000).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "-";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);

async function loadAccount() {
  const response = await fetch("/api/account/summary", { credentials: "same-origin" });
  if (response.status === 401) {
    location.href = "/app";
    return;
  }
  if (!response.ok) throw new Error("Could not load your workspace.");
  const data = await response.json();
  const auth = await fetch("/api/auth/me", { credentials: "same-origin" }).then((item) => item.json());
  state.user = data.user;
  state.csrf = auth.csrfToken;
  state.projects = data.projects || [];
  state.orders = data.orders || [];
  state.subscription = data.subscription || { status: "none", active: false };
  render();
}

function render() {
  document.querySelector("#welcome-title").textContent = `${state.user.name}'s application photos`;
  document.querySelector("#admin-link").hidden = state.user.role !== "admin";
  const ready = state.projects.filter((project) => project.entitled).length;
  document.querySelector("#metric-projects").textContent = state.projects.length;
  document.querySelector("#metric-membership").textContent = state.subscription.active ? "Active" : "None";
  document.querySelector("#metric-ready").textContent = ready;
  document.querySelector("#project-count").textContent = `${state.projects.length} saved`;
  document.querySelector("#project-list").innerHTML = state.projects.length ? state.projects.map(projectTemplate).join("") : '<p class="empty-state">No saved applications yet. Start with a new photo.</p>';
  document.querySelector("#order-list").innerHTML = state.orders.length ? state.orders.map((order) => `<tr><td>${escapeHtml(order.reference)}</td><td>${escapeHtml(order.productCode)}</td><td>${money(order.amountMinor, order.currency)}</td><td><span class="status-pill ${order.status}">${escapeHtml(order.status)}</span></td><td>${date(order.createdAt)}</td></tr>`).join("") : '<tr><td colspan="5">No orders yet.</td></tr>';
  renderMembership();
}

function renderMembership() {
  const title = document.querySelector("#membership-title");
  const detail = document.querySelector("#membership-detail");
  const join = document.querySelector("#membership-join");
  const manage = document.querySelector("#membership-manage");
  if (state.subscription.active) {
    title.textContent = "KVNP Studio membership active";
    detail.textContent = state.subscription.cancelAtPeriodEnd
      ? `Access continues until ${date(state.subscription.currentPeriodEnd)}.`
      : `Renews through Stripe. Current period ends ${date(state.subscription.currentPeriodEnd)}.`;
    join.hidden = true;
    manage.hidden = false;
  } else {
    title.textContent = state.subscription.status === "past_due" ? "Payment needs attention" : "Unlock the complete studio";
    detail.textContent = state.subscription.status === "past_due"
      ? "Open billing to update your payment method and restore prepared downloads."
      : "Subscribe in CAD to unlock prepared exports across your saved applications.";
    join.hidden = false;
    join.textContent = state.subscription.status === "past_due" ? "View billing options" : "View membership";
    manage.hidden = state.subscription.status === "none";
  }
  if (new URLSearchParams(location.search).get("checkout") === "success") {
    detail.textContent = state.subscription.active
      ? "Payment confirmed. Your membership and prepared downloads are active."
      : "Stripe is confirming your payment. Refresh this page in a moment if access is not yet active.";
  }
}

async function openBillingPortal() {
  const button = document.querySelector("#membership-manage");
  button.disabled = true;
  button.textContent = "Opening...";
  const response = await fetch("/api/billing/portal", {
    method: "POST",
    credentials: "same-origin",
    headers: { "x-kvnp-csrf": state.csrf },
  });
  const data = await response.json();
  if (response.ok && data.url) {
    location.href = data.url;
    return;
  }
  button.disabled = false;
  button.textContent = "Manage billing";
  document.querySelector("#membership-detail").textContent = data.error || data.detail || "Billing management could not open.";
}

function projectTemplate(project) {
  const status = project.entitled ? "paid" : project.status;
  const action = project.entitled && project.artifactAvailable
    ? `<a class="primary-button" href="/api/projects/${encodeURIComponent(project.id)}/artifact">Download saved JPEG</a>`
    : `<a class="primary-button" href="/app?project=${encodeURIComponent(project.id)}">Continue application</a>`;
  return `<article class="project-row"><div><span class="eyebrow">${escapeHtml(project.countryCode || "Studio")}</span><h3>${escapeHtml(project.applicantName || "Unnamed applicant")}</h3><p>${escapeHtml(project.programmeLabel || project.profileId)}</p></div><span class="status-pill ${status}">${escapeHtml(status)}</span><footer><span class="muted">Updated ${date(project.updatedAt)}</span>${action}</footer></article>`;
}

document.querySelector("#sign-out").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/app";
});

document.querySelector("#membership-manage").addEventListener("click", openBillingPortal);

document.querySelector("#enquiry-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.querySelector("#enquiry-status");
  status.textContent = "Sending...";
  const response = await fetch("/api/enquiries", {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name: state.user.name, email: state.user.email, subject: document.querySelector("#enquiry-subject").value, message: document.querySelector("#enquiry-message").value }),
  });
  const data = await response.json();
  if (!response.ok) { status.textContent = data.error || "Could not send the enquiry."; return; }
  status.textContent = `Received. Reference ${data.reference}.`;
  event.target.reset();
});

loadAccount().catch((error) => { document.querySelector("#project-list").innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`; });
