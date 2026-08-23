/* UPF-Insight business site — shared behaviors
   nav · scroll reveals · spotlight cards · 3D tilt · counters · launcher */

(() => {
  "use strict";

  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── navigation ─────────────────────────────────────────── */
  const nav = document.querySelector(".nav");
  const onScroll = () => nav.classList.toggle("scrolled", scrollY > 12);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const burger = document.querySelector(".nav-burger");
  const links = document.querySelector(".nav-links");
  if (burger && links) {
    burger.addEventListener("click", () => links.classList.toggle("open"));
    links.querySelectorAll("a").forEach(a =>
      a.addEventListener("click", () => links.classList.remove("open")));
  }

  /* mark active link */
  const here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach(a => {
    const href = a.getAttribute("href");
    if (href === here) a.classList.add("active");
  });

  /* ── scroll reveal ──────────────────────────────────────── */
  const io = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add("revealed");
        io.unobserve(e.target);
      }
    }
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  document.querySelectorAll(".reveal, .stagger").forEach(el => io.observe(el));

  /* ── spotlight cursor tracking on cards ─────────────────── */
  document.querySelectorAll(".card.spotlight").forEach(card => {
    card.addEventListener("pointermove", ev => {
      const r = card.getBoundingClientRect();
      card.style.setProperty("--mx", `${ev.clientX - r.left}px`);
      card.style.setProperty("--my", `${ev.clientY - r.top}px`);
    });
  });

  /* ── 3D tilt (pointer-tracked rotateX/Y) ────────────────── */
  if (!reducedMotion && matchMedia("(pointer: fine)").matches) {
    document.querySelectorAll("[data-tilt]").forEach(el => {
      const max = parseFloat(el.dataset.tilt) || 7;
      el.style.transition = "transform 0.15s ease-out";
      el.addEventListener("pointermove", ev => {
        const r = el.getBoundingClientRect();
        const px = (ev.clientX - r.left) / r.width - 0.5;
        const py = (ev.clientY - r.top) / r.height - 0.5;
        el.style.transform =
          `perspective(900px) rotateY(${(px * max).toFixed(2)}deg) ` +
          `rotateX(${(-py * max).toFixed(2)}deg) translateZ(0)`;
      });
      el.addEventListener("pointerleave", () => {
        el.style.transition = "transform 0.6s cubic-bezier(0.16,1,0.3,1)";
        el.style.transform = "perspective(900px) rotateY(0deg) rotateX(0deg)";
      });
    });
  }

  /* ── animated counters ──────────────────────────────────── */
  const animateCount = el => {
    const target = parseFloat(el.dataset.count);
    const decimals = (el.dataset.count.split(".")[1] || "").length;
    const dur = 1400;
    const t0 = performance.now();
    const step = now => {
      const p = Math.min((now - t0) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const cio = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (e.isIntersecting) { animateCount(e.target); cio.unobserve(e.target); }
    }
  }, { threshold: 0.5 });
  document.querySelectorAll("[data-count]").forEach(el => {
    if (reducedMotion) el.textContent = el.dataset.count;
    else cio.observe(el);
  });

  /* ── terminal typing demo ───────────────────────────────── */
  const term = document.querySelector(".terminal-body[data-script]");
  if (term) {
    const lines = JSON.parse(term.dataset.script);
    const speed = reducedMotion ? 0 : 26;
    let li = 0;
    const typeLine = () => {
      if (li >= lines.length) return;
      const [cls, text, pause] = lines[li++];
      const div = document.createElement("div");
      div.className = cls || "tl-info";
      term.appendChild(div);
      let ci = 0;
      const typeChar = () => {
        div.textContent = text.slice(0, ++ci);
        div.classList.add("caret");
        if (ci < text.length && speed) setTimeout(typeChar, speed);
        else {
          div.classList.remove("caret");
          setTimeout(typeLine, pause ?? 320);
        }
      };
      typeChar();
    };
    new IntersectionObserver((entries, obs) => {
      if (entries[0].isIntersecting) { obs.disconnect(); typeLine(); }
    }, { threshold: 0.4 }).observe(term);
  }

  /* ── tool launcher ────────────────────────────────────────
     Strategy:
     1. Probe http://localhost:{8000,8080,5000}/api/version with
        mode:'no-cors' — resolves only if the api_server answers.
     2. If alive → open the workspace root in a new tab.
     3. If not → open modal with the one-liner + retry button. */

  const TOOL_PORTS = [8585, 8000, 8080, 5000];
  const WS_PATH = "/";

  async function probeTool() {
    // file:// origin: browsers block fetch entirely → tell the user
    // to serve the site over HTTP instead of failing silently.
    if (location.protocol === "file:") return null;
    for (const port of TOOL_PORTS) {
      const base = `http://localhost:${port}`;
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 1200);
        // no-cors: any reachable HTTP server resolves; CORS never blocks.
        await fetch(`${base}/api/version`, {
          signal: ctrl.signal, mode: "no-cors", cache: "no-store",
        });
        clearTimeout(t);
        return base;
      } catch { /* server not there */ }
    }
    return null;
  }

  const modal = document.getElementById("launch-modal");
  const statusEl = document.getElementById("launch-status");

  function openModal() {
    if (!modal) return;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
  }
  function closeModal() {
    if (!modal) return;
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }

  document.querySelectorAll("[data-launch]").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const original = btn.innerHTML;
      btn.innerHTML = "Detecting…";
      const base = await probeTool();
      btn.disabled = false;
      btn.innerHTML = original;
      if (base) {
        window.open(base + WS_PATH, "_blank", "noopener");
      } else if (location.protocol === "file:") {
        openModal();
        if (statusEl) {
          statusEl.textContent =
            "this page was opened from disk — serve it over HTTP first";
          statusEl.className = "modal-status fail";
        }
      } else {
        openModal();
      }
    });
  });

  document.querySelectorAll("[data-demo]").forEach(btn => {
    btn.addEventListener("click", async ev => {
      // Demo fallback: probe once more, then route to the live demo
      // served by the API server if present, else guide the user.
      const base = await probeTool();
      if (base) {
        window.open(base + WS_PATH + "?demo=1", "_blank", "noopener");      } else {
        ev.preventDefault();
        openModal();
        if (statusEl) {
          statusEl.textContent =
            "demo needs the local server — start it below (takes ~2 s)";
          statusEl.className = "modal-status fail";
        }
      }
    });
  });

  if (modal) {
    modal.addEventListener("click", e => {
      if (e.target === modal) closeModal();
    });
    addEventListener("keydown", e => {
      if (e.key === "Escape") closeModal();
    });
    const copyBtn = modal.querySelector("[data-copy]");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        const cmd = modal.querySelector("code.cmd")?.textContent.trim();
        try {
          await navigator.clipboard.writeText(cmd);
          statusEl.textContent = "copied to clipboard";
          statusEl.className = "modal-status ok";
        } catch {
          statusEl.textContent = "copy failed — select the text manually";
          statusEl.className = "modal-status fail";
        }
      });
    }
    const retryBtn = modal.querySelector("[data-retry]");
    if (retryBtn) {
      retryBtn.addEventListener("click", async () => {
        statusEl.textContent = "probing localhost…";
        statusEl.className = "modal-status";
        const base = await probeTool();
        if (base) {
          statusEl.textContent = `server found at ${base} — opening…`;
          statusEl.className = "modal-status ok";
          setTimeout(() => window.open(base + WS_PATH, "_blank", "noopener"), 600);
        } else {
          statusEl.textContent =
            "not running yet — start it with the command above, then retry";
          statusEl.className = "modal-status fail";
        }
      });
    }
  }
})();
