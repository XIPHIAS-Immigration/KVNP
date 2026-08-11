const elements = {
  form: document.querySelector("#activation-form"),
  title: document.querySelector("#payment-title"),
  copy: document.querySelector("#payment-copy"),
  formTitle: document.querySelector("#form-title"),
  accountEmail: document.querySelector("#account-email"),
  nameField: document.querySelector("#name-field"),
  name: document.querySelector("#name"),
  password: document.querySelector("#password"),
  confirmField: document.querySelector("#confirm-field"),
  passwordConfirm: document.querySelector("#password-confirm"),
  button: document.querySelector("#activate-button"),
  status: document.querySelector("#activation-status"),
  error: document.querySelector("#activation-error"),
  errorCopy: document.querySelector("#activation-error-copy"),
  note: document.querySelector("#password-note"),
};

const sessionId = new URLSearchParams(location.search).get("session_id") || "";
let activation = null;

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function showError(message) {
  elements.form.hidden = true;
  elements.error.hidden = false;
  elements.title.textContent = "Verification needs attention";
  elements.copy.textContent = "Your card is not charged again by retrying activation.";
  elements.errorCopy.textContent = message;
}

function showForm(data) {
  activation = data;
  elements.error.hidden = true;
  elements.form.hidden = false;
  elements.title.textContent = "Payment confirmed";
  elements.copy.textContent = `Membership purchased with ${data.email}.`;
  elements.accountEmail.textContent = data.existingAccount
    ? `A KVNP account already uses ${data.email}. Enter its password to link this purchase.`
    : `Your login will use the payment email ${data.email}.`;
  elements.nameField.hidden = data.existingAccount;
  elements.confirmField.hidden = data.existingAccount;
  elements.name.required = !data.existingAccount;
  elements.passwordConfirm.required = !data.existingAccount;
  elements.password.autocomplete = data.existingAccount ? "current-password" : "new-password";
  elements.formTitle.textContent = data.existingAccount ? "Confirm your account" : "Create your account";
  elements.button.textContent = data.existingAccount ? "Link purchase and sign in" : "Activate and enter Studio";
  elements.note.textContent = data.existingAccount
    ? "Use your existing KVNP password. The purchase cannot be linked by email alone."
    : "Use at least 8 characters. KVNP stores a one-way password hash, never your readable password.";
}

async function verifyPayment() {
  if (!sessionId.startsWith("cs_")) {
    showError("The Stripe checkout reference is missing. Return to Membership and reopen checkout.");
    return;
  }
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const response = await fetch(`/api/billing/activation?session_id=${encodeURIComponent(sessionId)}`, {
      credentials: "same-origin",
    });
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || data.detail || "Payment verification failed.");
      return;
    }
    if (data.claimed) {
      location.replace("/account");
      return;
    }
    if (data.paid) {
      showForm(data);
      return;
    }
    elements.copy.textContent = "Stripe is finalizing the subscription. Checking again...";
    await wait(1800);
  }
  showError("Stripe has not confirmed the subscription yet. Wait a minute, then refresh this page.");
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!activation) return;
  if (!activation.existingAccount && elements.password.value !== elements.passwordConfirm.value) {
    elements.status.textContent = "The passwords do not match.";
    elements.passwordConfirm.focus();
    return;
  }
  elements.button.disabled = true;
  elements.button.textContent = "Activating...";
  elements.status.textContent = "";
  const response = await fetch("/api/billing/activate", {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ sessionId, name: elements.name.value, password: elements.password.value }),
  });
  const data = await response.json();
  if (!response.ok) {
    elements.button.disabled = false;
    elements.button.textContent = activation.existingAccount ? "Link purchase and sign in" : "Activate and enter Studio";
    elements.status.textContent = data.error || data.detail || "Account activation failed.";
    return;
  }
  elements.status.textContent = "Account ready. Opening your workspace...";
  location.replace("/account?activated=1");
});

verifyPayment().catch(() => showError("Payment verification is temporarily unavailable. Refresh this page to retry."));
