/* Injects shared navigation + footer into every page.
   Loaded before main.js. Keeps 6 pages consistent with zero build step. */

(() => {
  const NAV = `
  <header class="nav">
    <div class="container nav-inner">
      <a class="brand" href="index.html">
        <svg class="brand-mark" viewBox="0 0 16 16" aria-hidden="true" fill="none"
             stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M3.5 2.5v8.6"/>
          <path d="M3.5 2.5h4.4a2.6 2.6 0 0 1 0 5.2H3.5"/>
          <path d="M8 7.7 11.6 13"/>
          <circle cx="9.2" cy="14.2" r="0.9" fill="currentColor" stroke="none"/>
        </svg>
        <span class="brand-name">UPF<b>-Insight</b></span>
        <span class="brand-ver">v0.2.4</span>
      </a>
      <nav class="nav-links" aria-label="Primary">
        <a href="index.html">Home</a>
        <a href="product.html">Product</a>
        <a href="rules.html">Rule Catalog</a>
        <a href="about.html">About</a>
        <a href="contact.html">Contact</a>
      </nav>
      <button class="btn btn-primary btn-sm nav-cta" data-launch type="button">
        Launch Tool
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor"
             stroke-width="1.8" stroke-linecap="round"><path d="M3 8h9M9 4.5 12.5 8 9 11.5"/></svg>
      </button>
      <button class="nav-burger" aria-label="Toggle menu">☰</button>
    </div>
  </header>`;

  const FOOTER = `
  <footer class="footer">
    <div class="container">
      <div class="footer-grid">
        <div>
          <a class="brand" href="index.html">
            <svg class="brand-mark" viewBox="0 0 16 16" aria-hidden="true" fill="none"
                 stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <path d="M3.5 2.5v8.6"/><path d="M3.5 2.5h4.4a2.6 2.6 0 0 1 0 5.2H3.5"/>
              <path d="M8 7.7 11.6 13"/><circle cx="9.2" cy="14.2" r="0.9" fill="currentColor" stroke="none"/>
            </svg>
            <span class="brand-name">UPF<b>-Insight</b></span>
          </a>
          <p class="footer-desc">Deterministic power-intent intelligence for IEEE&nbsp;1801 (UPF).
          Every finding traces to a line. No LLM in the analysis path.</p>
        </div>
        <div>
          <h4>Product</h4>
          <a href="product.html">Overview</a>
          <a href="rules.html">Rule Catalog</a>
          <a href="contact.html">Contact</a>
        </div>
        <div>
          <h4>Company</h4>
          <a href="about.html">About</a>
          <a href="contact.html">Contact</a>
        </div>
        <div>
          <h4>Resources</h4>
          <a href="https://opencode.ai" target="_blank" rel="noopener">Docs</a>
          <a href="../upf/index.html">UPF Primer</a>
        </div>
      </div>
      <div class="footer-base">
        <span>© ${new Date().getFullYear()} UPF-Insight — deterministic · offline · evidence-backed</span>
        <span>"no errors" ≠ "power proven correct"</span>
      </div>
    </div>
  </footer>`;

  const launchModal = `
  <div class="modal-backdrop" id="launch-modal" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="launch-title">
      <h3 id="launch-title">Start your local workspace</h3>
      <p>The analysis engine runs entirely on your machine — nothing leaves it.
         Start the server, then relaunch:</p>
      <code class="cmd">pip install upf-insight &amp;&amp; upf-insight web</code>
      <p style="font-size:12.5px; color:var(--text-3); margin-top:-10px;">
        Serves on http://localhost:8585 by default (or add <span class="mono">--port N</span>).</p>
      <div class="modal-actions">
        <button class="btn btn-primary" data-retry type="button">Detect server again</button>
        <button class="btn btn-ghost" data-copy type="button">Copy command</button>
        <button class="btn btn-ghost" data-close-modal type="button">Close</button>
      </div>
      <div class="modal-status" id="launch-status"></div>
    </div>
  </div>`;

  /* Inject synchronously — these scripts load at end of <body>,
     so document.body already exists and main.js sees the nav. */
  {
    const body = document.body;
    body.insertAdjacentHTML("afterbegin", `<div class="bg-fx"></div><div class="bg-grid"></div>${NAV}`);
    body.insertAdjacentHTML("beforeend", `${launchModal}${FOOTER}`);
    body.querySelectorAll("[data-close-modal]").forEach(b =>
      b.addEventListener("click", () => {
        document.getElementById("launch-modal").classList.remove("open");
      }));
  }
})();
