# Capstone Roadmap

Takvim iki akademik döneme yayılır. Aşağıdaki geçişler teslim ve kabul koşullarına bağlıdır. Güncel durum [PROGRESS.md](PROGRESS.md) dosyasındadır.

| Phase | Aşama | Bağımlılık ve teslim | Acceptance criteria |
|---|---|---|---|
| 0 | Repository Audit | Başlangıç kodu, Git durumu ve yerel veri incelendi. Teslim [audit raporu](docs/capstone/REPOSITORY_AUDIT.md). | Mevcut mimari, veri kanıtı, test sonuçları, riskler ve doğrulanmamış noktalar kayıtlı. **Tamamlandı.** |
| 1 | Project Initialization and Persistent Context | Phase 0. Teslim çalışma kuralları, proje bağlamı, araştırma belgeleri ve profiling/collection planı. | Başlangıç commit'i, açık izin konusu, önerilen dal, mevcut durum ve sıradaki görev yazılı. Belge bağlantıları ve değişiklik kapsamı doğrulandı. **Tamamlandı.** |
| 2 | Literature Review and Research Design | Phase 1. Teslim kaynak matrisi, araştırma soruları, etiketleme planı ve ilk deney tasarımı. | Arama/eleme süreci izlenebilir. Araştırma boşluğu kanıtlarıyla tartışılmış. Hipotezler, ölçümler ve ground truth stratejisi gözden geçirilmiş. |
| 3 | Dataset Engineering and Long-Term Data Collection | Phase 1 ile profiling ve hazırlık başlayabilir. Canlı toplama, kullanım kapsamı ve işletim onayı gerektirir. Model verisi için Phase 2'deki etiket ve görev tanımı gerekir. Teslim profil, arşiv planı ve sürümlü dataset. | Kaynak manifest'i ve kalite raporu var. Arşiv yeniden başlatma/kesinti testinde boşlukları saptayabiliyor. Segmentler ve aday horizon kapsamı ölçülmüş. Split, sequence üretiminden önce sabitlenmiş. |
| 4 | Baseline Models | Phase 2 deney protokolü ve Phase 3 dataset sürümü. Teslim basit trajectory ve anomaly baseline'ları, ilk single-task modeller. | Sabit split ve seed ile tekrar koşulabilir. Sonuç tablosu, veri kapsaması, hata ve yanlış alarm ölçümleri mevcut. |
| 5 | Multi-Task Deep Learning | Phase 4 single-task referansları. Teslim ortak encoder ve görev başlıklarından oluşan model adayları. | Aynı girdiler, veri bölümleri, horizon ve değerlendirme kodu ile single-task modellerle karşılaştırılabilir. Model ve loss ayarları sürümlü. |
| 6 | Experimental Evaluation and Ablation Studies | Phase 4 ve 5. Teslim ana karşılaştırma, ablation ve hata analizi. | Birden çok seed, uçuş düzeyinde belirsizlik aralıkları, accuracy/genelleme/verim ölçümleri ve başarısız koşular kayıtlı. Sonuçlar test seti üzerinde tuning yapılmadan üretilmiş. |
| 7 | Real-Time Inference and Map Integration | Phase 6'dan seçilen model ve dağıtım sözleşmesi. Teslim online inference ve MapLibre katmanları. | Replay ile çevrimdışı/online tutarlılık, p50/p95 gecikme, throughput ve kopma sonrası toparlanma ölçülmüş. Gözlem, tahmin ve anomali haritada ayırt edilebilir. |
| 8 | Grounded LLM Assistant | Phase 7'nin sürümlü, yapılandırılmış sonuçları. Teslim doğal dil sorgulama ve açıklama. | Sayılar sonuç kimliği ve model sürümü ile izlenebilir. Eksik, eski veya desteklenmeyen çıktılara verilen yanıtlar doğrulanmış. |
| 9 | Thesis, Paper and Final Demonstration | Phase 6 sonuçları ve Phase 7–8 demo teslimleri. Teslim tez, makale taslağı, demo ve izin verilen reproducibility paketi. | İddialar deney kayıtlarına bağlı. Sınırlamalar, izin kapsamı ve akademik prototip niteliği açık. Demo ve yeniden üretim adımları doğrulanmış. |

## Paralel ilerleme

- Phase 1 sonrasında literature review, yerel export profiling ve uzun vadeli toplamanın kota, depolama ve arşiv tasarımı paralel ilerleyebilir.
- Literature review etiket ve değerlendirme seçeneklerini, profiling ise gözlem aralıklarını ve sınıf bulunabilirliğini besler. Baseline eğitiminden önce bu iki hat ortak dataset ve deney protokolünde buluşur. [Research](docs/capstone/RESEARCH.md) · [Profiling ve toplama planı](docs/capstone/DATA_PROFILING_AND_COLLECTION_PLAN.md)
- İlk dönem için veri ve baseline, ikinci dönem için kontrollü karşılaştırma, inference, açıklama ve tez teslimi hedefleniyor. Resmî teslim tarihleri danışman takvimiyle netleşecek.
