# Global mod

Varsayılan OPENSKY_AREA_MODE=turkey Türkiye ve yakın çevresi bounding box'ını kullanır. Global mod tüm dünyayı sorgular; OpenSky kotasını, Kafka mesaj hacmini, MongoDB diskini ve frontend yükünü belirgin artırır.

.env ayarı:

    OPENSKY_AREA_MODE=global
    POLL_INTERVAL_SECONDS=120

Aynı ayarları hazır profil ile uygulamak için:

    docker compose -f compose.yaml -f compose.global.yaml up -d

Global kullanım için en az 4 GB Docker belleği ve 30 GB boş disk ayırın. Standart OpenSky hesabında tüm gün kesintisiz global sorgunun kota sınırına ulaşabileceğini kabul edin. Producer 429 yanıtındaki retry süresine uyar; credential çifti eksikse başlangıçta açık hatayla durur.

Tek tur güvenli kontrol için MAX_POLLS=1 kullanın. Sürekli çalışma MAX_POLLS=0 değeridir.

    docker compose logs --tail=50 producer consumer
    curl http://127.0.0.1:5173/api/stats

Türkiye'ye dönmek için OPENSKY_AREA_MODE=turkey ve POLL_INTERVAL_SECONDS=30 kullanın.
