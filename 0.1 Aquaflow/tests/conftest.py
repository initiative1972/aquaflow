"""Pytest fixtures: a session-scoped local Spark + Delta session.

Adds the repository root to ``sys.path`` so tests import ``src.transforms.*``
as implicit namespace packages (no __init__.py required).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession
    from delta import configure_spark_with_delta_pip

    builder = (
        SparkSession.builder.master("local[2]")
        .appName("aquaflow-tests")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
    )
    session = configure_spark_with_delta_pip(builder).getOrCreate()
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture
def tmp_table(tmp_path) -> str:
    """A fresh Delta table path per test."""
    return str(tmp_path / "delta_tbl")
