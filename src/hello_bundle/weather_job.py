"""Job entry point: load Open-Meteo data and MERGE it into a Delta table."""

import argparse
from datetime import date

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DateType,
    DoubleType,
    StringType,
    StructField,
    StructType,
)

from hello_bundle.weather_api import fetch_all

SCHEMA = StructType(
    [
        StructField("city", StringType(), False),
        StructField("date", DateType(), False),
        StructField("temperature_max_c", DoubleType()),
        StructField("temperature_min_c", DoubleType()),
        StructField("precipitation_mm", DoubleType()),
        StructField("is_forecast", BooleanType(), False),
    ]
)


def merge_weather(spark: SparkSession, table: str, rows: list[dict]) -> None:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            city STRING NOT NULL,
            date DATE NOT NULL,
            temperature_max_c DOUBLE,
            temperature_min_c DOUBLE,
            precipitation_mm DOUBLE,
            is_forecast BOOLEAN NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        COMMENT 'Daily weather per city from Open-Meteo, upserted on (city, date)'
    """)

    updates = spark.createDataFrame(rows, SCHEMA).withColumn("updated_at", F.current_timestamp())
    updates.createOrReplaceTempView("weather_updates")

    # Only touch rows whose values changed, so updated_at shows when a forecast was revised
    spark.sql(f"""
        MERGE INTO {table} AS t
        USING weather_updates AS s
        ON t.city = s.city AND t.date = s.date
        WHEN MATCHED AND NOT (
            t.temperature_max_c <=> s.temperature_max_c
            AND t.temperature_min_c <=> s.temperature_min_c
            AND t.precipitation_mm <=> s.precipitation_mm
            AND t.is_forecast <=> s.is_forecast
        ) THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """).show()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")

    rows = fetch_all(today=date.today())
    merge_weather(spark, f"{args.catalog}.{args.schema}.daily_weather", rows)


if __name__ == "__main__":
    main()
