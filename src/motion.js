/* KVNP Studio motion layer (GSAP, self-hosted).
   Hooks the existing DOM via MutationObservers so app logic stays untouched.
   No-ops cleanly when GSAP is missing or the user prefers reduced motion. */
(function kvnpMotion() {
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (typeof window.gsap === "undefined" || reduced) return;
  const gsap = window.gsap;

  /* Fail-safe entrance helper: content must NEVER stay invisible if an
     animation is interrupted. fromTo + clearProps on complete, plus a hard
     safety timer that strips inline styles regardless. */
  function settleSafe(elements, fromVars, toVars, totalMs) {
    if (!elements || !elements.length) return;
    gsap.fromTo(elements, fromVars, { ...toVars, clearProps: "opacity,transform" });
    window.setTimeout(() => {
      for (const el of elements) {
        el.style.opacity = "";
        el.style.transform = "";
      }
    }, totalMs);
  }

  /* ---- entrance: staggered instrument boot when the app view appears ---- */
  function playEntrance() {
    settleSafe(
      document.querySelectorAll(".sidebar-nav .nav-item, .sidebar-brand"),
      { opacity: 0, x: -10 },
      { opacity: 1, x: 0, duration: 0.35, stagger: 0.05, ease: "power3.out" },
      1200,
    );
    settleSafe(
      document.querySelectorAll(".app-shell .card"),
      { opacity: 0, y: 16 },
      { opacity: 1, y: 0, duration: 0.45, stagger: 0.08, ease: "power3.out", delay: 0.12 },
      1600,
    );
  }

  const appView = document.querySelector("#app-view");
  if (appView) {
    if (!appView.hidden) {
      requestAnimationFrame(playEntrance);
    }
    new MutationObserver(() => {
      if (!appView.hidden) playEntrance();
    }).observe(appView, { attributes: true, attributeFilter: ["hidden"] });
  }

  /* ---- auth card entrance ---- */
  const authCard = document.querySelector(".auth-card");
  const authAside = document.querySelector(".auth-aside-inner");
  if (authCard && !document.querySelector("#auth-view").hidden) {
    settleSafe(authCard.children, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.5, stagger: 0.08, ease: "power3.out", delay: 0.1 }, 1500);
    if (authAside) settleSafe(authAside.children, { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.55, stagger: 0.09, ease: "power3.out" }, 1500);
  }

  /* ---- decision card: rubber-stamp hit ---- */
  const decision = document.querySelector("#decision-card");
  if (decision) {
    let lastKey = "";
    new MutationObserver(() => {
      const key = decision.className + "|" + (decision.querySelector("strong")?.textContent ?? "");
      if (key === lastKey) return;
      lastKey = key;
      const title = decision.querySelector("strong");
      if (!title) return;
      gsap.fromTo(
        title,
        { scale: 1.5, rotation: -6, opacity: 0, transformOrigin: "left center" },
        { scale: 1, rotation: -0.6, opacity: 1, duration: 0.32, ease: "power4.in" }
      );
      gsap.fromTo(decision, { x: 0 }, { x: 1.5, duration: 0.05, yoyo: true, repeat: 3, delay: 0.3 });
    }).observe(decision, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  }

  /* ---- check rows: cascade in when a new result lands ---- */
  function observeList(selector) {
    const list = document.querySelector(selector);
    if (!list) return;
    let pending = 0;
    new MutationObserver(() => {
      if (pending) return;
      pending = requestAnimationFrame(() => {
        pending = 0;
        const rows = Array.from(list.children);
        if (!rows.length) return;
        gsap.fromTo(
          rows,
          { opacity: 0, y: 8 },
          { opacity: 1, y: 0, duration: 0.28, stagger: { each: 0.025, from: "start" }, ease: "power2.out", overwrite: "auto", clearProps: "opacity,transform" }
        );
        // Hard settle: rows must never stay invisible if the tween is interrupted.
        window.setTimeout(() => {
          for (const row of rows) {
            row.style.opacity = "";
            row.style.transform = "";
          }
        }, 1200);
      });
    }).observe(list, { childList: true });
  }
  observeList("#checks-list");
  observeList("#source-quality-list");
  observeList("#pipeline-report");

  /* ---- corrections card slide ---- */
  const corrections = document.querySelector("#corrections-card");
  if (corrections) {
    new MutationObserver(() => {
      if (corrections.hidden) return;
      gsap.fromTo(corrections, { opacity: 0, x: -10 }, { opacity: 1, x: 0, duration: 0.35, ease: "power3.out", overwrite: "auto" });
    }).observe(corrections, { attributes: true, attributeFilter: ["hidden"] });
  }

  /* ---- overall status tick ---- */
  const overall = document.querySelector("#overall-status");
  if (overall) {
    new MutationObserver(() => {
      gsap.fromTo(overall, { opacity: 0.4 }, { opacity: 1, duration: 0.3, ease: "power2.out", overwrite: "auto" });
    }).observe(overall, { childList: true, attributes: true, attributeFilter: ["class"] });
  }

  /* ---- button micro-press (delegated) ---- */
  document.addEventListener("pointerdown", (event) => {
    const btn = event.target.closest(".btn, .seg-btn, .nav-item, .queue-item");
    if (!btn) return;
    gsap.fromTo(btn, { scale: 0.97 }, { scale: 1, duration: 0.22, ease: "power2.out", overwrite: "auto", clearProps: "scale" });
  });

  /* ---- final photo reveal ---- */
  const finalFrame = document.querySelector(".final-frame");
  const finalCanvas = document.querySelector("#final-canvas");
  const compare = document.querySelector("#compare");
  if (finalFrame && finalCanvas) {
    let revealKey = "";
    new MutationObserver(() => {
      const key = `${finalCanvas.hidden}|${compare ? compare.hidden : "x"}`;
      if (key === revealKey) return;
      revealKey = key;
      const target = finalCanvas.hidden ? compare : finalCanvas;
      if (!target || target.hidden) return;
      gsap.fromTo(target, { opacity: 0.2, scale: 0.985 }, { opacity: 1, scale: 1, duration: 0.4, ease: "power2.out", clearProps: "scale", overwrite: "auto" });
    }).observe(finalFrame, { attributes: true, subtree: true, attributeFilter: ["hidden"] });
  }
})();
