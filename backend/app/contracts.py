PUBLIC_AIRCRAFT_FIELDS = (
    "_id",
    "icao24",
    "callsign",
    "origin_country",
    "latitude",
    "longitude",
    "baro_altitude_m",
    "geo_altitude_m",
    "on_ground",
    "velocity_mps",
    "true_track_deg",
    "vertical_rate_mps",
    "observed_at",
    "ingested_at",
    "source",
    "kafka_topic",
    "kafka_partition",
    "kafka_offset",
)

PUBLIC_AIRCRAFT_PROJECTION = {
    field: 1 for field in PUBLIC_AIRCRAFT_FIELDS
}


def public_aircraft_from_event(event, message=None):
    """Kafka event'ini REST ile aynı public sözleşmeye indirger."""

    public = {
        field: event.get(field)
        for field in PUBLIC_AIRCRAFT_FIELDS
        if field != "_id"
    }
    public["_id"] = str(event.get("_id") or event.get("icao24") or "")

    if message is not None:
        public["kafka_topic"] = message.topic()
        public["kafka_partition"] = message.partition()
        public["kafka_offset"] = message.offset()

    return public
