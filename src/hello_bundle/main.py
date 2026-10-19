from pyspark.sql import SparkSession

from hello_bundle.transforms import add_greeting
from hello_bundle.goodbye import add_goodbye

def main() -> None:
    spark = SparkSession.builder.getOrCreate()
    rows = [{"name": "  ada lovelace "}, {"name": "grace hopper"}, {"name": "There can only be One"}]
    df = spark.createDataFrame(add_greeting(rows))
    df.show(truncate=False)
    df = spark.createDataFrame(add_goodbye(rows))
    df.show(truncate=False)


if __name__ == "__main__":
    main()
