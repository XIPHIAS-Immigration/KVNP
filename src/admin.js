const state = { csrf: null, data: null };
const money = (minor, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency }).format((minor || 0) / 100);
const date = (value) => value ? new Date(value * 1000).toLocaleString() : "-";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const eventLabels = {
  landing_view: "Landing visit", studio_opened: "Studio opened", programme_selected: "Programme selected",
  photo_added: "Photo added", processing_completed: "Processing completed", review_opened: "Review opened",
  checkout_started: "Checkout started", payment_completed: "Payment completed", download_completed: "Download completed",
  enquiry_created: "Enquiry created",
};

async function loadAdmin() {
  const auth = await fetch("/api/auth/me", { credentials: "same-origin" }).then((response) => response.json());
  if (!auth.user || auth.user.role !== "admin") {
    document.querySelector("main").innerHTML = '<p class="admin-error">Administrator access is required.</p>';
    return;
  }
  state.csrf = auth.csrfToken;
  const response = await fetch("/api/admin/dashboard", { credentials: "same-origin" });
  if (!response.ok) throw new Error("Could not load operations data.");
  state.data = await response.json();
  render();
}

function render() {
  const { metrics, traffic = {}, conversion30d = [], destinations = [], recentActivity = [], customers = [], orders, enquiries, commerce } = state.data;
  const cards = [
    ["Unique visitors", traffic.uniqueVisitors ?? 0], ["Active / 7 days", traffic.active7d ?? 0],
    ["Landing visits", traffic.landingViews ?? 0], ["Studio sessions", traffic.studioSessions ?? 0],
    ["Customers", metrics.users], ["Applications", metrics.projects], ["Downloads", metrics.downloads],
    ["Revenue", money(metrics.revenueMinor)], ["Open support", metrics.openEnquiries],
  ];
  document.querySelector("#admin-metrics").innerHTML = cards.map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join("");
  renderTraffic(traffic.daily || []);
  renderConversion(conversion30d);
  renderDestinations(destinations);
  renderRecentActivity(recentActivity);
  document.querySelector("#commerce-status").innerHTML = `<dt>Provider mode</dt><dd>${escapeHtml(commerce.mode)}</dd><dt>Checkout</dt><dd>${commerce.enabled ? "Enabled" : "Pending credentials"}</dd><dt>Download gate</dt><dd>${commerce.enforced ? "Active" : "Preview mode"}</dd><dt>Application pack</dt><dd>${money(commerce.product.amountMinor, commerce.product.currency)}</dd>`;
  document.querySelector("#admin-orders").innerHTML = orders.map((order) => `<tr><td>${escapeHtml(order.reference)}</td><td>#${order.userId}</td><td>${money(order.amountMinor, order.currency)}</td><td>${escapeHtml(order.provider)}</td><td><span class="status-pill ${order.status}">${escapeHtml(order.status)}</span></td><td>${date(order.createdAt)}</td></tr>`).join("") || '<tr><td colspan="6">No orders yet.</td></tr>';
  document.querySelector("#enquiry-count").textContent = `${enquiries.length} recent`;
  document.querySelector("#admin-enquiries").innerHTML = enquiries.map(enquiryTemplate).join("") || '<p class="empty-state">No enquiries yet.</p>';
  document.querySelector("#customer-count").textContent = `${customers.length} account${customers.length === 1 ? "" : "s"}`;
  document.querySelector("#admin-customers").innerHTML = customers.map((item) => `<tr><td><strong>${escapeHtml(item.name || "Not provided")}</strong><small class="customer-state">${escapeHtml(item.status)}</small></td><td><a class="customer-email" href="mailto:${escapeHtml(item.email)}">${escapeHtml(item.email)}</a></td><td><span class="account-role ${item.role === "admin" ? "admin" : ""}">${escapeHtml(item.role)}</span></td><td>${item.projects}</td><td>${item.downloads}</td><td>${date(item.createdAt)}</td><td>${item.lastLoginAt ? date(item.lastLoginAt) : "Never"}</td></tr>`).join("") || '<tr><td colspan="7" class="empty-state">No customer accounts yet.</td></tr>';
}

function renderTraffic(days) {
  const target = document.querySelector("#traffic-trend");
  if (!days.length) { target.innerHTML = '<p class="muted">Traffic appears after the first site visit.</p>'; return; }
  const maximum = Math.max(1, ...days.flatMap((item) => [item.visitors, item.studioSessions, item.processed]));
  target.innerHTML = days.map((item) => {
    const label = new Date(`${item.date}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
    const title = `${label}: ${item.visitors} visitors, ${item.studioSessions} studio sessions, ${item.processed} processed`;
    return `<div class="traffic-day" title="${escapeHtml(title)}"><div class="traffic-bars"><i class="visitor-bar" style="height:${(item.visitors / maximum) * 100}%"></i><i class="studio-bar" style="height:${(item.studioSessions / maximum) * 100}%"></i><i class="processed-bar" style="height:${(item.processed / maximum) * 100}%"></i></div><span>${escapeHtml(label)}</span></div>`;
  }).join("");
}

function renderConversion(stages) {
  const target = document.querySelector("#conversion-list");
  const maximum = Math.max(1, ...stages.map((item) => item.count));
  target.innerHTML = stages.map((item, index) => `<div class="funnel-row"><span>${escapeHtml(eventLabels[item.name] || item.name.replaceAll("_", " "))}</span><div class="funnel-track"><span style="width:${item.count ? Math.max(2, (item.count / maximum) * 100) : 0}%"></span></div><strong>${item.count}<small>${index ? `${item.fromPreviousPercent}%` : "entry"}</small></strong></div>`).join("") || '<p class="muted">Conversion events appear as customers use the studio.</p>';
}

function renderDestinations(items) {
  const target = document.querySelector("#destination-list");
  const maximum = Math.max(1, ...items.map((item) => item.selections));
  target.innerHTML = items.map((item) => `<div class="destination-row"><strong>${escapeHtml(item.country)}</strong><div><span style="width:${(item.selections / maximum) * 100}%"></span></div><em>${item.selections}</em></div>`).join("") || '<p class="muted">Destination demand appears after programme selections.</p>';
}

function renderRecentActivity(items) {
  document.querySelector("#recent-activity").innerHTML = items.map((item) => `<article><span class="activity-mark"></span><div><strong>${escapeHtml(eventLabels[item.name] || item.name.replaceAll("_", " "))}</strong><p>${escapeHtml(item.actor)}${item.detail ? ` / ${escapeHtml(item.detail)}` : ""}</p></div><time>${date(item.createdAt)}</time></article>`).join("") || '<p class="muted">No activity in the last 30 days.</p>';
}

function enquiryTemplate(item) {
  const statuses = [["new", "New"], ["in_progress", "In progress"], ["waiting", "Waiting"], ["resolved", "Resolved"]];
  const options = statuses.map(([value, label]) => `<option value="${value}" ${item.status === value ? "selected" : ""}>${label}</option>`).join("");
  return `<article class="enquiry-row" data-enquiry-id="${item.id}"><div><span class="eyebrow">${escapeHtml(item.status)}</span><h3>${escapeHtml(item.subject)}</h3><div class="enquiry-meta">${escapeHtml(item.name)} / ${escapeHtml(item.email)}<br>${date(item.createdAt)}</div></div><p>${escapeHtml(item.message)}</p><div class="enquiry-actions"><select aria-label="Enquiry status">${options}</select><textarea aria-label="Private admin note" placeholder="Private note">${escapeHtml(item.adminNote)}</textarea><button class="primary-button" type="button">Save case</button></div></article>`;
}

document.querySelector("#admin-enquiries").addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const row = button.closest("[data-enquiry-id]");
  button.disabled = true;
  const response = await fetch(`/api/admin/enquiries/${row.dataset.enquiryId}`, { method: "PATCH", credentials: "same-origin", headers: { "content-type": "application/json", "x-kvnp-csrf": state.csrf }, body: JSON.stringify({ status: row.querySelector("select").value, adminNote: row.querySelector("textarea").value }) });
  button.textContent = response.ok ? "Saved" : "Try again";
  button.disabled = false;
});

document.querySelector("#refresh-admin").addEventListener("click", () => loadAdmin().catch((error) => alert(error.message)));
loadAdmin().catch((error) => { document.querySelector("main").innerHTML = `<p class="admin-error">${escapeHtml(error.message)}</p>`; });
