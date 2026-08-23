"""Generate the UPF-Insight business site (static HTML, no build step).

Writes a polished single-page product site plus per-feature pages into
upf_insight/business_site/. Modern dark design with an ember-charcoal /
amber / copper identity (distinct from any sibling product sites).

Usage:
    python scripts/generate_business_site.py            # write the site
    python scripts/generate_business_site.py --verify   # exit 1 on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from upf_insight import __version__  # noqa: E402

SITE = ROOT / "upf_insight" / "business_site"

FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 32 32'><rect width='32' height='32' rx='7' "
           "fill='%231E2220'/><path d='M18 4 8 18h6l-2 10 12-15h-7z' "
           "fill='%2334D399'/></svg>")

CSS = """:root {
  --bg:            #131514;
  --bg-raised:     #191C1A;
  --bg-panel:      #1E2220;
  --line:          rgba(255, 255, 255, 0.07);
  --line-strong:   rgba(242, 163, 60, 0.35);
  --text-hi:       #F1F5F2;
  --text-mid:      #B2BBB4;
  --text-lo:       #7D8880;
  --accent:         #34D399;
  --accent-2:        #14B8A6;
  --green:         #6EE7B7;
  --grad:          linear-gradient(135deg, #F6B04E, #14B8A6);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg);
  color: var(--text-mid);
  font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif;
  font-size: 16px; line-height: 1.7;
  -webkit-font-smoothing: antialiased;
}
::selection { background: rgba(52,211,153,.28); color: #fff; }
a { color: inherit; text-decoration: none; }
.mono, code, pre { font-family: "Cascadia Code", ui-monospace, Consolas, monospace; }
.wrap { max-width: 1140px; margin: 0 auto; padding: 0 28px; }

.nav {
  position: sticky; top: 0; z-index: 40;
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  background: rgba(19, 17, 16, 0.78);
  border-bottom: 1px solid var(--line);
}
.nav-inner { display: flex; align-items: center; gap: 26px; height: 62px; }
.logo { display: flex; align-items: center; gap: 10px; font-weight: 700; color: var(--text-hi); letter-spacing: -0.01em; }
.logo svg { display: block; }
.logo b { color: var(--accent); font-weight: 700; }
.nav-links { display: flex; gap: 22px; margin-left: auto; font-size: 0.9rem; color: var(--text-mid); }
.nav-links a:hover { color: var(--text-hi); }
.nav-cta {
  padding: 8px 18px; border-radius: 8px; font-size: 0.88rem; font-weight: 600;
  background: var(--grad); color: #04231A;
}
.nav-cta:hover { filter: brightness(1.1); color: #04231A; }

.hero { padding: 92px 0 76px; position: relative; overflow: hidden; }
.hero::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(52% 42% at 82% -6%, rgba(20,184,166,.14), transparent 70%),
    radial-gradient(44% 38% at 6% 4%, rgba(52,211,153,.09), transparent 70%);
}
.hero-grid { position: relative; display: grid; grid-template-columns: minmax(0,1.05fr) minmax(0,.95fr); gap: 56px; align-items: center; }
@media (max-width: 920px) { .hero-grid { grid-template-columns: 1fr; } }
.pill {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em;
  color: var(--accent); background: rgba(52,211,153,.09);
  border: 1px solid rgba(52,211,153,.25); border-radius: 999px;
  padding: 6px 14px; margin-bottom: 22px;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); }
h1 {
  font-size: clamp(2.3rem, 4.6vw, 3.55rem); line-height: 1.08;
  letter-spacing: -0.035em; font-weight: 750; color: var(--text-hi);
}
h1 span { background: var(--grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero p.lede { margin-top: 20px; font-size: 1.11rem; max-width: 54ch; }
.hero-actions { display: flex; gap: 14px; margin-top: 32px; flex-wrap: wrap; }
.btn {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 13px 26px; border-radius: 10px; font-weight: 650; font-size: 0.95rem;
  transition: transform .16s ease, box-shadow .16s ease, filter .16s ease;
}
.btn-grad { background: var(--grad); color: #04231A; box-shadow: 0 8px 30px -10px rgba(52,211,153,.45); }
.btn-grad:hover { transform: translateY(-2px); filter: brightness(1.06); color: #04231A; }
.btn-ghost { border: 1px solid var(--line-strong); color: var(--text-hi); }
.btn-ghost:hover { background: rgba(52,211,153,.07); }
.trust { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 30px; font-size: 0.84rem; color: var(--text-lo); }
.trust span::before { content: "\\2713"; color: var(--green); margin-right: 7px; }

.window {
  background: var(--bg-panel); border: 1px solid var(--line);
  border-radius: 14px; overflow: hidden;
  box-shadow: 0 30px 70px -30px rgba(0,0,0,.65), 0 0 0 1px rgba(52,211,153,.05);
}
.window-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 16px; border-bottom: 1px solid var(--line);
  background: var(--bg-raised); font-size: 0.74rem; color: var(--text-lo);
}
.window-bar i { width: 10px; height: 10px; border-radius: 50%; background: var(--line); }
.window-bar i:first-child { background: rgba(20,184,166,.7); }
.window-body { padding: 20px 22px; font-size: 0.83rem; line-height: 2.0; overflow-x: auto; white-space: pre; }
.t-dim { color: var(--text-lo); } .t-p { color: var(--accent); }
.t-ok { color: var(--green); } .t-warn { color: var(--accent-2); }
.t-hi { color: var(--text-hi); }

section.blk { padding: 76px 0; border-top: 1px solid var(--line); }
.sec-head { max-width: 640px; margin-bottom: 46px; }
.kicker {
  font-size: 0.76rem; font-weight: 700; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 12px;
}
h2 { font-size: clamp(1.6rem, 3vw, 2.2rem); letter-spacing: -0.025em; line-height: 1.2; color: var(--text-hi); font-weight: 720; }
.sec-head p { margin-top: 12px; }

.feat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }
.feat {
  position: relative; display: block;
  background: var(--bg-raised); border: 1px solid var(--line);
  border-radius: 14px; padding: 26px 24px 22px;
  transition: border-color .2s ease, transform .2s ease, background .2s ease;
}
.feat:hover { border-color: rgba(52,211,153,.4); transform: translateY(-3px); background: var(--bg-panel); }
.feat-ic {
  width: 42px; height: 42px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.15rem; margin-bottom: 16px;
  background: rgba(52,211,153,.10); border: 1px solid rgba(52,211,153,.22);
}
.feat h3 { color: var(--text-hi); font-size: 1.02rem; font-weight: 650; letter-spacing: -0.01em; }
.feat p { font-size: 0.9rem; margin-top: 8px; }
.feat .lnk {
  display: inline-block; margin-top: 14px; font-size: 0.85rem; font-weight: 600;
  color: var(--accent);
}

.stats-band {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  border: 1px solid var(--line); border-radius: 16px; overflow: hidden;
  background: var(--bg-raised);
}
.stat-cell { padding: 30px 26px; border-right: 1px solid var(--line); }
.stat-cell:last-child { border-right: none; }
@media (max-width: 720px) { .stat-cell { border-right: none; border-bottom: 1px solid var(--line); } }
.stat-cell b { display: block; font-size: 2.15rem; font-weight: 750; letter-spacing: -0.03em; color: var(--text-hi); }
.stat-cell b i { font-style: normal; background: var(--grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.stat-cell span { font-size: 0.86rem; color: var(--text-lo); }

.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; counter-reset: st; }
.step { background: var(--bg-raised); border: 1px solid var(--line); border-radius: 14px; padding: 24px; }
.step::before {
  counter-increment: st; content: "0" counter(st);
  font-size: 0.8rem; font-weight: 700; letter-spacing: 0.14em;
  color: var(--accent);
}
.step h3 { color: var(--text-hi); font-size: 1rem; margin: 10px 0 6px; font-weight: 650; }
.step p { font-size: 0.9rem; }
.step code { font-size: 0.82rem; color: var(--accent); }

.cta-box {
  position: relative; overflow: hidden; text-align: center;
  background: linear-gradient(180deg, var(--bg-panel), var(--bg-raised));
  border: 1px solid var(--line); border-radius: 20px; padding: 64px 34px;
}
.cta-box::before {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(58% 90% at 50% -20%, rgba(52,211,153,.13), transparent 70%);
}
.cta-box h2 { position: relative; }
.cta-box > p { position: relative; max-width: 56ch; margin: 12px auto 0; }
.cmd-pill {
  position: relative; display: inline-flex; align-items: center; gap: 12px;
  margin-top: 30px; padding: 13px 22px;
  background: var(--bg); border: 1px solid var(--line-strong); border-radius: 12px;
  font-size: 0.92rem; color: var(--text-hi);
}
.cmd-pill em { font-style: normal; color: var(--accent); }
footer.site { border-top: 1px solid var(--line); padding: 44px 0 54px; }
.foot-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 34px; }
@media (max-width: 780px) { .foot-grid { grid-template-columns: 1fr 1fr; } }
.foot-brand { color: var(--text-lo); font-size: 0.88rem; max-width: 34ch; }
.foot-col h4 { font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-hi); margin-bottom: 14px; font-weight: 650; }
.foot-col a { display: block; font-size: 0.88rem; color: var(--text-lo); padding: 4px 0; }
.foot-col a:hover { color: var(--accent); }
.foot-note { margin-top: 36px; padding-top: 22px; border-top: 1px solid var(--line); font-size: 0.78rem; color: var(--text-lo); }

.reveal { opacity: 0; transform: translateY(16px); transition: opacity .55s ease, transform .55s ease; }
.reveal.in { opacity: 1; transform: none; }
.crumbs { font-size: 0.82rem; color: var(--text-lo); margin-bottom: 30px; }
.crumbs a { color: var(--accent); }
.article { max-width: 780px; }
.article h1 { font-size: clamp(1.9rem, 3.6vw, 2.7rem); margin: 10px 0 18px; }
.article .lede { font-size: 1.08rem; margin-bottom: 26px; }
.article ul { list-style: none; margin: 18px 0 26px; }
.article ul li { padding: 10px 0 10px 30px; position: relative; border-bottom: 1px dashed var(--line); }
.article ul li::before { content: "\\2192"; position: absolute; left: 2px; color: var(--accent); }
"""

HERO_TERMINAL = """<div class="window">
  <div class="window-bar"><i></i><span class="mono">upf-insight â€” deterministic power-intent validation</span></div>
  <div class="window-body mono"><span class="t-dim">$</span> <span class="t-p">upf-insight</span> check soc.upf --gate NO_READINESS_REGRESSION
<span class="t-dim">reading soc.upf â€¦ 22 commands Â· UPF 3.0</span>
<span class="t-dim">running <span class="t-hi">77 registered rules</span> â€¦</span>
<span class="t-warn">WARN  UPF-036  iso_core    isolation policy not PST-conditioned</span>
<span class="t-warn">WARN  UPF-087  inst*       wildcard risk 8/10 HIGH</span>
<span class="t-ok">PASS  readiness READY_WITH_ADVISORIES Â· coverage 1.00 / 1.00</span>
<span class="t-hi">GATE  result: PASS</span> <span class="t-dim">(exit 0)</span></div>
</div>"""


def _nav(prefix: str = "") -> str:
    return """
<nav class="nav">
  <div class="wrap nav-inner">
    <a class="logo" href="{p}index.html">
      <svg width="24" height="24" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1E2220"/><path d="M18 4 8 18h6l-2 10 12-15h-7z" fill="#34D399"/></svg>
      UPF<b>-Insight</b>
    </a>
    <div class="nav-links">
      <a href="{p}index.html#features">Features</a>
      <a href="{p}index.html#how">Workflow</a>
      <a href="{p}features/validation.html">Docs</a>
      <a href="{p}features/integrations.html">MCP</a>
    </div>
    <a class="nav-cta mono" href="{p}index.html#install">pip install upf-insight</a>
  </div>
</nav>""".format(p=prefix)


def _footer(prefix: str = "") -> str:
    p = prefix
    return f"""
<footer class="site">
  <div class="wrap">
    <div class="foot-grid">
      <div>
        <a class="logo" style="margin-bottom:14px" href="{p}index.html">
          <svg width="22" height="22" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1E2220"/><path d="M18 4 8 18h6l-2 10 12-15h-7z" fill="#34D399"/></svg>
          UPF<b>-Insight</b>
        </a>
        <p class="foot-brand">Deterministic power-intent intelligence for IEEE
        1801. Validate, analyze and gate UPF files before implementation â€”
        offline, reproducible, evidence-traced.</p>
      </div>
      <div class="foot-col">
        <h4>Product</h4>
        <a href="{p}features/validation.html">Validator</a>
        <a href="{p}features/power-states.html">PST analysis</a>
        <a href="{p}features/strategy-analysis.html">Strategy lint</a>
        <a href="{p}features/design-awareness.html">Netlist awareness</a>
      </div>
      <div class="foot-col">
        <h4>Toolchain</h4>
        <a href="{p}features/scaffolding.html">Generator</a>
        <a href="{p}features/toolchain.html">Lint Â· Convert Â· Batch</a>
        <a href="{p}features/semantic-diff.html">Semantic diff</a>
        <a href="{p}features/ci-gate.html">CI gates</a>
      </div>
      <div class="foot-col">
        <h4>Platform</h4>
        <a href="{p}features/integrations.html">Web workspace</a>
        <a href="{p}features/integrations.html">MCP server</a>
        <a href="{p}features/rules-registry.html">Rule registry</a>
        <a href="{p}features/coverage-readiness.html">Readiness</a>
      </div>
    </div>
    <div class="foot-note">
      UPF-Insight v{__version__} Â· MIT Â· deterministic Â· offline Â· no LLM in
      the analysis path. &quot;No errors&quot; does not mean power intent is proven
      correct â€” read the support boundary.
    </div>
  </div>
</footer>"""


SCRIPT = """<script>
const io = new IntersectionObserver((es) => {
  es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
}, { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));
</script>"""


def head(title: str, desc: str) -> str:
    return f"""<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<link rel="icon" href="{FAVICON}">
<style>{CSS}</style>
</head>"""


def build_index() -> str:
    feats = [
        ("âš¡", "validation", "Deterministic validator",
         "77 evidence-backed rules over seven audited layers â€” syntax through netlist-aware design checks."),
        ("âŒ˜", "rules-registry", "Honest rule registry",
         "Every rule declares its semantic inputs and context limits; the registryâ†”handlerâ†”test contract is machine-audited."),
        ("â—ˆ", "design-awareness", "Netlist awareness",
         "Structural Verilog parsing unlocks port-level coverage and design-layer rules â€” no EDA tool required."),
        ("â–¦", "power-states", "Power state intelligence",
         "PST declared-vs-used analysis, cross-state events, impossible states proven impossible."),
       ("â‡„", "domain-relations", "Domain relation graph",
         "Typed isolation, level-shifter, supply and hierarchy edges between domains, each traced to file:line."),
        ("â—Ž", "coverage-readiness", "Coverage & readiness",
         "Structural coverage ratios and a categorical handoff verdict across five dimensions."),
        ("âš ", "strategy-analysis", "Strategy interactions",
         "Duplicate, overriding and conflicting strategies; wildcard patterns scored 0â€“10 for drift risk."),
        ("Â±", "semantic-diff", "Semantic diff",
         "Model-level change detection that ignores cosmetic edits and reports what actually changed."),
        ("âœŽ", "scaffolding", "UPF scaffolding",
         "Flat or hierarchical projects generated from declarative parameters â€” output that passes your own gates."),
        ("â˜°", "toolchain", "Lint Â· Convert Â· Batch",
         "Reformat UPF/Tcl, export JSON/YAML, validate whole directory trees with one command."),
        ("â›¨", "ci-gate", "Baselines & CI gates",
         "Snapshot findings, gate regressions under BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT policies."),
        ("âŸ", "integrations", "CLI Â· Web Â· MCP",
         "One engine, three surfaces: terminal, local web workspace, and an MCP server for agents."),
    ]
    cards = "".join(
        f'<a class="feat reveal" href="features/{slug}.html">'
        f'<div class="feat-ic">{icon}</div><h3>{t}</h3><p>{d}</p>'
        f'<span class="lnk">Learn more â†’</span></a>'
        for icon, slug, t, d in feats)
    stats = "".join(
        f'<div class="stat-cell"><b><i>{n}</i></b><span>{s}</span></div>'
        for n, s in [
            ("77", "registered rule codes"),
            ("34", "supported UPF commands"),
            ("100%", "findings traced to file:line"),
            ("0", "LLMs in the analysis path"),
        ])
    content = f"""
{_nav()}
<header class="hero">
  <div class="wrap hero-grid">
    <div>
      <div class="pill"><span class="dot"></span>IEEE 1801 Â· Power Intent Â· v{__version__}</div>
      <h1>Ship power intent<br>you can <span>defend.</span></h1>
      <p class="lede">UPF-Insight deterministically validates your IEEE 1801
      files before implementation: 77 documented rules, PST and strategy
      analysis, netlist-aware context, and CI quality gates. No EDA tool. No
      LLM in the loop.</p>
      <div class="hero-actions">
        <a class="btn btn-grad" href="#install">Get started</a>
        <a class="btn btn-ghost" href="#features">Explore features</a>
      </div>
      <div class="trust"><span>Deterministic</span><span>Offline-capable</span><span>Evidence to file:line</span><span>MIT licensed</span></div>
    </div>
    {HERO_TERMINAL}
  </div>
</header>

<section class="blk" id="features">
  <div class="wrap">
    <div class="sec-head reveal">
      <div class="kicker">Capabilities</div>
      <h2>Everything a power-intent flow needs</h2>
      <p>From first parse to CI merge gate â€” one deterministic engine,
      twelve integrated capabilities.</p>
    </div>
    <div class="feat-grid">{cards}</div>
  </div>
</section>

<section class="blk">
  <div class="wrap">
    <div class="stats-band reveal">{stats}</div>
  </div>
</section>

<section class="blk" id="how">
  <div class="wrap">
    <div class="sec-head reveal">
      <div class="kicker">Workflow</div>
      <h2>Three steps to trustworthy power intent</h2>
    </div>
    <div class="steps reveal">
      <div class="step"><h3>Validate</h3><p>Run the deterministic checker over your UPF files. Every finding carries a rule code, severity and exact source line.</p><code>upf-insight check soc.upf</code></div>
      <div class="step"><h3>Analyze</h3><p>PST consistency, strategy conflicts, wildcard drift, domain relations and readiness â€” in one pass.</p><code>upf-insight analyze soc.upf --netlist cpu.v</code></div>
      <div class="step"><h3>Gate</h3><p>Save a baseline and let CI fail the merge when blockers, trust regressions or coverage drops appear.</p><code>upf-insight check soc.upf --gate STRICT</code></div>
    </div>
  </div>
</section>

<section class="blk" id="install">
  <div class="wrap">
    <div class="cta-box reveal">
      <div class="kicker">Install</div>
      <h2>Up and running in one command</h2>
      <p>Python 3.10+, a single dependency, fully offline. Open the local web
      workspace or wire the MCP server into your agent stack.</p>
      <div class="cmd-pill mono"><em>$</em> pip install upf-insight</div>
    </div>
  </div>
</section>

<footer class="site">{_footer()}</footer>
{SCRIPT}"""
    return f"""<!DOCTYPE html>
<html lang="en">
{head(f"UPF-Insight â€” Deterministic UPF Power-Intent Validation (v{__version__})",
      "Deterministic IEEE 1801 UPF validation before STA: 77 rules, PST and strategy analysis, netlist-aware coverage, CI gates and MCP. No EDA tool, no LLM.")}
<body>{content}</body>
</html>"""


def build_feature(icon: str, slug: str, title: str, desc: str,
                  points: list[str], term: str = "") -> str:
    lis = "".join(f"<li>{p}</li>" for p in points)
    term_html = f'<div class="window" style="margin-top:30px"><div class="window-bar"><i></i><span class="mono">{slug}</span></div><div class="window-body mono">{term}</div></div>' if term else ""
    content = f"""
{_nav('../')}
<div class="wrap" style="padding-top:44px;padding-bottom:70px">
  <div class="crumbs"><a href="../index.html">Home</a> / {title}</div>
  <article class="article">
    <div class="kicker">Capability</div>
    <h1>{title}</h1>
    <p class="lede">{desc}</p>
    <ul>{lis}</ul>
    {term_html}
    <p style="margin-top:34px"><a class="btn btn-ghost" href="../index.html">â† Back to overview</a></p>
  </article>
</div>
<footer class="site">{_footer('../')}</footer>
{SCRIPT}"""
    return f"""<!DOCTYPE html>
<html lang="en">
{head(f"{title} Â· UPF-Insight", desc)}
<body>{content}</body>
</html>"""


FEATURE_DATA = [
    ("âš¡", "validation", "Deterministic validation",
     "77 evidence-backed rules across seven audited layers.",
     ["Rule codes UPF-001â€¦100 organized into audited layers",
      "Cascade suppression downgrades dependent findings instead of duplicating them",
      "Evidence boundary: NETLIST_REQUIRED facts are never reported as errors",
      "A broken rule handler can never crash a run"],
     "$ upf-insight check soc.upf --format junit"),
    ("âŒ˜", "rules-registry", "Honest rule registry",
     "One canonical source of truth for every rule code, severity and limit.",
     ["Every rule declares its semantic inputs and design-context requirement",
      "UPF_ONLY / NETLIST_REQUIRED / PARTIAL taxonomy keeps claims honest",
      "Registry â†” handler â†” test contract is machine-audited every run"],
     "$ upf-insight rules show UPF-085\n$ upf-insight rules audit"),
    ("â—ˆ", "design-awareness", "Netlist-aware power intent",
     "Feed a Verilog netlist or JSON snapshot and design-layer rules come alive.",
     ["Structural Verilog parser (.v/.sv): ports, buses, instances, sequential elements",
      "Netlist-aware port coverage: CONSTRAINED / UNCONSTRAINED / PARTIAL buckets",
      "Without a netlist the engine stays honest: UNKNOWN is not FALSE"],
     "$ upf-insight analyze soc.upf --netlist cpu.v"),
    ("â–¦", "power-states", "Power state table intelligence",
     "Declared vs used states, crossings, and provably impossible PST rows.",
     ["Cross-references declared states against create_pst rows",
      "Models power-down crossings and unmodeled switch behavior",
      "Switch ON while input OFF is flagged as impossible (UPF-039)"],
     "$ upf-insight pst soc.upf"),
    ("â‡„", "domain-relations", "Domain relation graph",
     "Typed relations between power domains, each with evidence.",
     ["Isolation, level-shifter, retention, supply and hierarchy relations",
      "Matrix view plus machine-readable JSON",
      "Every edge carries file:line provenance"],
     "$ upf-insight relations soc.upf"),
    ("â—Ž", "coverage-readiness", "Coverage and readiness",
     "Structural ratios plus a categorical handoff verdict.",
     ["Five readiness dimensions including DESIGN_CONTEXT",
      "READY Â· READY_WITH_ADVISORIES Â· REVIEW_REQUIRED Â· BLOCKED Â· INSUFFICIENT_CONTEXT",
      "Never a vanity score â€” coverage is NOT correctness"],
     ""),
    ("âš ", "strategy-analysis", "Strategy interactions & wildcard risk",
     "Find strategies that fight each other; score wildcard drift risk.",
     ["Identical strategies flagged as duplicates (UPF-085)",
      "Silent overrides, overlapping switch outputs, contradictory locations (UPF-086)",
      "Wildcard patterns scored 0â€“10 for elaboration-time drift (UPF-087)"],
     "$ upf-insight analyze soc.upf --json | jq .interactions"),
    ("Â±", "semantic-diff", "Semantic diff",
     "Model-level change detection that ignores cosmetic edits.",
     ["Domains, supplies, switches, PSTs and strategy deltas",
      "Provenance-only edits are not changes"],
     "$ upf-insight diff v1/cpu.upf v2/cpu.upf"),
    ("âœŽ", "scaffolding", "UPF scaffolding",
     "Flat or hierarchical projects from declarative parameters.",
     ["Domains, voltages, switches, isolation, retention, repeaters, relations",
      "Generated output passes the validator it came from"],
     "$ upf-insight generate --domains core,io,sram --isolation core:latch:vdd_ao"),
    ("â˜°", "toolchain", "Lint, convert, batch",
     "Reformat UPF/Tcl, convert formats, validate whole trees.",
     ["lint --check for CI, --fix for humans",
      "convert to structured JSON or YAML",
      "batch check|report over every .upf/.tcl in a tree"],
     "$ upf-insight lint rtl/power.upf --fix\n$ upf-insight batch check designs/"),
    ("â›¨", "ci-gate", "Baselines and CI gates",
     "Gate regressions under declarative policies with documented exit codes.",
     ["BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT or custom policy JSON",
      "Reusable GitHub composite action and pre-commit hook",
      "Exit codes: 0 pass Â· 1 gate failed Â· 2 bad invocation Â· 3 engine failure"],
     "$ upf-insight check soc.upf --baseline base.json --gate STRICT"),
    ("âŸ", "integrations", "CLI, web workspace, MCP",
     "One deterministic engine, three ways in.",
     ["Local vanilla-JS workspace: 22 pages, stdlib HTTP server, no build step",
      "MCP server exposing eight tools over JSON-RPC stdio",
      "The engine itself stays LLM-free"],
     "$ upf-insight web          # http://localhost:8585\n$ upf-insight-mcp           # JSON-RPC over stdio"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    files: dict[Path, str] = {SITE / "index.html": build_index()}
    for icon, slug, title, desc, points, term in FEATURE_DATA:
        files[SITE / "features" / f"{slug}.html"] = build_feature(
            icon, slug, title, desc, points, term)
    changed = 0
    for path, text in sorted(files.items()):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            if args.verify:
                print(f"business site stale: {path}")
                return 1
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            changed += 1
    stale = SITE / "assets"
    if stale.exists():
        import shutil

        shutil.rmtree(stale)
    if args.verify:
        print(f"business site verified ({len(files)} files)")
        return 0
    print(f"wrote {len(files)} files ({changed} changed) to "
          f"{SITE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
