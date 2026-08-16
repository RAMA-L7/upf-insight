# Feature 12 — 5-Minute UPF Test Drive

> **Backend:** `engine` (validate) · `diff/differ` · `engine/policy` ·
> `report/reporter`
> **CLI:** `upf-insight check / diff / report / web`
> **Fixture:** `tests/examples/cpu_subsys/` (realistic CPU-subsystem
> power-intent, V1 known-good + V2 regressed + design context)

## What this is

A complete walkthrough of the UPF-Insight loop on a believable block:

```
Install → Load UPF → Analyze → Understand findings → Compare V1/V2
→ Gate/regression check → Report
```

Every command below runs against the **real engine** — no mocked results.
The sample is a realistic CPU subsystem: switchable CPU domain, always-on
control domain, 1.8 V I/O domain, SRAM retention domain, one power switch,
isolation, level shifting, retention, and a complete Power State Table.

**The V2 file contains one subtle, realistic regression** (a level shifter
was removed on the 1.8 V I/O boundary). Finding it is the point of the demo.

## 1. Install (30 seconds)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e .
```

## 2. Load + analyze the known-good version

```bash
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v1.upf
```

Expected: **PASS** (0 errors), readiness **REVIEW_REQUIRED** (honest
advisories — static checks can only partially confirm always-on status),
coverage **1.0 / 1.0**.

## 3. Understand the findings on the regressed version

```bash
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v2.upf
```

Expected: **FAIL** with `UPF-061` errors — domains `PD_CPU` (1.0 V),
`PD_AO` (1.0 V) and `PD_SRAM` (1.0 V) cross into the 1.8 V `PD_IO` domain
with **no level shifter**. Readiness is **BLOCKED**.

Each finding answers three questions:

| Question | Answer in the finding |
|---|---|
| WHAT is wrong? | Domains differ in voltage but no level shifter is declared |
| WHERE? | `:line` points at the involved domain's declaration line |
| WHY does it matter? | A raw 1.0 V → 1.8 V crossing can damage or mis-read receivers |

## 4. Compare V1 / V2 (the diff)

```bash
upf-insight diff tests/examples/cpu_subsys/cpu_subsys_v1.upf \
               tests/examples/cpu_subsys/cpu_subsys_v2.upf
```

Expected: `MODIFY strategy 'level_shifter' count 1 -> 0` — the removed
level shifter is visible as a structural change.

## 5. Gate / regression check (CI)

```bash
# save the known-good result as the baseline
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v1.upf \
    --save-baseline baseline.json

# gate the new revision against it
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v2.upf \
    --baseline baseline.json --gate STRICT
echo $?    # 1 — the gate blocks the regression
```

Exit-code contract: **0** pass · **1** gate failed · **2** invalid
invocation · **3** engine failure. An engine failure can never produce a
passing result.

## 6. Report

```bash
upf-insight report tests/examples/cpu_subsys/cpu_subsys_v2.upf -o report.html
```

The self-contained HTML report contains the real findings (UPF-061 ×3),
severity, source lines, support boundary, readiness verdict, and coverage.

## Design-aware mode (optional)

The fixture ships with a matching design context
(`cpu_subsys_design.json` — instances, ports, signals, liberty PG pins).
Enable the design-aware rules (UPF-080…084) with:

```bash
upf-insight check tests/examples/cpu_subsys/cpu_subsys_v1.upf \
    --netlist tests/examples/cpu_subsys/cpu_subsys_design.json
```

V1 stays clean in design-aware mode (all instances/signals/PG pins
resolve); V2 remains BLOCKED on UPF-061.

## Trust framing (never weakened)

- **PASS ≠ power-intent correct.** A clean result means no deterministic
  rule fired against the modeled intent.
- **Coverage ≠ correctness.** Coverage reports what the intent *touches*,
  not that it is safe.
- **CI PASS ≠ low-power closure.** The gate protects against regression; it
  does not verify timing, IR, or signoff.
- **Static layer limits.** Always-on claims, crossings and electrical
  behavior are PARTIAL / NETLIST_REQUIRED without a full supply-state model
  and netlist — the support boundary always says which.
