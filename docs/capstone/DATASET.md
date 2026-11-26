# Dataset and Data Governance

## Veri kaynakları ve erişim

| Kaynak | Araştırmadaki rolü |
|---|---|
| OpenSky `/api/states/all` | İşlenmiş uçak konum vektörleri. Producer global ve Türkiye modlarını destekliyor. 120 saniye yapılandırılmış varsayılan bekleme. Kimliksiz mod ve 429 yanıtları beklemeyi değiştiriyor. [Producer](../../producer/opensky_producer.py#L27) |
| Kafka ve MongoDB raw | Son olayları yeniden işleme ve kısa süreli geçmiş. Her ikisinin varsayılan zaman sınırı **48 saat**. Kafka boyut sınırı ayrıca uygulanır ve MongoDB TTL `ingested_at` alanına bağlıdır. [Kafka retention](../../kafka/admin.py#L45) · [MongoDB TTL ve yazım](../../consumer/mongodb_consumer.py#L280) |
| Yerel gzip Canonical Extended JSON export | Tam kaynak alanlarıyla Phase 0'da incelenen pilot arşiv. MongoDB export ve yedekleme farklı zarf yapıları kullanabiliyor. Parser giriş biçimini doğrulamalı. [Spark export](../../scripts/export-spark-raw-positions.sh#L45) · [MongoDB yedek formatı](../../consumer/mongodb_transfer.py#L40) |
| Spark/Iceberg | Bronze, Silver, Rejected ve Gold tabanlı toplu inceleme. Tabloların snapshot kimlikleri sürümlü girdiler için kullanılabilir. [Iceberg rehberi](../../spark/iceberg-README.md) |
| Mock ve yerel fixture | Parser ve kontrollü test girdileri. Eğitim, gerçek gözlem profili ve sentetik stres testi için `source` ayrı kaydedilir. [Mock producer](../../producer/mock_producer.py#L53) · [Spark fixture](../../spark/tests/fixtures/raw_positions.extended.jsonl) |

## Phase 0 veri bulguları

| Ölçüm | Bulgular |
|---|---|
| Dört yerel export | **4.620.879 ham satır**, **2.704.999 benzersiz `event_id`**. `source` değeri `opensky`. Export'lar arasında aynı olaylar var. |
| Gözlem kapsaması | En eski ve en yeni `observed_at` arasında **3,39 gün**. Sürekli kapsama ve uçuş fazı temsili henüz ölçülmedi. |
| Sampling | Her dosyada uçak başına farklı gözlem zamanları arasındaki medyan **121 saniye**. P90 dosyaya göre **130–466 saniye**. Hesap segmentasyon öncesi. |
| Duplicate observation | Aynı dosya içindeki tekrar eden `(icao24, observed_at)` satırları **%7,4–%8,5**. Benzersiz olay kimliği ile fiziksel gözlemin benzersizliği farklı ölçümler. |
| Eksik alanlar ve zaman | `geo_altitude_m` yaklaşık **%10–%12**, `vertical_rate_mps` **%9,5–%11** eksik. İki export'ta negatif `ingested_at - observed_at` farkı görüldü. |
| Yerel Iceberg metadata | Bir warehouse'da güncel snapshot metadata'sı **2.704.999 Bronze** ve **2.690.086 Silver** satırı bildiriyor. Tablo içerikleri Spark ile tekrar sorgulanmadı. |

Ölçüm zamanı için `time_position`, `last_contact` ve `api_time` kaynakları ayrı incelenmeli. Producer `observed_at` türetirken bu sırayı kullanıyor. Producer tarafındaki `ingested_at`, yeni OpenSky kayıtlarında MongoDB yazımından önce üretiliyor. Mevcut Spark Bronze, Canonical Extended JSON'dan seçilmiş alanları içeri alıyor. `time_position`, `last_contact`, `api_time`, `position_source`, `geo_altitude_m` ve `schema_version` projeksiyonda yer almıyor. İhtiyaç duyulan alanlar için tam export veya tam alanlı arşiv aday girdi. [Phase 0 audit](REPOSITORY_AUDIT.md#dataset-readiness-for-machine-learning) · [Zaman ve kaynak alanları](../../producer/opensky_producer.py#L265) · [Bronze projeksiyonu](../../spark/jobs/hourly_traffic_report.py#L58)

## Eğitim seti gereksinimleri

- **Kimlik ve sıra:** `event_id` ile kayıt tekrarı, `(icao24, observed_at)` ile ölçüm tekrarı ve aynı zamanlı çelişkili payload'lar ölçülür. Uçuş segmenti için kayıtlı bir kimlik veya türetilmiş sınır gerekir. `icao24` hava aracına ait olduğundan birden fazla uçuş içerebilir.
- **Zaman ve özellikler:** UTC event ve API zamanları, ölçüm kaynağı, gözlem aralıkları, gap, on-ground durumu ve feature maskeleri kaydedilir. Görev için hangi alanların hangi zamanda bilindiği açık olmalı.
- **Hedef ve etiket:** Trajectory hedefi aynı uçuş segmentinin gelecekteki gözleminden türetilebilir. **2, 4 ve 6 dakika** geçici horizon adaylarıdır. Anomali etiketi ve ground truth stratejisi henüz açık. Kalite kuralıyla reddedilen olaylar ayrı bir quality kaydı sağlar.
- **Split ve sürüm:** Train/validation/test ataması sequence oluşturulmadan önce yapılır. Segment sınırları, dedup kuralı, horizon eşleme toleransı, split listeleri ve preprocessing sürümü manifest'e girer. Zaman tabanlı test ve uçak holdout'u ayrı tanımlanır.
- **Köken ve erişim:** Manifest minimum dataset kimliği/sürümü, kaynak ve izin referansı, giriş checksum'ları, zaman aralığı, varsa tablo snapshot'ları, gözlem ve dışlama sayıları, şema ve split sürümü içerir. Staj kaynaklı kod ve verinin akademik kullanım ve paylaşım izni açık bir konudur. Ham arşiv ve erişim bilgileri için yetkilendirilmiş saklama alanı kullanılır.

## Arşivleme yaklaşımı

Mevcut Kafka/MongoDB saklama süresi kısa. MongoDB export'unun `ingested_at` watermark'ı ve overlap penceresi, gecikmiş bazı yazımların kaçırılmasına yol açabilir. Kısa dönem hazırlık, eldeki export'ların checksum ve kapsamını kaydederek başlar. Uzun dönem seçiminde Kafka'dan bağımsız arşiv consumer'ı ile MongoDB tabanlı export ve uzlaştırma seçenekleri karşılaştırılacak. İzlenecek gap'ler, kapasite hesabı ve geri yükleme kabulü [Data Profiling and Collection Plan](DATA_PROFILING_AND_COLLECTION_PLAN.md) belgesindedir.
