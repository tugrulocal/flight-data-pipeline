# Experiment Protocol

Bu belge deney taslağını ve koşu kayıt şablonunu tanımlar. Sonuç tablosu, ilk ölçümler üretildiğinde doldurulacak.

## Dataset ve split protokolü

1. Ham girdileri, checksum'ları, şemayı ve kalite kurallarını dataset sürümüne bağla. `event_id` çakışmalarını, aynı uçak/zaman tekrarlarını ve belirsiz sıra durumlarını pencere üretiminden önce çöz ve kaydet.
2. Uçuş segmentlerinin train, validation ve test atamalarını **sequence üretiminden önce** sabitle. Birincil değerlendirmede kronolojik split kullanmayı değerlendir. Ayrı bir genelleme deneyi için uçak holdout'u tanımlanabilir. Sınırda kalan segment ve giriş/hedef pencereleri için embargo veya dışlama kuralını kaydet.
3. Ölçekleme, imputasyon parametreleri ve feature dönüşümlerini train üzerinde öğren. İnference anında henüz bilinmeyen bilgileri girdi olarak kullanma. Threshold, hyperparameter ve early stopping seçimini validation üzerinde yap. Test verisi final değerlendirme için ayrılır.
4. Split'ler arasında ortak olay, segment veya sınırı aşan pencere bulunmadığını otomatik kontrol et. Her split için kapsama, eksik feature, anomaly prevalence ve çıkarılan örnek sayılarını kaydet. Zaman aralığına göre tahmin edilebilir örneklerin payını ayrıca raporla. [Dataset gereksinimleri](DATASET.md)

## Baseline ve model matrisi

| Grup | Aday | Kontrol |
|---|---|---|
| Basit trajectory | Son bilinen konumu koruma ve sabit hız/yön ile ilerleme | Aynı as-of zaman, horizon, ölçüm koordinat sistemi ve değerlendirme örnekleri. Eksik hız veya yönde davranış önceden tanımlanır. |
| Basit anomaly | Aday etiket tanımına uygun basit kural ya da istatistiksel eşik | Etiket kaynağından bağımsız değerlendirme. Threshold validation'da seçilir. |
| Single-task | Trajectory için bir, anomaly detection için ayrı LSTM veya GRU | Mümkün olduğunca aynı girdi, temsil, tuning bütçesi ve metrikler. |
| Multi-task | Ortak LSTM/GRU encoder ve iki görev başlığı | Loss ağırlıkları, label maskeleri, backbone ve görev başlıkları kaydedilir. Ortak eğitimde aynı örneklerin hangi görevi beslediği belirtilir. |
| Genişletme | Veri ve compute bütçesi desteklerse Transformer | Mimari farkı, model kapasitesi ve eğitim maliyeti raporlanır. |

Ana karşılaştırmada eşleşen veri, hedef eşleme, split, seed seti ve tuning bütçesi kullanılır. Rapor, single-task modellerin toplam maliyeti ile multi-task modelin iki görev için maliyetini birlikte gösterir. Ablation adayları shared encoder, loss ağırlığı, feature/missingness maskesi ve anomaly supervision kaynağıdır. Kontroller ve birincil metrikler sonuçlar görülmeden önce seçilir.

## Metrikler

| Alan | Aday ölçüm |
|---|---|
| Trajectory | Jeodezik yatay ADE/FDE metre cinsinden, irtifa MAE, horizon başına hedef kapsaması. Benzer örneklerde karşılaştır ve uçuş fazına göre hata kırılımı ver. |
| Anomaly | PR-AUC, sabit yanlış alarm bütçesinde recall, izlenen uçuş saati başına yanlış alarm ve tespit gecikmesi. Etiket birimine göre alarm birleştirme kuralı, prevalence ve belirsiz örnek kapsamı kaydedilir. |
| Genelleme | Zaman holdout'u ve veri uygunsa ayrı uçak veya bölge holdout'u. Seed'ler arası değişkenlik ve uçuş düzeyinde belirsizlik aralığı. |
| Inference | Aynı donanım ve yükte p50/p95 gecikme, throughput, bellek ve model parametre sayısı. Model çalışma süresi, pencere hazırlığı ve uçtan uca gecikme ayrı ölçülür. Batch boyutu, warm-up ve eşzamanlılık kayıtlı tutulur. |

## Koşu kaydı şablonu

| Alan | Kayıt |
|---|---|
| Kimlik ve durum | Run ID, tarih, planlanan/tamamlandı/başarısız, git commit, çalıştırma komutu, config ve artifact referansı |
| Veri | Dataset manifest'i, split sürümü, snapshot ve checksum referansı, preprocessing, window/horizon ve ground truth sürümü |
| Model | Baseline/variant, model ve parametre sayısı, loss ağırlığı, optimizer, seed, tuning bütçesi, eşik ve checkpoint |
| Ortam | Donanım, işletim sistemi, bağımlılık lock veya image digest'i, inference batch ve yük ayarı |
| Sonuç | Split ve horizon, örnek/uçuş sayısı, kapsama, trajectory/anomaly metrikleri, belirsizlik aralığı, inference metrikleri |
| Hata ve yorum | Başarısız adım ve hata sınıfı, config farkı, tekrar koşusu, log/artifact referansı ve gözlenen sınırlama |

Bir sonuç satırı her **run × split × horizon** için şu alanları içerebilir.

| Run | Model | Split | Horizon | Uçuş / pencere | Kapsama | ADE / FDE / alt. MAE | PR-AUC / recall / yanlış alarm | p50 / p95 / throughput | Durum / kanıt |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |
