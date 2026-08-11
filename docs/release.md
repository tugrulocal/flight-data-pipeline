# Release ve offline dağıtım

Release sırası aynı commit üzerinde `v1.0.0-rc.2` kabul adayı, kabul matrisi tamamlanınca `v1.0.0` etiketidir. `latest` etiketi çalıştırma için gerekmez.

Tag workflow'u:

- Etiket biçimini doğrular ve ortak CI test/audit/integration kapısını çalıştırır.
- Release kapısında dört uygulama image'ına ek olarak resmî Kafka/MongoDB image'larını tarar.
- Dört uygulama için `linux/amd64` ve `linux/arm64` OCI image üretir.
- GHCR'a sürümlü tag ile gönderir ve package görünürlüğünü public yapar.
- SPDX SBOM, SLSA provenance ve OIDC tabanlı keyless Cosign imzası üretir.
- İki mimari için image, Compose, `.env.example`, kurulum scriptleri ve doküman içeren checksum'lı offline paket üretir.

## Offline kurulum

1. İlgili mimarinin `.tar.gz` paketini ve `SHA256SUMS` dosyasını indirin.
2. Dış paketin checksum'unu işletim sisteminize göre doğrulayın:

       sha256sum -c SHA256SUMS-amd64.txt
       shasum -a 256 -c SHA256SUMS-arm64.txt

   Windows PowerShell'de `Get-FileHash -Algorithm SHA256` çıktısını `SHA256SUMS` dosyasındaki değerle karşılaştırın.
3. Paketi `tar -xzf flight-data-pipeline-<version>-<arch>.tar.gz` ile açın.
4. Açılan proje kökünde `scripts/setup.sh` veya `scripts/setup.ps1` çalıştırın. Setup paket içindeki ikinci `SHA256SUMS.txt` dosyasını otomatik doğrular.
5. Setup servisleri otomatik başlatır ve 5175 adresindeki health kontrolünü doğrular. OpenSky credentials isteğe bağlıdır.

Kurulum scripti Docker/Compose, Linux container modu, CPU mimarisi, en az 4 GB Docker belleği, frontend portu ve Türkiye/global moda göre 10/30 GB boş diski kontrol eder. `.env` yoksa global örnekten üretir; secret değerlerini yazdırmaz. Offline archive varsa bütün Compose image'larının gerçekten yüklenmiş olduğunu doğrular; yoksa public GHCR image'larını indirir.

## Registry kurulumu ve doğrulama

Registry kurulumu aynı klasörde offline archive olmadan yapılır. Setup scripti `APP_VERSION` ile belirtilen public GHCR image'larını ve digest-pinned Kafka/MongoDB image'larını çekip sistemi başlatır.

Image imzası ve provenance doğrulaması release yöneticisi tarafından registry referansındaki digest üzerinden yapılmalıdır:

    cosign verify \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com \
      --certificate-identity-regexp 'github.com/.*/flight-data-pipeline/.github/workflows/release.yml' \
      ghcr.io/tugrulocal/flight-data-pipeline-backend@sha256:<digest>

Release workflow'u image başına SPDX SBOM ve provenance attestation'ını registry'ye ekler. Offline pakette ayrıca üçüncü taraf bildirimi bulunur.

## Kabul ve rollback

Kabul matrisi [release-acceptance.md](release-acceptance.md) dosyasında tutulur. Fiziksel/harici makine sonuçları kanıtlarıyla tamamlanmadan final `v1.0.0` etiketi oluşturulmamalıdır.

Önceki sürüme dönüş için `.env` içindeki `APP_VERSION` önceki etikete alınır ve `docker compose up -d` çalıştırılır. Mongo şeması geri uyumlu değilse önceki uygulama verisi export'u kontrollü restore edilir. Kafka retention nedeniyle süresi dolan kayıtlar geri getirilemez.

### Eski yerel MongoDB volume geçişi

Yeni ve boş kurulumda ek işlem gerekmez. Docker Official `mongo` image'ıyla daha önce oluşturulmuş bir `flight-mongodb-data` volume'u dosyaları UID 999 ile saklayabilir; UBI9 slim image UID 1000 kullanır. Logda `Failed to read metadata from /data/db/storage.bson` görülürse önce eski çalışan image ile `backup-mongodb.sh` çıktısı alınmalı, sonra yalnız doğrulanmış volume için sahiplik tek seferlik taşınmalıdır:

    docker compose stop mongodb
    docker run --rm --user 0 --entrypoint /bin/sh \
      -v flight-mongodb-data:/data/db \
      mongodb/mongodb-community-server:8.0.28-ubi9-slim@sha256:905f93fe770819a134dd8f74e14caf319735d068da86ff9c2e7c80dec140f191 \
      -c 'set -eu; test -f /data/db/storage.bson; chown -R 1000:1000 /data/db'
    docker compose up -d --wait

Bu komut belge silmez; volume dosya sahipliğini değiştirir. Eski image'a geri dönmek gerekirse ve dosya izni hatası oluşursa aynı kontrollü işlem `999:999` yönünde ters uygulanır. Yedek doğrulanmadan bu migration çalıştırılmamalıdır.

Güncel güvenlik kapısı ve image seçiminin gerekçesi için [SECURITY.md](../SECURITY.md) dosyasına bakın. Python Alpine, Kafka-native veya MongoDB UBI9 slim digest'leri ya da `librdkafka`/`confluent-kafka` eşleşmesi değiştirilirse iki mimarili build, Trivy ve tam compatibility testi yeniden çalıştırılmalıdır.
