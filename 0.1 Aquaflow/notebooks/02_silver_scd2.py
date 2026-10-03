# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Silver (cleanse + SCD Type 2)
# MAGIC Thin wrapper around `src.transforms.scd2.upsert_scd2`. All SCD2 logic
# MAGIC lives in the tested package; this notebook only reads Bronze, applies
# MAGIC cleansing, and calls the shared function.

# COMMAND ----------
dbutils.widgets.text("bronze_path", "/mnt/lakehouse/bronze/customer")
dbutils.widgets.text("silver_path", "/mnt/lakehouse/silver/dim_customer")
dbutils.widgets.text("business_key", "account_id")

bronze_path = dbutils.widgets.get("bronze_path")
silver_path = dbutils.widgets.get("silver_path")
business_key = dbutils.widgets.get("business_key")

# Critical Data Elements — single source of truth in config/reconciliation_rules.json
CDE_COLS = ["plan_type", "property_id"]

# COMMAND ----------
# Import the tested transforms. On Databricks, install the repo as a wheel or add
# the Repo to sys.path so `src.transforms` resolves (same code path as CI).
from src.transforms.scd2 import upsert_scd2
from pyspark.sql import functions as F

# COMMAND ----------
# Cleanse Bronze -> staged Silver input (dedupe latest per key, trim, standardise).
bronze = spark.read.format("delta").load(bronze_path)

staged = (
    bronze.withColumn("account_id", F.trim("account_id"))
    .withColumn("plan_type", F.upper(F.trim("plan_type")))
    .dropDuplicates([business_key, "ingestion_ts"])
    .orderBy(F.col("ingestion_ts").desc())
    .dropDuplicates([business_key])  # keep latest landed record per key
    .select("account_id", "plan_type", "property_id", "billed_amount")
)

# COMMAND ----------
# Delegate to the shared, unit-tested SCD2 upsert (no logic duplicated here).
upsert_scd2(spark, staged, silver_path, business_key, CDE_COLS)

# COMMAND ----------
display(spark.read.format("delta").load(silver_path).where("is_current = true"))
