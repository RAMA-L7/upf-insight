Fix cross-file UPF elaboration by expanding `load_upf` at every load site and preserving object identity using scope plus declaring file. This recovers previously discarded hierarchical instances and prevents cross-scope false conflicts.

```
AnyCore load-set: 1546 -> 2663
Domains: 123 -> 278
Nets:    180 -> 474
PSTs:      5 -> 10
Per-file: 1337 -> 1337
Tests: 438 passed
```

## Why the finding count went up

**1546 and 2663 are not directly comparable as a quality metric, and the increase is not a regression.**

```
old model  -> incomplete representation -> 1546 findings
new model  -> expanded load sites      -> 2663 findings
                                          (previously invisible instances
                                           are now validated)
```

The old implementation discarded roughly 50 child instances, so it was never in a position to report findings living inside them. The new one validates substantially more of the actual UPF structure, which necessarily surfaces more findings. The like-for-like check is **per-file: 1337 -> 1337** — unchanged, which is what demonstrates single-file behaviour was not disturbed.

The previous tool was not validating the whole project. This one does more of it.

## The three defects

**1. `load_upf` did not expand per load site.** `build_model` walked a flat record list and tracked child scope in a dict keyed by *file basename*, so a child loaded into N scopes was built once:

```
load site A --\
load site B ---+--> same child file --> build once
load site C --/
```

AnyCore has **75 load sites across 25 distinct targets** — `PipeLineReg.upf` alone is loaded 30 times under 30 distinct scopes (`PIPEREG[0].fs1fs2Reg` …). ~50 instances were silently discarded. That discard is what made identically named objects *appear* to collide. Expansion now happens at the load site, recursively, in the scope the child loads into.

**2. Scope alone was not sufficient identity.** Seven of the nine `Core_OOO_PST` fragments never call `set_scope`; they are independent, complete files that all sit at top scope, so no scope-based scheme can separate them. Identity is now `(scope, declaring file)`. The unqualified key is kept whenever unambiguous, which is why single-file output is byte-identical.

**3. A regression found *by* measuring the first two.** `_detect_switch_output_overlap` grouped switches by bare output net name. Once expansion produced scope-distinct switches driving same-named `vout` nets, it reported **1585 false conflicts** (UPF-086 47 -> 1632). Caught because 1632 findings from 71 strategies did not reconcile with 51 possible pairs. Now keyed by `(scope, net)`; UPF-086 settles at 62.

## Ordering semantics preserved

Expansion is strictly ordered — `set_scope` remains positional and reordering the stream still changes the result. Construction was deliberately **not** made order-independent; `test_reordering_set_scope_changes_the_model` pins that.

## Grammar-layer false positives: 32 -> 126 occurrences

After cross-file expansion, known grammar-layer false-positive **occurrences** increased from 32 to 126 because previously discarded UPF instances are now validated. The underlying parsing defects are unchanged. The 126 occurrences originate from **8 source lines** across recovered scope instances (line 53 reported 59 times, line 61 reported 55 times).

The rate moved 1.4% -> 4.7%; that should not be read as degraded parser quality.

## Not assumed correct

**No rule was muted, re-registered, or severity-tuned.** Every count change is explained by the model becoming more faithful.

None of the new findings should be assumed correct merely because they appeared after expansion. **UPF-038's 620** grew because 30 recovered `PD_PIPEREG` instances each began reporting an unmodeled switch output; whether those are real per-instance violations, valid advisories, artifacts of the recovered model, another modelling defect, or cascades is **unadjudicated**. The same applies to the **1303 unresolved** findings (up from 747 — again, more of the project is now represented). Establishing which is the next milestone.

## Verification

- 438 passed (418 + 20 new), 0 xfail
- AnyCore deterministic over repeated runs; Tenstorrent deterministic
- 38 external files SHA-256 verified unchanged (digests match pre-change baseline)
- CLI smoke test passes
- Corpus read-only throughout