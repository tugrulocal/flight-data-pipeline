"""Raw uçuş export'unu yerel Apache Iceberg Bronze/Silver/Gold tablolarına yazar."""

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import partitioning

from hourly_traffic_report import add_quality_columns, raw_positions_dataframe


def arguments():
    parser = argparse.ArgumentParser(
        description="Uçuş export'undan yerel Iceberg tabloları oluşturur."
    )
    parser.add_argument("--input", required=True, help="Extended JSONL veya .jsonl.gz girdi dosyası")
    parser.add_argument("--warehouse", required=True, help="Iceberg warehouse klasörü")
    parser.add_argument("--namespace", default="flight", help="Iceberg namespace (varsayılan: flight)")
    parser.add_argument(
        "--max-velocity-mps",
        type=float,
        default=400.0,
        help="Silver katmanı için kabul edilen en yüksek hız (varsayılan: 400).",
    )
    parser.add_argument(
        "--max-observation-lag-minutes",
        type=int,
        default=20,
        help="observed_at ile ingested_at arasındaki en yüksek fark (varsayılan: 20).",
    )
    return parser.parse_args()


def create_table(dataframe, table_name, partition_column=None):
    """Yeni Iceberg tablosu oluşturur; var olan tabloyu asla ezmez."""

    writer = dataframe.writeTo(table_name).using("iceberg")
    if partition_column is not None:
        writer = writer.partitionedBy(partitioning.days(partition_column))
    writer.create()


def main():
    args = arguments()
    warehouse = Path(args.warehouse)
    warehouse.mkdir(parents=True, exist_ok=True)

    spark = (
        SparkSession.builder.appName("flight-iceberg-bootstrap")
        .config("spark.sql.session.timeZone", "UTC")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", str(warehouse))
        .config("spark.sql.defaultCatalog", "local")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    assessed = None
    try:
        raw = raw_positions_dataframe(spark, args.input)
        bronze = raw.withColumn("observed_date", F.to_date("observed_at"))
        assessed = add_quality_columns(
            raw,
            args.max_velocity_mps,
            args.max_observation_lag_minutes,
        ).cache()
        silver = assessed.where(F.col("quality_status") == "accepted")
        rejected = assessed.where(F.col("quality_status") == "rejected")

        hourly = (
            silver.withColumn("hour", F.date_trunc("hour", "observed_at"))
            .groupBy("hour", "origin_country")
            .agg(
                F.count("*").alias("position_events"),
                F.countDistinct("icao24").alias("unique_aircraft"),
                F.sum(F.when(~F.col("on_ground"), 1).otherwise(0)).alias("airborne_events"),
                F.round(F.avg("baro_altitude_m"), 1).alias("avg_baro_altitude_m"),
                F.round(F.avg("velocity_mps"), 1).alias("avg_velocity_mps"),
            )
        )
        hourly_activity = (
            silver.withColumn("hour", F.date_trunc("hour", "observed_at"))
            .groupBy("hour")
            .agg(
                F.count("*").alias("position_events"),
                F.countDistinct("icao24").alias("unique_aircraft"),
                F.sum(F.when(~F.col("on_ground"), 1).otherwise(0)).alias("airborne_events"),
                F.round(
                    100.0 * F.sum(F.when(~F.col("on_ground"), 1).otherwise(0)) / F.count("*"),
                    2,
                ).alias("airborne_rate_pct"),
                F.round(F.avg("baro_altitude_m"), 1).alias("avg_baro_altitude_m"),
                F.round(F.avg("velocity_mps"), 1).alias("avg_velocity_mps"),
            )
        )
        quality_summary = (
            assessed.groupBy("quality_status", "quality_reason")
            .count()
        )

        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS local.{args.namespace}")
        tables = {
            "bronze_positions": (bronze, "observed_at"),
            "silver_positions": (silver, "observed_at"),
            "silver_rejected_positions": (rejected, "observed_at"),
            "gold_hourly_traffic": (hourly, "hour"),
            "gold_hourly_activity": (hourly_activity, "hour"),
            "gold_data_quality": (quality_summary, None),
        }
        for table, (dataframe, partition_column) in tables.items():
            create_table(
                dataframe,
                f"local.{args.namespace}.{table}",
                partition_column,
            )

        print("Oluşturulan Iceberg tabloları:")
        for table in tables:
            table_name = f"local.{args.namespace}.{table}"
            print(f"- {table_name}: {spark.table(table_name).count()} kayıt")
        print(f"Warehouse: {warehouse}")
        print("Tablolar yeni oluşturuldu; aynı warehouse'a ikinci kez yazmak güvenli olarak reddedilir.")
    finally:
        if assessed is not None:
            assessed.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
