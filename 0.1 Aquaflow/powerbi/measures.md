# Power BI DAX Measures

Measures for the AquaFlow‑Modernize semantic model — a star schema over the Gold
marts (`FactBilling` + `DimCustomer` / `DimProperty` / `DimDate` / `DimTariff`,
with a disconnected `ReconciliationLog`). See `semantic-model.md` for grain,
relationships, and governance. Measures are synthetic/illustrative; names match
the Gold marts.

The canonical source is `measures.dax` (paste‑ready into Tabular Editor / the
Power BI model). This document is the annotated, reviewable version.

## 1. Core billing

```dax
Total Billed =
    SUM ( FactBilling[total_billed] )

Bill Count =
    COUNTROWS ( FactBilling )

Avg Bill Value =
    DIVIDE ( [Total Billed], [Bill Count] )

Active Customers =
    CALCULATE (
        DISTINCTCOUNT ( DimCustomer[account_id] ),
        DimCustomer[is_current] = TRUE ()
    )
```

- `Avg Bill Value` uses `DIVIDE` (safe divide — no divide‑by‑zero error).
- `Active Customers` counts only the **current** SCD2 slice, so historical
  versions never inflate the count.

## 2. Time intelligence

> Requires `DimDate` to be **marked as the date table**.

```dax
Total Billed LY =
    CALCULATE ( [Total Billed], SAMEPERIODLASTYEAR ( DimDate[date] ) )

Total Billed YoY % =
    DIVIDE ( [Total Billed] - [Total Billed LY], [Total Billed LY] )

Total Billed MTD =
    TOTALMTD ( [Total Billed], DimDate[date] )

Total Billed YTD =
    TOTALYTD ( [Total Billed], DimDate[date] )
```

- All time intelligence flows through the marked date table — avoids ambiguous
  filter context and keeps the measures composable.

## 3. Data‑quality KPIs

> Sourced from `_reconciliation_log` (written by `notebooks/04_reconciliation.py`)
> and surfaced to stewards so trust signals sit on the report, not just numbers.

```dax
Reconciliation Drift % =
    CALCULATE (
        MAX ( ReconciliationLog[drift_pct] ),
        LASTNONBLANK ( ReconciliationLog[run_ts], 1 )
    )

Reconciliation Status =
    VAR latest = [Reconciliation Drift %]
    VAR tol = SELECTEDVALUE ( ReconciliationLog[tolerance_pct], 0.01 )
    RETURN IF ( latest <= tol, "PASS", "BREACH" )

Reconciliation Status Colour =   // for conditional formatting
    IF ( [Reconciliation Status] = "PASS", "#2E7D32", "#C62828" )

Late Arriving Records =
    CALCULATE (
        COUNTROWS ( FactBilling ),
        FactBilling[is_late_arriving] = TRUE ()
    )
```

- `Reconciliation Drift %` takes the **latest** run via `LASTNONBLANK`.
- `Reconciliation Status` compares drift against the stored tolerance and returns
  `PASS` / `BREACH`; `Reconciliation Status Colour` drives conditional formatting.
- These are the DAX counterpart to the pipeline circuit breaker — the same
  equivalence story, made visible to the business.

## 4. Governance helper

```dax
Last Refresh =
    MAX ( ReconciliationLog[run_ts] )   // shown on the report cover for trust
```

- Placed on the report cover alongside `Reconciliation Status` so consumers know
  the data passed the gate and when it last loaded.

## Measure index

| Measure | Group | Notes |
| --- | --- | --- |
| `Total Billed` | Core | Base additive measure |
| `Bill Count` | Core | Row count of fact |
| `Avg Bill Value` | Core | Safe `DIVIDE` |
| `Active Customers` | Core | Current SCD2 slice only |
| `Total Billed LY` | Time | `SAMEPERIODLASTYEAR` |
| `Total Billed YoY %` | Time | Year‑over‑year growth |
| `Total Billed MTD` | Time | Month‑to‑date |
| `Total Billed YTD` | Time | Year‑to‑date |
| `Reconciliation Drift %` | DQ | Latest run drift |
| `Reconciliation Status` | DQ | PASS / BREACH vs tolerance |
| `Reconciliation Status Colour` | DQ | Conditional formatting hex |
| `Late Arriving Records` | DQ | Count of late‑flagged rows |
| `Last Refresh` | Governance | Report‑cover trust signal |
