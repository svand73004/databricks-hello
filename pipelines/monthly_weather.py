"""Lakeflow Declarative Pipeline: monthly temperature stats per city.

Reads the daily_weather table that weather_job MERGEs into. The source table name comes
from the pipeline configuration (resources/weather_pipeline.yml).
"""

from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.active()


@dp.materialized_view(comment="Highest, lowest and average temperature per city and month (actuals only)")
def monthly_weather_per_city():
    daily = spark.read.table(spark.conf.get("source_table")).where(~F.col("is_forecast"))
    daily_avg = (F.col("temperature_max_c") + F.col("temperature_min_c")) / 2

    return daily.groupBy("city", F.trunc("date", "month").alias("month")).agg(
        F.max("temperature_max_c").alias("highest_temperature_c"),
        F.min("temperature_min_c").alias("lowest_temperature_c"),
        F.round(F.avg(daily_avg), 1).alias("average_temperature_c"),
        F.count("*").alias("days"),
    )
