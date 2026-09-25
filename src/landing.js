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

  /* ---------- before / after slider (landing demo + SEO pages) ---------- */
  var ba = document.getElementById("ba");
  var baAfter = document.getElementById("baAfter");
  var baHandle = document.getElementById("baHandle");
  var baSetPos = null;
  (function () {
    if (!ba || !baAfter || !baHandle) return;
    var dragging = false;
    baSetPos = function (p) {
      var pct = (Math.max(0, Math.min(1, p)) * 100).toFixed(1);
      baAfter.style.clipPath = "inset(0 0 0 " + pct + "%)";
      baHandle.style.left = pct + "%";
    };
    function fromEvent(clientX) { var r = ba.getBoundingClientRect(); baSetPos((clientX - r.left) / r.width); }
    baHandle.addEventListener("pointerdown", function (e) { dragging = true; try { baHandle.setPointerCapture(e.pointerId); } catch (err) {} e.preventDefault(); });
    window.addEventListener("pointermove", function (e) { if (dragging) fromEvent(e.clientX); });
    window.addEventListener("pointerup", function () { dragging = false; });
    ba.addEventListener("pointerdown", function (e) { if (e.target !== baHandle && !baHandle.contains(e.target)) { fromEvent(e.clientX); dragging = true; } });
  })();

  /* demo pickers: sample photo × country → pre-rendered results */
  (function () {
    var before = document.getElementById("baBefore");
    if (!ba || !before || !baAfter) return;
    var RULES = { ca: ["50 / 70", "Canada passport rules"], us: ["1 / 1", "US passport rules"], "in": ["1 / 1", "India OCI card rules"] };
    var state = { photo: "street", country: docEl.getAttribute("data-region") === "us" ? "us" : "ca" };
    var ruleEl = document.querySelector("[data-demo-rule]");
    function show() {
      var base = "/assets/landing/demo-" + state.photo + "-" + state.country + "-";
      [before, baAfter].forEach(function (img) { img.classList.add("swap"); });
      var pending = 2;
      function done() { if (--pending === 0) [before, baAfter].forEach(function (img) { img.classList.remove("swap"); }); }
      setTimeout(function () {
        before.onload = done; baAfter.onload = done;
        before.src = base + "before.jpg"; baAfter.src = base + "after.jpg";
      }, 180);
      ba.style.setProperty("--ratio", RULES[state.country][0]);
      if (ruleEl) ruleEl.textContent = RULES[state.country][1];
      document.querySelectorAll("[data-demo-photo]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-demo-photo") === state.photo); });
      document.querySelectorAll("[data-demo-country]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-demo-country") === state.country); });
    }
    document.querySelectorAll("[data-demo-photo]").forEach(function (b) { b.addEventListener("click", function () { state.photo = b.getAttribute("data-demo-photo"); show(); }); });
    document.querySelectorAll("[data-demo-country]").forEach(function (b) { b.addEventListener("click", function () { state.country = b.getAttribute("data-demo-country"); show(); }); });
    if (state.country !== "ca") show();
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
  function bump() { document.querySelectorAll(".plan-price b").forEach(function (el) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); setTimeout(function () { el.classList.remove("bump"); }, 350); }); }
  document.querySelectorAll("[data-bill]").forEach(function (b) { b.addEventListener("click", function () { period = b.getAttribute("data-bill"); applyPrices(); bump(); }); });
  document.querySelectorAll("[data-cur]").forEach(function (b) { b.addEventListener("click", function () { currency = b.getAttribute("data-cur"); try { localStorage.setItem("pl-currency", currency); } catch (e) {} applyPrices(); bump(); }); });
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

  /* ---------- story: captions, rail, HUD, posters (works with or without 3D) ---------- */
  var storyEl = document.getElementById("story");
  var caps = [].slice.call(document.querySelectorAll(".cap"));
  var rail = document.querySelector(".story-rail");
  var railItems = [].slice.call(document.querySelectorAll("[data-rail]"));
  var posters = [].slice.call(document.querySelectorAll("[data-poster]"));
  var hudIndex = document.querySelector("[data-hud=index]");
  var hudCaption = document.querySelector("[data-hud=caption]");
  var hudTilt = document.querySelector("[data-hud=tilt]");
  var hudSpec = document.querySelector("[data-hud=spec]");
  var capFlags = [].slice.call(document.querySelectorAll(".cap-flags span:not([hidden]) img"));
  var CAPTIONS = ["Capturing portrait…", "Mapping 478 face landmarks · levelling tilt", "Dissolving background · balancing light", "Loading the programme's rules", "Photo OK · ready to submit or print"];
  var SPECS = docEl.getAttribute("data-region") === "us"
    ? ["Canada · 50 × 70 mm", "India OCI · 51 × 51 mm", "United Kingdom · 35 × 45 mm", "United States · 2 × 2 in"]
    : ["United States · 2 × 2 in", "India OCI · 51 × 51 mm", "United Kingdom · 35 × 45 mm", "Canada · 50 × 70 mm"];
  var chapter = -1;
  function clamp01(v) { return Math.max(0, Math.min(1, v)); }
  function seg(p, a, b) { return clamp01((p - a) / (b - a)); }
  function smooth(t) { return t * t * (3 - 2 * t); }
  function storyProgress() {
    if (!storyEl) return 0;
    var r = storyEl.getBoundingClientRect();
    return clamp01(-r.top / Math.max(1, r.height - innerHeight));
  }
  function setChapter(c) {
    if (c === chapter) return;
    var prev = chapter;
    chapter = c;
    caps.forEach(function (el, i) {
      el.classList.toggle("is-on", i === c);
      el.classList.toggle("is-off-up", i < c);
    });
    railItems.forEach(function (el, i) { el.classList.toggle("on", i <= c); });
    posters.forEach(function (el, i) { el.classList.toggle("on", i === c); });
    if (hudIndex) hudIndex.textContent = "0" + c;
    if (hudCaption) hudCaption.textContent = CAPTIONS[c] || "";
    if (prev !== -1 && !reduce && A && A.animate) {
      var on = caps[c];
      if (on) A.animate(on.children, { opacity: [0, 1], y: [26, 0], duration: 700, ease: "outExpo", delay: A.stagger(70) });
    }
  }
  function onStoryScroll() {
    if (!storyEl) return;
    var p = storyProgress();
    var c = p < 0.09 ? 0 : p < 0.32 ? 1 : p < 0.52 ? 2 : p < 0.74 ? 3 : 4;
    setChapter(c);
    if (rail) rail.style.setProperty("--p", p.toFixed(4));
    if (hudTilt) hudTilt.textContent = Math.round(8 * (1 - smooth(seg(seg(p, 0.1, 0.32), 0.35, 0.75)))) + "°";
    var k = Math.round(Math.max(0, Math.min(3, seg(seg(p, 0.52, 0.74), 0.1, 0.92) * 3)));
    if (hudSpec) hudSpec.textContent = SPECS[k];
    capFlags.forEach(function (img, i) { img.classList.toggle("on", i === k); });
  }
  if (storyEl) { addEventListener("scroll", onStoryScroll, { passive: true }); onStoryScroll(); }
  /* no WebGL (or the 3D module failed): show pre-rendered frames of the story */
  function loadPosters() {
    docEl.dataset.tier = "none";
    posters.forEach(function (img) { if (!img.getAttribute("src") && img.getAttribute("data-src")) img.src = img.getAttribute("data-src"); });
  }
  addEventListener("pl:fallback", loadPosters);
  if (storyEl) setTimeout(function () { var t = docEl.dataset.tier; if (!t || t === "none") loadPosters(); }, 3000);

  /* ---------- nav shadow, sticky CTA ---------- */
  var sticky = document.getElementById("stickyCta");
  var hideZones = [].slice.call(document.querySelectorAll("#pricing, .final, #contact"));
  var inHideZone = false;
  if (sticky && "IntersectionObserver" in window) {
    var zoneHits = new Set();
    var zio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) zoneHits.add(e.target); else zoneHits.delete(e.target); });
      inHideZone = zoneHits.size > 0;
      onScrollUi();
    }, { threshold: 0.15 });
    hideZones.forEach(function (z) { zio.observe(z); });
  }
  function onScrollUi() {
    docEl.classList.toggle("scrolled", scrollY > 8);
    if (!sticky) return;
    var narrow = innerWidth < 980;
    var past = storyEl ? (narrow ? storyEl.getBoundingClientRect().bottom < innerHeight * 0.6 : storyEl.getBoundingClientRect().top < -innerHeight * 0.5) : scrollY > 700;
    var show = past && !inHideZone && !docEl.classList.contains("exit-open");
    sticky.classList.toggle("show", show);
    sticky.setAttribute("aria-hidden", show ? "false" : "true");
    var link = sticky.querySelector("a"); if (link) link.tabIndex = show ? 0 : -1;
  }
  addEventListener("scroll", onScrollUi, { passive: true });
  onScrollUi();

  /* ---------- exit reminder (desktop, once per session) ---------- */
  (function () {
    var card = document.getElementById("exitCard");
    if (!card || !matchMedia("(pointer: fine)").matches) return;
    var seen = false;
    try { seen = sessionStorage.getItem("pl-exit-seen") === "1"; } catch (e) {}
    if (seen) return;
    var armed = false;
    setTimeout(function () { armed = true; }, 9000);
    function open() {
      if (!armed || seen) return;
      seen = true;
      try { sessionStorage.setItem("pl-exit-seen", "1"); } catch (e) {}
      card.hidden = false;
      docEl.classList.add("exit-open");
      onScrollUi();
      requestAnimationFrame(function () { requestAnimationFrame(function () { card.classList.add("show"); }); });
    }
    function close() {
      card.classList.remove("show");
      docEl.classList.remove("exit-open");
      setTimeout(function () { card.hidden = true; onScrollUi(); }, 400);
    }
    document.addEventListener("mouseout", function (e) { if (!e.relatedTarget && e.clientY <= 4) open(); });
    card.querySelector("[data-exit-close]").addEventListener("click", close);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !card.hidden) close(); });
  })();

  /* ---------- reveal everything (no motion path) ---------- */
  function revealEverything() {
    docEl.classList.remove("anim");
    document.querySelectorAll("[data-count]").forEach(function (el) { el.textContent = el.getAttribute("data-count") + (el.getAttribute("data-suffix") || ""); });
    if (baSetPos) baSetPos(0.5);
  }

  if (reduce || !A || !A.animate) { revealEverything(); return; }

  /* ---------- smooth scrolling (Lenis) ---------- */
  var lenis = null;
  if (window.Lenis) {
    try {
      lenis = new window.Lenis({ lerp: 0.09, smoothWheel: true, wheelMultiplier: 0.9 });
      var raf = function (time) { lenis.raf(time); requestAnimationFrame(raf); };
      requestAnimationFrame(raf);
      window.PL_LENIS = lenis;
      document.querySelectorAll('a[href^="#"]').forEach(function (a) {
        a.addEventListener("click", function (e) {
          var id = a.getAttribute("href");
          var el = id.length > 1 && document.querySelector(id);
          if (!el) return;
          e.preventDefault();
          lenis.scrollTo(el, { offset: -64, duration: 1.4 });
        });
      });
    } catch (e) { lenis = null; }
  }

  /* ---------- motion (anime.js v4) ---------- */
  var animate = A.animate, stagger = A.stagger, createTimeline = A.createTimeline;
  var failsafe = setTimeout(revealEverything, 5000);
  try {
    docEl.classList.add("motion-ready");

    function countUp(el) {
      var end = parseFloat(el.getAttribute("data-count")) || 0;
      var suffix = el.getAttribute("data-suffix") || "";
      var obj = { v: 0 };
      animate(obj, { v: end, duration: 1600, ease: "outExpo", onUpdate: function () { el.textContent = Math.round(obj.v) + suffix; }, onComplete: function () { el.textContent = end + suffix; } });
    }

    /* hero intro (the 3D phone assembles in parallel, see story.js) */
    var heroCap = document.querySelector('.cap[data-cap="0"]');
    if (heroCap) {
      var tl = createTimeline({ defaults: { ease: "outExpo", duration: 900 } });
      tl.add("[data-hero=kicker]", { opacity: [0, 1], y: [18, 0], duration: 600 }, 150)
        .add(".cap h1 .w", { opacity: [0, 1], y: [48, 0], rotate: [3, 0], duration: 1000, delay: stagger(80) }, 260)
        .add("[data-hero=sub]", { opacity: [0, 1], y: [18, 0], duration: 700 }, 900)
        .add("[data-hero=cta]", { opacity: [0, 1], y: [18, 0], duration: 700 }, 1050)
        .add("[data-hero=stats]", { opacity: [0, 1], y: [18, 0], duration: 700, onBegin: function () { document.querySelectorAll("[data-hero=stats] [data-count]").forEach(countUp); } }, 1200)
        .add("[data-hero=cue]", { opacity: [0, 1], duration: 700 }, 1500);
    }

    /* scroll reveals */
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        io.unobserve(el);
        var children = [].slice.call(el.children);
        if (!children.length) children = [el];
        animate(children, { opacity: [0, 1], y: [34, 0], duration: 1000, ease: "outExpo", delay: stagger(90) });
        el.querySelectorAll("[data-count]").forEach(countUp);
        if (el.classList.contains("demo-stage") && baSetPos) {
          var s = { p: 0.92 };
          animate(s, { p: [0.92, 0.12, 0.5], duration: 2400, delay: 500, ease: "inOutSine", onUpdate: function () { baSetPos(s.p); } });
        }
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
