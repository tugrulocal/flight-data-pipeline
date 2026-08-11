# Release kabul matrisi

Bu tablo fiziksel veya bağımsız hedef makinelerde doldurulur. Mevcut kullanıcı verisi bulunan bir makinede temiz kurulum testi yapılmaz; test için boş ve disposable Docker ortamı kullanılır. Her satırda tarih, işletim sistemi/Docker sürümü ve health/log kanıtı release notlarına eklenir.

| Hedef | Registry temiz kurulum | Offline kurulum | Restart + lag 0 | Backup/boş restore | Sonuç/kanıt |
|---|---|---|---|---|---|
| Windows AMD64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| macOS ARM64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| macOS Intel | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| Linux AMD64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| Linux ARM64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |

## Her hedefte uygulanacak kontroller

1. Docker 24+, Compose v2, CPU mimarisi, 4 GB Docker belleği, port ve disk kontrolünün setup tarafından geçtiğini kaydet.
2. Registry senaryosunda offline archive olmadan sürümlü GHCR image'larıyla `docker compose up -d` çalıştır.
3. Offline senaryosunda image yüklemeden sonra ağı kapat; dış ve iç checksum'u doğrula, bütün container'ları başlat.
4. `docker compose ps -a`, `/health`, `/api/aircraft`, `/api/stats`, WebSocket reconnect ve MapLibre/Leaflet fallback davranışını doğrula.
5. Her iki consumer group için lag değerinin `0` olduğunu kaydet.
6. `docker compose restart` sonrasında health ve lag kontrollerini tekrarla.
7. `backup-mongodb.sh` ile archive al; consumer durdurulmuş boş hedefte restore et ve Mongo sayımlarını karşılaştır.
8. `.env` içindeki `APP_VERSION` değerini bir önceki sürüme alarak rollback image'larının çekilebildiğini doğrula. Mongo şeması geri uyumlu değilse önceden alınmış dump ile geri dönüş yolunu ayrıca dene.

`v1.0.0-rc.1` yalnız bütün satırlar geçtiğinde aynı commit üzerinde `v1.0.0` olarak etiketlenebilir. Kafka retention nedeniyle süresi dolmuş kayıtların Mongo dump ile geri getirilemeyeceği release notunda korunur.
