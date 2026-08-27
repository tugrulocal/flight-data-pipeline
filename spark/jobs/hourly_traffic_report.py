"""Raw MongoDB Extended JSONL dosyasından ilk Spark trafik raporu üretir.

Bu iş yalnız okuma yapar: Kafka'ya, MongoDB'ye veya mevcut canlı uygulamaya
yazmaz. Çıktılar yerel Parquet veri gölü ve CSV özetidir.
"""

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


def arguments():
    parser = argparse.ArgumentParser(
        description="Uçuş ham olaylarından saatlik Spark trafik raporu üretir."
    )
    parser.add_argument("--input", required=True, help="Extended JSONL veya .jsonl.gz girdi dosyası")
    parser.add_argument("--output", required=True, help="Yeni oluşturulacak çıktı klasörü")
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


def canonical_number(line, field_name):
    """MongoDB Canonical Extended JSON sayısını Spark sayısına dönüştürür."""

    return F.coalesce(
        F.get_json_object(line, f"$.{field_name}.$numberDouble"),
        F.get_json_object(line, f"$.{field_name}.$numberLong"),
        F.get_json_object(line, f"$.{field_name}.$numberInt"),
        F.get_json_object(line, f"$.{field_name}"),
    ).cast("double")


def canonical_timestamp(line, field_name):
    """MongoDB'nin milisaniye tabanlı Canonical Extended JSON tarihini çözer."""

    milliseconds = F.get_json_object(
        line, f"$.{field_name}.$date.$numberLong"
    ).cast("double")
    iso_value = F.get_json_object(line, f"$.{field_name}.$date")
    return F.coalesce(
        F.to_timestamp(F.from_unixtime(milliseconds / F.lit(1000))),
        F.to_timestamp(iso_value),
    )


def raw_positions_dataframe(spark, input_path):
    """MongoDB'den dışa aktarılan satırları, analiz için tipli tabloya çevirir."""

    lines = spark.read.text(input_path).where(F.length("value") > 0)
    line = F.col("value")
    return lines.select(
        F.get_json_object(line, "$._id").alias("event_id"),
        F.get_json_object(line, "$.icao24").alias("icao24"),
        F.get_json_object(line, "$.callsign").alias("callsign"),
        F.get_json_object(line, "$.origin_country").alias("origin_country"),
        canonical_number(line, "latitude").alias("latitude"),
        canonical_number(line, "longitude").alias("longitude"),
        canonical_number(line, "baro_altitude_m").alias("baro_altitude_m"),
        canonical_number(line, "velocity_mps").alias("velocity_mps"),
        canonical_number(line, "vertical_rate_mps").alias("vertical_rate_mps"),
        canonical_number(line, "true_track_deg").alias("true_track_deg"),
        F.get_json_object(line, "$.on_ground").cast("boolean").alias("on_ground"),
        canonical_timestamp(line, "observed_at"),
        canonical_timestamp(line, "ingested_at"),
    ).toDF(
        "event_id",
        "icao24",
        "callsign",
        "origin_country",
        "latitude",
        "longitude",
        "baro_altitude_m",
        "velocity_mps",
        "vertical_rate_mps",
        "true_track_deg",
        "on_ground",
        "observed_at",
        "ingested_at",
    )


def add_quality_columns(raw, max_velocity_mps, max_observation_lag_minutes):
    """Silver'a alınma kararını ve reddedilme nedenlerini ekler.

    Bu eşik fiziksel bir yasa değil, ilk analiz laboratuvarının yapılandırılabilir
    kalite kuralıdır. Ham Bronze kayıtları hiçbir zaman bu kuralla silinmez.
    """

    if max_observation_lag_minutes < 0:
        raise ValueError("max_observation_lag_minutes negatif olamaz.")

    invalid_identity = (
        F.col("event_id").isNull()
        | F.col("icao24").isNull()
        | ~F.col("icao24").rlike("^[0-9a-f]{6}$")
    )
    invalid_coordinates = (
        F.col("latitude").isNull()
        | ~F.col("latitude").between(-90, 90)
        | F.col("longitude").isNull()
        | ~F.col("longitude").between(-180, 180)
    )
    invalid_velocity = (
        F.col("velocity_mps").isNull()
        | (F.col("velocity_mps") < 0)
        | (F.col("velocity_mps") > F.lit(max_velocity_mps))
    )
    observation_lag_seconds = F.when(
        F.col("observed_at").isNotNull() & F.col("ingested_at").isNotNull(),
        F.unix_timestamp("ingested_at") - F.unix_timestamp("observed_at"),
    )
    stale_observation = observation_lag_seconds > F.lit(
        max_observation_lag_minutes * 60
    )
    quality_reason = F.concat_ws(
        ",",
        F.when(invalid_identity, F.lit("invalid_identity")),
        F.when(F.col("observed_at").isNull(), F.lit("missing_observed_at")),
        F.when(invalid_coordinates, F.lit("invalid_coordinates")),
        F.when(invalid_velocity, F.lit("implausible_velocity")),
        F.when(stale_observation, F.lit("stale_observation")),
    )
    return (
        raw.withColumn("observed_date", F.to_date("observed_at"))
        .withColumn("observation_lag_seconds", observation_lag_seconds)
        .withColumn("quality_reason", quality_reason)
        .withColumn(
            "quality_status",
            F.when(F.length("quality_reason") == 0, F.lit("accepted")).otherwise(
                F.lit("rejected")
            ),
        )
    )


def main():
    args = arguments()
    output_path = Path(args.output)
    if output_path.exists():
        raise ValueError(f"Çıktı klasörü zaten var: {output_path}")

    spark = (
        SparkSession.builder.appName("flight-hourly-traffic-report")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    assessed = None
    try:
        raw = raw_positions_dataframe(spark, args.input)
        bronze = raw.withColumn("observed_date", F.to_date("observed_at"))
        # Aynı veri Bronze, Silver, red ve Gold yazımlarında tekrar kullanılır.
        # Cache, ham JSONL'i her Spark action'ında yeniden taramayı önler.
        assessed = add_quality_columns(
            raw,
            args.max_velocity_mps,
            args.max_observation_lag_minutes,
        ).cache()
        silver = assessed.where(F.col("quality_status") == "accepted")
        rejected = assessed.where(F.col("quality_status") == "rejected")

        quality_counts = {
            row["quality_status"]: row["count"]
            for row in assessed.groupBy("quality_status").count().collect()
        }
        accepted_rows = quality_counts.get("accepted", 0)
        rejected_rows = quality_counts.get("rejected", 0)
        input_rows = accepted_rows + rejected_rows
        print(
            f"Girdi satırı: {input_rows}; Silver kabul: {accepted_rows}; "
            f"Silver red: {rejected_rows}"
        )
        if accepted_rows == 0:
            raise ValueError("Geçerli uçuş olayı bulunamadı; export ve şemayı kontrol edin.")

        bronze_path = str(output_path / "bronze_positions")
        bronze.write.mode("errorifexists").partitionBy("observed_date").parquet(bronze_path)
        silver_path = str(output_path / "silver_positions")
        silver.write.mode("errorifexists").partitionBy("observed_date").parquet(silver_path)
        rejected_path = str(output_path / "silver_rejected_positions")
        rejected.write.mode("errorifexists").partitionBy("observed_date").parquet(rejected_path)

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
            .orderBy("hour", F.desc("position_events"), "origin_country")
        )

        gold_path = str(output_path / "gold_hourly_traffic_csv")
        hourly.coalesce(1).write.mode("errorifexists").option("header", True).csv(gold_path)
        quality_summary = (
            assessed.groupBy("quality_status", "quality_reason")
            .count()
            .orderBy("quality_status", F.desc("count"), "quality_reason")
        )
        quality_path = str(output_path / "gold_data_quality_csv")
        quality_summary.coalesce(1).write.mode("errorifexists").option("header", True).csv(quality_path)
        print("İlk 20 saat/ülke özeti:")
        hourly.show(20, truncate=False)
        print("Veri kalitesi özeti:")
        quality_summary.show(20, truncate=False)
        print(f"Parquet (bronze): {bronze_path}")
        print(f"Parquet (silver): {silver_path}")
        print(f"Parquet (silver rejected): {rejected_path}")
        print(f"CSV raporu (gold): {gold_path}")
        print(f"CSV kalite raporu (gold): {quality_path}")
    finally:
        if assessed is not None:
            assessed.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
