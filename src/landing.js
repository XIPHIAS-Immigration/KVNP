/* KVNP Studio — landing page motion.
   GSAP + ScrollTrigger when available; degrades to fully-visible, still-interactive
   content when GSAP is missing or the visitor prefers reduced motion. */
(function () {
  "use strict";

  var docEl = document.documentElement;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hasGSAP = !!window.gsap;

  /* ---------- sticky nav state ---------- */
  var nav = document.getElementById("nav");
  function onScroll() {
    if (window.scrollY > 40) nav.classList.add("scrolled");
    else nav.classList.remove("scrolled");
  }
  if (nav) { onScroll(); window.addEventListener("scroll", onScroll, { passive: true }); }

  /* ---------- mobile menu ---------- */
  var toggle = document.getElementById("navToggle");
  var links = document.getElementById("navLinks");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    links.addEventListener("click", function (e) {
      if (e.target.tagName === "A") {
        links.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
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
      handle.setAttribute("aria-valuenow", Math.round(p * 100));
    }
    handle.addEventListener("pointerdown", function (e) {
      dragging = true;
      try { handle.setPointerCapture(e.pointerId); } catch (err) {}
      e.preventDefault();
    });
    window.addEventListener("pointermove", function (e) { if (dragging) setPos(e.clientX); });
    window.addEventListener("pointerup", function () { dragging = false; });
    ba.addEventListener("pointerdown", function (e) {
      if (e.target !== handle && !handle.contains(e.target)) setPos(e.clientX);
    });
    handle.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      var value = Number(handle.getAttribute("aria-valuenow") || 50);
      value += e.key === "ArrowRight" ? 5 : -5;
      value = Math.max(0, Math.min(100, value));
      after.style.clipPath = "inset(0 0 0 " + value + "%)";
      handle.style.left = value + "%";
      handle.setAttribute("aria-valuenow", value);
      e.preventDefault();
    });
  })();

  /* ---------- reveal / parallax / counters ---------- */
  function revealEverything() {
    docEl.classList.remove("anim");
    document.querySelectorAll("[data-reveal], .hero h1 .lw").forEach(function (el) {
      el.style.opacity = "1";
      el.style.transform = "none";
    });
  }

  if (reduce || !hasGSAP) { revealEverything(); return; }

  var gsap = window.gsap;
  var ST = window.ScrollTrigger;
  if (ST) gsap.registerPlugin(ST);

  // hard failsafe: if anything throws or stalls, force everything visible
  var failsafe = setTimeout(revealEverything, 4500);

  try {
    /* hero intro timeline. Let GSAP own the headline's initial yPercent so the
       clip-reveal actually tweens (CSS translateY(110%) reads as y-px, not yPercent). */
    gsap.set(".hero h1 .lw", { y: 46, opacity: 0 });
    var tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    tl.to(".hero .eyebrow", { opacity: 1, y: 0, duration: 0.5 })
      .to(".hero h1 .lw", { y: 0, opacity: 1, duration: 0.8, stagger: 0.1 }, "-=0.15")
      .to(".hero-sub", { opacity: 1, y: 0, duration: 0.6 }, "-=0.45")
      .to(".hero-cta", { opacity: 1, y: 0, duration: 0.5 }, "-=0.35")
      .to(".hero-proof", { opacity: 1, y: 0, duration: 0.5 }, "-=0.35")
      .fromTo(".hero-photo", { scale: 1.025 }, { scale: 1, duration: 1.1, ease: "power2.out" }, "-=0.8")
      .fromTo(".hero-status", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.5 }, "-=0.45");

    /* scroll reveals (everything with data-reveal outside the hero) */
    gsap.utils.toArray("[data-reveal]").forEach(function (el) {
      if (el.closest(".hero")) return;
      var props = { opacity: 1, duration: 0.7, ease: "power3.out", overwrite: false,
        scrollTrigger: { trigger: el, start: "top 87%", once: true } };
      if (el.hasAttribute("data-parallax")) {
        props.scale = 1;              // parallax owns Y; reveal only clears scale + opacity
      } else {
        props.x = 0; props.y = 0; props.scale = 1;
      }
      gsap.to(el, props);
    });

    /* parallax drift (Y only, independent of the scale-based reveal) */
    gsap.utils.toArray("[data-parallax]").forEach(function (el) {
      var amt = parseFloat(el.getAttribute("data-parallax")) || -40;
      gsap.to(el, { y: amt, ease: "none", overwrite: false,
        scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: 0.6 } });
    });

    /* number count-ups */
    gsap.utils.toArray("[data-count]").forEach(function (el) {
      var end = parseFloat(el.getAttribute("data-count"));
      var suffix = el.getAttribute("data-suffix") || "";
      var obj = { v: 0 };
      ST.create({ trigger: el, start: "top 90%", once: true, onEnter: function () {
        gsap.to(obj, { v: end, duration: 1.4, ease: "power2.out",
          onUpdate: function () { el.textContent = Math.round(obj.v) + suffix; } });
      }});
    });

    if (ST) window.addEventListener("load", function () { ST.refresh(); });
    clearTimeout(failsafe);
  } catch (err) {
    clearTimeout(failsafe);
    revealEverything();
  }
})();

(function () {
  "use strict";
  var memberEntries = document.querySelectorAll("[data-member-entry]");
  fetch("/api/commerce/config", { credentials: "same-origin" })
    .then(function (response) { return response.json(); })
    .then(function (data) {
      if (!data.signedIn || !data.subscription || !data.subscription.active) return;
      memberEntries.forEach(function (entry) {
        entry.href = "/app";
        if (entry.classList.contains("btn")) {
          entry.firstChild.textContent = "Open Studio ";
        } else {
          entry.textContent = "Studio";
        }
      });
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
      body: JSON.stringify({
        name: "landing_view",
        anonymousId: anonymousId,
        metadata: {
          path: location.pathname,
          referrerHost: referrerHost,
          device: matchMedia("(max-width: 680px)").matches ? "mobile" : "desktop",
        },
      }),
    }).catch(function () {});
  } catch (error) {}
  var promptKey = "kvnp-contact-prompt-v1";
  var dialog = document.getElementById("contact-dialog");

  document.querySelectorAll("[data-enquiry-form]").forEach(function (form) {
    var status = form.querySelector("[data-enquiry-status]");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      status.textContent = "Sending...";
      var button = form.querySelector("button[type='submit']");
      button.disabled = true;
      var values = new FormData(form);
      try {
        var response = await fetch("/api/enquiries", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            name: values.get("name"),
            email: values.get("email"),
            subject: values.get("subject"),
            message: values.get("message"),
          }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "Could not send the enquiry.");
        form.reset();
        status.textContent = "Received / " + data.reference;
        try { sessionStorage.setItem(promptKey, "submitted"); } catch (error) {}
        if (form.closest("dialog")) setTimeout(function () { dialog.close(); }, 1200);
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  });

  if (dialog) {
    function dismissDialog() {
      if (dialog.open) dialog.close();
      try { sessionStorage.setItem(promptKey, "dismissed"); } catch (error) {}
    }
    dialog.querySelector("[data-dialog-close]").addEventListener("click", dismissDialog);
    dialog.addEventListener("cancel", function (event) { event.preventDefault(); dismissDialog(); });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dismissDialog();
    });
    setTimeout(function () {
      var seen = false;
      try { seen = !!sessionStorage.getItem(promptKey); } catch (error) {}
      if (!seen && location.hash !== "#contact" && !dialog.open) dialog.showModal();
    }, 2000);
  }
})();
