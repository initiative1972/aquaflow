# aquaflow
Data engineering project for AquaFlow
# AquaFlow‑Modernise

**An Azure lakehouse migration accelerator: reverse‑engineering legacy T‑SQL into a governed Databricks Medallion architecture, with automated dual‑run reconciliation, a Power BI semantic layer, and a Salesforce‑ready serving tier.**

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions)](../../actions)
[![Azure](https://img.shields.io/badge/Platform-Microsoft_Azure-0078D4?logo=microsoftazure)](https://azure.microsoft.com/)
[![Databricks](https://img.shields.io/badge/Compute-Azure_Databricks-FF3621?logo=databricks)](https://databricks.com/)
[![Delta Lake](https://img.shields.io/badge/Storage-Delta_Lake-00ADD8?logo=delta)](https://delta.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What this repository is — and is not

This is a **portfolio reference implementation**, built to demonstrate the technical‑lead competencies required to modernise a legacy enterprise data platform onto Azure. It is deliberately honest about what runs and what is design evidence, because a lead is judged on judgement, not on badges.

| Layer | Status in this repo | How to verify it |
| --- | --- | --- |
| Pure PySpark transforms (Silver SCD2, Gold marts) | **Runs & tested in CI** | `pytest` on a local Spark session in GitHub Actions |
| Reconciliation engine (hash + aggregate gate) | **Runs & tested in CI** | `pytest tests/test_reconciliation.py` |
| Great Expectations data‑quality suite | **Runs in CI** on sample data | `great_expectations checkpoint run` |
| Source‑to‑target mappings, DAX measures, ADRs | **Design artefacts** (reviewed, not executed) | Human review of `/docs`, `/powerbi` |
| ADF pipelines, Bicep IaC, Auto Loader, Unity Catalog | **Design artefacts** — require an Azure subscription to deploy | `az deployment what-if` (not run in CI) |

All data in this repository is **synthetic**. No employer, customer, or production data is used or reproduced. Numbers quoted in `/reports` are from the latest local run and are reproducible with `make demo`.

> **Scenario context.** The design is framed around a public utility ("AquaFlow Water", fictional) migrating an undocumented 3,000‑line billing stored procedure and a Land Development dataset from on‑prem SQL Server to an Azure Databricks lakehouse, ahead of a Salesforce customer‑domain transition. The scenario is illustrative; the engineering patterns are real.

---

## 1. The problem this solves

A monolithic, undocumented T‑SQL stored procedure generates daily billing and land‑development datasets. It uses cursors, temp tables, and embedded business rules. The business needs to retire it, but cannot cut over until the new platform is **demonstrably equivalent** within an agreed tolerance — not "trust me," but a reconciliation artefact a data steward can sign.

**Objectives**

1. **Reverse‑engineer and modularise** procedural T‑SQL into set‑based PySpark across Bronze / Silver / Gold Delta layers.
2. **Model history correctly** with SCD Type 2 dimensions and a documented star schema.
3. **Prove equivalence** with an automated dual‑run reconciliation gate (macro aggregates + micro row hashing) wired as a circuit breaker.
4. **Serve** a Power BI semantic model and a Salesforce‑ready outbound dataset.
5. **Automate** the lifecycle with CI/CD across Dev / SIT / UAT / Prod.

---

## 2. Architecture

```
 SOURCE (on‑prem SQL Server)                 INGEST            LAKEHOUSE (Azure Databricks + Delta)                   SERVE
 ┌───────────────────────────┐   Azure Data  ┌──────────┐     ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌──────────────────────────┐
 │ 3,000‑line billing SP      │──  Factory  ──▶│  BRONZE  │──▶ │ SILVER  │──▶│  GOLD   │──▶│ Power BI semantic model  │
 │ Land Dev tables, temp/cur. │  (metadata‑   │ raw Delta│    │ SCD2    │   │ C360 +  │   │ (star schema + DAX)      │
 └───────────────────────────┘   driven copy) │ Auto Ldr │    │ cleansed│   │ marts   │   ├──────────────────────────┤
                                               └──────────┘    └─────────┘   └────┬────┘   │ Salesforce outbound set  │
                                                                                  │        │ (Bulk API / ADF sink)    │
                                                      ┌───────────────────────────▼──────┐ └──────────────────────────┘
                                                      │   RECONCILIATION GATE (circuit    │
                                                      │   breaker): macro aggregates +    │
                                                      │   SHA‑256 row hash vs. legacy     │
                                                      └───────────────────────────────────┘
                                                      CI/CD: GitHub Actions · Bicep IaC · PyTest · Great Expectations · Dev/SIT/UAT/Prod
```

---

## 3. Repository structure

```
├── .github/workflows/
│   ├── ci.yml                     # lint + local-Spark pytest + Great Expectations (RUNS)
│   └── cd.yml                     # Databricks Asset Bundle deploy per environment (design)
├── docs/
│   ├── adr/                       # Architecture Decision Records (lead artefact)
│   │   ├── 0001-rrf-reconciliation-over-full-row-transfer.md
│   │   ├── 0002-scd2-merge-pattern.md
│   │   └── 0003-batch-vs-streaming-for-billing.md
│   ├── source-to-target-mapping.md   # STTM: legacy column -> layer -> rule
│   ├── runbook-cutover.md            # dual-run, go/no-go, rollback (lead artefact)
│   └── profiling-report.md           # data discovery & profiling of legacy source
├── powerbi/
│   ├── semantic-model.md          # star schema, grain, relationships, RLS/governance
│   └── measures.dax               # DAX measures (billing, consumption, DQ KPIs)
├── config/
│   ├── pipeline_config.json       # metadata-driven source→target config
│   └── reconciliation_rules.json  # tolerances + Critical Data Element (CDE) lists
├── data/
│   ├── legacy_samples/legacy_billing_sp.sql   # trimmed, synthetic legacy procedure
│   └── synthetic/                 # generated source + expected-output fixtures
├── infra/bicep/                   # ADLS Gen2, ADF, Databricks, Key Vault (design)
├── notebooks/
│   ├── 01_bronze_ingestion.py
│   ├── 02_silver_scd2.py
│   ├── 03_gold_customer_360.py
│   └── 04_reconciliation.py
├── src/
│   ├── transforms/                # PURE functions (no Databricks deps) — tested in CI
│   │   ├── scd2.py
│   │   ├── gold.py
│   │   └── reconciliation.py
│   ├── modernizer/                # Gemini-assisted T-SQL → PySpark accelerator (HITL)
│   └── utils/                     # hashing, logging, Key Vault connectors
├── tests/
│   ├── test_scd2.py
│   ├── test_gold.py
│   └── test_reconciliation.py
├── Makefile                       # make demo / make test / make lint
├── requirements.txt
└── README.md
```

**Design principle that makes CI real:** all business logic lives in `src/transforms/` as **pure functions that take and return Spark DataFrames** and have no Databricks‑runtime dependency. Notebooks are thin wrappers that read/write Delta and call these functions. That is why the transforms can be unit‑tested on a local Spark session in GitHub Actions, and also why they lift onto Databricks without a rewrite.

---

## 4. Core implementation

### 4.1 Silver — SCD Type 2 (correct Delta merge)

The canonical two‑step merge. The first action **expires** the current version when the CDE hash changes; the second **inserts** a new version. New and changed keys are inserted; **unchanged keys are not re‑appended** (this is the common bug a naïve "merge then append all" introduces — it creates duplicate `is_current = true` rows).

```python
from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, functions as F

def add_scd2_metadata(df: DataFrame, cde_cols: list[str]) -> DataFrame:
    hash_col = F.sha2(
        F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("\u2205")) for c in cde_cols]),
        256,
    )
    return (df
        .withColumn("record_hash", hash_col)
        .withColumn("effective_start", F.current_timestamp())
        .withColumn("effective_end", F.lit(None).cast("timestamp"))
        .withColumn("is_current", F.lit(True)))

def upsert_scd2(spark: SparkSession, staged: DataFrame, target_path: str,
                business_key: str, cde_cols: list[str]) -> None:
    staged = add_scd2_metadata(staged, cde_cols)

    if not DeltaTable.isDeltaTable(spark, target_path):
        staged.write.format("delta").save(target_path)      # first load
        return

    target = DeltaTable.forPath(spark, target_path)
    current = target.toDF().where("is_current = true")

    # Keys that are new OR whose CDEs changed
    updates = (staged.alias("s")
        .join(current.alias("t"), business_key, "left")
        .where("t.record_hash IS NULL OR t.record_hash <> s.record_hash")
        .select("s.*"))

    # Two-row payload for changed keys: NULL mergeKey => inserts a new version;
    # real key => matches and expires the old version.
    changed = (updates.alias("u")
        .join(current.alias("t"), business_key)
        .where("t.record_hash <> u.record_hash")
        .select("u.*"))

    payload = (changed.withColumn("mergeKey", F.lit(None).cast("string"))
        .unionByName(updates.withColumn("mergeKey", F.col(business_key))))

    (target.alias("t")
        .merge(payload.alias("s"), f"t.{business_key} = s.mergeKey AND t.is_current = true")
        .whenMatchedUpdate(
            condition="t.record_hash <> s.record_hash",
            set={"is_current": "false", "effective_end": "s.effective_start"})
        .whenNotMatchedInsertAll()
        .execute())
```

### 4.2 Reconciliation — macro gate + micro hash

Equivalence is proved to a **tolerance**, never asserted as "zero defect." Audit/metadata columns are excluded from the hash so processing latency cannot create false mismatches.

```python
from pyspark.sql import DataFrame, functions as F

def reconcile(legacy: DataFrame, modern: DataFrame, keys: list[str],
              cde_cols: list[str], tolerance_pct: float = 0.01) -> dict:
    def hashed(df):
        h = F.sha2(F.concat_ws("||",
            *[F.coalesce(F.col(c).cast("string"), F.lit("\u2205")) for c in cde_cols]), 256)
        return df.select(*keys, h.alias("row_hash"))

    cmp = (hashed(legacy).alias("l")
           .join(hashed(modern).alias("m"), on=keys, how="full_outer"))
    mismatches = cmp.where(
        F.col("l.row_hash").isNull() | F.col("m.row_hash").isNull() |
        (F.col("l.row_hash") != F.col("m.row_hash")))

    # Denominator is the union of keys on both sides (not just legacy).
    universe = legacy.select(*keys).unionByName(modern.select(*keys)).distinct().count()
    bad = mismatches.count()
    drift_pct = (bad / universe * 100) if universe else 0.0

    result = {"universe": universe, "mismatches": bad, "drift_pct": round(drift_pct, 4),
              "passed": drift_pct <= tolerance_pct}
    if not result["passed"]:
        raise ValueError(
            f"Circuit breaker: drift {drift_pct:.4f}% exceeds tolerance {tolerance_pct}%")
    return result
```

> **ADR‑0001** records *why* row hashing + `EXCEPT`/`full_outer` is chosen over transferring full rows between systems, and the trade‑offs (collision risk, column‑order sensitivity, null handling). See `docs/adr/`.

### 4.3 The modernizer accelerator (honest framing)

`src/modernizer/` is a **Gemini‑assisted, human‑in‑the‑loop accelerator**, not an automatic transpiler. It parses a legacy procedure into a dependency graph (temp tables, cursors, final `INSERT INTO`), proposes a PySpark refactor per block, and **flags every block for engineer review** before it is accepted. The claim is "cuts reverse‑engineering time," not "converts T‑SQL automatically." Treating an LLM translation as trusted output is exactly the failure mode this repo argues against.

---

## 5. Serving tier

### 5.1 Power BI semantic layer (`/powerbi`)
- **Star schema:** `FactMeterRead` (grain: one row per meter per read per day) with conformed dimensions `DimCustomer` (SCD2), `DimProperty` (SCD2), `DimDate`, `DimTariff`.
- **`measures.dax`:** billing totals, consumption YoY, days‑sales‑outstanding, plus **data‑quality KPIs** (reconciliation drift %, late‑arrival count) surfaced to stewards.
- **Governance:** row‑level security by service region, documented refresh/incremental policy, and a certified dataset note.

### 5.2 Salesforce outbound (`/docs/source-to-target-mapping.md`)
Gold `Customer360` is published as an outbound dataset for the Salesforce customer‑domain transition — field‑level mapping to Salesforce objects, upsert external‑id strategy, and delivery via ADF Salesforce sink / Bulk API 2.0. Documented as a design because it needs a Salesforce org to execute.

---

## 6. CI/CD and environments

- **`ci.yml` (runs on every PR):** `flake8` → `pytest` against a **local Spark session** (`pyspark` + `delta-spark` on `ubuntu-latest`, no cluster needed) → Great Expectations checkpoint on sample data.
- **`cd.yml` (design):** Databricks Asset Bundle deploy promoted **Dev → SIT → UAT → Prod**, each gated by the reconciliation result. Mock‑migration reconciliation runs in SIT/UAT against synthetic fixtures.
- **IaC:** Bicep for ADLS Gen2, ADF, Databricks workspace, Key Vault; `what-if` previewed, not applied in CI.

```yaml
# .github/workflows/ci.yml (excerpt)
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: flake8 src tests --max-line-length=120
      - run: pytest -q                          # local SparkSession, no Databricks
      - run: great_expectations checkpoint run gold_checkpoint
```

---

## 7. Quick start

```bash
pip install -r requirements.txt     # pyspark, delta-spark, great_expectations, pytest, flake8
make demo                           # generate synthetic source, run Bronze→Gold, reconcile
make test                           # local-Spark unit tests (same as CI)
```
`make demo` writes a reconciliation summary to `reports/last_run.json` — the numbers in this README come from there and regenerate on every run.

---

## 8. How this maps to the Technical Lead – Data & Analytics role

| JD requirement | Evidence in this repo |
| --- | --- |
| Reverse‑engineer undocumented legacy ETL / stored procedures | `src/modernizer/`, `data/legacy_samples/`, `docs/profiling-report.md` |
| Azure lakehouse, scalable pipelines, reusable data products | Medallion `src/transforms/` + `notebooks/`, Delta ACID |
| Data modelling (SCD2, star schema, semantic layer) | `src/transforms/scd2.py`, `powerbi/semantic-model.md` |
| **Advanced Power BI (semantic, DAX, governance)** | `powerbi/measures.dax`, RLS + certified‑dataset notes |
| Reconciliation / validation / fit for consumption | `src/transforms/reconciliation.py`, circuit breaker, tolerances |
| Source‑to‑target mappings | `docs/source-to-target-mapping.md` |
| DevOps / CI/CD / automation | `.github/workflows/`, Bicep IaC, Dev/SIT/UAT/Prod |
| Mock migrations across Dev/SIT/UAT | `cd.yml` environment promotion + SIT/UAT reconciliation |
| Technical leadership, standards, mentoring | `docs/adr/`, `docs/runbook-cutover.md`, coding standards in `CONTRIBUTING.md` |
| Salesforce‑enabled customer domain | Salesforce outbound mapping in `docs/source-to-target-mapping.md` |
| Stakeholder communication under pressure | Cutover runbook: go/no‑go, 8:00 AM breaker, exec comms, rollback |

---

## 9. Honest limitations

- Databricks‑runtime features (Auto Loader, Unity Catalog, `DeltaTable.forPath` on DBFS) and all Azure IaC need a subscription; they are **not executed in CI**.
- Scale is demonstrated by **pattern** (set‑based, partition‑aware, broadcast joins) on synthetic data, not by a billion‑row benchmark.
- The Salesforce and Power BI tiers are **specified and designed**, not deployed, because they need a Salesforce org and a Power BI workspace.
- The modernizer is an **accelerator with human review**, not a verified transpiler.

License: MIT.
