# Power BI Semantic Model

Star schema over the Gold marts produced by `notebooks/03_gold_customer_360.py`.
Design is illustrative/synthetic; it exists to evidence semantic modelling, DAX,
performance, and governance for the Technical Lead role.

## 1. Star schema

```
                 ┌───────────────┐        ┌───────────────┐
                 │  DimCustomer  │        │  DimProperty  │
                 │ (SCD2→current)│        │ (SCD2→current)│
                 └───────┬───────┘        └───────┬───────┘
                         │ 1                      │ 1
                         │                        │
                      *  ▼                        ▼ *
                 ┌───────────────────────────────────────┐
   ┌───────────┐ │              FactBilling              │ ┌───────────┐
   │  DimDate   │─┤  grain: one row per account per day   │─│ DimTariff │
   │ (date tbl) │*│  measures: total_billed, is_late...   │*│           │
   └───────────┘ └───────────────────────────────────────┘ └───────────┘
```

| Table | Role | Grain | Key |
|---|---|---|---|
| `FactBilling` | Fact | account × bill_date | `account_id`, `bill_date` |
| `DimCustomer` | Dimension (SCD2, current slice) | one row per customer | `account_id` |
| `DimProperty` | Dimension (SCD2, current slice) | one row per property | `property_id` |
| `DimDate` | Date dimension (marked) | one row per day | `date` |
| `DimTariff` | Dimension | one row per tariff | `tariff_id` |
| `ReconciliationLog` | DQ metrics (disconnected) | one row per run | `run_ts` |

## 2. Relationships
- `FactBilling[account_id]` → `DimCustomer[account_id]` (many‑to‑one, single).
- `FactBilling[property_id]` → `DimProperty[property_id]` (many‑to‑one, single).
- `FactBilling[bill_date]` → `DimDate[date]` (many‑to‑one, single); **mark
  `DimDate` as the date table** for time intelligence.
- `ReconciliationLog` is **disconnected** — DQ KPIs are intentionally not sliced
  by the fact.
- All relationships single‑direction (no bidirectional) to avoid ambiguity.

## 3. Measures
Defined in `measures.dax`: core billing, time intelligence (YoY / MTD / YTD),
and **data‑quality KPIs** (`Reconciliation Drift %`, `Reconciliation Status`,
`Late Arriving Records`, `Last Refresh`) so stewards see trust signals on the
report, not just numbers.

## 4. Performance
- **Import mode** for curated Gold (small, fast) — switch high‑volume fact to
  **Direct Lake** on Fabric / **DirectQuery** on Databricks SQL if volume grows.
- **Star schema, no snowflaking;** integer surrogate keys on relationships.
- Pre‑aggregate in Gold (notebook 03), not in DAX, to keep measures cheap.
- Mark the date table; avoid calculated columns where a measure will do.
- **Incremental refresh** on `FactBilling` partitioned by `bill_date` (e.g.
  refresh last 7 days, archive older) to cut refresh time and cost.

## 5. Governance
- **Row‑level security (RLS):** a `Region` role filters `DimCustomer` /
  `DimProperty` by service region; tested with "View as role".
- **Certified dataset:** publish as a certified shared semantic model so report
  authors reuse one trusted source (no duplicate models).
- **Sensitivity label** applied; access via workspace/app, not file sharing.
- **Trust on the page:** `Last Refresh` and `Reconciliation Status` on the cover
  so consumers know the data passed the gate and when it last loaded.

## 6. Status
Specified and designed, **not deployed** — a Power BI workspace is required to
build the `.pbix`. The DAX and this model are review artefacts; the Gold tables
they sit on are produced by the (Databricks) Gold notebook.
