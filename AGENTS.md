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
- Kafka image: `apache/kafka:4.3.1`
- Kafka çalışma modu: tek node KRaft
- MongoDB image: `mongo:8.0`
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
- `producer/opensky_producer.py` ile İstanbul çevresinden gerçek OpenSky verisi alındı ve Kafka'ya gönderildi.
- OpenSky producer ortam değişkeni destekleyecek ve sürekli çalışabilecek şekilde düzenlendi:
  - `KAFKA_BOOTSTRAP_SERVERS`
  - `KAFKA_TOPIC`
  - `POLL_INTERVAL_SECONDS`
  - `MAX_POLLS`
- `consumer/mongodb_consumer.py` oluşturuldu ve bağlantı ayarları ortam değişkeniyle çalışacak şekilde düzenlendi.
- Consumer'da otomatik offset commit kapatıldı.
- MongoDB yazımları başarılı olduktan sonra senkron manuel commit uygulanıyor.
- Kafka/MongoDB altyapısı `compose.yaml` içine taşındı.
- Kafka ve MongoDB için ayrı named volume'lar tanımlandı.
- `topic-init` servisi topic'i `--if-not-exists` ile oluşturacak şekilde düzeltildi.
- Git repository başlatıldı ve ana dal `main` olarak ayarlandı.
- `requirements.txt` ve `.dockerignore` oluşturuldu.
- Producer ve consumer için Docker image'ları oluşturuldu.
- Producer ve consumer servisleri `compose.yaml` içine eklendi.
- Producer → Kafka → consumer → MongoDB akışı log, lag ve MongoDB sorgularıyla doğrulandı.

## Consumer teslim garantisi

Mevcut consumer tasarımı **at-least-once** işlemeye yakındır:

1. Kafka mesajı alınır.
2. Mesaj `raw_positions` collection'ına yazılır.
3. Aynı uçağın son hali `live_positions` collection'ına upsert edilir.
4. İki MongoDB işlemi de başarılıysa Kafka offset'i senkron commit edilir.
5. Yazma sırasında hata olursa offset commit edilmez.

Consumer çöküp yeniden başladığında commit edilmemiş mesajı yeniden okuyabilir. Bu nedenle raw kayıt kimliği:

```text
topic:partition:offset
```

biçimindedir ve `update_one(..., upsert=True)` ile yazılır. Aynı Kafka mesajı tekrar işlense bile ikinci raw belge oluşmaz. Bu, **idempotent consumer yazımıdır**.

Şu ayrımı kullanıcıya açıkla:

- Producer'da `enable.idempotence=True`, Kafka'ya gönderim tekrarlarındaki duplicate riskini azaltır.
- Consumer'daki idempotent Mongo upsert, aynı Kafka mesajının yeniden işlenmesinde duplicate raw belgeyi önler.
- Bunlar tek başına uçtan uca “exactly once” garantisi değildir.

## MongoDB collection amaçları

### `raw_positions`

- Her Kafka mesajının tarihçesini saklar.
- Analiz, geçmiş sorgusu, yeniden oynatma ve hata inceleme için kullanılır.
- `_id = topic:partition:offset`
- Temel index: `{ icao24: 1, observed_at: -1 }`

### `live_positions`

- Her uçak için yalnızca son bilinen durumu saklar.
- `_id = icao24`
- Frontend haritası ve canlı uçuş listesi buradan okunmalıdır.
- Yeni konum geldiğinde aynı belge upsert ile güncellenir.

## Bilinen teknik riskler ve daha sonraki iyileştirmeler

- Hatalı/bozuk bir Kafka mesajı consumer'ın aynı offset'te tekrar tekrar durmasına yol açabilir. Retry sınırı ve dead-letter topic daha sonra eklenmeli.
- Yeni ve boş bir Kafka cluster'ı eski MongoDB volume'uyla birleştirilirse `topic:partition:offset` kimlikleri çakışabilir. Cluster değişiminde yeni volume kullan veya kimliğe cluster/source bilgisi ekle.
- OpenSky anonim API kotası nedeniyle sürekli çalışma aralığı varsayılan olarak 300 saniyedir. Daha sık sorgu için kimlik doğrulama ve kota kuralları resmî dokümantasyondan doğrulanmalıdır.
- Frontend MongoDB'ye doğrudan bağlanmamalıdır; veri FastAPI üzerinden sunulmalıdır.
- Frontend Kafka broker'a doğrudan bağlanmamalıdır; gerçek zamanlı mesajlar FastAPI WebSocket üzerinden yayınlanmalıdır.
- MongoDB writer ve FastAPI realtime consumer aynı Kafka group'u kullanmamalıdır. Aynı group kullanılırsa mesajlar iki işlev arasında paylaştırılır; her ikisi de bütün mesajları alamaz.
- WebSocket geçici güncelleme kanalıdır. İlk yükleme ve bağlantı sonrası yeniden eşitleme için `live_positions` REST endpoint'i kalıcı durum kaynağı olmalıdır.
- Geliştirme ortamındaki plaintext Kafka ve kimlik doğrulamasız MongoDB yalnızca local eğitim içindir.

## Sıradaki işler

Öncelik sırasını koru:

1. Mevcut dosyaları ve Git durumunu incele.
2. FastAPI backend oluştur:
    - sağlık kontrolü
    - `live_positions` üzerinden canlı uçak listesi
    - `live_positions` üzerinden tek uçak son durumu
    - `raw_positions` üzerinden uçak geçmişi
    - temel istatistikler
    - `flight-realtime-gateway-v1` group'uyla Kafka consumer
    - Kafka mesajlarını yayınlayan WebSocket endpoint'i
3. Backend Dockerfile oluştur ve `compose.yaml` içine backend servisini ekle.
4. Backend REST, WebSocket, Kafka group ve kapanış davranışını test et.
5. Frontend oluştur:
    - canlı uçak tablosu
    - harita üzerinde marker'lar
    - son güncelleme ve sistem durumu
    - ilk açılış ve WebSocket yeniden bağlantısında REST snapshot alma
    - canlı güncellemeleri yalnızca FastAPI WebSocket'ten alma
6. Consumer retry/DLQ ve gözlemlenebilirlik geliştirmelerini ekle.

Bir sonraki aşamaya geçmeden önce mevcut aşamayı çalışan bir testle doğrula.

## Beklenen proje yapısı

```text
flight-data-pipeline/
├── AGENTS.md
├── README.md
├── .gitignore
├── .dockerignore
├── compose.yaml
├── requirements.txt
├── producer/
│   ├── Dockerfile
│   ├── mock_producer.py
│   └── opensky_producer.py
├── consumer/
│   ├── Dockerfile
│   └── mongodb_consumer.py
├── backend/
│   ├── Dockerfile
│   └── app/
└── frontend/
```

Henüz bulunmayan dosya veya klasörleri varmış gibi kabul etme; önce kontrol et.

## Doğrulama komutları

### Python sözdizimi

```bash
python -m py_compile producer/opensky_producer.py
python -m py_compile consumer/mongodb_consumer.py
```

### Compose yapılandırması

```bash
docker compose config
docker compose config --services
docker compose ps -a
```

### Servis logları

```bash
docker compose logs --tail=50 producer
docker compose logs --tail=50 consumer
docker compose logs --tail=50 kafka
docker compose logs --tail=50 mongodb
```

### Kafka topic

```bash
docker compose exec kafka \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:29092 \
  --describe \
  --topic aircraft.positions.raw.v1
```

### Consumer group ve lag

```bash
docker compose exec kafka \
  /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:29092 \
  --describe \
  --group flight-mongodb-writer-v1
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
