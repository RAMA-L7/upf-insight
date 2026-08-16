"""CDP-driven browser smoke test for the UPF-Insight workspace.

Drives real Chrome via the DevTools Protocol: renders the SPA, clicks the
real buttons, waits on real async results, and records every console error.
Exit 0 = all steps PASS. Prints a per-step report.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

from websocket import create_connection

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = int(os.environ.get("CDP_PORT", "9341"))
BASE = "http://127.0.0.1:8670"
MARKER = f"cdp-smoke-{os.getpid()}"

console_errors = []
runtime_exceptions = []


def kill_leftovers():
    """Kill only prior smoke-test Chrome instances (never the user's browser)."""
    ps = ("powershell -NoProfile -Command "
          "\"Get-CimInstance Win32_Process | "
          "Where-Object { $_.CommandLine -like '*cdp-smoke-*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\"")
    subprocess.run(ps, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)


def launch_chrome():
    kill_leftovers()
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",
        f"--user-data-dir=/tmp/{MARKER}",
        "--window-size=1440,1000", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1)
            return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Chrome DevTools endpoint did not come up")


def get_page_ws():
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2) as r:
                targets = json.loads(r.read())
            for t in targets:
                if t.get("type") == "page":
                    return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("no page target")


class CDP:
    def __init__(self, ws_url):
        self.ws = create_connection(ws_url, timeout=60)
        self._id = 0

    def _recv_until(self, want_id):
        while True:
            msg = json.loads(self.ws.recv())
            if "id" in msg and msg["id"] == want_id:
                return msg
            self._event(msg)

    def _event(self, msg):
        method = msg.get("method", "")
        if method == "Runtime.exceptionThrown":
            d = msg.get("params", {}).get("exceptionDetails", {})
            runtime_exceptions.append(d.get("text", "") + " :: " +
                                      d.get("exception", {}).get("description", ""))
        elif method == "Runtime.consoleAPICalled" and msg.get("params", {}).get("type") == "error":
            console_errors.append("console.error: " + json.dumps(
                [a.get("value", "") for a in msg["params"].get("args", [])]))
        elif method == "Log.entryAdded":
            e = msg.get("params", {}).get("entry", {})
            if e.get("level") == "error":
                console_errors.append("log.error: " + e.get("text", ""))

    def send(self, method, params=None):
        self._id += 1
        want = self._id
        self.ws.send(json.dumps({"id": want, "method": method, "params": params or {}}))
        return self._recv_until(want)

    def js(self, expr):
        r = self.send("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True,
        })
        res = r.get("result", {}).get("result", {})
        if "exceptionDetails" in r.get("result", {}):
            runtime_exceptions.append("evaluate: " + r["result"]["exceptionDetails"].get("text", ""))
        return res.get("value")

    def navigate(self, url):
        self.send("Page.navigate", {"url": url})

    def wait(self, expr, timeout=15.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            v = self.js(expr)
            if v:
                return True
            time.sleep(0.25)
        return False


STEPS = []


def step(name, ok, detail=""):
    STEPS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def main():
    launch_chrome()
    cdp = CDP(get_page_ws())
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.send("Log.enable")

    # 1. Home catalog + nav
    cdp.navigate(BASE + "/")
    step("home renders catalog", cdp.wait(
        "document.querySelectorAll('.cap-card').length >= 15"), ">=15 cards")
    groups = cdp.js("""[...document.querySelectorAll('#main .page-title, .page-title')]
        .map(e => e.textContent).join(' | ')""")
    section_labels = cdp.js("""[...document.querySelectorAll('h2, .cap-title')]
        .map(e => e.textContent).join(' | ')""")
    step("home shows CORE/ANALYZE/ADVANCED/OUTPUT",
         all(g in (section_labels or "") for g in ["CORE", "ANALYZE", "ADVANCED", "OUTPUT & KNOWLEDGE"]),
         (section_labels or "")[:160])
    nav_labels = cdp.js("""[...document.querySelectorAll('.nav-group-label')]
        .map(e => e.textContent).join('|')""")
    step("nav has WORKSPACE group", "WORKSPACE" in (nav_labels or ""), nav_labels or "")
    step("no 'More tools' in nav", "More tools" not in (nav_labels or ""))
    hero_btns = cdp.js("""[...document.querySelectorAll('.hero-actions button')]
        .map(b => b.textContent.trim()).join(' | ')""")
    step("hero has 3 primary actions", "Test Drive" in hero_btns and "Validate" in hero_btns and "CI Gate" in hero_btns,
         hero_btns)

    # 2. Diff page — real samples + compare
    cdp.js("location.hash = '#/diff'")
    step("diff page renders", cdp.wait("!!document.querySelector('#df-run')"))
    cdp.js("document.querySelector('#df-sample-a').click()")
    time.sleep(0.6)
    cdp.js("document.querySelector('#df-sample-b').click()")
    time.sleep(0.6)
    la = cdp.js("document.querySelector('#df-a').value.length")
    lb = cdp.js("document.querySelector('#df-b').value.length")
    step("diff samples loaded", la > 500 and lb > 500, f"A={la}B={lb}")
    cdp.js("document.querySelector('#df-run').click()")
    step("diff result rendered", cdp.wait(
        "!!document.querySelector('#df-out') && (document.querySelector('#df-out').textContent.includes('change') || document.querySelector('#df-out .tbl'))"))
    diff_txt = cdp.js("document.querySelector('#df-out').textContent")
    step("diff shows semantic change", "level_shifter" in diff_txt and "MODIFY" in diff_txt,
         (diff_txt or "").replace(chr(10), " ")[:200])
    step("diff next actions present", cdp.js(
        "[...document.querySelectorAll('#df-out [data-diff-next]')].length >= 3"))

    # 3. CI Gate — STRICT on regressed V2
    cdp.js("location.hash = '#/gate'")
    step("gate page renders", cdp.wait("!!document.querySelector('#gt-run')"))
    cdp.js("document.querySelector('#gt-sample').click()")
    time.sleep(0.6)
    cdp.js("document.querySelector('#gt-run').click()")
    step("gate result rendered", cdp.wait(
        "!!document.querySelector('#gt-out') && document.querySelector('#gt-out').textContent.includes('Exit code')"))
    gate_txt = cdp.js("document.querySelector('#gt-out').textContent")
    step("gate FAIL exit 1", "FAIL" in gate_txt and "1" in gate_txt, gate_txt.replace(chr(10), " ")[:160])
    step("gate disclosure present", "signoff" in gate_txt)

    # 4. Reports — HTML generation
    cdp.js("location.hash = '#/reports'")
    step("reports page renders", cdp.wait("!!document.querySelector('#rp-run')"))
    cdp.js("document.querySelector('#rp-sample').click()")
    time.sleep(0.6)
    cdp.js("document.querySelector('#rp-run').click()")
    step("report frame rendered", cdp.wait("!!document.querySelector('.report-frame')"))
    step("report has real findings", cdp.js(
        "document.querySelector('.report-frame') && document.querySelector('.report-frame').srcdoc.includes('UPF-061')"))

    # 5. Test Drive — full regression workflow
    cdp.js("location.hash = '#/test_drive'")
    step("test drive renders", cdp.wait("!!document.querySelector('#td-run')"))
    cdp.js("""document.querySelector('#td-sample').value = 'regression'""")
    cdp.js("document.querySelector('#td-run').click()")
    step("regression workflow result", cdp.wait(
        "!!document.querySelector('#td-out') && document.querySelector('#td-out').textContent.includes('Semantic changes')"))
    td_txt = cdp.js("document.querySelector('#td-out').textContent")
    step("workflow shows metrics", "Errors" in td_txt and "Readiness" in td_txt)
    step("workflow next actions", cdp.js(
        "[...document.querySelectorAll('#td-out [data-td-next]')].length >= 4"))
    cdp.js("[...document.querySelectorAll('#td-out [data-td-next]')][0].click()")
    step("findings page opens from workflow", cdp.wait(
        "location.hash.includes('validator') && !!document.querySelector('#val-analyze')"))

    # 6. Nav RESULTS group appears after analysis
    nav2 = cdp.js("""[...document.querySelectorAll('.nav-group-label')]
        .map(e => e.textContent).join('|')""")
    step("RESULTS group visible after analysis", "RESULTS" in (nav2 or ""), nav2 or "")

    print()
    print(f"console errors: {len(console_errors)}")
    for e in console_errors:
        print("  -", e)
    print(f"runtime exceptions: {len(runtime_exceptions)}")
    for e in runtime_exceptions:
        print("  -", e)

    failed = [s for s in STEPS if not s[1]]
    print(f"\nRESULT: {len(STEPS) - len(failed)}/{len(STEPS)} steps PASS")
    try:
        subprocess.run(("powershell -NoProfile -Command "
                        "\"Get-CimInstance Win32_Process | "
                        f"Where-Object {{ $_.CommandLine -like '*{MARKER}*' }} | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\""),
                       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return 1 if (failed or console_errors or runtime_exceptions) else 0


if __name__ == "__main__":
    sys.exit(main())
