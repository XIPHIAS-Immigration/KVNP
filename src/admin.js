const state = { csrf: null, data: null };
const money = (minor, currency = "INR") => new Intl.NumberFormat("en-IN", { style: "currency", currency }).format((minor || 0) / 100);
const date = (value) => value ? new Date(value * 1000).toLocaleString() : "-";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);

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
  const { metrics, funnel, orders, enquiries, commerce } = state.data;
  const cards = [
    ["Customers", metrics.users], ["Applications", metrics.projects], ["Paid orders", metrics.paidOrders],
    ["Pending", metrics.pendingOrders], ["Revenue", money(metrics.revenueMinor)], ["Downloads", metrics.downloads], ["Open support", metrics.openEnquiries],
  ];
  document.querySelector("#admin-metrics").innerHTML = cards.map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join("");
  const max = Math.max(1, ...Object.values(funnel));
  document.querySelector("#funnel-list").innerHTML = Object.entries(funnel).sort((a, b) => b[1] - a[1]).map(([name, value]) => `<div class="funnel-row"><span>${escapeHtml(name.replaceAll("_", " "))}</span><div class="funnel-track"><span style="width:${Math.max(2, (value / max) * 100)}%"></span></div><strong>${value}</strong></div>`).join("") || '<p class="muted">Events appear as customers use the new workflow.</p>';
  document.querySelector("#commerce-status").innerHTML = `<dt>Provider mode</dt><dd>${escapeHtml(commerce.mode)}</dd><dt>Checkout</dt><dd>${commerce.enabled ? "Enabled" : "Pending credentials"}</dd><dt>Download gate</dt><dd>${commerce.enforced ? "Active" : "Preview mode"}</dd><dt>Application pack</dt><dd>${money(commerce.product.amountMinor, commerce.product.currency)}</dd>`;
  document.querySelector("#admin-orders").innerHTML = orders.map((order) => `<tr><td>${escapeHtml(order.reference)}</td><td>#${order.userId}</td><td>${money(order.amountMinor, order.currency)}</td><td>${escapeHtml(order.provider)}</td><td><span class="status-pill ${order.status}">${escapeHtml(order.status)}</span></td><td>${date(order.createdAt)}</td></tr>`).join("") || '<tr><td colspan="6">No orders yet.</td></tr>';
  document.querySelector("#enquiry-count").textContent = `${enquiries.length} recent`;
  document.querySelector("#admin-enquiries").innerHTML = enquiries.map(enquiryTemplate).join("") || '<p class="empty-state">No enquiries yet.</p>';
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
