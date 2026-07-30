# Global Flight Mode Plan

## Özet

Global moda kontrollü geçilecek: OpenSky'den tüm dünya verisi alınacak, veri
akışı mevcut mimaride kalacak, frontend Kafka veya MongoDB'ye doğrudan
bağlanmayacak. Türkiye modu varsayılan kalır; global mod ilk aşamada
`POLL_INTERVAL_SECONDS=120` ile denenir.

Varsayılan kararlar:

- `OPENSKY_AREA_MODE=turkey` güvenli varsayılandır.
- Global testler önce `MAX_POLLS=1` ile yapılır.
- Leaflet güvenli fallback ve ilk açılış haritası kalır.
- MapLibre global görünüm için deneysel adaydır.
- `raw_positions` için 48 saat retention uygulanır.

## Uygulama Değişiklikleri

- Producer global modu destekler; `429` durumunda OpenSky retry header'ına
  göre bekler ve kalan kredi bilgisini loglar.
- Global modda 90 saniyenin altındaki çağrı aralıkları için açık uyarı
  gösterilir; önerilen ilk sürekli global değer 120 saniyedir.
- MongoDB writer consumer `raw_positions` için TTL index oluşturur.
  `live_positions` TTL almaz.
- FastAPI Kafka realtime gateway mesajları 250 ms veya 500 uçak dolana kadar
  bufferlar ve `aircraft.batch` WebSocket mesajı yayınlar.
- Frontend hem `aircraft.position` hem de `aircraft.batch` mesajlarını işler.
- Harita snapshot limiti 20.000'e çıkarılır; tablo ilk 300 satırla sınırlanır.

## Test Planı

Python sözdizimi:

```bash
python -m py_compile producer/opensky_producer.py
python -m py_compile consumer/mongodb_consumer.py
python -m py_compile backend/app/*.py
```

Frontend build:

```bash
cd frontend
npm run build
```

Compose kontrol:

```bash
docker compose config
docker compose ps -a
```

Global tek poll test:

```bash
OPENSKY_AREA_MODE=global MAX_POLLS=1 POLL_INTERVAL_SECONDS=120 \
  docker compose up producer
```

Sürekli global test için `.env` içinde:

```env
OPENSKY_AREA_MODE=global
POLL_INTERVAL_SECONDS=120
MAX_POLLS=0
```

Kontroller:

- Producer kaç state aldığını ve kalan krediyi loglar.
- MongoDB consumer lag'i sıfıra iner.
- `raw_positions` TTL index'i görünür.
- Backend `/health` içinde `published_batches` artar.
- Frontend Leaflet ile stabil açılır, MapLibre deney modunda uçak gösterir.

## Kabul Kriterleri

- Türkiye modu bozulmadan çalışır.
- Global tek poll başarıyla tamamlanır.
- Global snapshot frontend'e gelir.
- WebSocket batch mesajları frontend state'e doğru uygulanır.
- `raw_positions` TTL index'i MongoDB'de görünür.
- `live_positions` TTL'den etkilenmez.
- OpenSky 429 durumunda producer bekleyip devam eder.
- Frontend ilk açılışta Leaflet ile stabil kalır.

## Notlar

- OpenSky global `/states/all` isteği yüksek kredi maliyetlidir.
- Standart kota için global 30 saniye tüm gün uygun değildir.
- Global DOM marker performansı yeterli olmazsa MapLibre WebGL circle/symbol
  layer ayrı bir optimizasyon aşaması olarak ele alınacaktır.
- Gerçek OpenSky secret değerleri yalnızca local `.env` içinde kalmalıdır.
