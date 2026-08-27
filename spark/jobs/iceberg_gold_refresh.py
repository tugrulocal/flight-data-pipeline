"""Güncel Silver/Rejected sonuçlarından Iceberg Gold özetlerini yeniler."""

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import partitioning


def arguments():
    parser = argparse.ArgumentParser(
        description="Iceberg Gold saatlik trafik ve kalite özetlerini yeniler."
    )
    parser.add_argument("--warehouse", required=True, help="Mevcut Iceberg warehouse klasörü")
    parser.add_argument("--namespace", default="flight")
    return parser.parse_args()


def latest_snapshot(spark, table_name):
    return spark.sql(
        f"SELECT snapshot_id, parent_id, summary FROM {table_name}.snapshots "
        "ORDER BY committed_at DESC LIMIT 1"
    ).first()


def overwrite_or_create(spark, dataframe, table_name, partition_column=None):
    """Gold tablosunu atomik yeniler; yeni metrik tablosunu ilk kez oluşturur."""

    if spark.catalog.tableExists(table_name):
        dataframe.writeTo(table_name).overwrite(F.lit(True))
        return

    writer = dataframe.writeTo(table_name).using("iceberg")
    if partition_column is not None:
        writer = writer.partitionedBy(partitioning.days(partition_column))
    writer.create()


def main():
    args = arguments()
    warehouse = Path(args.warehouse)
    if not warehouse.is_dir():
        raise ValueError(f"Warehouse bulunamadı: {warehouse}")

    spark = (
        SparkSession.builder.appName("flight-iceberg-gold-refresh")
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

    try:
        prefix = f"local.{args.namespace}"
        silver = spark.table(f"{prefix}.silver_positions")
        rejected = spark.table(f"{prefix}.silver_rejected_positions")
        hourly_table = f"{prefix}.gold_hourly_traffic"
        activity_table = f"{prefix}.gold_hourly_activity"
        quality_table = f"{prefix}.gold_data_quality"

        hourly = (
            silver.withColumn("hour", F.date_trunc("hour", "observed_at"))
            .groupBy("hour", "origin_country")
            .agg(
                F.count("*").alias("position_events"),
                F.countDistinct("icao24").alias("unique_aircraft"),
                F.sum(F.when(~F.col("on_ground"), 1).otherwise(0)).alias(
                    "airborne_events"
                ),
                F.round(F.avg("baro_altitude_m"), 1).alias("avg_baro_altitude_m"),
                F.round(F.avg("velocity_mps"), 1).alias("avg_velocity_mps"),
            )
        )
        quality = (
            silver.select("quality_status", "quality_reason")
            .unionByName(rejected.select("quality_status", "quality_reason"))
            .groupBy("quality_status", "quality_reason")
            .count()
        )
        hourly_activity = (
            silver.withColumn("hour", F.date_trunc("hour", "observed_at"))
            .groupBy("hour")
            .agg(
                F.count("*").alias("position_events"),
                F.countDistinct("icao24").alias("unique_aircraft"),
                F.sum(F.when(~F.col("on_ground"), 1).otherwise(0)).alias(
                    "airborne_events"
                ),
                F.round(
                    100.0
                    * F.sum(F.when(~F.col("on_ground"), 1).otherwise(0))
                    / F.count("*"),
                    2,
                ).alias("airborne_rate_pct"),
                F.round(F.avg("baro_altitude_m"), 1).alias("avg_baro_altitude_m"),
                F.round(F.avg("velocity_mps"), 1).alias("avg_velocity_mps"),
            )
        )

        # Her tablo kendi içinde atomik biçimde tamamen yenilenir. Yeni metrik
        # tablosu ilk çalışmada oluşturulur; sonraki çalışmalarda eski snapshot
        # görünür kalırken yeni Iceberg snapshot'ı commit edilir.
        overwrite_or_create(spark, hourly, hourly_table, "hour")
        overwrite_or_create(spark, hourly_activity, activity_table, "hour")
        overwrite_or_create(spark, quality, quality_table)

        hourly_snapshot = latest_snapshot(spark, hourly_table)
        activity_snapshot = latest_snapshot(spark, activity_table)
        quality_snapshot = latest_snapshot(spark, quality_table)
        print(f"Gold saatlik trafik satırı: {spark.table(hourly_table).count()}")
        print(f"Gold saatlik aktivite satırı: {spark.table(activity_table).count()}")
        print(f"Gold kalite satırı: {spark.table(quality_table).count()}")
        print(
            f"Saatlik Gold snapshot: {hourly_snapshot['snapshot_id']}; "
            f"parent: {hourly_snapshot['parent_id']}"
        )
        print(
            f"Aktivite Gold snapshot: {activity_snapshot['snapshot_id']}; "
            f"parent: {activity_snapshot['parent_id']}"
        )
        print(
            f"Kalite Gold snapshot: {quality_snapshot['snapshot_id']}; "
            f"parent: {quality_snapshot['parent_id']}"
        )
        print(
            "Gold yenilendi. HTML raporu bundan sonra bu iki güncel tabloyu okuyabilir."
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
