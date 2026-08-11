# Flight Data Pipeline

OpenSky uçuş konumlarını Kafka üzerinden MongoDB'ye taşıyan, FastAPI REST/WebSocket ile React haritada sunan yerel veri mühendisliği projesi.

## Veri akışı

    OpenSky → producer → Kafka aircraft.positions.raw.v1
                              ├→ consumer → MongoDB raw_positions + live_positions
                              └→ backend WebSocket ─┐
    MongoDB live_positions → backend REST ─────────┴→ frontend
    bozuk kalıcı mesajlar → aircraft.positions.dlq.v1

MongoDB yazıcısı ve realtime gateway farklı consumer group kullanır. Teslim modeli **at-least-once + idempotent MongoDB yazımıdır**; uçtan uca exactly-once iddiası yoktur.

## Hızlı başlangıç

Hedef bilgisayarda yalnız Docker Desktop/Engine ve Compose v2 gerekir. Python, Node.js, Kafka ve MongoDB kurulmaz.

    sh scripts/setup.sh

Windows PowerShell:

    powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

Uygulama: http://127.0.0.1:5175

Release Compose yalnız frontend portunu ve yalnız loopback arayüzünde açar. Backend, Kafka ve MongoDB host ağına açılmaz. Global mod varsayılandır. Credential girilmezse ilk OpenSky sorgusu hemen, sonraki anonim sorgular kotayı korumak için 15 dakikada bir yapılır. Credential değerleri yalnız yerel `.env` içine yazılır.

Normal kapatma `docker compose down` komutudur; Kafka ve MongoDB volume'ları korunur. `down -v` veriyi siler ve normal kapatma için kullanılmamalıdır.

GHCR image'ları release workflow'u tag çalıştırdıktan sonra public package olarak kullanılabilir. Yerel geliştirmede aşağıdaki override source'tan image oluşturur.

## Geliştirme ve test

    docker compose -f compose.yaml -f compose.dev.yaml build
    docker compose -f compose.yaml -f compose.dev.yaml up -d

Development override Kafka 9092, MongoDB 27017 ve backend 8000 local portlarını ekler. Kalıcı volume adları release ile aynıdır; down -v veri siler.

Python:

    python -m pip install --require-hashes -r requirements-dev.txt
    python -m pip install --require-hashes -r producer/requirements.txt
    python -m pip install --require-hashes -r consumer/requirements.txt
    python -m pip install --require-hashes -r backend/requirements.txt
    pytest -q

Frontend:

    cd frontend
    npm ci
    npm test
    npm run build

İzole Kafka/MongoDB testi yalnız kendine ait geçici volume'ları kullanır:

    tests/integration/run.sh

## Temel doğrulama

    docker compose ps -a
    curl http://127.0.0.1:5175/health
    curl 'http://127.0.0.1:5175/api/aircraft?limit=5'
    curl http://127.0.0.1:5175/api/stats
    docker compose logs --tail=50 producer consumer backend frontend

GET /api/aircraft yalnız runtime LIVE_POSITION_WINDOW_MINUTES içindeki public uçak alanlarını döndürür; yanıtta window_minutes ve truncated bulunur. REST snapshot ile WebSocket aircraft.batch aynı uçak sözleşmesini kullanır.

MapLibre varsayılandır. WebGL yoksa, harita kurulamazsa veya context kaybolursa kullanıcı seçimi beklenmeden Leaflet açılır; uyumluluk bildirimi ve yeniden deneme düğmesi gösterilir.

## Saklama ve kaynak sınırları

- Kafka raw: 48 saat veya 10 GiB; önce dolan sınır uygulanır.
- Kafka DLQ: 30 gün veya 1 GiB.
- MongoDB raw_positions: ingested_at üzerinden 48 saat TTL.
- MongoDB live_positions: ingested_at üzerinden 7 gün TTL.
- Kafka native broker JVM heap ayarı gerektirmez; MongoDB WiredTiger cache: 512 MiB.
- Global varsayılan: en az 4 GB Docker belleği ve 30 GB boş disk; OAuth ile yapılandırılan poll aralığı 120 saniye, anonim etkili aralık en az 900 saniyedir.
- Türkiye seçeneği: `.env` içinde `OPENSKY_AREA_MODE=turkey`; en az 10 GB boş disk, anonim etkili aralık en az 660 saniyedir.

## Ayrıntılı dokümanlar

- [Operasyon ve hata çözme](docs/operations.md)
- [Global mod](docs/global-mode.md)
- [Backup ve restore](docs/backup-restore.md)
- [Release ve offline dağıtım](docs/release.md)
- [Release kabul matrisi](docs/release-acceptance.md)
- [Üçüncü taraf bildirimleri](THIRD_PARTY_NOTICES.md)
- [Güvenlik politikası ve RC kapısı](SECURITY.md)

Proje localhost eğitimi içindir. LAN erişimi, kullanıcı hesabı, TLS ve internetten yayın v1.0 kapsamı dışındadır. Çalışma sırasında OpenSky ve harita tile'ları için internet gerekir.
