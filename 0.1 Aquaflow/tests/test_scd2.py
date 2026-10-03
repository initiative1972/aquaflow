"""Unit tests for the Silver SCD2 upsert (local Spark + Delta)."""
from __future__ import annotations

from src.transforms.scd2 import add_scd2_metadata, upsert_scd2
from src.data_generator import customers_v1, customers_v2

CDE = ["plan_type", "property_id"]
KEY = "account_id"


def _current(spark, path):
    return spark.read.format("delta").load(path).where("is_current = true")


def test_metadata_columns_present(spark):
    df = add_scd2_metadata(spark.createDataFrame(customers_v1()), CDE)
    for col in ["record_hash", "effective_start", "effective_end", "is_current"]:
        assert col in df.columns


def test_initial_load_all_current(spark, tmp_table):
    upsert_scd2(spark, spark.createDataFrame(customers_v1()), tmp_table, KEY, CDE)
    assert _current(spark, tmp_table).count() == 3


def test_rerun_unchanged_no_duplicates(spark, tmp_table):
    df = spark.createDataFrame(customers_v1())
    upsert_scd2(spark, df, tmp_table, KEY, CDE)
    upsert_scd2(spark, df, tmp_table, KEY, CDE)  # identical feed again
    current = _current(spark, tmp_table)
    assert current.count() == 3  # the duplicate-current bug would make this 6
    assert current.select(KEY).distinct().count() == 3


def test_change_creates_new_version_and_expires_old(spark, tmp_table):
    upsert_scd2(spark, spark.createDataFrame(customers_v1()), tmp_table, KEY, CDE)
    upsert_scd2(spark, spark.createDataFrame(customers_v2()), tmp_table, KEY, CDE)
    rows = spark.read.format("delta").load(tmp_table)

    a001 = rows.where("account_id = 'A001'")  # plan changed
    assert a001.count() == 2
    assert a001.where("is_current = true").count() == 1
    assert a001.where("is_current = false").count() == 1

    assert rows.where("account_id = 'A004' and is_current = true").count() == 1  # new key

    current = _current(spark, tmp_table)
    assert current.count() == current.select(KEY).distinct().count()  # one current per key
