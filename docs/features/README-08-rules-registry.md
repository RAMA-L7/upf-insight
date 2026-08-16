# Feature 08 — Rules Registry

> Backend: `engine/rules/rules_registry.py`
> Docs: [docs/upf/RULES_REGISTRY.md](../upf/RULES_REGISTRY.md)

## What it does

Holds the canonical list of rule codes — the contract between the checker,
reports, the workspace, and (planned) CI policy.

## Rule shape

```python
Rule(code="UPF-040", severity="error", layer="STRATEGY",
     title="Isolation on non-always-on supply",
     description="Isolation cell uses a switchable (non-always-on) supply.")
```

## Layering

- Layer 1 Syntax: UPF-001…006
- Layer 2 Reference: UPF-010…016
- Layer 3 Supply/domain: UPF-020…025
- Layer 4 PST: UPF-030…036
- Layer 5 Strategy: UPF-040…073
- Layer 6 Design (v2): UPF-080…084

## Registry vs implementation

The registry is the **contract**; not every rule has a handler yet. Rules
without a handler are dormant — the checker skips them and the
implementation-status table (in the docs) records the gap. This keeps the
registry stable while implementation catches up layer by layer.

## Access

- `registered_rules()` — the ordered list.
- `get_rule(code)` — lookup.
- `GET /api/rules` — served to the workspace.