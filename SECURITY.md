# Security policy

Bu proje localhost eğitim kullanımı içindir. Güvenlik açığını public issue içinde secret, token veya kişisel veriyle paylaşmayın; repository sahibine GitHub Security Advisory üzerinden bildirin.

Release güvenlik kapısı:

- Python lock dosyaları pip-audit ile;
- frontend lock dosyası npm audit ile;
- dört uygulama image'ı ile resmî Kafka/MongoDB image'ları Trivy tarafından;
- yalnız düzeltmesi bulunan Critical/High bulgular için sıfır toleransla taranır.

Normal branch/PR CI dört uygulama image'ını tarar. Tag ile çağrılan release kapısı bunlara resmî Kafka ve MongoDB image taramalarını ekler; kapı geçmeden GHCR publish işi başlamaz.

Bir bulguyu yalnız görünmez kılmak için ignore listesine eklemeyin. İstisna ancak erişilemez kod yolunu kanıtlayan, süreli ve gerekçeli bir VEX kaydıyla değerlendirilebilir.

## 6 Ağustos 2026 RC kapısı

Yerel taramada dört custom uygulama image'ı 0 Critical / 0 High sonucuna ulaştı. Buna karşılık en güncel desteklenen Apache Kafka 4.3.1 resmî image'ında düzeltmesi yayımlanmış High bağımlılık bulguları; MongoDB 8.0.28 resmî image'ının bundled araçlarında Critical/High bulgular bulundu. Release workflow'u bu nedenle RC publish işini bilinçli olarak durduracaktır. Upstream düzeltmeli resmî image yayımlanana veya kapsamı kanıtlayan VEX incelemesi tamamlanana kadar v1.0.0 yayınlanmamalıdır.
