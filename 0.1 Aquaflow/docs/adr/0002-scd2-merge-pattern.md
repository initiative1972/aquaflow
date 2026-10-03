# ADR 0002 — Two-step Delta MERGE for SCD Type 2

- **Status:** Accepted
- **Date:** 2026-10-03
- **Deciders:** Technical Lead (portfolio)
- **Related:** `src/transforms/scd2.py`, `tests/test_scd2.py`, ADR 0001 (reconciliation)

## Context
The legacy billing procedure rebuilt dimension state with cursors and full
truncate‑reload, losing history. The target lakehouse must keep **SCD Type 2**
history (`effective_start`, `effective_end`, `is_current`) on Delta, fed by a
periodic change feed that mixes new, changed, and unchanged keys.

A frequently‑seen implementation performs a MERGE to expire changed rows and
then appends the entire staged batch. This re‑inserts **unchanged** keys and
produces **duplicate `is_current = true`** rows — a correctness defect that is
invisible until a downstream count or join doubles.

## Decision
Use the canonical **two‑step / null‑merge‑key** pattern:

1. Compute `updates` = staged rows that are new **or** whose CDE hash differs
   from the current version (unchanged keys are dropped here).
2. Build a payload of two branches:
   - changed keys with `mergeKey = NULL` → cannot match → **INSERT** a new
     current version;
   - all `updates` with `mergeKey = <business_key>` → **match & expire** the old
     version (changed) or **INSERT** (brand‑new).
3. MERGE on `CAST(t.<key> AS STRING) = s.mergeKey AND t.is_current = true`,
   with `whenMatchedUpdate` (set `is_current = false`, close `effective_end`)
   and `whenNotMatchedInsert`.

The change hash covers **Critical Data Elements only**, so audit/metadata
columns never trigger a spurious new version.

## Consequences
**Positive**
- No duplicate current rows; one current version per key (asserted by tests).
- Business logic is pure and Delta‑free, so it unit‑tests on local Spark and
  lifts to Databricks unchanged.

**Negative / trade‑offs**
- The null‑merge‑key payload reads as non‑obvious; mitigated by comments, this
  ADR, and tests.
- Source **deletes/tombstones** are out of scope — an absent key stays current.
  A later ADR will choose soft‑delete flag vs. full‑snapshot diff.
- Single business key for readability; composite keys need the condition and
  payload generalised to a key list.

## Alternatives considered
- **Truncate‑reload:** simplest, but destroys history — fails the requirement.
- **`MERGE ... WHEN NOT MATCHED BY SOURCE`:** handles deletes but needs a full
  snapshot each run; heavier and not required by the current feed.
- **Framework (e.g. DLT APPLY CHANGES):** less code, but hides the logic the
  team needs to understand and test; revisit once standardised on Databricks.
