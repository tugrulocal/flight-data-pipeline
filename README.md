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
- [x] FastAPI backend, Docker image ve Compose servisi
- [x] Sağlık, canlı uçak, detay, geçmiş ve istatistik REST endpoint'leri
- [x] `flight-realtime-gateway-v1` group'uyla Kafka consumer
- [x] Kafka mesajlarını frontend'e yayınlayan WebSocket endpoint'i
- [x] REST, WebSocket, iki consumer group ve kontrollü kapanış doğrulaması
- [x] React + TypeScript frontend
- [x] Leaflet canlı uçuş haritası
- [x] Canlı uçak tablosu, arama ve sistem durumu
- [x] REST snapshot, WebSocket reconnect ve yeniden eşitleme akışı
- [x] Nginx frontend image ve aynı-origin backend proxy
- [x] Nginx üzerinden gerçek OpenSky WebSocket mesajı doğrulaması
- [x] Global mod için OpenSky kota uyarısı, MongoDB TTL retention ve WebSocket batch altyapısı

### Şu anda yapılacak

- [ ] Consumer retry sınırı
- [ ] Dead-letter topic
- [ ] Yapılandırılmış loglar ve temel metrikler

### Sonraki aşamalar

- [ ] Frontend otomatik testleri ve erişilebilirlik kontrolü
- [ ] Production harita tile sağlayıcısı seçimi
- [ ] Gözlemlenebilirlik iyileştirmeleri

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

FastAPI iki farklı veri yolu sunar:

1. **REST API:** İlk sayfa yüklemesi ve bağlantı sonrası yeniden eşitleme için `live_positions` okur. Bir uçağın geçmiş sorguları `raw_positions` üzerinden yapılır.
2. **WebSocket:** FastAPI, `aircraft.positions.raw.v1` topic'ini `flight-realtime-gateway-v1` group'uyla tüketir ve yeni mesajları bağlı frontend istemcilerine anlık yayınlar.

WebSocket geçici, düşük gecikmeli güncelleme kanalıdır; MongoDB ise yeniden bağlanıldığında başvurulan kalıcı durum kaynağıdır. Frontend Kafka broker'a veya MongoDB'ye doğrudan bağlanmaz.

### Backend endpoint'leri

| Yöntem | Yol | Veri kaynağı | Amaç |
|---|---|---|---|
| `GET` | `/health` | MongoDB + Kafka durumu | Servis sağlığı |
| `GET` | `/api/aircraft?limit=200` | `live_positions` | Canlı uçak listesi; global harita snapshot'ı için `limit=20000` kullanılabilir |
| `GET` | `/api/aircraft/{icao24}` | `live_positions` | Tek uçağın son durumu |
| `GET` | `/api/aircraft/{icao24}/history?limit=100` | `raw_positions` | Uçak geçmişi |
| `GET` | `/api/stats` | `live_positions` | Temel uçak sayaçları |
| WebSocket | `/ws/aircraft` | Kafka realtime consumer | Yeni konum yayınları |

Swagger arayüzü `http://localhost:8000/docs`, OpenAPI şeması `http://localhost:8000/openapi.json` adresindedir.

WebSocket bağlantısı önce `connection.ready`, ardından yeni Kafka kayıtları için `aircraft.position` mesajları gönderir. `connection.ready`, ilk verinin WebSocket'ten geleceği anlamına gelmez; frontend başlangıç snapshot'ını REST endpoint'inden almalıdır.

## Frontend teknoloji ve performans kararı

React ve CSS birbirinin alternatifi değildir:

- **React + TypeScript**, REST/WebSocket verisini, bağlantı durumunu, filtreyi ve seçili uçağı yönetir.
- **CSS**, yerleşimi, renkleri, responsive görünümü ve tablo stilini yönetir.
- **MapLibre GL JS**, global harita, WebGL uçak sembolleri ve düz/küre görünümü yönetir.
- **Leaflet**, güvenli fallback harita motoru olarak korunur.
- **Vite**, TypeScript kontrolü ve production build işlemini yapar.
- **Nginx**, statik frontend dosyalarını sunar; `/api`, `/health` ve `/ws` yollarını FastAPI'ye proxy eder.

Harita varsayılan olarak MapLibre GL JS ile açılır. Bunun nedeni global modda
binlerce uçağı DOM marker yerine WebGL symbol layer ile çizerek pan/zoom
akışını daha stabil tutmaktır. MapLibre düz harita ve küre projection geçişini
destekler. Leaflet hâlâ kullanıcı arayüzündeki harita motoru toggle'ı ile
seçilebilen güvenli fallback olarak durur. WebSocket mesajları
`requestAnimationFrame` ile aynı ekran karesinde toplu uygulanır ve tablo en
fazla 300 DOM satırı gösterir.

Uçak renkleri OpenSky benzeri feet tabanlı irtifa skalasına göre seçilmiştir ve
haritanın altında yatay bir renk efsanesi bulunur. Backend verisi metre olarak
gelir; frontend renk hesabında metre değerini feet karşılığına çevirir. Uçağa
tıklandığında frontend `raw_positions` tabanlı history endpoint'inden son
kayıtları alır ve seçili uçağın geçmiş rotasını harita üzerinde çizer. MapLibre
rotayı WebGL `line-gradient` ile yumuşak irtifa renk geçişleri olarak gösterir.
Uçak bilgi popup'ı MapLibre tarafında 1.5 saniye hover sonrası açılır; rota
yükleme için tıklama davranışı korunur.

Canlı ekranda yalnızca yapılandırılan canlı görünüm penceresi içinde gözlenen
uçaklar gösterilir. Varsayılan değer `10` dakikadır; bu değer “son 10 dakika
içinde görülmüş uçakları canlı kabul et” anlamına gelir.
`live_positions` hâlâ uçak başına son bilinen durumu saklar; fakat bu pencerenin
dışında kalan eski son konumlar harita ve canlı listeden gizlenir. Bu kayıtlar
raw veri değildir, yalnızca artık canlı kabul edilmeyen son bilinen konumlardır.
Uçak geçmişi sorguları `raw_positions` üzerinden yapılmaya devam eder.

Producer varsayılan olarak Türkiye ve yakın çevresi modunda kalabilir; global
testlerde `OPENSKY_AREA_MODE=global` ve güvenli başlangıç için
`POLL_INTERVAL_SECONDS=120` kullanılır. Harita dünya üzerinde hareket edebilir;
ancak canlı uçak kapsamı producer'ın o anda topladığı alan kadar olur.

Frontend veri akışı:

1. Sayfa açıldığında `GET /api/aircraft` ile MongoDB snapshot alınır.
2. `/ws/aircraft` bağlantısı kurulur.
3. Bağlantı açıldıktan sonra arada kaçan veri ihtimaline karşı REST snapshot yenilenir.
4. Yeni Kafka olayları WebSocket üzerinden tekil veya batch mesaj olarak gelir
   ve frontend'de ekran karesi içinde toplu biçimde harita ve tabloya uygulanır.
5. WebSocket koparsa artan bekleme süresiyle yeniden bağlanılır ve REST ile tekrar eşitlenir.

Harita, yerel eğitimde API anahtarı gerektirmeyen OpenStreetMap raster tile
katmanını kullanır. Public tile servisi production SLA sunmadığı için production
ortamında kullanım politikası, destek ve erişilebilirlik gereksinimine uygun
bir tile sağlayıcısı veya self-hosted çözüm seçilmelidir.

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
| `RAW_POSITIONS_RETENTION_HOURS` | `48` | `.env` veya `48` | `raw_positions` TTL saklama süresi |
| `OPENSKY_AREA_MODE` | `turkey` | `.env` veya `turkey` | `turkey` veya `global` veri alanı |
| `POLL_INTERVAL_SECONDS` | `30` | `.env` veya `30` | OpenSky çağrı aralığı |
| `MAX_POLLS` | `0` | `.env` veya `0` | `0`, producer'ın sürekli çalışmasıdır |
| `WEBSOCKET_BATCH_INTERVAL_MS` | `250` | `.env` veya `250` | FastAPI WebSocket batch süresi |
| `WEBSOCKET_BATCH_MAX_SIZE` | `500` | `.env` veya `500` | FastAPI WebSocket batch uçak sınırı |
| `OPENSKY_CLIENT_ID` | boş | host `.env` değerinden | OpenSky OAuth API client kimliği |
| `OPENSKY_CLIENT_SECRET` | boş | host `.env` değerinden | OpenSky OAuth API client secret değeri |

`localhost`, program Mac üzerinde çalışırken kullanılır. Docker container içindeki servisler birbirlerine Compose servis adlarıyla ulaşır: `kafka` ve `mongodb`.

OpenSky credential'ları repo'ya yazılmamalıdır. Kayıtlı kullanım için
`.env.example` dosyasını örnek alarak local `.env` dosyası oluştur:

```bash
cp .env.example .env
```

Ardından `.env` içindeki `OPENSKY_CLIENT_ID` ve `OPENSKY_CLIENT_SECRET`
değerlerini doldur. `.env` ve `.env.*` dosyaları `.gitignore` ve
`.dockerignore` içinde gizli dosya olarak korunur.

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

Uygulama servislerinin loglarını izle:

```bash
docker compose logs -f producer consumer backend frontend
```

Backend sağlık ve REST cevaplarını kontrol et:

```bash
curl http://localhost:8000/health
curl 'http://localhost:8000/api/aircraft?limit=5'
curl http://localhost:8000/api/stats
```

Frontend'i aç:

```text
http://127.0.0.1:5173
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

Producer iki veri alanı modunu destekler:

- `OPENSKY_AREA_MODE=turkey`: Türkiye ve yakın çevresi için bounding box kullanır.
- `OPENSKY_AREA_MODE=global`: Bounding box göndermeden tüm dünyayı sorgular.

Varsayılan mod `turkey` olarak bırakılmıştır. Bunun nedeni yanlışlıkla global
modda sürekli çalışıp OpenSky kredisini hızlı tüketmemektir.

Türkiye ve yakın çevresi modu aşağıdaki bounding box ile veri alır:

```python
{
    "lamin": 35.00,
    "lomin": 25.00,
    "lamax": 43.50,
    "lomax": 46.00,
}
```

Her geçerli uçak ayrı Kafka mesajı olur. Kafka message key olarak `icao24` kullanılır. Aynı uçağın mesajlarının aynı partition'a yönlenebilmesi ve sırasının korunabilmesi için key önemlidir.

Çağrı aralığı 30 saniyedir. Türkiye ve yakın çevresi kutusu yaklaşık 178.5
sq° alan tuttuğu için OpenSky `/states/all` kredi tablosunda istek başına
yaklaşık 3 kredi sınıfına girer. 30 saniyede bir tüm gün çalıştırmak yaklaşık
8640 kredi/gün tüketir; anonim kota için sürdürülebilir değildir. Producer 429
aldığında OpenSky'nin `X-Rate-Limit-Retry-After-Seconds` header'ına göre bekler.

Global modda bounding box gönderilmediği için tüm dünya istenir. Bu daha fazla
veri getirir ve `/states/all` kredi tablosunda istek başına en yüksek maliyet
sınıfına yaklaşır. Standart kayıtlı kullanıcı kotasıyla global mod için 30
saniye aralık tüm gün sürdürülebilir değildir; `90` veya `120` saniye daha
güvenli bir başlangıç aralığıdır.

Global tek poll testi için `.env` veya geçici shell ortamında şu değerler
kullanılabilir:

```env
OPENSKY_AREA_MODE=global
POLL_INTERVAL_SECONDS=120
MAX_POLLS=1
```

Sürekli global test için `MAX_POLLS=0` bırakılır. Global modda 90 saniyenin
altında çağrı aralığı seçilirse producer loglarında açık kota uyarısı gösterir.

OpenSky kayıtlı kullanıcı credential'ları verilirse producer OAuth2 client
credentials akışıyla access token alır ve `/states/all` isteklerini `Bearer`
token ile yapar. Token bellekte tutulur ve süresi yaklaşınca yenilenir; token,
client secret veya benzeri gizli değerler loglanmaz. Credential yoksa producer
anonim modda çalışmaya devam eder.

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

## Doğrulanan kilometre taşları

Kalıcı veri akışı:

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

FastAPI veri erişimi ve gerçek zamanlı yayın:

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

İki Kafka consumer group'unda da aynı log sonu offsetine ulaşılıp lag değerinin `0` olduğu ve gerçek OpenSky mesajının WebSocket istemcisine ulaştığı doğrulandı.

## Yakın hedef

React frontend kilometre taşı da doğrulandı:

```text
Frontend açılıyor
        ↓
REST /api/aircraft ile snapshot
        ↓
Tablo + harita oluşturuluyor
        ↓
WebSocket /ws/aircraft ile canlı güncellemeler
        ↓
Bağlantı koparsa yeniden bağlan + REST ile eşitle
```

Sıradaki çalışan hedef, bozuk bir Kafka mesajının MongoDB writer consumer'ını aynı offsette kilitlemesini engelleyen sınırlı retry ve dead-letter topic akışıdır.
