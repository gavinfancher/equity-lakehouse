#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F


REQUIRED_COLUMNS = {
    "ticker",
    "volume",
    "open",
    "close",
    "high",
    "low",
    "window_start",
    "transactions",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Aggregate minute/window bars into per-ticker OHLC over a period."
    )
    parser.add_argument(
        "--config",
        help="JSON run config path. Supports local paths and gs:// URIs.",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        help="One or more input CSV/CSV.GZ paths.",
    )
    parser.add_argument("--output", help="Output CSV directory.")
    parser.add_argument(
        "--output-partitions",
        type=int,
        default=None,
        help="Number of CSV output part files to write. Defaults to 1.",
    )
    return parser.parse_args()


def read_text(spark, uri):
    if uri.startswith("gs://"):
        return "\n".join(spark.sparkContext.textFile(uri).collect())
    return Path(uri).read_text(encoding="utf-8")


def resolve_run_config(spark, args):
    config = {}
    if args.config:
        config = json.loads(read_text(spark, args.config))

    input_paths = config.get("input", args.input)
    output_path = config.get("output", args.output)
    output_partitions = config.get("output_partitions", args.output_partitions)

    if isinstance(input_paths, str):
        input_paths = [input_paths]

    if not input_paths:
        raise ValueError("Specify input paths with --input or config.input")
    if not output_path:
        raise ValueError("Specify an output path with --output or config.output")
    if output_partitions is None:
        output_partitions = 1
    if output_partitions < 1:
        raise ValueError("output_partitions must be at least 1")

    return input_paths, output_path, output_partitions


def main():
    args = parse_args()

    spark = (
        SparkSession.builder.appName("finpipe-3day-ticker-ohlc")
        .getOrCreate()
    )
    input_paths, output_path, output_partitions = resolve_run_config(spark, args)

    raw = (
        spark.read.option("header", "true")
        .option("mode", "FAILFAST")
        .csv(input_paths)
    )

    missing = sorted(REQUIRED_COLUMNS.difference(raw.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    bars = (
        raw.select(
            F.col("ticker").cast("string").alias("ticker"),
            F.col("volume").cast("double").alias("volume"),
            F.col("open").cast("double").alias("open"),
            F.col("close").cast("double").alias("close"),
            F.col("high").cast("double").alias("high"),
            F.col("low").cast("double").alias("low"),
            F.col("window_start").cast("long").alias("window_start"),
            F.col("transactions").cast("long").alias("transactions"),
        )
        .where(
            F.col("ticker").isNotNull()
            & F.col("window_start").isNotNull()
            & F.col("open").isNotNull()
            & F.col("close").isNotNull()
            & F.col("high").isNotNull()
            & F.col("low").isNotNull()
        )
    )

    first_bar = (
        bars.withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("ticker").orderBy(
                    F.col("window_start").asc(), F.col("open").asc()
                )
            ),
        )
        .where(F.col("rn") == 1)
        .select(
            "ticker",
            F.col("open").alias("open"),
            F.col("window_start").alias("first_window_start"),
        )
    )

    last_bar = (
        bars.withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("ticker").orderBy(
                    F.col("window_start").desc(), F.col("close").desc()
                )
            ),
        )
        .where(F.col("rn") == 1)
        .select(
            "ticker",
            F.col("close").alias("close"),
            F.col("window_start").alias("last_window_start"),
        )
    )

    totals = bars.groupBy("ticker").agg(
        F.max("high").alias("high"),
        F.min("low").alias("low"),
        F.sum("volume").alias("volume"),
        F.sum("transactions").alias("transactions"),
        F.count("*").alias("bar_count"),
    )

    result = (
        first_bar.join(totals, on="ticker", how="inner")
        .join(last_bar, on="ticker", how="inner")
        .select(
            "ticker",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "transactions",
            "bar_count",
            "first_window_start",
            "last_window_start",
        )
        .orderBy("ticker")
    )

    output_df = result.coalesce(output_partitions)
    output_df.write.mode("overwrite").option("header", "true").csv(output_path)

    spark.stop()


if __name__ == "__main__":
    main()
