# Release kabul matrisi

Bu tablo fiziksel veya bağımsız hedef makinelerde doldurulur. Mevcut kullanıcı verisi bulunan bir makinede temiz kurulum testi yapılmaz; test için boş ve disposable Docker ortamı kullanılır. Her satırda tarih, işletim sistemi/Docker sürümü ve health/log kanıtı release notlarına eklenir.

| Hedef | Registry temiz kurulum | Offline kurulum | Restart + lag 0 | Backup/boş restore | Sonuç/kanıt |
|---|---|---|---|---|---|
| Windows AMD64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| macOS ARM64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| macOS Intel | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| Linux AMD64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |
| Linux ARM64 | Bekliyor | Bekliyor | Bekliyor | Bekliyor | — |

## Yerel ön-kabul — 11 Ağustos 2026

macOS ARM64 geliştirme makinesinde release öncesi teknik kapı tamamlandı:

- Producer, consumer ve backend Dockerfile'ları `linux/amd64,linux/arm64` için ayrı ayrı build edildi.
- Dört uygulama image'ı ile Kafka ve MongoDB image'larının AMD64 ve ARM64 varyantları Trivy 0.72.0 taramasında `0 Critical / 0 High` verdi.
- İzole integration testi duplicate/idempotency, DLQ, Mongo kesintisi ve backlog recovery, lag, TTL, retention, IXSCAN ve backup/boş restore senaryolarıyla geçti.
- Çalışan release Compose `127.0.0.1:5175` üzerinde sağlıklı; iki consumer group için `total_lag: 0` görüldü ve son 20 dakikalık veride Türkiye kutusu dışında kayıtlar bulundu.
- ARM64 offline paketinin hem dış arşiv checksum'u hem paket içi image/kurulum checksum'ları doğrulandı.
- `v1.0.0-rc.2` temiz named volume testinde Kafka data directory izin hatası verdiği için kabul edilmedi. `v1.0.0-rc.3`, non-root Kafka'yı koruyan `kafka-volume-init` düzeltmesiyle tekrar doğrulanmalıdır.

Bu ön-kabul fiziksel hedef tablosunun yerine geçmez. Özellikle registry'den temiz kurulum ve offline paketten gerçek kurulum, kullanıcı verisi olmayan bağımsız makinelerde ayrıca yapılmalıdır.

## Her hedefte uygulanacak kontroller

1. Docker 24+, Compose v2, CPU mimarisi, 4 GB Docker belleği, port ve disk kontrolünün setup tarafından geçtiğini kaydet.
2. Registry senaryosunda offline archive olmadan setup scriptinin sürümlü GHCR image'larını çekip bütün container'ları başlattığını doğrula.
3. Offline senaryosunda setup scriptinin dış/iç checksum'u doğrulayıp image'ları yüklediğini ve ağ kapalıyken bütün container'ları başlattığını doğrula.
4. `docker compose ps -a`, `/health`, `/api/aircraft`, `/api/stats`, WebSocket reconnect ve MapLibre/Leaflet fallback davranışını doğrula.
5. Her iki consumer group için lag değerinin `0` olduğunu kaydet.
6. `docker compose restart` sonrasında health ve lag kontrollerini tekrarla.
7. `backup-mongodb.sh` ile `.jsonl.gz` export al; consumer durdurulmuş boş hedefte restore et ve Mongo sayımlarını karşılaştır.
8. `.env` içindeki `APP_VERSION` değerini bir önceki sürüme alarak rollback image'larının çekilebildiğini doğrula. Mongo şeması geri uyumlu değilse önceden alınmış uygulama verisi export'u ile geri dönüş yolunu ayrıca dene.

`v1.0.0-rc.3` yalnız bütün satırlar geçtiğinde aynı commit üzerinde `v1.0.0` olarak etiketlenebilir. Kafka retention nedeniyle süresi dolmuş kayıtların Mongo export ile geri getirilemeyeceği release notunda korunur.
