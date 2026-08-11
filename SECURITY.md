# Security policy

Bu proje localhost eğitim kullanımı içindir. Güvenlik açığını public issue içinde secret, token veya kişisel veriyle paylaşmayın; repository sahibine GitHub Security Advisory üzerinden bildirin.

Release güvenlik kapısı:

- Python lock dosyaları pip-audit ile;
- frontend lock dosyası npm audit ile;
- dört uygulama image'ı ile resmî Kafka/MongoDB image'ları Trivy tarafından;
- düzeltme durumu fark etmeksizin bütün Critical/High bulgular için sıfır toleransla taranır.

Normal branch/PR CI dört uygulama image'ını tarar. Tag ile çağrılan release kapısı bunlara resmî Kafka ve MongoDB image taramalarını ekler; kapı geçmeden GHCR publish işi başlamaz.

Bir bulguyu yalnız görünmez kılmak için ignore listesine eklemeyin. İstisna ancak erişilemez kod yolunu kanıtlayan, süreli ve gerekçeli bir VEX kaydıyla değerlendirilebilir.

## 11 Ağustos 2026 RC kapısı

Trivy 0.72.0 ile yapılan güncel yerel taramada dört uygulama image'ı, Kafka-native ve MongoDB UBI9 slim image'larının hem AMD64 hem ARM64 varyantları ayrı ayrı 0 Critical / 0 High sonucuna ulaştı. Python lock dosyalarında ve frontend npm ağacında da bilinen bulgu kalmadı.

İlk seçilen JVM tabanlı Apache Kafka 4.3.1 image'ında 4 Alpine ve 6 Java High; Docker Official `mongo:8.0.28` image'ının bundled Database Tools ve `gosu` binary'lerinde Critical/High bulgular bulundu. Bulgular ignore/VEX ile saklanmadı.

Yerel kullanım kapsamına uygun resmî, iki mimarili minimal varyantlar seçildi:

- `apache/kafka-native:4.3.1@sha256:2885898ba17065023f1bd605f3a81efcfa986014f062b73b91ef5462485f9060`: Trivy 0.72.0 ile 0 Critical / 0 High. Apache bu GraalVM tabanlı image'ı deneysel ve yalnız yerel geliştirme/test için önerir; projenin localhost eğitim kapsamı bununla uyumludur. Java yönetim scriptleri image'da olmadığı için topic/config ve lag işlemleri producer image'ındaki `confluent-kafka` istemcisine taşındı.
- `mongodb/mongodb-community-server:8.0.28-ubi9-slim@sha256:905f93fe770819a134dd8f74e14caf319735d068da86ff9c2e7c80dec140f191`: Trivy 0.72.0 ile 0 Critical / 0 High. Slim image `mongod` ve `mongosh` içerir, zafiyetli Database Tools içermez. Backup/restore consumer image'ındaki PyMongo ile Canonical Extended JSON olarak yapılır.

İlk Python slim tabanlı producer, consumer ve backend image'larının her birinde ham tarama 4 Critical / 19 High işletim sistemi bulgusu gösterdi. Bulguların düzeltme sürümü yoktu; Bookworm tabanı da 6 Critical / 18 High sonucuyla çözüm olmadı.

Üç servis `python:3.13.14-alpine3.23@sha256:9fdbf2e3e82628351513560b121e2ee6ce31cac212be9e070c5a5e2769fb5e76` tabanına taşındı. Alpine stable'ın `librdkafka 2.12.1-r0` paketiyle sürüm uyumu için Python binding `confluent-kafka 2.12.1` olarak sabitlendi. Uygulama ve build bağımlılıklarının kaynakları hash'li lock dosyalarıyla doğrulanır; native wheel'ler ayrı builder katmanında üretilir. Derleyici ve build araçları final image'a girmez. Kafka 4.3.1 uyumluluğu tam integration testiyle, Dockerfile'lar da ayrı AMD64/ARM64 build'leriyle doğrulandı.

`ignore-unfixed` bütün workflow taramalarında kapalı kalır. Yerel güvenlik kapısı artık geçmektedir; publish öncesinde aynı katı kapının GitHub Actions üzerinde de geçmesi ve release kabul matrisinin kaydedilmesi gerekir.

## GitHub Actions tedarik zinciri kontrolü

Repository'nin önceki CI tanımı `aquasecurity/trivy-action@0.33.1` kullanıyordu. Aqua'nın [Mart 2026 güvenlik duyurusuna](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23) göre `0.35.0` öncesi etiketsiz action referansları saldırıdan etkilendi ve kaldırıldı. Public Actions geçmişindeki 31 koşunun tamamı 11 Ağustos 2026 tarihindeydi; `compose-and-images` işi setup aşamasında başarısız olmuş ve Trivy adımlarından hiçbiri başlamamıştı. Bu repository için zararlı action'ın çalıştığına dair kanıt bulunmadı.

CI artık güvenli `v0.36.0` sürümünün tam commit SHA'sına (`ed142fd0673e97e23eac54620cfb913e5ce36c25`) sabitlidir ve Trivy `v0.72.0` kullanır. Uygulama image'ları her branch/PR koşusunda hem AMD64 hem ARM64 build edilip taranır. Release kapısı Kafka ve MongoDB resmî image'larının iki mimarisini de aynı sıfır Critical/High politikasıyla tarar.
