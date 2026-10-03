# `scd2.py` — Silver SCD Type 2 upsert

## Purpose
Maintains full history for conformed dimensions (e.g. `DimCustomer`, `DimProperty`) using **Slowly Changing Dimension Type 2** on Delta Lake. Each business key keeps one *current* row (`is_current = true`) and any number of expired historical versions bounded by `effective_start` / `effective_end`.

## Public functions
| Function | Pure? | What it does |
| --- | --- | --- |
| `add_scd2_metadata(df, cde_cols)` | Yes | Adds `record_hash` (SHA‑256 over Critical Data Elements only), `effective_start`, `effective_end`, `is_current`. |
| `compute_updates(staged, current, business_key)` | Yes | Returns staged rows that are **new** or whose **CDE hash changed**. |
| `build_merge_payload(updates, current, business_key)` | Yes | Builds the two‑branch MERGE payload using the `mergeKey = NULL` trick. |
| `upsert_scd2(spark, staged_df, target_path, business_key, cde_cols)` | No (Delta) | Orchestrates the Delta `MERGE`. |

The first three are **Delta‑free** so they unit‑test on a plain Spark session; `upsert_scd2` imports `DeltaTable` lazily.

## The bug this fixes
A common first draft does `merge(...expire old...)` and then `staged.write.mode("append")`. That re‑appends **unchanged** keys, producing **duplicate `is_current = true`** rows. The two‑step pattern here:
1. `mergeKey = NULL` rows → cannot match → **INSERT** a new current version (for changed keys).
2. `mergeKey = <key>` rows → **match & expire** the old current version (changed keys) or **INSERT** brand‑new keys.

Unchanged keys are filtered out in `compute_updates`, so they are never touched. The test `test_rerun_unchanged_no_duplicates` locks this behaviour in.

## Design notes
- **Hash over CDEs only.** Audit columns (`ingestion_ts`, surrogate keys) are excluded so processing latency can’t fake a change.
- **NULL token (`∅`).** `concat_ws` skips NULLs, which would make `(A, NULL)` and `(A)` collide; coalescing to a sentinel prevents that.
- **Deletes/tombstones are out of scope** — a key absent from a later feed stays current. Handling source deletes (soft‑delete flag or full‑snapshot diff) is a documented extension.
- **Multi‑key dimensions:** generalise `business_key: str` to a list and adjust the merge condition; kept single‑key here for readability.

## How it runs
Called by `notebooks/02_silver_scd2.py` on Databricks and by `src/data_generator.py` in the local demo. Validated by `tests/test_scd2.py` on a local Spark + Delta session (see `tests/conftest.py`).
