# Cutover Runbook — Legacy Billing → Databricks Lakehouse

Operational playbook for the dual‑run and production cutover. Written as a
**technical‑lead artefact**: it is about decisions, gates, and communication
under pressure, not just commands.

## 1. Phases
1. **Shadow / dual‑run** — legacy and modern run in parallel on the same inputs;
   modern output is not consumed. Reconciliation runs each cycle.
2. **Validation (SIT → UAT)** — mock migrations; defects logged and resolved;
   stewards review reconciliation reports.
3. **Cutover** — reporting repointed to Gold; legacy frozen (read‑only).
4. **Decommission** — after an agreed clean dual‑run window.

## 2. Go / No-Go gate (per cycle)
| Signal | Go | No‑Go |
|---|---|---|
| Micro reconciliation drift | ≤ tolerance (e.g. 0.01%) | > tolerance |
| Macro aggregate variance (`SUM(total_billed)` by day) | ≤ 0.05% | > 0.05% |
| Great Expectations suite | all pass | any critical fail |
| Late‑arriving backlog | drained within T+1 window | still draining |

The reconciliation **circuit breaker** (`reconciliation.enforce`) is the
automated enforcer of row 1; it fails the pipeline between Silver and Gold so
corrupted data never reaches Power BI.

## 3. The 8:00 AM scenario (worked example)
*Breaker trips at 08:00; executive dashboard expected 08:30.*

1. **08:00 — Contain.** Breaker halts Silver→Gold; Power BI dataset refresh is
   **not** triggered (stale‑but‑trusted beats fresh‑but‑wrong).
2. **08:02 — Assess.** Read the drift report: % drift, affected domain, spike
   timestamp, link to the exception dashboard.
3. **08:05 — Decide & communicate.** If drift is isolated and understood,
   activate the **fallback**: point the semantic layer at the last validated
   Gold snapshot (Delta `VERSION AS OF`) so the 08:30 dashboard shows *verified
   prior‑day* data, clearly labelled.
4. **08:10 — Notify stakeholders** (template below). Lead the message: what they
   see, what’s trusted, when the fix lands. No raw "Job Failed" alerts to execs.
5. **Post‑incident.** Root‑cause the out‑of‑sequence spike; add/adjust a test or
   watermark; record in ADRs if the design changes.

### Stakeholder message template
> *Subject: Billing dashboard — showing verified data as of [date], refresh delayed*
> The automated data‑quality gate detected a discrepancy in this morning’s load
> and paused the refresh to prevent incorrect figures. Your dashboard is showing
> the **last fully reconciled** dataset ([date/time]). The engineering team is
> resolving the issue; expected refresh by [time]. We chose accuracy over speed
> deliberately — you can rely on the numbers currently shown.

## 4. Rollback
- **Serving:** repoint semantic model to the prior validated Gold version
  (Delta time travel) — minutes, no data movement.
- **Pipeline:** the legacy system remains the system of record until
  decommission sign‑off, so a full rollback is "freeze modern, keep legacy."

## 5. Late / out-of-sequence data
- **Watermark** both extracts to a shared batch id / transaction timestamp.
- Reconcile the **settled T+1 partition**, not a live moving target.
- Compare point‑in‑time via Delta `VERSION AS OF` / `TIMESTAMP AS OF`.
- Model out‑of‑sequence updates as SCD2 so the active version at extract time is
  recoverable.

## 6. Roles
| Role | Responsibility at cutover |
|---|---|
| Technical Lead | Go/No‑Go call, exec comms, final sign‑off |
| Data Engineers | Pipeline run, defect fixes, fallback activation |
| Data Stewards | Reconciliation review, business validation |
| Platform/DevOps | Environment promotion, monitoring, rollback execution |
