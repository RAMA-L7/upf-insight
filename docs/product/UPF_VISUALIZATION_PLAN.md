# UPF-Insight — Visualization & UX Plan

> **Document kind:** product plan / architecture input.
> **Date:** 2026-08-18 · **Version:** v0.3.0
> **Status:** planning — no commitment. This document captures a set of
> visualization and UX opportunities for UPF-Insight, prioritized for
> implementation sequencing.

---

## Architectural boundary

> **Mimo is a design-time tool, not a runtime dependency.**
> It must never become the authority for UPF correctness.

### Design time

```
                 ┌──────────────────────┐
                 │ Mimo / visual model  │
                 │ exploration          │
                 └──────────┬───────────┘
                            │
                       design decisions
                            │
                            ▼
                    Human-approved UI
                            │
                            ▼
                        Production
```

Mimo generates visual concepts and layout alternatives during the design
phase. The human reviews, selects, and approves the visual direction.
Mimo has no role at runtime.

### Runtime

```
UPF ──► Parser ──► PowerIntentModel ──► Rule Engine ──► Findings
                         │                         │
                         │                         │
                         └──────────┬──────────────┘
                                    ▼
                              SVG / UI layer
```

The deterministic engine is the only authority. The SVG/UI layer consumes
`PowerIntentModel` and `Finding[]` — it never calls the engine and never
produces findings.

**Never at runtime:**

```
UPF → AI → "looks wrong" → validator finding
```

**Always at runtime:**

```
UPF → deterministic engine → finding → SVG / UI layer
```

**Why the distinction matters:** Mimo should not be a runtime dependency
at all. The design-time/runtime separation eliminates future ambiguity —
the workspace ships with vanilla JS + SVG, no model API calls, no network
requests to an image generation service.

---

## Visualization contract

The SVG renderer should not understand UPF semantics. The semantic graph
adapter understands semantics; the renderer understands visualization
primitives. This prevents `viz.js` from becoming tightly coupled to the
validator's internal data structures.

### Data flow

```
UPF semantics
     ↓
semantic adapter        ← understands PowerIntentModel
     ↓
VisualizationModel      ← knows nothing about UPF
     ↓
SVG renderer            ← knows only visual primitives
```

### VisualizationModel

```python
@dataclass
class DomainNode:
    """A power domain rendered as a container."""
    name: str
    voltage: Optional[float]
    is_switchable: bool
    status: str  # OK | WARNING | ERROR
    children: List[str]  # element names

@dataclass
class SupplyNode:
    """A supply net/set/port rendered as a rail."""
    name: str
    kind: str  # net | set | port
    connected_to: List[str]
    status: str

@dataclass
class SwitchNode:
    """A power switch rendered as a gate."""
    name: str
    input_supply: str
    output_supply: str
    control_port: str
    on_state: Optional[str]
    status: str

@dataclass
class StrategyEdge:
    """An isolation, level-shifter, or retention strategy rendered as a
    boundary protection, directional bridge, or memory marker."""
    kind: str  # isolation | level_shifter | retention
    from_domain: str
    to_domain: str
    location: str
    direction: Optional[str]  # low_to_high | high_to_low | both
    status: str

@dataclass
class ControlEdge:
    """A control signal rendered as a dashed signal line."""
    name: str
    source: str
    target: str
    sense: Optional[str]

@dataclass
class FindingAnnotation:
    """A finding rendered as a status annotation on a node or edge."""
    rule: str
    severity: str  # error | warning | info
    message: str
    target_node: Optional[str]
    target_edge: Optional[str]
    dependency_of: List[str]  # downstream findings blocked by this one
```

### Why this matters

Without this contract, the renderer accumulates UPF-specific knowledge:

```
❌  SVG code containing 74-rule knowledge
```

With this contract, the layers are clean:

```
✅  PowerIntentModel → adapter → VisualizationModel → renderer
```

The renderer renders nodes, edges, status, and annotations. It never
queries `PowerIntentModel.domains` or checks rule codes.

---

## Visual grammar

Once the exploration phase selects a visual direction, the following
primitives must be fixed before implementation. Every visualization in
the plan uses these same primitives — no per-view custom styles.

| UPF concept | Visual primitive | Shape | Notes |
|---|---|---|---|
| Domain | Container | Rounded rect with label | Filled by voltage; outline by status |
| Supply | Rail | Horizontal line / bar | Width by hierarchy depth |
| Switch | Gate | Diamond or trapezoid | Input → gate → output |
| Isolation | Boundary protection | Slash / barrier on edge | Between domains |
| Level shifter | Directional bridge | Arrow with direction marker | LOW→HIGH or HIGH→LOW |
| Retention | Memory marker | Dotted outline or save icon | On domain boundary |
| Control signal | Dashed line | Dashed arrow | From control port to target |
| Finding | Status annotation | Badge / callout | Positioned on affected node/edge |
| Impossible state | Violation marker | X or ⚠ on supply state | Ties to UPF-039 |

**Fixed mappings** (once chosen, never change per-view):

```
Domain       = container
Supply       = rail
Switch       = gate
Isolation    = boundary protection
Level shift  = directional bridge
Retention    = memory marker
Control      = dashed signal
Finding      = status annotation
```

The same grammar represents switches, LS, ISO, retention, and PST
across all views. If a primitive doesn't fit a new view, extend the
grammar — don't invent a one-off style.

---

## Current state

The workspace (`upf-insight web`) already ships with:

| Existing capability | File | Notes |
|---|---|---|
| Readiness dimension rail | `viz.js` | 5-dimension UPF readiness bar |
| Supply coverage strips | `viz.js` | Per-domain element-set bit coverage |
| PST state inventory | `viz.js` | Supply-state ON/OFF matrix |
| Domain relation matrix | `pages.js` | Cross-domain ISO/LS/RET/SW/CTRL grid |
| Finding table | `pages.js` | Rule-severity-line listing |
| Inspector panel | `index.html` | Right-side detail on click |
| Source viewer | `components.js` | Line-highlighted UPF source |

This plan builds **on top of** these foundations, not replacing them.

---

## Prioritized visualization ideas

### 🥇 1. UPF Semantic Graph Visualizer

**Goal:** Interactive power-domain topology view from the `PowerIntentModel`.

**What it shows:**

```
                    TOP
                     │
          ┌──────────┴──────────┐
          │                     │
       AON 1.0V             CORE 0.8V
          │                     │
          │                 ┌───▼────┐
          │                 │ POWER  │
          │                 │ SWITCH │
          │                 └───┬────┘
          │                     │
          │                 VDD_CORE
          │                     │
          │                 ┌───▼────┐
          │                 │ CORE   │
          │                 └────────┘
          │
          └──── Isolation / LS ────┘
```

**Data source:** `PowerIntentModel.domains`, `.switches`, `.supply_nets`,
`.supply_sets`, `.supply_ports`, `.isolation`, `.level_shifters`.

**Interaction:** Click any node → inspector shows detail (e.g., clicking
`SW_CORE` shows input/output/control/on-state/off-state/domain/status).

**Implementation notes:**
- SVG-based, rendered client-side from the model JSON
- Layout algorithm: hierarchical tree (supplies top → domains bottom)
- Power switches, isolation, level shifters shown on edges
- Color-coded by voltage domain; monochrome ink option for dark mode
- No external graph library — keep it vanilla JS like the rest of the workspace

**Effort estimate:** Large (2–3 sessions). Core visualization foundation.

---

### 🥈 2. Finding → Visual Explanation

**Goal:** Replace pure-text finding explanations with visual diagrams
showing *why* the engine flagged something.

**What it shows:**

```
UPF-062 — Wrong level-shifter direction

              ACTUAL

CORE 0.8V ───────────────► AON 1.0V
          HIGH → LOW ❌


              EXPECTED

CORE 0.8V ───────────────► AON 1.0V
          LOW → HIGH ✅
```

**Data source:** `Finding` object + `PowerIntentModel` context (voltages,
strategies, domains).

**Categories to visualize:**

| Rule family | Visual |
|---|---|
| UPF-060–066 (isolation/LS direction) | Supply voltage arrows with direction indicators |
| UPF-070–073 (switch topology) | Switch node diagram with broken connections |
| UPF-030–039 (PST consistency) | Power-state matrix with impossible-state flag |
| UPF-010–019 (supply topology) | Supply chain with undefined/missing nodes |
| UPF-080–084 (design-aware) | Instance/signal cross-reference diagram |

**Implementation notes:**
- Rendered in the inspector panel on finding click
- Each rule family gets a dedicated visual template
- Falls back to text for rule families without a visual template yet
- SVG generators per category, composed into `inspector-body`

**Effort estimate:** Medium per category (1 session each). Start with
isolation/LS and switch families — highest bang-for-buck.

---

### 🥉 3. Power-State Visualizer

**Goal:** Visual power-state table with ON/OFF indicators and
impossible-state flagging.

**What it shows:**

```
### ALL_ON

VDD       🟢
VDD_CORE  🟢
CORE      🟢
AON       🟢

### CORE_OFF

VDD       🟢
VDD_CORE  🔴
CORE      🔴
AON       🟢

### SYSTEM_OFF

VDD       🔴
VDD_CORE  🔴
CORE      🔴
AON       🔴
```

**Impossible state detection:**

```
VDD       🔴
VDD_CORE  🟢   ← ❌ impossible
```

**Data source:** `PowerIntentModel.psts`, `PowerIntentModel.supply_states`,
`PowerIntentModel.switches`. Cross-references with `UPF-039` rule logic.

**Implementation notes:**
- Extends existing PST inventory (`viz.js::pstMatrixHtml`) with visual
  state cards
- Each state shown as a vertical supply stack with ON/OFF color indicators
- Impossible states flagged with warning icon and UPF-039 reference
- Click a state → show transitions to/from it

**Effort estimate:** Small (1 session). Builds on existing PST infrastructure.

---

### 4. UPF Mutation Playground

**Goal:** Interactive educational/debugging tool turning the adversarial
mutation suite into a living demonstration.

**What it shows:**

```
VALID DESIGN
       │
       ▼
   POWER SWITCH
       │
       ▼
   VDD_CORE
       │
       ▼
      CORE

        ↓ introduce mutation

BROKEN DESIGN

VDD
 │
 ▼
SWITCH
 │
 X──── VDD_CORE disconnected

        ↓
UPF-073 ❌
```

**Interaction:** Buttons to break supply, isolation, level shifter,
retention, PST, always-on. Each click shows:
1. The original topology
2. The broken topology
3. The exact rule that catches it

**Data source:** Mutation test fixtures (`tests/examples/`) + rule
definitions (`upf_rules.py`).

**Implementation notes:**
- Standalone page in the workspace
- Pre-built mutation scenarios from the test suite
- SVG topology diagrams per scenario
- Links to the specific rule documentation

**Effort estimate:** Medium (2 sessions). Requires curating mutation
scenarios and building the topology renderer.

---

### 5. Architecture & Documentation Diagrams

**Goal:** Generate visual diagrams for technical documentation.

**Target diagrams:**

| Diagram | Content |
|---|---|
| UPF validation pipeline | Preprocess → Model → Rules → Findings |
| Semantic graph architecture | Domains, supplies, switches, strategies |
| Finding dependency graph | How findings cascade |
| Evidence boundary | What UPF-Insight proves vs. doesn't |
| Mutation testing pipeline | Generate → Inject → Validate → Assert |
| Generator → Validator round trip | Generate UPF → Parse back → Compare |
| Power-domain architecture | Domain hierarchy and supply topology |
| PST state transitions | State machine of power states |

**Implementation notes:**
- SVG diagrams embedded in docs or generated on-demand
- Source diagrams as `docs/diagrams/*.svg` or as HTML in the workspace
- Can be generated from the model JSON at build time

**Effort estimate:** Small per diagram (0.5 session each). High value
for onboarding, README, and future demos.

---

### 6. Power Intent Map View

**Goal:** Replace the current text-based finding/rule/source-line view
with a visual map of the entire power intent.

**What it shows:**

```
┌───────────────────────────────────────────┐
│ POWER INTENT MAP                          │
│                                           │
│   AON                 CORE                │
│  1.0V                0.8V                │
│   🟢                    🟢                │
│    │                     │                │
│    │                Power Switch          │
│    │                     │                │
│    │                  VDD_CORE             │
│    │                     │                │
│    └────── LS / ISO ─────┘                │
│                                           │
└───────────────────────────────────────────┘
```

**Data source:** Same as #1 (semantic graph), but at a higher level —
showing the full intent without interactive drill-down.

**Implementation notes:**
- Overview card on the home/overview page
- Read-only, static layout (interactive drill-down is #1)
- Click a domain → navigate to its detail page

**Effort estimate:** Small (1 session). Overlaps with #1; could be
a simplified render of the same SVG.

---

### 7. Cascade Finding Visualization

**Goal:** Show how findings depend on each other in the dependency-aware
finding architecture.

**What it shows:**

```
UPF-010 — Undefined supply
    │
    ├── UPF-070 — Switch supply undefined
    └── UPF-073 — Switch output disconnected
         blocked_by ↑
```

**Data source:** `Finding` dependency relationships + rule registry.

**Implementation notes:**
- Rendered in the inspector or as a collapsible tree in the finding list
- Click a finding → see its upstream/downstream dependencies
- Monochrome SVG tree diagram

**Effort estimate:** Small (1 session).

---

### 8. UPF Explorer Panel

**Goal:** Hierarchical browse of all UPF objects with relationship graphs.

**What it shows:**

```
UPF Explorer
─────────────────────────────

Domains       Supplies       Strategies
  4             8               12

CORE
├─ Primary: SS_CORE
├─ Voltage: 0.8V
├─ Switch: SW_CORE
├─ Isolation: ISO_CORE_AON
├─ LS: LS_CORE_AON
└─ Retention: RET_CORE
```

**Data source:** `PowerIntentModel` — all entities.

**Implementation notes:**
- Sidebar or dedicated page
- Tree view with expand/collapse
- Click any item → relationship graph (#1) or detail panel

**Effort estimate:** Medium (1–2 sessions).

---

### 9. Rule Category Visual Guides

**Goal:** Visual explanations for each of the 74 UPF rule categories,
used for onboarding and documentation.

**Categories:**

```
Supply Topology          Power Switching
Isolation                Level Shifting
Retention                Always-On
Power States             PST Consistency
Evidence Boundaries      Finding Dependencies
```

**Example — Isolation:**

```
CORE OFF
   │
   X
   │
[ ISOLATION ]
   │
   ▼
 AON
```

**Implementation notes:**
- Static SVG/HTML diagrams
- Embedded in `docs/upf/` or rendered in the workspace documentation page
- Each category gets one diagram + short explanation

**Effort estimate:** Small per category (0.5 session each). 10 categories
= ~5 sessions total.

---

### 10. "Why did UPF-Insight flag this?" Visual Explanations

**Goal:** Make every finding visually self-explanatory.

This is the overarching UX principle behind ideas #2, #3, and #7. The
implementation is:

1. **For isolation/LS findings** (#2): show voltage arrows with direction
2. **For switch findings** (#2): show supply chain with break points
3. **For PST findings** (#3): show impossible-state indicators
4. **For cascade findings** (#7): show dependency tree

**Effort estimate:** Captured in the estimates above.

---

## Implementation sequencing

| Phase | Items | Sessions | Dependencies |
|---|---|---|---|
| **Phase 1** — Foundation | #1 (Semantic Graph), #3 (Power-State) | 3–4 | PowerIntentModel API |
| **Phase 2** — Finding UX | #2 (Visual Explanations), #7 (Cascade) | 2–3 | Phase 1 renderer |
| **Phase 3** — Education | #4 (Mutation Playground), #5 (Doc Diagrams) | 3–4 | Test suite fixtures |
| **Phase 4** — Polish | #6 (Intent Map), #8 (Explorer), #9 (Rule Guides) | 3–4 | Phase 1 foundation |

---

## Design principles

1. **Monochrome ink first.** Color is for status, not decoration. Works
   in light mode, dark mode, and print.
2. **No external dependencies.** Vanilla JS + SVG. No D3, no React, no
   graph libraries.
3. **Reduced-motion respected.** All animations use `prefers-reduced-motion`.
4. **Labels escaped.** Every string through `esc()` — no raw HTML from
   model data.
5. **Presentation never produces findings.** Visual layers consume
   `PowerIntentModel` + `Finding[]` — they never call the engine.
6. **Graceful fallback.** If the model is incomplete or the visual
   template doesn't exist for a rule family, fall back to the existing
   text-based display.

---

## Appendix: Mimo design exploration prompts

The following prompts are structured for use with an image generation
model (Mimo 2.5) during **design-time exploration only**. The goal is
not to use generated images directly in production — it is to discover
the best visual grammar before implementation.

### Design exploration matrix

Generate and compare **3 concepts × 4 views = 12 visual explorations**,
then choose one consistent visual language:

| | Overall architecture | Finding explanation | PST | Mutation |
|---|---|---|---|---|
| **Concept A:** Classic EDA schematic | | | | |
| **Concept B:** Semantic graph | | | | |
| **Concept C:** Power-domain map | | | | |

### Evaluation criteria

For each of the 12 combinations, evaluate against these criteria:

| Criterion | Question | Weight |
|---|---|---|
| **Semantic accuracy** | Can every visual element map to a real `PowerIntentModel` object? | **High** |
| **Implementation feasibility** | Can vanilla JS + SVG reproduce it without external libraries? | **High** |
| **EDA clarity** | Can an engineer understand the topology immediately? | High |
| **Finding clarity** | Does the visualization explain *why* something failed? | High |
| **Consistency** | Can the same grammar represent switches, LS, ISO, retention and PST? | High |
| **Density** | Can complex designs remain readable at scale? | Medium |
| **Dark/light** | Does it work in both modes with monochrome ink? | Medium |
| **Accessibility** | Does meaning survive without color (outline, fill, shape)? | Medium |

**Decision rule:** Weight semantic clarity and implementation feasibility
above visual beauty. The best Mimo output is the one whose visual grammar
a vanilla JS + SVG renderer can faithfully reproduce — not the one that
looks most impressive as a static image.

### Prompt 1 — Semantic Graph

```
Design a professional EDA visualization for a deterministic UPF
validation product.

Show:

TOP
 ├── AON domain — 1.0V
 └── CORE domain — 0.8V
       │
       ├── Power switch SW_CORE
       │      input: VDD
       │      output: VDD_CORE
       │      control: core_power_en
       │
       ├── Isolation CORE → AON
       │      location: parent
       │      clamp: 0
       │
       ├── Level shifter CORE → AON
       │      low → high
       │
       └── Retention
              save / restore
              retained elements

The visualization must communicate:
- supply topology
- domain boundaries
- voltage differences
- switchable vs always-on domains
- isolation
- level shifters
- retention
- control signals

Style:
- professional EDA engineering software
- technical, restrained, precise
- monochrome-first
- status colors only
- no decorative gradients
- no futuristic AI aesthetic
- no 3D
- no unnecessary animation
- suitable for dark and light UI
```

**Goal:** Discover the best visual grammar for supply topology and
domain relationships. Not necessarily to use the image directly.

### Prompt 2 — Finding Explanation ("Why did UPF-Insight flag this?")

```
Design a finding explanation card for a UPF validation tool.

Finding:

UPF-062

CORE = 0.8V
AON = 1.0V

Actual:
CORE → AON
declared: high_to_low

Expected:
CORE → AON
required: low_to_high

The visualization must make the semantic error understandable in under
3 seconds without reading the full text.

Style:
- professional EDA engineering software
- monochrome-first, status colors only
- the "wrong" direction must be immediately visually obvious
- the "correct" direction must be clearly shown
- compact, suitable for an inspector panel
```

**Goal:** Explore how to make isolation/level-shifter findings
visually self-explanatory. This is the highest-value UX problem.

### Prompt 3 — Power-State Table Visualization

```
Design a power-state visualization for a UPF validation tool.

Valid:

VDD       ON
VDD_CORE  OFF

Invalid:

VDD       OFF
VDD_CORE  ON

The visualization must allow an EDA engineer to immediately recognize:

"Power cannot appear downstream when the switch input is OFF."

Show:
- two power states side by side (valid vs invalid)
- supply ON/OFF status for each state
- the impossible state must be visually flagged
- the causal relationship (switch input OFF → downstream cannot be ON)
  must be visually obvious

Style:
- professional EDA engineering software
- monochrome-first
- ON/OFF indicated by fill or outline, not just color
- compact, suitable for a PST analysis page
```

**Goal:** Explore how impossible power states should look. Ties directly
to UPF-039 rule logic.

### Prompt 4 — Cascade Finding Dependency Tree

```
Design a dependency visualization for UPF validation findings.

Given:

UPF-010 ERROR
Undefined supply

    ├── UPF-070
    │     blocked_by UPF-010
    │
    └── UPF-073
          blocked_by UPF-010

Design a compact dependency visualization that clearly distinguishes:
- root-cause findings (the source of the problem)
- blocked/dependent findings (consequences of the root cause)

The root cause must be visually dominant. Blocked findings must be
visually subordinate. The "blocked_by" relationship must be clear.

Style:
- professional EDA engineering software
- monochrome-first
- compact, suitable for a finding list or inspector panel
- tree-like layout, not a flat list
```

**Goal:** Explore how finding cascades should be visualized. This
communicates the semantic hardening architecture.

### Prompt 5 — Mutation Playground Interaction

```
Design an interactive mutation playground for a UPF validation tool.

Starting state (valid):

VDD
 │
 ▼
SW_CORE
 │
 ▼
VDD_CORE
 │
 ▼
CORE

Mutation applied:

VDD
 │
 ▼
SW_CORE
 │
 X──── VDD_CORE disconnected

Validator result:

UPF-073 ERROR

Design a visual interaction flow showing:

VALID
  ↓
INJECT MUTATION
  ↓
BROKEN
  ↓
VALIDATOR
  ↓
UPF-073

The flow must:
- clearly show the "before" and "after" topology
- make the break/disconnection visually obvious
- show the validator catching the defect
- feel like an educational demonstration, not a static diagram

Style:
- professional EDA engineering software
- monochrome-first
- sequential flow (top to bottom or left to right)
- suitable for a standalone educational page
```

**Goal:** Explore how to make the mutation testing suite into an
interactive demonstration. Could become the strongest product demo.

---

## Notes on using Mimo outputs

1. **Use outputs to discover visual grammar, not as production assets.**
   The generated images inform the SVG implementation — they are not
   embedded in the workspace.

2. **Choose one consistent visual language** from the exploration matrix
   before implementation. The coding agent should receive:
   - `UPF_VISUALIZATION_PLAN.md` (this document)
   - Chosen visual direction
   - Specific approved mockups
   - Existing UI constraints (`viz.js`, `pages.js`, `components.js`)

3. **Keep the name UPF-Insight** inside this technical plan. Use
   **Ṛta** for the broader product/brand where appropriate.

4. **Design time is cheap; runtime dependencies are expensive.** The
   exploration phase costs nothing in code. Adding a runtime dependency
   on an image generation API would violate the architectural boundary.
