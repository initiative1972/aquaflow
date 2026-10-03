# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze ingestion (Auto Loader)
# MAGIC Thin wrapper: lands raw source files into an append-only Bronze Delta
# MAGIC table with schema inference + evolution. **Databricks-only** (Auto Loader
# MAGIC and `cloudFiles` are not available in the local CI harness).

# COMMAND ----------
dbutils.widgets.text("source_path", "/mnt/landing/billing")
dbutils.widgets.text("bronze_path", "/mnt/lakehouse/bronze/billing")
dbutils.widgets.text("schema_path", "/mnt/lakehouse/_schemas/billing")

source_path = dbutils.widgets.get("source_path")
bronze_path = dbutils.widgets.get("bronze_path")
schema_path = dbutils.widgets.get("schema_path")

# COMMAND ----------
from pyspark.sql import functions as F

bronze = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", schema_path)
    .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    .load(source_path)
    # Audit columns — excluded from reconciliation hashing downstream.
    .withColumn("ingestion_ts", F.current_timestamp())
    .withColumn("source_file", F.col("_metadata.file_path"))
)

# COMMAND ----------
(
    bronze.writeStream.format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{bronze_path}/_checkpoint")
    .option("mergeSchema", "true")
    .trigger(availableNow=True)  # batch-style micro-batch for scheduled runs
    .start(bronze_path)
    .awaitTermination()
)

# COMMAND ----------
# MAGIC %md
# MAGIC Bronze preserves raw history as-landed. No business logic here — cleansing
# MAGIC and SCD2 happen in `02_silver_scd2`.
