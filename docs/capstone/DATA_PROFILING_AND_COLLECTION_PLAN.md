# Data Profiling and Collection Plan

**Durum:** Phase 1 planı · 2026-11-26

Bu çalışma planı, ayrı bir kodlama görevi olarak açılacak **Data Profiling Report** ve sonraki toplama hazırlığı için ölçümleri tanımlar. İlk giriş, mevcut yerel Canonical Extended JSON export'larıdır. Phase 1 teslimi bu planla sınırlıdır. [Phase 0 bulguları](DATASET.md#phase-0-veri-bulguları)

## 1. Girdi envanteri ve yöntem

1. Export'ları salt okunur aç. Özel çalışma manifest'inde girdi kimliği, format, SHA-256, sıkıştırılmış bayt ve varsa kaynak snapshot referansını kaydet. Rapor için dosya ve uçak kimlikleri yerine toplu ölçüler kullan. Ham arşivler ve secret'lar Git dışında kalır.
2. Gzip akışını satır satır oku, Canonical Extended JSON tarih ve sayı tiplerini normalize et. Bozuk satır, eksik/alışılmadık kaynak, geçersiz koordinat ve çözülemeyen zaman için ayrı sayaç tut. MongoDB `_id` fallback'i ile producer UUID'sini ayır. `observed_at`, `time_position`, `last_contact`, `api_time` ve `ingested_at` anlamlarını koru.
3. Her girdi için ham sayaçları, birleşik girdide `event_id` dedup sonrası sayaçları ve `(icao24, observed_at)` çakışmalarını üret. Çelişkili konum/hız gibi alanları aynı gözlemin tekrarından ayır. Birden çok aday varsa profil raporu kullanılan deterministik seçim kuralını belirtir ve dışlananları sayar.
4. Büyük veri için satırları toplu okuyup zaman sıralama ve dedup işlemlerinde bütçeye uygun disk destekli bir yöntem değerlendir. İlk kontrol için mevcut fixture, sınır durumları için küçük sentetik örnekler kullanılabilir. Aynı girdiler ve aynı ayarlarla yapılan iki koşunun kararlı agregat çıktısı eşleşmeli.

## 2. Profil ölçümleri

| Başlık | Yöntem ve çıktı |
|---|---|
| Gün ve saat dağılımı | UTC `observed_at` ile saat ve gün başına olay ve benzersiz uçak. İlk/son kısmi günleri, boş saatleri ve veri alınmayan dönemleri işaretle. Mümkünse `ingested_at` ile gecikme dağılımını ayrı göster. |
| Coğrafi kapsam | Geçerli koordinatları toplulaştırılmış grid ve Türkiye bounding box içinde/dışında say. Boş veya düşük kapsamalı hücreleri ve kapsam farklarını raporla. Hassas veya tekil uçuş konumları rapora girmez. |
| Benzersiz uçak | Normalize `icao24` değerlerinden birleşik toplam ve zaman/coğrafya kırılımı. Geçersiz veya eksik kimlikleri ayrı say. |
| Sampling interval | Uçak başına zamana göre sıralanan farklı gözlemlerin pozitif farkı. Ham tekrarlar, segmentasyon öncesi p50/p90/p95 ve uzun gap oranları, segmentasyon sonrası ölçümler ayrı gösterilir. Kaynak ve bölge kırılımı, örnek sayısı yeterliyse eklenir. |
| Duplicate observation | Export içi ve export arası `event_id` tekrarları, `event_id` dedup sonrasında aynı `(icao24, observed_at)` ve aynı zamanda farklı payload oranı. Her oran için pay ve payda görünür. |
| Missing feature | `null`, alan yok ve geçersiz değer ayrı sayılır. En az koordinat, barometrik/geometrik irtifa, hız, dikey hız, yön, `on_ground` ve zaman alanlarının eksikliği raporlanır. |
| Muhtemel flight segment | Dedup sonrası gözlemleri uçak ve zamana göre sırala. Farklı gap eşiklerini ve mevcutsa `on_ground` geçişlerini dene. Başlangıç hassasiyet analizi için 5, 10 ve 20 dakika aday eşikler. Segment sayısı, süre/nokta dağılımı, tek noktalı ve kısmi segment oranı verilir. Türetilen segmentler, doğrulanmış sefer kimliği olarak yorumlanmaz. |
| Horizon bulunabilirliği | Her uygun giriş sonu için aynı segmentte 2, 4 ve 6 dakika sonrasına yakın gerçek ölçüm ara. Aday eşleme toleranslarını, örneğin ±30 ve ±60 saniyeyi, ayrı ölç. Hedef giriş bitiminden sonra olmalı ve segment sınırı aşılmamalı. En yakın eşlemenin zaman hatası, bulunan hedef sayısı, uygun giriş sayısı ve her horizon kapsaması raporlanır. Interpolated hedefler gerçek ölçüm kapsamından ayrı tutulur. |

Kapsama oranları mümkünse uçuş ve gözlem düzeyinde birlikte verilir. Bölge veya saat başına düşük örnek sayısı olan kırılımlar genelleme iddiasını desteklemek için kullanılmaz. Segment ve tolerans parametreleri bu aşamada geçici adaylardır.

## 3. Uzun süreli toplama ve depolama maliyeti

| Girdi | Hesaplama ve çıktı |
|---|---|
| Veri üretim hızı | Global ve bölgesel senaryoları ayrı yaz. Mevcut export'lardaki tam UTC günleri için dedup sonrası olay sayısını ölç. Sıkıştırılmış bayt/olay değerini temsili bir örnekten tahmin et ve örtüşen export'ların brüt hacmini ayrı tut. Tam gün sayısı yetersizse belirsizliği belirt. İzinli canlı pilot sonrası başarılı poll, 429, bekleme ve kayıt/poll ölçümlerini kullan. |
| Depolama | `sıkıştırılmış bayt/gün × saklama günü × kopya sayısı` ile ham arşivi hesapla. Bronze/Silver, snapshot, indeks, geçici export alanı ve güvenlik payını ayrı ekle. Haftalık ve dönemlik senaryoları GiB/TiB üzerinden karşılaştır. |
| Diğer maliyetler | Yerel disk, compute süresi, aktarma gereksinimi ve yedek kopya ayrı bütçelenir. Ücretli saklama seçeneği değerlendirilirse sağlayıcı fiyatı ve tarih daha sonra doğrulanır. |
| Kaynak ve onay | Bölge, poll sıklığı, süre, hesap kotası ve kullanım iznini danışman ve kullanıcıyla netleştir. Üretim veya örnek hacimleri tahmin ve ölçüm olarak ayrı göster. |

## 4. Veri kaybını azaltan arşivleme tasarımı

**Seçenek A · Kafka'dan arşiv.** Ayrı consumer group, olay payload'ı ve topic/partition/offset metadata'sını kalıcı parçalar halinde yazar. Parça ve manifest doğrulandıktan sonra offset ilerler. Retry aynı arşiv birimini yeniden üretirse offset aralığı ve checksum ile idempotent işlenir. Partition başlangıç ve bitiş offset'leri, beklenen gap'ler ve decode hataları kaydedilir. Mevcut broker saklama süresi içinde commit/lag izlenir.

**Seçenek B · MongoDB'den export.** Mevcut script ve overlap ile düşük altyapı maliyeti sağlar. `ingested_at` yeni OpenSky olaylarında producer zamanı olduğundan mevcut watermark, MongoDB'ye geç ulaşan veriyi kaçırabilir. Güvenilir sıra işareti veya periyodik pencere uzlaştırması ve `event_id` dedup, arşiv kabulünde değerlendirilir. Export sıklığı ve gecikme bütçesi, varsayılan 48 saatlik TTL'den önce toparlanmaya izin vermeli. [Mevcut export](../../scripts/export-spark-raw-positions.sh#L45) · [Watermark](../../spark/jobs/iceberg_bronze_watermark.py#L47)

Her iki seçenek için arşiv manifest'i zaman sınırı, kayıt sayısı, parçanın checksum'u, şema sürümü ve saklama politikasını içerir. İzlenecek sinyaller son başarılı poll, son arşivlenen olay, arşiv gecikmesi, eksik saat, offset boşluğu, başarısız yazım ve kalan disk. OpenSky'dan hiç alınmayan veri arşivden geri getirilemeyeceği için kaynak kesintileri de ayrı kaydedilir. Arşiv kabulü, onaylı deneme ortamında restart, kesinti ve yeniden oynatma sırasında sıra ve tekrar kontrolü, ardından örnek parti geri yükleme ve checksum doğrulaması içerir. Hedef, çökme sonrası doğrulanabilir toparlanmadır. [Arşiv kararı](DECISIONS.md)

## Teslim ve acceptance criteria

- Yeniden çalıştırma komutu, girdi manifest'i, UTC kapsamı, ölçüm parametreleri ve beklenen çıktı formatı raporda kayıtlı.
- Ölçüm tablosundaki sekiz başlık, pay ve paydaları ile üretilebilmiş. Ham, benzersiz ve profil dışı satır sayıları uzlaşıyor. Aynı input seti kullanılırsa Phase 0 toplamlarıyla fark açıklanmış.
- Segment ve horizon sonuçları en az iki makul parametre seçeneğinde raporlanmış. Hedef gözlemi bulunamayan pencereler sayılmış.
- Toplama ve arşiv planı için depolama tahmini, quota ve izin gereksinimleri, offset/zaman boşluğu kontrolü ve geri yükleme kabulü yazılı.
- Profil çalışması kaynak dosyaları salt okunur kullanıyor. Rapor ve manifest'in paylaşılabilir sürümü gizli değerleri ve tekil kayıtları içermiyor.
