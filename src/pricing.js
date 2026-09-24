/* PassportLens — pricing page: starts Stripe Checkout for Silver or a single photo. */
(function () {
  "use strict";
  var notice = document.getElementById("pricing-notice");
  var params = new URLSearchParams(location.search);
  var period = params.get("period") === "yearly" ? "yearly" : "monthly";
  var currency = "cad";
  var config = null;
  var me = null;
  function currentCurrency() {
    var on = document.querySelector("[data-cur].on");
    return on ? on.getAttribute("data-cur") : "cad";
  }

  function show(message, kind) {
    notice.className = "notice pay-note " + (kind || "");
    notice.innerHTML = message;
    notice.hidden = false;
  }

  document.querySelectorAll("[data-bill]").forEach(function (button) {
    button.addEventListener("click", function () { period = button.getAttribute("data-bill"); });
  });
  if (period === "yearly") {
    var yearly = document.querySelector("[data-bill=yearly]");
    if (yearly) yearly.click();
  }
  if (params.get("plan")) {
    var card = document.querySelector('[data-plan="' + params.get("plan") + '"]');
    if (card) { card.classList.add("featured"); card.scrollIntoView({ block: "center" }); }
  }
  if (params.get("checkout") === "cancelled") show("Checkout was cancelled — nothing was charged. Pick a plan whenever you're ready.", "warn");

  Promise.all([
    fetch("/api/commerce/config", { credentials: "same-origin" }).then(function (r) { return r.json(); }),
    fetch("/api/auth/me", { credentials: "same-origin" }).then(function (r) { return r.json(); }),
  ]).then(function (results) {
    config = results[0];
    me = results[1];
    // prices come from the server (.env) so the page never drifts from Stripe
    if (config.prices && window.PL_PRICES) {
      var fmt = function (cur, minor) { return cur + " " + (minor % 100 === 0 ? String(minor / 100) : (minor / 100).toFixed(2)); };
      ["CAD", "USD"].forEach(function (cur) {
        var p = config.prices[cur]; if (!p) return;
        window.PL_PRICES[cur.toLowerCase()] = { single: fmt(cur, p.single), monthly: fmt(cur, p.monthly), yearly: fmt(cur, p.yearly) };
      });
      var onBtn = document.querySelector("[data-bill].on"); if (onBtn) onBtn.click();
    }
    if (config.currencies && config.currencies.indexOf("USD") === -1) {
      var usdBtn = document.querySelector("[data-cur=usd]"); if (usdBtn) usdBtn.closest(".cur-toggle").hidden = true;
    }
    var plan = me && me.plan;
    if (plan && plan.unlimited) {
      show('Your plan is active. <a href="/app">Open the studio</a> or manage it from <a href="/account">your account</a>.', "ok");
      document.querySelectorAll("[data-buy=silver]").forEach(function (b) { b.disabled = true; b.textContent = "Already active"; });
    }
    if (!config.enabled) {
      show('Online payment is being set up. To get started today, <a href="/#contact">send us a message</a> and we will set your account up by hand.', "warn");
      document.querySelectorAll("[data-buy]").forEach(function (b) { b.disabled = true; });
    }
  }).catch(function () {});

  document.querySelectorAll("[data-buy]").forEach(function (button) {
    button.addEventListener("click", async function () {
      var product = button.getAttribute("data-buy");
      button.disabled = true;
      var label = button.textContent;
      button.textContent = "Opening secure checkout…";
      try {
        var headers = { "content-type": "application/json" };
        if (me && me.csrfToken) headers["x-kvnp-csrf"] = me.csrfToken;
        var response = await fetch("/api/billing/checkout", {
          method: "POST",
          credentials: "same-origin",
          headers: headers,
          body: JSON.stringify({ product: product, period: document.querySelector("[data-bill].on") ? document.querySelector("[data-bill].on").getAttribute("data-bill") : period, currency: currentCurrency() }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok || !data.checkout || !data.checkout.url) throw new Error(data.error || data.detail || "Checkout is temporarily unavailable.");
        location.href = data.checkout.url;
      } catch (error) {
        show(error.message, "bad");
        button.disabled = false;
        button.textContent = label;
      }
    });
  });
})();
