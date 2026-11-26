# Project Context

**Real-Time Aircraft Trajectory Prediction and Anomaly Detection Using Multi-Task Deep Learning**

Bu çalışma, stajda geliştirilen gerçek zamanlı uçuş veri hattını İTÜ Bilgisayar Mühendisliği iki dönemlik bitirme projesinin araştırma altyapısı olarak kullanır. Sistem akademik araştırma prototipi olarak değerlendirilir. Çalışmanın amacı trajectory prediction ve anomaly detection için tekrarlanabilir deneyler yürütmek, sonuçları canlı sisteme bağlamak ve değerlendirmeyi tez ya da makale taslağına taşımaktır.

## Başlangıç referansı

| Alan | Referans |
|---|---|
| İncelenen dal | `main` |
| Phase 0 commit'i | `cf3b28e` (`cf3b28e682c36b1d6f9532a090a4a9d850855d6b`) |
| Phase 0 tarihi ve kanıtları | 2026-11-26 · [Repository Audit Report](docs/capstone/REPOSITORY_AUDIT.md) |
| Geliştirme dalı | `capstone-development`, kullanıcı onayıyla yerelde `cf3b28e` commit'inden oluşturuldu. |
| Kullanım kapsamı | Staj kapsamında üretilmiş kod ve verinin akademik kullanım, paylaşım ve yayın izinleri açık konu. |

## Mevcut sistem ve kanıt düzeyi

OpenSky konum verisi Python producer üzerinden Kafka'ya, oradan MongoDB geçmiş ve son durum koleksiyonlarına akıyor. FastAPI REST ile kayıtları ve Kafka consumer üzerinden WebSocket güncellemelerini sunuyor. React/MapLibre mevcut konumları ve geçmiş rotaları gösteriyor. Spark ve Iceberg, yerel MongoDB export'larından batch analiz üretiyor. [Mevcut ve önerilen mimari](docs/capstone/ARCHITECTURE.md)

- Phase 0'da 65 Python ve 6 frontend unit testi, frontend build ve statik Compose/Kustomize kontrolleri geçti. Mock Playwright turu 5/6 sonuçlandı. Mobil harita zemini yeniden yükleme testi izole tekrarda 1/2 geçti. Docker daemon'una erişim sağlanamadığından canlı entegrasyon ve dağıtım kabulü doğrulanmadı. [Denetim ve test sonuçları](docs/capstone/REPOSITORY_AUDIT.md#existing-functionalities)
- Dört yerel export'ta **4.620.879 ham satır**, **2.704.999 benzersiz `event_id`**, **3,39 günlük** gözlem aralığı ve uçak başına yaklaşık **121 saniyelik** medyan ardışık gözlem farkı ölçüldü. Bu bulgular pilotun kapsamını belirler. [Veri bulguları ve sınırlamalar](docs/capstone/DATASET.md#phase-0-veri-bulguları)

## Araştırma hedefi

**Ana soru.** Trajectory prediction ve anomaly detection görevlerinin ortak bir modelde öğrenilmesi, ayrı single-task modellere kıyasla doğruluk, genelleme ve hesaplama verimliliği açısından avantaj sağlıyor mu?

Bu, literature review ve kontrollü deneylerle sınanacak bir hipotezdir. Özgünlük ve beklenen avantaj açık araştırma konularıdır. Baseline, leakage kontrollü split, anomaly ground truth ve ablation çalışmaları değerlendirme için gereklidir. **2, 4 ve 6 dakika** şimdilik veri bulunabilirliği ölçülecek aday horizon'lardır. [Araştırma tasarımı](docs/capstone/RESEARCH.md) · [Deney protokolü](docs/capstone/EXPERIMENTS.md)

Hedef demo, gözlenen ve tahmin edilen yörüngeleri, anomali işaretlerini ve sonuçlara dayalı bir doğal dil açıklamasını gösterebilir. LLM açıklaması doğrulanabilir backend ve model çıktılarına dayanır. Her sayısal tahminin kaynağı model çıktısı olarak izlenebilir. [Hedef mimari](docs/capstone/ARCHITECTURE.md#önerilen-capstone-mimarisi)

## Güncel çalışma belgeleri

- [AGENTS.md](AGENTS.md) çalışma ve güvenlik kuralları
- [ROADMAP.md](ROADMAP.md) aşamalar, bağımlılıklar ve kabul ölçütleri
- [PROGRESS.md](PROGRESS.md) tamamlanan işler, açık konular ve sıradaki görev
- [DECISIONS.md](docs/capstone/DECISIONS.md) tarihli kararlar ve değerlendirilmekte olan seçenekler
- [Data Profiling and Collection Plan](docs/capstone/DATA_PROFILING_AND_COLLECTION_PLAN.md) ilk veri mühendisliği görevinin planı
