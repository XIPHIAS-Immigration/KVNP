/* PassportLens — landing page behaviour.
   Motion: anime.js v4 (window.anime) when present and the visitor allows motion;
   otherwise every element is simply visible. Also used by the server-rendered
   requirement / audience pages, so every block checks its elements exist. */
(function () {
  "use strict";

  var docEl = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var A = window.anime;

  /* ---------- nav / mobile menu ---------- */
  var toggle = document.getElementById("navToggle");
  var links = document.getElementById("navLinks");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    links.addEventListener("click", function (e) {
      if (e.target.tagName === "A") { links.classList.remove("open"); toggle.setAttribute("aria-expanded", "false"); }
    });
  }

  /* ---------- before / after slider ---------- */
  (function () {
    var ba = document.getElementById("ba");
    var after = document.getElementById("baAfter");
    var handle = document.getElementById("baHandle");
    if (!ba || !after || !handle) return;
    var dragging = false;
    function setPos(clientX) {
      var r = ba.getBoundingClientRect();
      var p = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
      var pct = (p * 100).toFixed(1);
      after.style.clipPath = "inset(0 0 0 " + pct + "%)";
      handle.style.left = pct + "%";
    }
    handle.addEventListener("pointerdown", function (e) { dragging = true; try { handle.setPointerCapture(e.pointerId); } catch (err) {} e.preventDefault(); });
    window.addEventListener("pointermove", function (e) { if (dragging) setPos(e.clientX); });
    window.addEventListener("pointerup", function () { dragging = false; });
    ba.addEventListener("pointerdown", function (e) { if (e.target !== handle && !handle.contains(e.target)) setPos(e.clientX); });
  })();

  /* ---------- prices: currency + billing period ---------- */
  var PRICES = {
    cad: { single: "CAD 9.99", monthly: "CAD 100", yearly: "CAD 999" },
    usd: { single: "USD 7.99", monthly: "USD 75", yearly: "USD 749" },
  };
  var period = "monthly";
  var currency = "cad";
  function detectCurrency() {
    var q = new URLSearchParams(location.search).get("cur");
    if (q === "usd" || q === "cad") return q;
    try { var saved = localStorage.getItem("pl-currency"); if (saved === "usd" || saved === "cad") return saved; } catch (e) {}
    if (docEl.getAttribute("data-region") === "us") return "usd";
    var lang = (navigator.language || "").toLowerCase();
    if (lang === "en-us") return "usd";
    try { var tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; if (/^America\/(New_York|Chicago|Denver|Los_Angeles|Phoenix|Anchorage|Detroit|Boise|Indiana|Kentucky|Juneau|Honolulu)/.test(tz)) return "usd"; } catch (e) {}
    return "cad";
  }
  function applyPrices() {
    var p = PRICES[currency];
    document.querySelectorAll("[data-price=single]").forEach(function (el) { el.textContent = p.single; });
    document.querySelectorAll("[data-price=silver]").forEach(function (el) { el.textContent = period === "yearly" ? p.yearly : p.monthly; });
    document.querySelectorAll("[data-period-monthly]").forEach(function (el) { el.textContent = el.getAttribute(period === "yearly" ? "data-period-yearly" : "data-period-monthly"); });
    document.querySelectorAll("[data-plan-link]").forEach(function (el) {
      var plan = el.getAttribute("data-plan-link");
      el.href = "/pricing?plan=" + plan + "&cur=" + currency + (plan === "silver" && period === "yearly" ? "&period=yearly" : "");
    });
    document.querySelectorAll("[data-bill]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-bill") === period); });
    document.querySelectorAll("[data-cur]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-cur") === currency); });
  }
  window.PL_PRICES = PRICES;
  currency = detectCurrency();
  document.querySelectorAll("[data-bill]").forEach(function (b) { b.addEventListener("click", function () { period = b.getAttribute("data-bill"); applyPrices(); }); });
  document.querySelectorAll("[data-cur]").forEach(function (b) { b.addEventListener("click", function () { currency = b.getAttribute("data-cur"); try { localStorage.setItem("pl-currency", currency); } catch (e) {} applyPrices(); }); });
  applyPrices();

  /* ---------- "Talk to us" buttons preselect the tier ---------- */
  (function () {
    var select = document.getElementById("contact-tier");
    if (!select) return;
    document.querySelectorAll("[data-tier]").forEach(function (el) {
      el.addEventListener("click", function () {
        var tier = el.getAttribute("data-tier");
        if ([].some.call(select.options, function (o) { return o.value === tier; })) select.value = tier;
      });
    });
  })();

  /* ---------- task box: programme search (suggestions from the rules) ---------- */
  (function () {
    var input = document.getElementById("task-search");
    var list = document.getElementById("task-list");
    var form = input && input.closest("form");
    if (!input || !list || !form) return;
    var programmes = [];
    fetch("/api/profiles").then(function (r) { return r.json(); }).then(function (d) {
      programmes = (d.profiles || []).map(function (p) { return { id: p.id, label: (p.countryName || p.country) + " — " + p.programme }; });
      list.innerHTML = programmes.map(function (p) { return '<option value="' + p.label.replace(/"/g, "&quot;") + '"></option>'; }).join("");
    }).catch(function () {});
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim().toLowerCase();
      var hit = programmes.find(function (p) { return p.label.toLowerCase() === q; }) || programmes.find(function (p) { return q && p.label.toLowerCase().indexOf(q) !== -1; });
      location.href = hit ? "/app?programme=" + encodeURIComponent(hit.id) : "/app" + (q ? "?q=" + encodeURIComponent(q) : "");
    });
  })();

  /* ---------- reveal everything (no motion path) ---------- */
  function revealEverything() {
    docEl.classList.remove("anim");
    document.querySelectorAll("[data-count]").forEach(function (el) { el.textContent = el.getAttribute("data-count") + (el.getAttribute("data-suffix") || ""); });
  }

  if (reduce || !A || !A.animate) { revealEverything(); return; }

  /* ---------- motion (anime.js v4) ---------- */
  var animate = A.animate, stagger = A.stagger, createTimeline = A.createTimeline, svg = A.svg, utils = A.utils;
  var failsafe = setTimeout(revealEverything, 5000);
  try {
    docEl.classList.add("motion-ready");

    /* counters */
    function countUp(el) {
      var end = parseFloat(el.getAttribute("data-count")) || 0;
      var suffix = el.getAttribute("data-suffix") || "";
      var obj = { v: 0 };
      animate(obj, { v: end, duration: 1400, ease: "outExpo", onUpdate: function () { el.textContent = Math.round(obj.v) + suffix; }, onComplete: function () { el.textContent = end + suffix; } });
    }

    /* hero timeline */
    var hero = document.getElementById("hero");
    if (hero) {
      var tl = createTimeline({ defaults: { ease: "outExpo", duration: 900 } });
      tl.add("[data-hero=kicker]", { opacity: [0, 1], y: [18, 0], duration: 500 }, 0)
        .add(".hero .w", { opacity: [0, 1], y: [38, 0], rotate: [2, 0], duration: 800, delay: stagger(70) }, 120);
      var rule = svg.createDrawable(".hero-rule .draw");
      tl.add(rule, { draw: ["0 0", "0 1"], duration: 700, ease: "inOutQuad" }, 520)
        .add("[data-hero=sub]", { opacity: [0, 1], y: [18, 0], duration: 600 }, 640)
        .add("[data-hero=cta]", { opacity: [0, 1], y: [18, 0], duration: 600 }, 760)
        .add("[data-hero=stats]", { opacity: [0, 1], y: [18, 0], duration: 600, onBegin: function () { document.querySelectorAll("[data-hero=stats] [data-count]").forEach(countUp); } }, 880)
        .add("[data-hero=task]", { opacity: [0, 1], y: [18, 0], duration: 700 }, 1000);

      /* the frame assembles: card → photo → guides draw → corners → labels → stamp */
      var guides = svg.createDrawable(".frame-guides .draw");
      tl.add("[data-f=card]", { opacity: [0, 1], y: [30, 0], scale: [0.96, 1], duration: 800 }, 300)
        .add("[data-f=photo]", { opacity: [0, 1], duration: 700 }, 700)
        .add(guides, { draw: ["0 0", "0 1"], duration: 900, ease: "inOutSine", delay: stagger(120) }, 900)
        .add("[data-f=corner]", { opacity: [0, 1], scale: [0.4, 1], duration: 500, ease: "outBack(2)", delay: stagger(80) }, 1200)
        .add("[data-f=label]", { opacity: [0, 1], x: [-12, 0], duration: 500, delay: stagger(160) }, 1700)
        .add("[data-f=stamp]", { opacity: [0, 1], scale: [1.6, 1], rotate: [-14, -6], duration: 650, ease: "outBack(3)" }, 2150)
        .add("[data-f=meta]", { opacity: [0, 1], duration: 500 }, 2300);
      tl.then(function () {
        /* idle float so the hero never looks frozen */
        animate(".frame-card", { y: [0, -8, 0], duration: 5200, ease: "inOutSine", loop: true });
        animate(".glow.g1", { scale: [1, 1.12, 1], duration: 7000, ease: "inOutSine", loop: true });
      });
    }

    /* scroll reveals */
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        io.unobserve(el);
        var children = [].slice.call(el.children);
        if (!children.length) children = [el];
        animate(children, { opacity: [0, 1], y: [22, 0], duration: 750, ease: "outExpo", delay: stagger(90) });
        el.querySelectorAll("[data-count]").forEach(countUp);
        var drawables = el.querySelectorAll(".step-ico .draw");
        if (drawables.length) animate(svg.createDrawable(drawables), { draw: ["0 0", "0 1"], duration: 1100, ease: "inOutSine", delay: stagger(140) });
      });
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.12 });
    document.querySelectorAll("[data-reveal]").forEach(function (el) { io.observe(el); });

    clearTimeout(failsafe);
  } catch (err) {
    clearTimeout(failsafe);
    if (window.console) console.warn("motion disabled", err);
    revealEverything();
  }
})();

/* ---------- signed-in state, analytics event, enquiry form ---------- */
(function () {
  "use strict";
  var memberEntries = document.querySelectorAll("[data-member-entry]");
  var signins = document.querySelectorAll("[data-signin]");
  fetch("/api/commerce/config", { credentials: "same-origin" })
    .then(function (response) { return response.json(); })
    .then(function (data) {
      if (!data.signedIn) return;
      signins.forEach(function (el) { el.href = "/app"; el.textContent = "My studio"; });
      if (!data.plan || !data.plan.unlimited) return;
      memberEntries.forEach(function (entry) { entry.href = "/app"; entry.firstChild.textContent = "Open studio "; });
    })
    .catch(function () {});

  try {
    var anonymousId = localStorage.getItem("kvnp-anonymous-id") || crypto.randomUUID();
    localStorage.setItem("kvnp-anonymous-id", anonymousId);
    var referrerHost = "direct";
    try { referrerHost = document.referrer ? new URL(document.referrer).hostname : "direct"; } catch (error) {}
    fetch("/api/events", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "landing_view", anonymousId: anonymousId, metadata: { path: location.pathname, referrerHost: referrerHost, device: matchMedia("(max-width: 680px)").matches ? "mobile" : "desktop" } }),
    }).catch(function () {});
  } catch (error) {}

  document.querySelectorAll("[data-enquiry-form]").forEach(function (form) {
    var status = form.querySelector("[data-enquiry-status]");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (!form.checkValidity()) { form.reportValidity(); return; }
      status.className = "form-msg";
      status.textContent = "Sending…";
      var button = form.querySelector("button[type='submit']");
      button.disabled = true;
      var v = new FormData(form);
      var tier = String(v.get("tier") || "Question");
      var business = String(v.get("business") || "").trim();
      var phone = String(v.get("phone") || "").trim();
      var subject = "[" + tier + "] " + (business || String(v.get("name") || "").trim());
      try {
        var response = await fetch("/api/enquiries", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ name: v.get("name"), email: v.get("email"), business: business, phone: phone, tier: tier, subject: subject.slice(0, 200), message: String(v.get("message") || "").trim().slice(0, 5000) }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "Could not send the message.");
        form.reset();
        status.className = "form-msg ok";
        status.textContent = "Thanks — received (ref " + data.reference + "). We'll reply by email.";
      } catch (error) {
        status.className = "form-msg bad";
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  });
})();
