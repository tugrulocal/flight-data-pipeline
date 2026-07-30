from pymongo import DESCENDING, MongoClient


class MongoRepository:
    """REST endpoint'lerinin kullandığı MongoDB okuma katmanı."""

    def __init__(self, uri, database_name):
        self.client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
        )
        database = self.client[database_name]
        self.live_positions = database["live_positions"]
        self.raw_positions = database["raw_positions"]

    def ping(self):
        """MongoDB bağlantısının cevap verdiğini doğrular."""

        self.client.admin.command("ping")

    def list_live_aircraft(self, limit):
        """En yeni canlı uçak durumlarını döndürür."""

        cursor = (
            self.live_positions
            .find()
            .sort("observed_at", DESCENDING)
            .limit(limit)
        )

        return [
            normalize_document(document)
            for document in cursor
        ]

    def get_live_aircraft(self, icao24):
        """Bir uçağın son bilinen durumunu döndürür."""

        document = self.live_positions.find_one(
            {"_id": icao24.lower()}
        )

        return normalize_document(document)

    def get_aircraft_history(self, icao24, limit):
        """Bir uçağın geçmiş konumlarını en yeniden eskiye döndürür."""

        cursor = (
            self.raw_positions
            .find({"icao24": icao24.lower()})
            .sort("observed_at", DESCENDING)
            .limit(limit)
        )

        return [
            normalize_document(document)
            for document in cursor
        ]

    def get_live_statistics(self):
        """Canlı uçak koleksiyonundan temel sayaçları hesaplar."""

        total = self.live_positions.count_documents({})
        airborne = self.live_positions.count_documents(
            {"on_ground": False}
        )
        on_ground = self.live_positions.count_documents(
            {"on_ground": True}
        )
        latest = self.live_positions.find_one(
            {},
            sort=[("observed_at", DESCENDING)],
            projection={"observed_at": 1},
        )

        return {
            "total_aircraft": total,
            "airborne": airborne,
            "on_ground": on_ground,
            "unknown_ground_state": total - airborne - on_ground,
            "last_observed_at": (
                latest.get("observed_at")
                if latest
                else None
            ),
        }

    def close(self):
        """MongoDB bağlantı havuzunu kapatır."""

        self.client.close()


def normalize_document(document):
    """MongoDB belgesini JSON'a uygun bir sözlüğe dönüştürür."""

    if document is None:
        return None

    normalized = dict(document)
    normalized["_id"] = str(normalized["_id"])

    return normalized
