# `reconciliation.py` — dual-run reconciliation gate

## Purpose
Produces the **equivalence evidence** a data steward signs before the legacy system is decommissioned. It does not claim "zero defect"; it proves the modern output matches the legacy output **within an agreed tolerance**, and trips a circuit breaker when it doesn't.

## Public functions
| Function | What it does |
| --- | --- |
| `find_mismatches(legacy, modern, keys, cde_cols)` | Full‑outer join on `keys`; returns rows missing on one side or with a differing CDE hash. |
| `reconcile(legacy, modern, keys, cde_cols, tolerance_pct=0.01)` | Returns a result dict (`universe`, `mismatches`, `drift_pct`, `tolerance_pct`, `passed`). **Never raises.** |
| `enforce(result)` | Raises `ValueError` if `passed` is `False` — the pipeline circuit breaker. |

## Why compute and enforce are separate
Tests and dashboards need to **inspect** a failing reconciliation (how much drift, how many rows) without an exception interrupting them. Pipelines need a hard **stop**. Splitting the two keeps both honest.

## Design notes
- **Hash over CDEs only**, with the same `∅` NULL sentinel as `scd2.py`, so audit columns and processing latency can’t create false mismatches. `test_audit_columns_excluded_from_hash` proves this.
- **Union denominator.** `drift_pct` divides by the distinct union of keys on both sides — a row only in legacy *or* only in modern still counts. (Dividing by `legacy.count()` alone would hide extra rows in the modern set.)
- **Macro + micro.** This module is the micro (row‑hash) gate; macro aggregate checks (e.g. `SUM(total_billed)` by date) live alongside in `notebooks/04_reconciliation.py` and should run first as a cheap pre‑filter.
- **Tolerance is a policy, not a constant.** Real CDE lists and per‑domain tolerances belong in `config/reconciliation_rules.json`.

## Tests (`tests/test_reconciliation.py`)
- identical datasets → `drift_pct == 0`, `passed`, `enforce` does not raise;
- one changed amount → `mismatches == 1`, breaker trips;
- a dropped row → counted as a mismatch, `universe` unchanged;
- an extra audit column with a fresh timestamp → still passes (excluded from hash).
