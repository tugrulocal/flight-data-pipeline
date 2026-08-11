# Global ve Türkiye modları

Varsayılan `OPENSKY_AREA_MODE=global` tüm dünyayı sorgular. Global veri Kafka mesaj hacmini, MongoDB diskini ve frontend yükünü artırdığı için en az 4 GB Docker belleği ve 30 GB boş disk ayrılmalıdır.

.env ayarı:

    OPENSKY_AREA_MODE=global
    POLL_INTERVAL_SECONDS=120

Credential alanları boşsa ilk sorgu hemen yapılır, sonraki global sorgular anonim günlük kotayı korumak için en az 900 saniye aralıkla çalışır. OAuth credential çifti verilirse yapılandırılmış 120 saniye kullanılır. Producer 429 yanıtındaki retry süresine uyar; credential çiftinin yalnız biri verilirse başlangıçta açık hatayla durur.

Tek tur güvenli kontrol için MAX_POLLS=1 kullanın. Sürekli çalışma MAX_POLLS=0 değeridir.

    docker compose logs --tail=50 producer consumer
    curl http://127.0.0.1:5175/api/stats

Türkiye ve yakın çevresi bounding box'ına dönmek için `.env` içinde `OPENSKY_AREA_MODE=turkey` ve OAuth kullanılıyorsa `POLL_INTERVAL_SECONDS=30` ayarlayın. Anonim Türkiye modunda etkili minimum aralık 660 saniyedir ve disk alt sınırı 10 GB'dir.
