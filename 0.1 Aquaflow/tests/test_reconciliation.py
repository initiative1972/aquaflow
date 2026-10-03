"""Unit tests for the dual-run reconciliation gate."""
from __future__ import annotations

import pytest
from pyspark.sql import functions as F

from src.transforms.reconciliation import reconcile, enforce
from src.data_generator import legacy_billing, modern_billing

KEYS = ["account_id", "bill_date"]
CDE = ["total_billed"]


def test_identical_zero_drift(spark):
    legacy = spark.createDataFrame(legacy_billing())
    modern = spark.createDataFrame(modern_billing(introduce_drift=False))
    result = reconcile(legacy, modern, KEYS, CDE)
    assert result["mismatches"] == 0
    assert result["drift_pct"] == 0.0
    assert result["passed"] is True
    enforce(result)  # must not raise


def test_value_drift_detected_and_breaker_trips(spark):
    legacy = spark.createDataFrame(legacy_billing())
    modern = spark.createDataFrame(modern_billing(introduce_drift=True))
    result = reconcile(legacy, modern, KEYS, CDE, tolerance_pct=0.01)
    assert result["mismatches"] == 1
    assert result["passed"] is False
    with pytest.raises(ValueError):
        enforce(result)


def test_missing_row_counts_as_mismatch(spark):
    legacy = spark.createDataFrame(legacy_billing())
    modern = spark.createDataFrame(legacy_billing()[:-1])  # drop one row
    result = reconcile(legacy, modern, KEYS, CDE)
    assert result["mismatches"] == 1
    assert result["universe"] == 3


def test_audit_columns_excluded_from_hash(spark):
    legacy = spark.createDataFrame(legacy_billing())
    modern = spark.createDataFrame(modern_billing(introduce_drift=False)).withColumn(
        "ingestion_ts", F.current_timestamp()
    )
    # CDE excludes ingestion_ts, so the fresh timestamp must not cause drift.
    result = reconcile(legacy, modern, KEYS, CDE)
    assert result["passed"] is True
