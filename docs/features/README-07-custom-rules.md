# Feature 07 — Custom Rules (planned)

> Backend: TBD (v0.2.0)

## What it does (planned)

Lets teams express their own power-intent checks as YAML rulesets validated
against the same `PowerIntentModel` — without touching the core registry.

## Sketch (planned shape)

```yaml
rules:
  - code: CUST-001
    severity: error
    layer: STRATEGY
    title: Domain must have isolation
    check: "every domain referenced by a switch must appear in isolation strategies"
```

## Trust boundary

Custom rules run at the same deterministic engine level and must report the
same evidence shape (rule, severity, message, file, line, support). A custom
rule that cannot be proven statically must declare `PARTIALLY_VALIDATED`.

## Why model-based

Custom rules query the power-intent model, so they get the same hierarchical,
stateful view the built-in rules get — cross-object semantics, not regex on
text.