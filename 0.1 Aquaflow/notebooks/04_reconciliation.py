# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · Reconciliation gate (circuit breaker)
# MAGIC Dual-run equivalence check between the legacy extract and the new Gold
# MAGIC output. Delegates to `src.transforms.reconciliation`. Fails the pipeline
# MAGIC (raises) when drift exceeds tolerance, so Power BI never refreshes on bad
# MAGIC data.

# COMMAND ----------
dbutils.widgets.text("legacy_path", "/mnt/lakehouse/legacy/billing_extract")
dbutils.widgets.text("gold_path", "/mnt/lakehouse/gold/fact_billing")
dbutils.widgets.text("tolerance_pct", "0.01")

legacy_path = dbutils.widgets.get("legacy_path")
gold_path = dbutils.widgets.get("gold_path")
tolerance_pct = float(dbutils.widgets.get("tolerance_pct"))

KEYS = ["account_id", "bill_date"]
CDE_COLS = ["total_billed"]

# COMMAND ----------
from src.transforms.reconciliation import reconcile, enforce
from pyspark.sql import functions as F
import json

# COMMAND ----------
# Compare the settled (T+1) partition only — see docs/runbook-cutover.md.
legacy = spark.read.format("delta").load(legacy_path)
modern = spark.read.format("delta").load(gold_path)

# Optional macro pre-check: aggregate totals must be close before micro hashing.
macro_legacy = legacy.agg(F.sum("total_billed")).first()[0] or 0.0
macro_modern = modern.agg(F.sum("total_billed")).first()[0] or 0.0
macro_variance = abs(macro_legacy - macro_modern) / macro_legacy * 100 if macro_legacy else 0.0
print(f"Macro variance on SUM(total_billed): {macro_variance:.4f}%")

# COMMAND ----------
result = reconcile(legacy, modern, KEYS, CDE_COLS, tolerance_pct=tolerance_pct)
print(json.dumps(result, indent=2))

# Persist the reconciliation evidence for the steward dashboard / audit trail.
(spark.createDataFrame([{**result, "run_ts": None}])
    .withColumn("run_ts", F.current_timestamp())
    .write.format("delta").mode("append").save("/mnt/lakehouse/gold/_reconciliation_log"))

# COMMAND ----------
# Circuit breaker: raising here fails the ADF/Databricks job and blocks the
# Silver->Gold->BI promotion. Fallback to the last validated snapshot is handled
# by the contingency runbook (docs/runbook-cutover.md).
enforce(result)
print("Reconciliation passed — safe to promote to serving.")
