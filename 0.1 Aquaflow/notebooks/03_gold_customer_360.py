# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Gold (Customer 360 + billing fact)
# MAGIC Builds the curated, Power BI / Salesforce-ready marts from current Silver
# MAGIC dimensions and the billing fact. Star schema per `powerbi/semantic-model.md`.

# COMMAND ----------
dbutils.widgets.text("silver_customer", "/mnt/lakehouse/silver/dim_customer")
dbutils.widgets.text("silver_billing", "/mnt/lakehouse/silver/fact_billing")
dbutils.widgets.text("gold_path", "/mnt/lakehouse/gold")

silver_customer = dbutils.widgets.get("silver_customer")
silver_billing = dbutils.widgets.get("silver_billing")
gold_path = dbutils.widgets.get("gold_path")

# COMMAND ----------
from pyspark.sql import functions as F

# Current customer dimension (SCD2 -> only active versions for the 360 view).
dim_customer = (
    spark.read.format("delta").load(silver_customer).where("is_current = true")
)
fact_billing = spark.read.format("delta").load(silver_billing)

# COMMAND ----------
# Customer 360: one row per customer with current attributes + billing rollups.
billing_rollup = fact_billing.groupBy("account_id").agg(
    F.sum("total_billed").alias("lifetime_billed"),
    F.max("bill_date").alias("last_bill_date"),
    F.count("*").alias("bill_count"),
)

customer_360 = (
    dim_customer.join(billing_rollup, "account_id", "left")
    .select(
        "account_id",
        "plan_type",
        "property_id",
        F.coalesce("lifetime_billed", F.lit(0.0)).alias("lifetime_billed"),
        "last_bill_date",
        F.coalesce("bill_count", F.lit(0)).alias("bill_count"),
    )
)

# COMMAND ----------
# Write Gold marts (Delta, optimised for BI). FactBilling kept at grain for Power BI.
(customer_360.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").save(f"{gold_path}/customer_360"))

(fact_billing.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true").save(f"{gold_path}/fact_billing"))

# COMMAND ----------
display(customer_360)
