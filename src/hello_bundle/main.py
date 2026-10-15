from pyspark.sql import SparkSession

from hello_bundle.transforms import add_greeting


def main() -> None:
    spark = SparkSession.builder.getOrCreate()
    rows = [{"name": "  ada lovelace "}, {"name": "grace hopper"}]
    df = spark.createDataFrame(add_greeting(rows))
    df.show(truncate=False)


if __name__ == "__main__":
    main()
