# Flight Data Pipeline — Codex Çalışma Rehberi

Bu repository bir staj eğitim projesidir. Projenin iki eşit amacı vardır:

1. OpenSky uçuş verisini Kafka ve MongoDB üzerinden frontend'e taşıyan çalışan bir sistem kurmak.
2. Kullanıcının Docker, Kafka, MongoDB, backend ve frontend kavramlarını uygulayarak öğrenmesini sağlamak.

## En önemli çalışma kuralı

Sadece kod yazıp görevi kapatma. Kullanıcı başlangıç seviyesinde olduğu için her anlamlı değişiklikte kısa ve açık biçimde şunları anlat:

- Ne yapıyoruz?
- Bu bileşenin sistemdeki görevi nedir?
- Neden bu yaklaşımı seçiyoruz?
- Veri hangi bileşenden hangisine gidiyor?
- Hata veya çökme halinde ne olur?
- Sonucun doğru çalıştığını hangi komut, log veya sorguyla doğruluyoruz?

Kodları repository içinde doğrudan düzenle; kullanıcıdan uzun kodları kopyalayıp yapıştırmasını isteme. Öğretici açıklama yap, ardından güvenli ve geri alınabilir değişiklikleri uygula.

## İletişim biçimi

- Türkçe konuş.
- Terimi önce sade dille açıkla, ardından teknik adını kullan.
- Küçük ve doğrulanabilir aşamalarla ilerle.
- Terminal çıktılarındaki warning, error ve normal logları birbirinden ayır.
- Bir komut verdiğinde parametrelerin önemli olanlarını açıkla.
- Kullanıcının yaptığı işi gereksiz yere tekrar ettirme; önce mevcut dosyaları ve `git diff` çıktısını incele.
- Uzun teori yerine o anda yapılan uygulamayla bağlantılı teori ver.
- Her aşamanın sonunda “ne öğrendik?” ve “sırada ne var?” özeti sun.

## Güvenlik ve değişiklik disiplini

- Çalışmaya başlamadan önce `git status --short` çalıştır ve mevcut kullanıcı değişikliklerini koru.
- Dosyaları değiştirmeden önce ilgili mevcut kodu oku.
- Kullanıcının yaptığı değişiklikleri ezme veya geri alma.
- `.env`, API anahtarı, parola, token ve OAuth secret değerlerini commit etme.
- Gizli ayarlar için `.env.example` kullan; gerçek değerleri yalnızca `.env` içinde tut.
- `docker compose down -v`, volume silme, container silme veya veritabanı temizleme gibi veri kaybettiren işlemleri açık kullanıcı onayı olmadan çalıştırma.
- `kafka-local-backup`, `mongodb-local-backup` ve eski volume'lar kullanıcı açıkça istemedikçe silinmemeli.
- Anlamlı bir aşama tamamlandığında değişiklikleri ve test sonuçlarını özetle; commit öner, ancak kullanıcı istemeden push yapma.

## Hedef mimari

```text
OpenSky REST API
        |
        v
Python OpenSky Producer
        |
        v
Kafka: aircraft.positions.raw.v1
        |
        +------------------------------------+
        |                                    |
        v                                    v
Python MongoDB Consumer              FastAPI Kafka Consumer
group: flight-mongodb-writer-v1      group: flight-realtime-gateway-v1
        |                                    |
        +----------------------+             v
        |                      |         WebSocket
        v                      v             |
raw_positions          live_positions       |
(tarihçe/arşiv)         (son durum)          |
        |                      |             |
        +----------+-----------+             |
                   |                         |
                   v                         |
             FastAPI REST                    |
                   |                         |
                   +------------+------------+
                                |
                                v
                    Frontend tablo + canlı harita
```

Frontend ilk açılış verisini ve WebSocket bağlantısı sonrası toparlanmayı `live_positions` üzerinden REST API ile alır. Geçmiş sorguları `raw_positions` üzerinden yapılır. Frontend Kafka broker'a ve MongoDB'ye doğrudan bağlanmaz.

## Mevcut teknoloji ve isimler

- Yerel geliştirme: macOS, Apple Silicon, Docker Desktop, VS Code
- Kafka image: `apache/kafka-native:4.3.1` (localhost geliştirme/test broker'ı)
- Kafka çalışma modu: tek node KRaft
- MongoDB image: `mongodb/mongodb-community-server:8.0.28-ubi9-slim`
- Kafka topic: `aircraft.positions.raw.v1`
- MongoDB writer consumer group: `flight-mongodb-writer-v1`
- FastAPI realtime consumer group: `flight-realtime-gateway-v1`
- MongoDB database: `flightdb`
- MongoDB collections:
  - `raw_positions`
  - `live_positions`
- Python kütüphaneleri:
  - `confluent-kafka`
  - `pymongo`
  - `requests`
  - `fastapi`
  - `uvicorn`
- Frontend:
  - React + TypeScript
  - Vite
  - Leaflet
  - Nginx

Sürümleri değiştirmeden önce mevcut dosyaları ve uyumluluğu kontrol et. Güncel teknik bilgi gerekiyorsa birincil/resmî kaynak kullan.

## Şimdiye kadar tamamlananlar

- Docker temel komutları uygulandı: image, container, port, volume, start/stop/remove kavramları.
- Kafka container'ı çalıştırıldı ve producer/consumer terminal deneyleri yapıldı.
- Topic, partition, replication factor, consumer group ve offset kavramları uygulandı.
- Aynı group ile consumer yeniden başlayınca son commit edilen offset'ten devam ettiği doğrulandı.
- Consumer kapalıyken producer'ın mesaj üretmeye devam edebildiği ve consumer geri gelince backlog'u işlediği test edildi.
- MongoDB Docker container'ında çalıştırıldı.
- `flightdb`, `raw_positions` ve `live_positions` tasarımı uygulandı.
- `raw_positions` üzerinde `{ icao24: 1, observed_at: -1 }` index'i oluşturuldu.
- `_id` index'i ve `IXSCAN`/`COLLSCAN` mantığı `explain("executionStats")` ile incelendi.
- `producer/mock_producer.py` oluşturuldu.
- `producer/opensky_producer.py` ile Türkiye ve yakın çevresinden gerçek OpenSky verisi alındı ve Kafka'ya gönderildi.
- OpenSky producer ortam değişkeni destekleyecek ve sürekli çalışabilecek şekilde düzenlendi:
  - `KAFKA_BOOTSTRAP_SERVERS`
  - `KAFKA_TOPIC`
  - `POLL_INTERVAL_SECONDS`
  - `MAX_POLLS`
  - `OPENSKY_AREA_MODE`
  - `OPENSKY_CLIENT_ID`
  - `OPENSKY_CLIENT_SECRET`
- `consumer/mongodb_consumer.py` oluşturuldu ve bağlantı ayarları ortam değişkeniyle çalışacak şekilde düzenlendi.
- Consumer'da otomatik offset commit kapatıldı.
- MongoDB yazımları başarılı olduktan sonra senkron manuel commit uygulanıyor.
- Kafka/MongoDB altyapısı `compose.yaml` içine taşındı.
- Kafka ve MongoDB için ayrı named volume'lar tanımlandı.
- `topic-init` servisi topic'i `--if-not-exists` ile oluşturacak şekilde düzeltildi.
- Git repository başlatıldı ve ana dal `main` olarak ayarlandı.
- Servis bazlı, hash doğrulamalı Python lock dosyaları ve `.dockerignore` oluşturuldu.
- Producer ve consumer için Docker image'ları oluşturuldu.
- Producer ve consumer servisleri `compose.yaml` içine eklendi.
- Producer → Kafka → consumer → MongoDB akışı log, lag ve MongoDB sorgularıyla doğrulandı.
- FastAPI backend oluşturuldu ve `compose.yaml` içine eklendi.
- Sağlık, canlı uçak listesi, tek uçak son durumu, geçmiş ve istatistik REST endpoint'leri oluşturuldu.
- Backend, `flight-realtime-gateway-v1` group'uyla Kafka topic'ini tüketip `/ws/aircraft` üzerinden yayın yapıyor.
- İki Kafka group'unun aynı mesajları bağımsız okuyup lag `0` olduğu doğrulandı.
- Gerçek OpenSky mesajının FastAPI WebSocket istemcisine ulaştığı doğrulandı.
- Backend kontrollü restart ile Kafka ve MongoDB bağlantılarını kapatıp sağlıklı biçimde yeniden bağlandı.
- React + TypeScript frontend oluşturuldu.
- Canlı uçak tablosu, arama, sistem durumu ve Leaflet harita eklendi.
- Frontend ilk açılışta REST snapshot alıyor; WebSocket yeniden bağlandığında REST ile tekrar eşitleniyor.
- MapLibre varsayılan harita motoru yapıldı; Leaflet aynı public veri sözleşmesini kullanan otomatik uyumluluk katmanı olarak korundu.
- Uçaklar her iki motorda uçuş yönüne göre döndürülen sembollerle gösteriliyor.
- Uçak renkleri yüksek kontrastlı irtifa aralıklarına göre veriliyor ve haritada metre aralıklarını açıklayan renk efsanesi gösteriliyor.
- Uçağa tıklanınca frontend `raw_positions` history endpoint'inden geçmiş noktaları alıp seçili uçağın rotasını haritada çiziyor. Rota kesikli değildir; segmentler uçağın o noktadaki irtifa aralığına göre renklendirilir.
- MapLibre GL JS varsayılan harita motorudur; uçak sembolleri, popup ve irtifa renkli rota WebGL üzerinde çalışır. WebGL/yükleme/context hatasında otomatik Leaflet fallback açılır ve yeniden deneme düğmesi gösterilir.
- Frontend canlı ekranda yalnızca son 20 dakika içinde gözlenen uçakları gösteriyor; daha eski `live_positions` kayıtları geçmiş/snapshot verisi olarak saklanıyor ama haritadan gizleniyor.
- Harita OpenStreetMap raster tile katmanını kullanıyor.
- WebSocket güncellemeleri `requestAnimationFrame` ile toplu uygulanıyor.
- Frontend Nginx image'ı ve aynı-origin REST/WebSocket proxy yapılandırması oluşturuldu.
- Nginx üzerinden bağlanan WebSocket istemcisinin gerçek OpenSky mesajı aldığı doğrulandı.
- Raw event sözleşmesine `schema_version=1` ve UUID `event_id` eklendi.
- Kalıcı bozuk mesajlar Base64 kaynak zarfıyla `aircraft.positions.dlq.v1` topic'ine güvenli biçimde taşınıyor; DLQ teslimi doğrulanmadan ana offset ilerlemiyor.
- MongoDB geçici hataları sınırlı exponential backoff ile deneniyor; sınır aşılırsa geçerli mesaj DLQ'ya atılmadan consumer non-zero çıkıyor.
- `raw_positions` ve `live_positions` TTL index'leri `ingested_at` üzerinden, canlı liste index'i `observed_at` üzerinden yönetiliyor.
- Unit, frontend, Playwright ve izole Kafka/MongoDB integration test altyapısı eklendi.
- Release Compose yalnız frontend portunu loopback'e açıyor; development override debug portlarını ve source build'lerini ekliyor.
- Release workflow ortak CI/audit/integration kapısından sonra AMD64/ARM64 image, SPDX SBOM, provenance ve keyless Cosign imzası üretir; resmî Kafka/Mongo taraması geçmeden publish başlamaz.
- AMD64/ARM64 offline paketleyici dış ve paket içi SHA-256, sürümlü Compose, setup/backup/restore scriptleri ve operasyon dokümanlarını içerir.
- Setup scriptleri mimari, Linux container modu, Docker/Compose sürümü, 4 GB bellek, port, disk ve offline image bütünlüğünü doğrular; image'ları pull/load edip servisleri health kontrolüyle başlatır. Restore çalışan MongoDB consumer varken veya dolu hedefte açık replace onayı olmadan çalışmaz.

## Consumer teslim garantisi

Mevcut consumer tasarımı **at-least-once + idempotent yazım** sağlar:

1. Kafka mesajı alınır.
2. Mesaj `raw_positions` collection'ına yazılır.
3. Aynı uçağın son hali `live_positions` collection'ına upsert edilir.
4. İki MongoDB işlemi de başarılıysa Kafka offset'i senkron commit edilir.
5. Yazma sırasında hata olursa offset commit edilmez.

Consumer çöküp yeniden başladığında commit edilmemiş mesajı yeniden okuyabilir. Bu nedenle raw kayıt kimliği:

```text
event_id
```

Yeni mesajlarda producer'ın bir kez ürettiği UUID `event_id`, legacy mesajlarda `topic:partition:offset` fallback'i kullanılır. `update_one(..., upsert=True)` sayesinde aynı Kafka mesajı tekrar işlense bile ikinci raw belge oluşmaz.

Şu ayrımı kullanıcıya açıkla:

- Producer'da `enable.idempotence=True`, Kafka'ya gönderim tekrarlarındaki duplicate riskini azaltır.
- Consumer'daki idempotent Mongo upsert, aynı Kafka mesajının yeniden işlenmesinde duplicate raw belgeyi önler.
- Bunlar tek başına uçtan uca “exactly once” garantisi değildir.

## MongoDB collection amaçları

### `raw_positions`

- Her Kafka mesajının tarihçesini saklar.
- Analiz, geçmiş sorgusu, yeniden oynatma ve hata inceleme için kullanılır.
- `_id = event_id`; legacy olaylarda `topic:partition:offset`
- Temel index: `{ icao24: 1, observed_at: -1 }`

### `live_positions`

- Her uçak için yalnızca son bilinen durumu saklar.
- `_id = icao24`
- Frontend haritası ve canlı uçuş listesi buradan okunmalıdır.
- Yeni konum geldiğinde aynı belge upsert ile güncellenir.

## Bilinen teknik riskler ve daha sonraki iyileştirmeler

- DLQ operasyonel olarak izlenmelidir; kalıcı hatalar ana akışı durdurmaz ama veri sözleşmesi sorununu görünmez kılmamalıdır.
- Legacy offset tabanlı `_id` kayıtları korunur; yeni UUID `event_id` yapısı yeni boş Kafka cluster'ı ile restore edilen eski Mongo dump'ında kimlik çakışması riskini azaltır.
- Global mod varsayılandır ve yapılandırılmış çağrı aralığı 120 saniyedir. Credential yoksa producer ilk sorguyu hemen yapar; sonraki sorgularda global için en az 900, Türkiye için en az 660 saniye uygular. Kota hesabı kullanıcının OpenSky hesap türüne göre doğrulanmalıdır; producer rate-limit header'ına göre bekler.
- OpenSky OAuth client credential değerleri yalnızca local `.env` içinde tutulmalıdır; `.env.example` sadece boş örnek değişkenleri içermelidir. Chat'e veya terminal çıktısına düşen secret açığa çıkmış kabul edilmeli ve OpenSky hesabından yenilenmelidir.
- Producer `OPENSKY_AREA_MODE=turkey|global` destekler. `turkey` modunda Türkiye + yakın çevresi bounding box'ı gönderilir; `global` modunda bounding box gönderilmeden tüm dünya istenir. Varsayılan `global` kalmalıdır; Türkiye modu runtime `.env` seçeneğidir.
- Frontend MongoDB'ye doğrudan bağlanmamalıdır; veri FastAPI üzerinden sunulmalıdır.
- Frontend Kafka broker'a doğrudan bağlanmamalıdır; gerçek zamanlı mesajlar FastAPI WebSocket üzerinden yayınlanmalıdır.
- MongoDB writer ve FastAPI realtime consumer aynı Kafka group'u kullanmamalıdır. Aynı group kullanılırsa mesajlar iki işlev arasında paylaştırılır; her ikisi de bütün mesajları alamaz.
- WebSocket geçici güncelleme kanalıdır. İlk yükleme ve bağlantı sonrası yeniden eşitleme için `live_positions` REST endpoint'i kalıcı durum kaynağı olmalıdır.
- Backend şimdilik tek Uvicorn worker ile çalışmalıdır. Birden fazla worker ayrı WebSocket istemci listeleri oluşturur; ortak pub/sub katmanı olmadan Kafka mesajını almayan worker kendi istemcilerine yayın yapamaz.
- Pan/zoom seçili harita motorunun kendi event modeliyle yönetilmelidir; zoom/pan state'i React state'ine taşınmamalıdır.
- Canlı harita eski konumları göstermemelidir. Backend ve frontend runtime `LIVE_POSITION_WINDOW_MINUTES` değerini ortak sözleşmeden uygular; varsayılan 20 dakikadır.
- WebSocket mesajları çok sık gelirse her mesajda ayrı render yerine ekran karesi içinde toplu uygulanmalıdır.
- OpenStreetMap public tile servisi yalnızca local eğitim içindir. Production öncesinde kullanım politikası, destek ve erişilebilirlik gereksinimine uygun bir tile sağlayıcısı veya self-hosted çözüm seçilmelidir.
- Geliştirme ortamındaki plaintext Kafka ve kimlik doğrulamasız MongoDB yalnızca local eğitim içindir.

## Sıradaki işler

1. `v1.0.0-rc.2` image ve offline paketleri yayımlandı ancak temiz Kafka volume izin hatası nedeniyle kabul edilmedi; bu etiket değiştirilmemelidir.
2. `v1.0.0-rc.3` için `kafka-volume-init` ile temiz-volume offline/registry testini, GHCR manifest/SBOM/provenance/Cosign doğrulamasını ve `docs/release-acceptance.md` matrisini tamamla.
3. Bütün kabul satırları geçerse `v1.0.0-rc.3` uygulama commit'i için kullanıcı onayıyla `v1.0.0` etiketi oluştur; kullanıcı istemeden tag/push yapma.

## Beklenen proje yapısı

```text
flight-data-pipeline/
├── AGENTS.md
├── README.md
├── .gitignore
├── .dockerignore
├── compose.yaml
├── requirements-build.in/.txt
├── requirements-dev.in/.txt
├── producer/
│   ├── Dockerfile
│   ├── requirements.in/.txt
│   ├── mock_producer.py
│   └── opensky_producer.py
├── consumer/
│   ├── Dockerfile
│   ├── requirements.in/.txt
│   ├── mongodb_consumer.py
│   └── mongodb_transfer.py
├── kafka/
│   └── admin.py
├── backend/
│   ├── Dockerfile
│   ├── requirements.in/.txt
│   └── app/
└── frontend/
```

Henüz bulunmayan dosya veya klasörleri varmış gibi kabul etme; önce kontrol et.

## Doğrulama komutları

### Python sözdizimi

```bash
python -m py_compile producer/opensky_producer.py
python -m py_compile consumer/mongodb_consumer.py
python -m py_compile backend/app/*.py
```

### Frontend build

```bash
cd frontend
npm ci
npm test
npm run build
```

### İzole integration

```bash
tests/integration/run.sh
```

Bu test DLQ/retry/lag/TTL/retention yanında gerçek, izole MongoDB backup ve boş-target restore akışını da doğrular.

### Release statik ve paket doğrulama

```bash
sh -n scripts/*.sh tests/integration/run.sh
OFFLINE_SKIP_PULL=1 VERSION=v1.0.0-rc.3 PLATFORM=arm64 scripts/build-offline-package.sh
```

Offline test mimarisi çalışılan Docker host mimarisiyle eşleşmelidir. Release workflow'u iki mimariyi ayrı runner işlerinde üretir.

### Compose yapılandırması

```bash
docker compose config --quiet
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
docker compose config --services
docker compose ps -a
```

### Servis logları

```bash
docker compose logs --tail=50 producer
docker compose logs --tail=50 consumer
docker compose logs --tail=50 kafka
docker compose logs --tail=50 mongodb
docker compose logs --tail=50 backend
docker compose logs --tail=50 frontend
```

### Kafka topic

```bash
docker compose run --rm --no-deps topic-init topics
```

### Consumer group ve lag

```bash
docker compose run --rm --no-deps topic-init group flight-mongodb-writer-v1
docker compose run --rm --no-deps topic-init group flight-realtime-gateway-v1
```

### FastAPI REST

```bash
curl http://localhost:8000/health
curl 'http://localhost:8000/api/aircraft?limit=5'
curl http://localhost:8000/api/stats
```

### Frontend ve proxy

```bash
curl http://127.0.0.1:5175/
curl http://127.0.0.1:5175/health
curl 'http://127.0.0.1:5175/api/aircraft?limit=5'
docker compose exec frontend find /usr/share/nginx/html/assets \
  -name '*.js' -type f
```

### MongoDB kayıt sayıları

```bash
docker compose exec mongodb mongosh --quiet flightdb --eval \
  'printjson({
    raw: db.raw_positions.countDocuments(),
    live: db.live_positions.countDocuments()
  })'
```

## Tamamlanma ölçütü

Bir iş yalnızca kod yazıldığı için tamamlanmış sayılmaz. Şunların hepsi bulunmalı:

- Kod veya yapılandırma değişikliği
- Değişikliğin amacı
- Çalıştırılan doğrulama
- Beklenen ve gerçekleşen sonuç
- Kullanıcı için kısa öğrenme özeti
- Gerekliyse güvenli geri alma yolu
