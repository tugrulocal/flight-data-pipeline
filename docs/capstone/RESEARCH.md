# Research Design and Literature Review

**Real-Time Aircraft Trajectory Prediction and Anomaly Detection Using Multi-Task Deep Learning**

## Araştırma soruları

| Kimlik | Soru |
|---|---|
| RQ1 | Ortak bir encoder ile öğrenilen trajectory prediction ve anomaly detection, ayrı single-task modellerle aynı veri ve değerlendirme koşullarında hata veya yanlış alarm oranını iyileştiriyor mu? |
| RQ2 | Sonuçlar daha geç tarihlerde, yeni uçaklarda veya kapsama izin veriyorsa farklı bölgelerde ne ölçüde korunuyor? |
| RQ3 | Tek ortak encoder kullanıldığında iki görevi birlikte yürütmenin gecikme, throughput ve bellek maliyeti nasıl değişiyor? |

## Sınanacak hipotezler

- **H1 · Görev başarısı.** Ortak temsil, aynı değerlendirme koşullarında en az bir görevde iyileşme sağlayabilir. Her görev ayrı raporlanır. Diğer görevin kötüleşmesi ve iyileşme görülmeyen sonuçlar değerlendirmeye dahil edilir.
- **H2 · Genelleme.** Görevler ortak uçuş dinamiklerinden yararlanıyorsa, zamansal veya uçak bazlı holdout'ta performans kaybı ayrı eğitime göre daha küçük olabilir.
- **H3 · Verimlilik.** Tek encoder, aynı donanım ve yük koşullarında iki görevi çalıştırmanın toplam inference maliyetini düşürebilir. Kalite kaybı ve kuyruk gecikmesi ayrıca ölçülür.

Her hipotez için iyileşme görülmemesi olası bir deney sonucudur. Birincil metrikler, anlamlı etki eşiği ve belirsizlik hesabı test split'i açılmadan önce belirlenir. Özgünlük iddiası, kaynak taraması ve kontrollü karşılaştırma kanıtına bağlı. [Deney protokolü](EXPERIMENTS.md)

## Literature review çalışma yapısı

1. **Sorguları kaydet.** Örnek konu kümeleri `ADS-B aircraft trajectory prediction`, `flight trajectory anomaly detection`, `multi-task trajectory forecasting`, `aviation surveillance trajectory dataset` ve `streaming inference`. Her arama için kaynak platformu, tarih, tam sorgu ve filtreyi kaydet.
2. **Eleme ölçütlerini belirle.** İlgili görev, veri kaynağı, örnekleme aralığı, etiketi ve değerlendirme protokolü okunabilen birincil çalışmaları önceliklendir. Dahil etme veya dışlama gerekçesini, tekrar eden yayınları ve erişim sınırlamalarını kaydet.
3. **Çalışmaları karşılaştır.** Farklı horizon, sampling, etiket ve split'lerden gelen skorların karşılaştırılabilirliğini değerlendir. Birlikte öğrenme, ayrı modeller, shared feature extractor ve sadece iki ayrı değerlendirme yapan sistemleri model tasarımı üzerinden tanımla.
4. **Araştırma boşluğunu yaz.** Benzer bulunan çalışmaları, yeniden üretilebilir yönlerini, ölçmedikleri koşulları ve bu projenin hangi kontrolde ek kanıt sunabileceğini göster. İddiaları kaynak matrisiyle ilişkilendir.

| Kaynak / DOI | Veri, bölge, sampling | Görev, horizon ve anomaly ground truth | Model, split ve baseline | Metrikler ve inference ortamı | Kod/veri erişimi, sınırlama ve proje ile ilişkisi |
|---|---|---|---|---|---|
| Phase 2'de doldurulacak | | | | | |

## Anomali ve ground truth seçenekleri

- **Veri kalitesi olayı:** Ölçüm boşluğu, geç veri, fiziksel olarak tutarsız sıçrama veya eksik alan. Spark kalite bayrakları aday veri kaynağıdır. Her kuralın hangi sinyale dayandığı belgelenir.
- **Uçuş davranışı anomalisi:** Tanımlı bir operasyonel bağlama göre sıra dışı yörünge veya manevra. Bağlam, doğrulama yöntemi ve hangi durumlarda belirsiz etiket kullanılacağı Phase 2'de kararlaştırılır. Bağımsız veri ve uzman etiketlemesi erişime bağlı seçeneklerdir.
- **Kontrollü sentetik bozulma:** Ölçüm eksiltme veya konum sapması gibi açıkça tanımlı stres senaryoları. Üretim parametreleri, seed ve gerçek/kurgusal test alt kümeleri kaydedilir.

Etiket birimi olay, pencere veya uçuş olarak seçilecek. Etiket güveni, bilinmeyen örneklerin dışlama koşulu ve uzmanlar arasındaki uyuşmazlığın ele alınışı protokole dahil edilecek. Kalite kuralını hem etiketi üretmek hem de aynı kuralı bir başarı kanıtı olarak kullanmak döngüsel değerlendirme oluşturur. Anomali tanımı, coğrafi kapsam ve yayın hedefi henüz açıktır. [Karar kaydı](DECISIONS.md)
