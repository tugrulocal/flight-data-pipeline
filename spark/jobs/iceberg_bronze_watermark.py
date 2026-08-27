"""Bronze tablosunun güvenli incremental export başlangıcını yazmadan hesaplar."""

import argparse
from datetime import timedelta, timezone
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


def arguments():
    parser = argparse.ArgumentParser(
        description="Iceberg Bronze için overlap'li ingested_at watermark hesaplar."
    )
    parser.add_argument("--warehouse", required=True, help="Iceberg warehouse klasörü")
    parser.add_argument("--namespace", default="flight")
    parser.add_argument("--overlap-minutes", type=int, default=5)
    return parser.parse_args()


def utc_isoformat(value):
    """Spark'tan gelen zamanı MongoDB ISODate biçimine dönüştürür."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def main():
    args = arguments()
    if args.overlap_minutes < 0:
        raise ValueError("overlap-minutes negatif olamaz.")
    if not Path(args.warehouse).is_dir():
        raise ValueError(f"Warehouse bulunamadı: {args.warehouse}")

    spark = (
        SparkSession.builder.appName("flight-iceberg-bronze-watermark")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", args.warehouse)
        .config("spark.sql.defaultCatalog", "local")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        latest = spark.table(f"local.{args.namespace}.bronze_positions").agg(
            F.max("ingested_at").alias("latest_ingested_at")
        ).first()["latest_ingested_at"]
        if latest is None:
            raise ValueError("Bronze boş; incremental export için watermark yok.")

        export_since = latest - timedelta(minutes=args.overlap_minutes)
        # Makine tarafından okunacak sabit satırlar: Shell script Spark loglarından
        # yalnız bu anahtarları ayıklar.
        print(f"BRONZE_WATERMARK={utc_isoformat(latest)}")
        print(f"EXPORT_SINCE={utc_isoformat(export_since)}")
        print(f"OVERLAP_MINUTES={args.overlap_minutes}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
