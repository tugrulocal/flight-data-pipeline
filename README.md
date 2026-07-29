# Flight Data Pipeline

OpenSky'dan alınan gerçek uçuş konumlarını Kafka üzerinden MongoDB'ye aktaran; FastAPI REST ve WebSocket arayüzleriyle frontend'de gösterecek yerel bir veri mühendisliği eğitim projesi.

Bu proje yalnızca çalışan bir uygulama üretmek için değil; Docker, Kafka, consumer offset yönetimi, MongoDB veri modelleme, backend API ve frontend veri görselleştirme kavramlarını uygulamalı öğrenmek için geliştiriliyor.

## Hedef veri akışı

```text
OpenSky API
    ↓
Python Producer
    ↓
Kafka: aircraft.positions.raw.v1
    ├──────────────────────────────────────┐
    ↓                                      ↓
MongoDB Consumer                     FastAPI Kafka Consumer
group: flight-mongodb-writer-v1      group: flight-realtime-gateway-v1
    ↓                                      ↓
MongoDB                                  WebSocket
    ├── raw_positions                      ↓
    └── live_positions ──→ FastAPI REST ──→ Frontend harita + tablo
```

İki Kafka consumer farklı group kullanır. Bu sayede Kafka her uçuş mesajını hem MongoDB yazıcısına hem de gerçek zamanlı FastAPI geçidine teslim eder. Aynı group kullanılsaydı mesajlar iki consumer arasında iş bölümüyle dağıtılır ve her iki kol da bütün mesajları göremezdi.

Kafka topic:

```text
aircraft.positions.raw.v1
```

MongoDB writer consumer group:

```text
flight-mongodb-writer-v1
```

FastAPI gerçek zamanlı consumer group:

```text
flight-realtime-gateway-v1
```

MongoDB database:

```text
flightdb
```

## Proje durumu

### Tamamlananlar

- [x] Docker temel komutları ve volume mantığı
- [x] Tek node Kafka/KRaft kurulumu
- [x] Kafka topic oluşturma
- [x] Producer ve consumer terminal deneyi
- [x] Partition, replication factor, consumer group ve offset deneyi
- [x] Consumer kapalıyken oluşan backlog'un yeniden başlatıldığında işlenmesi
- [x] MongoDB container ve named volume
- [x] `raw_positions` ve `live_positions` collection tasarımı
- [x] MongoDB compound index ve `explain()` deneyi
- [x] Python mock producer
- [x] OpenSky gerçek veri producer'ı
- [x] MongoDB'ye yazan, manuel offset commit kullanan consumer
- [x] Kafka ve MongoDB için Docker Compose altyapısı
- [x] Git repository başlangıcı
- [x] Python bağımlılık dosyası ve Docker build context filtresi
- [x] Producer ve consumer Docker image'ları
- [x] Producer ve consumer Compose servisleri
- [x] Producer → Kafka → consumer → MongoDB akış doğrulaması

### Şu anda yapılacak

- [ ] FastAPI backend iskeleti ve sağlık kontrolü
- [ ] `live_positions` tabanlı canlı uçak REST endpoint'leri
- [ ] `raw_positions` tabanlı uçak geçmişi endpoint'i
- [ ] `flight-realtime-gateway-v1` group'uyla Kafka consumer
- [ ] Kafka mesajlarını frontend'e yayınlayan WebSocket endpoint'i

### Sonraki aşamalar

- [ ] Temel istatistik endpoint'i
- [ ] Frontend uçak tablosu
- [ ] Frontend harita görünümü
- [ ] WebSocket kopmasından sonra REST ile durum toparlama
- [ ] Retry ve dead-letter topic
- [ ] Healthcheck, loglama ve gözlemlenebilirlik iyileştirmeleri

## MongoDB veri modeli

### `raw_positions`

Her Kafka mesajı için tarihsel kayıt saklar.

Amaçları:

- Uçağın geçmiş konumlarını sorgulamak
- Analiz yapmak
- Hata durumunda kayıtları incelemek
- Gelecekte veriyi yeniden işleyebilmek

Belge kimliği:

```text
topic:partition:offset
```

Bu kimlik aynı Kafka mesajının consumer çökmesi nedeniyle tekrar işlenmesi halinde duplicate raw kayıt oluşmasını engeller.

Temel index:

```javascript
{ icao24: 1, observed_at: -1 }
```

Bu index, belirli bir uçağın en yeni konumlarını hızlı sorgulamak içindir.

### `live_positions`

Her uçak için yalnızca son bilinen konumu saklar.

Belge kimliği:

```text
_id = icao24
```

Yeni mesaj geldiğinde mevcut uçak belgesi `upsert` ile güncellenir. Frontend ilk açılışta ve WebSocket bağlantısı koptuktan sonra toparlanırken FastAPI REST üzerinden bu collection'daki güncel durumu okuyacaktır.

## Backend veri erişim kararı

FastAPI iki farklı veri yolu sunacaktır:

1. **REST API:** İlk sayfa yüklemesi ve bağlantı sonrası yeniden eşitleme için `live_positions` okur. Bir uçağın geçmiş sorguları `raw_positions` üzerinden yapılır.
2. **WebSocket:** FastAPI, `aircraft.positions.raw.v1` topic'ini `flight-realtime-gateway-v1` group'uyla tüketir ve yeni mesajları bağlı frontend istemcilerine anlık yayınlar.

WebSocket geçici, düşük gecikmeli güncelleme kanalıdır; MongoDB ise yeniden bağlanıldığında başvurulan kalıcı durum kaynağıdır. Frontend Kafka broker'a veya MongoDB'ye doğrudan bağlanmaz.

## Offset ve çökme dayanıklılığı

Consumer'da otomatik offset commit kapalıdır:

```python
"enable.auto.commit": False
"enable.auto.offset.store": False
```

İşlem sırası:

1. Kafka mesajını oku.
2. `raw_positions` collection'ına yaz.
3. `live_positions` collection'ını güncelle.
4. İki MongoDB işlemi başarılıysa offset'i senkron commit et.

Consumer MongoDB yazısından önce çökerse offset ilerlemez. Yeniden başladığında aynı mesajı tekrar alır. Raw yazım idempotent olduğu için tekrar işleme duplicate tarihçe kaydı oluşturmaz.

Bu tasarım veri kaybetmemeyi duplicate riskinden daha öncelikli tutan **at-least-once processing** yaklaşımıdır.

## Ortam değişkenleri

| Değişken | Local varsayılan | Docker Compose değeri | Amaç |
|---|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | `kafka:29092` | Kafka bağlantısı |
| `KAFKA_TOPIC` | `aircraft.positions.raw.v1` | aynı | Mesaj topic'i |
| `KAFKA_CONSUMER_GROUP` | `flight-mongodb-writer-v1` | aynı | Consumer offset kimliği |
| `KAFKA_REALTIME_CONSUMER_GROUP` | `flight-realtime-gateway-v1` | aynı | FastAPI WebSocket consumer offset kimliği |
| `MONGODB_URI` | `mongodb://localhost:27017` | `mongodb://mongodb:27017` | MongoDB bağlantısı |
| `MONGODB_DATABASE` | `flightdb` | aynı | Database adı |
| `POLL_INTERVAL_SECONDS` | `300` | `300` | OpenSky çağrı aralığı |
| `MAX_POLLS` | `0` | `0` | `0`, producer'ın sürekli çalışmasıdır |

`localhost`, program Mac üzerinde çalışırken kullanılır. Docker container içindeki servisler birbirlerine Compose servis adlarıyla ulaşır: `kafka` ve `mongodb`. `KAFKA_REALTIME_CONSUMER_GROUP` backend aşamasında kullanılacak planlı değişkendir.

## Temel komutlar

Sistemi başlat:

```bash
docker compose up -d
```

Image'ları yeniden oluşturup başlat:

```bash
docker compose up -d --build
```

Servis durumlarını göster:

```bash
docker compose ps -a
```

Producer ve consumer loglarını izle:

```bash
docker compose logs -f producer consumer
```

Sistemi durdur:

```bash
docker compose stop
```

Yeniden çalıştır:

```bash
docker compose start
```

Container ve ağı kaldır, volume'ları koru:

```bash
docker compose down
```

> `docker compose down -v` volume'ları ve içlerindeki Kafka/MongoDB verisini siler. Bilinçli veri temizliği dışında kullanılmamalıdır.

## OpenSky producer

Producer İstanbul ve çevresi için aşağıdaki bounding box ile veri alır:

```python
{
    "lamin": 40.50,
    "lomin": 27.50,
    "lamax": 42.00,
    "lomax": 30.00,
}
```

Her geçerli uçak ayrı Kafka mesajı olur. Kafka message key olarak `icao24` kullanılır. Aynı uçağın mesajlarının aynı partition'a yönlenebilmesi ve sırasının korunabilmesi için key önemlidir.

Anonim API kotasını kontrollü kullanmak için varsayılan çağrı aralığı 300 saniyedir.

## Geliştirme yaklaşımı

Her özellik şu döngüyle geliştirilir:

1. Amaç ve veri akışındaki yeri açıklanır.
2. Küçük bir değişiklik uygulanır.
3. Sözdizimi/yapılandırma kontrol edilir.
4. Servis çalıştırılır.
5. Log, Kafka offset/lag veya MongoDB sorgusuyla sonuç doğrulanır.
6. Ne öğrenildiği özetlenir.
7. Çalışan aşama Git commit'iyle güvence altına alınır.

Codex için ayrıntılı çalışma kuralları ve güncel proje bağlamı [`AGENTS.md`](AGENTS.md) dosyasındadır.

## Yakın hedef

Bir sonraki çalışan kilometre taşı:

```text
docker compose up -d --build
        ↓
OpenSky producer veri alıyor
        ↓
Kafka topic offsetleri ilerliyor
        ↓
Consumer MongoDB'ye yazıyor
        ↓
raw_positions ve live_positions doluyor
```

Bu kilometre taşı doğrulandı. Sıradaki çalışan hedef:

```text
Frontend ilk açılışı / yeniden bağlantı
        ↓
FastAPI REST → MongoDB live_positions

Yeni Kafka mesajı
        ↓
FastAPI consumer (flight-realtime-gateway-v1)
        ↓
WebSocket → Frontend

Uçak geçmişi isteği
        ↓
FastAPI REST → MongoDB raw_positions
```
