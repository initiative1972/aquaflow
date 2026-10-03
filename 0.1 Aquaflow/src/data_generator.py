"""Synthetic data generator and local demo entrypoint for AquaFlow-Modernize.

All data here is SYNTHETIC. No employer, customer, or production data is used.

Pure factories (``customers_v1`` / ``customers_v2`` / ``legacy_billing`` /
``modern_billing``) return plain dicts and are used by the unit tests. Running
``python -m src.data_generator`` builds a local Spark + Delta session, exercises
the SCD2 upsert twice (initial load + a change feed), runs the reconciliation
gate, and writes ``reports/last_run.json``.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path


# --------------------------------------------------------------------------- #
# Pure data factories (no Spark; unit-testable)                               #
# --------------------------------------------------------------------------- #
def customers_v1() -> list[dict]:
    return [
        {"account_id": "A001", "plan_type": "RESIDENTIAL", "property_id": "P100", "billed_amount": 120.50},
        {"account_id": "A002", "plan_type": "RESIDENTIAL", "property_id": "P101", "billed_amount": 98.00},
        {"account_id": "A003", "plan_type": "COMMERCIAL", "property_id": "P102", "billed_amount": 540.75},
    ]


def customers_v2() -> list[dict]:
    """Change feed: A001 plan changes (new version), A002 unchanged,
    A004 is brand new, A003 is absent (stays current historically)."""
    return [
        {"account_id": "A001", "plan_type": "CONCESSION", "property_id": "P100", "billed_amount": 120.50},
        {"account_id": "A002", "plan_type": "RESIDENTIAL", "property_id": "P101", "billed_amount": 98.00},
        {"account_id": "A004", "plan_type": "COMMERCIAL", "property_id": "P103", "billed_amount": 310.00},
    ]


def legacy_billing() -> list[dict]:
    return [
        {"account_id": "A001", "bill_date": "2026-09-01", "total_billed": 120.50},
        {"account_id": "A002", "bill_date": "2026-09-01", "total_billed": 98.00},
        {"account_id": "A003", "bill_date": "2026-09-01", "total_billed": 540.75},
    ]


def modern_billing(introduce_drift: bool = False) -> list[dict]:
    rows = [dict(r) for r in legacy_billing()]
    if introduce_drift:
        rows[0]["total_billed"] = 999.99  # a migration bug the gate must catch
    return rows


# --------------------------------------------------------------------------- #
# Spark demo wiring                                                           #
# --------------------------------------------------------------------------- #
def _build_spark():
    from pyspark.sql import SparkSession
    from delta import configure_spark_with_delta_pip

    builder = (
        SparkSession.builder.master("local[2]")
        .appName("aquaflow-demo")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def main() -> dict:
    from src.transforms.scd2 import upsert_scd2
    from src.transforms.reconciliation import reconcile

    spark = _build_spark()
    spark.sparkContext.setLogLevel("ERROR")

    cde = ["plan_type", "property_id"]
    table = str(Path("build/silver_customers").resolve())
    if Path(table).exists():
        shutil.rmtree(table)  # deterministic demo

    upsert_scd2(spark, spark.createDataFrame(customers_v1()), table, "account_id", cde)
    upsert_scd2(spark, spark.createDataFrame(customers_v2()), table, "account_id", cde)

    silver = spark.read.format("delta").load(table)
    current_rows = silver.where("is_current = true").count()
    total_versions = silver.count()

    legacy = spark.createDataFrame(legacy_billing())
    modern = spark.createDataFrame(modern_billing(introduce_drift=False))
    recon = reconcile(legacy, modern, ["account_id", "bill_date"], ["total_billed"])

    report = {
        "silver_current_rows": current_rows,
        "silver_total_versions": total_versions,
        "reconciliation": recon,
    }
    out = Path("reports")
    out.mkdir(exist_ok=True)
    (out / "last_run.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    spark.stop()
    return report


if __name__ == "__main__":
    main()
