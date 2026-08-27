# Spark ders 02: local Apache Iceberg

Iceberg, Parquet'in alternatifi değildir. Iceberg tablosunun veri dosyaları yine
Parquet'tir; Iceberg bu dosyalara tablo adı, şema, partition ve snapshot
metadata'sı ekler.

```text
Parquet laboratuvarı:
  spark/output/.../bronze_positions/part-....parquet

Iceberg laboratuvarı:
  local.flight.bronze_positions
      ├── data/      (Parquet veri dosyaları)
      └── metadata/  (tablo şeması ve snapshot'lar)
```

Bu ders yine cluster değildir. Tek Docker container içindeki Spark `local[2]`
çalışır. Iceberg'in `HadoopCatalog` türü, catalog ve warehouse için yalnız local
disk kullanır; MinIO, Kubernetes, Kafka veya ayrı bir Iceberg server kurulmaz.

## İlk Iceberg tablolarını oluştur

Önce mevcut MongoDB export'unu kullan. Warehouse'ın yeni olması gerekir; script
var olan tabloyu veya warehouse'ı ezmeyi reddeder.

```bash
scripts/run-iceberg-local.sh \
  spark/data/validation-raw-positions.jsonl.gz \
  spark/warehouse/ilk-iceberg-lab
```

İlk çalıştırmada Spark, resmi ve Spark 4.0 uyumlu
`iceberg-spark-runtime-4.0_2.13:1.11.0` runtime JAR'ını indirir. Sonraki
çalıştırmalarda `spark/.ivy2/` cache'i kullanılır. JAR ve warehouse Git'e
eklenmez.

## Oluşan tablolar

- `local.flight.bronze_positions`: tüm tiplenmiş ham olaylar
- `local.flight.silver_positions`: kalite kurallarını geçen olaylar
- `local.flight.silver_rejected_positions`: Silver'dan reddedilen olaylar
- `local.flight.gold_hourly_traffic`: saatlik/ülkeli trafik özeti
- `local.flight.gold_hourly_activity`: dashboard için saat başına tek satırlık uçuş aktivitesi
- `local.flight.gold_data_quality`: kabul/red kalite özeti

Silver, 400 m/s üzerindeki/negatif hızları ve `ingested_at - observed_at`
farkı 20 dakikayı aşan `stale_observation` kayıtlarını reddeder. Tazelik
kuralı işlem anındaki saate değil, olayın iki kendi zaman alanına göre çalışır;
bu nedenle tekrar çalıştırmalarda aynı sonuç üretilir.

`bronze_positions`, `silver_positions` ve `silver_rejected_positions`,
`observed_at` gününe göre; saatlik Gold tablosu `hour` gününe göre Iceberg
partition transform kullanır. Klasör adını elle sorgulamak yerine tablo adını
kullanırız.

## Spark SQL ile sorgula

Örneğin Bronze'daki tüm gerçek event sayısı:

```bash
scripts/query-iceberg-local.sh spark/warehouse/ilk-iceberg-lab \
  'SELECT COUNT(*) AS bronze_event_count FROM local.flight.bronze_positions'
```

Silver kalite özeti:

```bash
scripts/query-iceberg-local.sh spark/warehouse/ilk-iceberg-lab \
  'SELECT * FROM local.flight.gold_data_quality ORDER BY quality_status'
```

## Ders 03 — Snapshot ve time-travel

Bir Iceberg yazımı başarılı biçimde tamamlandığında tablo için bir **snapshot**
oluşur: o anki tablo sürümünü gösteren değişmez bir kayıt. `append` yeni bir
snapshot ekler; önceki snapshot'taki Parquet dosyalarını silmez. Bu sayede
güncel tabloyu normal SQL ile, eski tablo hâlini de `VERSION AS OF` ile aynı
tablo adından sorgulayabiliriz.

Bu dersi Bronze/Silver/Gold'a yeniden yazmadan yapıyoruz. Aşağıdaki iki komut,
Bronze'dan yalnız 3 + 2 örnek olayı ayrı `local.flight.snapshot_demo_positions`
eğitim tablosuna kopyalar. `initial` mevcut demo tablosunu ezmeyi; `append` ise
ilk aşama yoksa çalışmayı reddeder.

```bash
scripts/run-iceberg-snapshot-demo.sh \
  spark/warehouse/ilk-iceberg-lab initial

scripts/run-iceberg-snapshot-demo.sh \
  spark/warehouse/ilk-iceberg-lab append
```

İkinci komutun sonunda şuna benzer bir sonuç görürsün: güncel tabloda 5 kayıt,
ilk snapshot'a time-travel yapınca 3 kayıt. Snapshot kimliklerini SQL ile de
görebilirsin:

```bash
scripts/query-iceberg-local.sh spark/warehouse/ilk-iceberg-lab \
  'SELECT snapshot_id, parent_id, committed_at, operation FROM local.flight.snapshot_demo_positions.snapshots ORDER BY committed_at'
```

Çıktıdaki ilk `snapshot_id` değerini aşağıdaki sorguda `ILK_SNAPSHOT_ID`
yerine koy:

```bash
scripts/query-iceberg-local.sh spark/warehouse/ilk-iceberg-lab \
  'SELECT COUNT(*) AS eski_event_sayisi FROM local.flight.snapshot_demo_positions VERSION AS OF ILK_SNAPSHOT_ID'
```

`.snapshots` Iceberg'in metadata tablosudur: normal iş verisini değil, hangi
yazımın hangi sürümü oluşturduğunu gösterir. Normal `SELECT COUNT(*)` her zaman
en güncel snapshot'ı okur. Time-travel sorgusu ise belirtilen snapshot'ın
manifest/Parquet listesini izler. Bu, dosya klasörlerini elle saymaktan daha
güvenilir olan Iceberg tablo soyutlamasıdır.

## Ders 04 — Batch yenilemeden önce dry-run

Canlı uygulama Kafka → MongoDB yolunda çalışmaya devam eder. Analitik taraf,
MongoDB `raw_positions` koleksiyonundan ara sıra yeni bir export alır. Aynı
export önceki olayları da içerir; bu yüzden toplam satır farkına bakarak ekleme
yapamayız. Her olayın kalıcı kimliği olan `event_id` ile karşılaştırma yaparız.

Önce salt-okunur export al:

```bash
scripts/export-spark-raw-positions.sh \
  spark/data/raw_positions-yeni-batch.jsonl.gz
```

Sonra aşağıdaki dry-run yalnız iki veri kümesini `event_id` ile karşılaştırır.
Docker mount'ları da salt-okunur olduğu için MongoDB'ye ve Iceberg warehouse'a
yazması teknik olarak mümkün değildir.

```bash
scripts/inspect-iceberg-batch-refresh.sh \
  spark/data/raw_positions-yeni-batch.jsonl.gz \
  spark/warehouse/validation-real-data-stale
```

Çıktıdaki `Iceberg'de olmayan yeni event_id`, bir sonraki gerçek yenilemede
Bronze'a eklenecek kesin aday sayısıdır. Export satır sayısı ile Bronze satır
sayısı arasındaki fark yalnız ipucudur; doğru karar anti-join sonucudur.

## Ders 05 — Kontrollü Bronze append

Dry-run sonucunu gördükten sonra yalnız Bronze'u güncellemek için aşağıdaki
komut kullanılır:

```bash
scripts/apply-iceberg-bronze-batch-refresh.sh \
  spark/data/raw_positions-yeni-batch.jsonl.gz \
  spark/warehouse/validation-real-data-stale
```

Bu iş önce dry-run ile aynı `event_id` benzersizlik kontrolünü yapar. Kontrol
geçerse Iceberg Bronze'a yalnız anti-join'den çıkan olayları `append` eder ve
tek yeni Bronze snapshot oluşturur. Kontrol veya yazım başarısızsa yeni
snapshot görünmez; mevcut Bronze verisi korunur.

Bu aşamada `silver_positions`, `silver_rejected_positions` ve Gold tabloları
bilerek güncellenmez. Bronze yeni, diğer katmanlar eski olacağı için dashboard
henüz bu Bronze snapshot'ını kullanmamalıdır. Sonraki ders, Silver/Gold'u aynı
batch ile tutarlı biçimde yenileme problemidir.

## Ders 06 — Silver yenileme dry-run

Silver'a doğrudan yeniden tüm Bronze'u yazmayız. Önce daha önce işlenmiş iki
grubun kimliklerini bir araya getiririz:

```text
işlenecek yeni Bronze = Bronze − (Silver ∪ Silver Rejected)
```

Bu komut yalnız bu fark kümesine mevcut kalite kurallarını uygular; warehouse
salt-okunur mount edildiği için hiçbir Iceberg tablosuna yazamaz:

```bash
scripts/inspect-iceberg-silver-refresh.sh \
  spark/warehouse/validation-real-data-stale
```

Sonuçtaki `accepted` kayıtlar `silver_positions`a, `rejected` kayıtlar
`silver_rejected_positions`a bir sonraki derste eklenecek adaylardır. Önceki
Silver ve Rejected arasında aynı `event_id` varsa iş durur; aynı olayın iki
farklı kalite sonucuyla yazılmasını önleriz.

## Ders 07 — Silver ve Rejected append

Dry-run sonucunu onayladıktan sonra yeni kalite kararlarını kalıcılaştır:

```bash
scripts/apply-iceberg-silver-refresh.sh \
  spark/warehouse/validation-real-data-stale
```

Kabul edilen ve reddedilen olaylar iki ayrı Iceberg tablosuna gittiği için bu
içeride iki bağımsız atomic snapshot commit'idir. İkinci yazım hata verirse
ilk tablo geri alınmaz; ancak komutu tekrar çalıştırmak güvenlidir. Anti-join,
ilk commit'te yazılmış `event_id`leri dışarıda bırakır ve yalnız eksik kalan
grubu tamamlar. Bu, tam anlamıyla çok-tablu transaction değildir; bu yerel
eğitim tasarımında geri kazanım stratejimizdir.

Bu adım sonunda Bronze, Silver ve Rejected tutarlıdır. Gold özetleri ve rapor
henüz eski kalır; onları bir sonraki derste yenileriz.

## Ders 08 — Gold tam yenileme

Gold, satır seviyesindeki Bronze/Silver geçmişini tekrar kopyalamaz. Güncel
Silver'dan saat/ülke trafik özetini, Silver ve Rejected'ın birleşiminden kalite
özetini üretir. Bu iki tabloyu yenilemek için:

```bash
scripts/apply-iceberg-gold-refresh.sh \
  spark/warehouse/validation-real-data-stale
```

`gold_hourly_traffic` ve `gold_data_quality` tümüyle yeniden hesaplanır. Her
tablo için `overwrite(true)` eski Gold snapshot'ı görünür tutarken yeni bir
Iceberg snapshot commit eder. Bu iki tablo bağımsız commit edildiğinden
aralarında tam transaction yoktur; yerel batch işinde ikisi de başarılı olduktan
sonra HTML raporunu üretiriz.

## Gold tablolarını görselleştir

Bu dersin görselleştirme adımı, Gold tablolarından tek dosyalık bir HTML raporu
üretir. Grafikler bağımsızdır; CDN, yeni web servisi veya Kubernetes bileşeni
gerektirmez.

```bash
scripts/generate-iceberg-report.sh \
  spark/warehouse/ilk-iceberg-lab \
  spark/reports/ilk-iceberg-lab.html
```

Oluşan `spark/reports/ilk-iceberg-lab.html` dosyasını tarayıcıda aç. Raporda
Bronze/Silver/red sayıları, Silver kabul oranı, saatlik Silver konum olayları,
en yoğun kaynak ülkeler ve kalite özeti bulunur. Rapor yalnız Iceberg Gold
tablolarını okur; Kafka, MongoDB ve Iceberg tablolarına yazmaz.

## Ders 09 — Tek komutla kontrollü dashboard yenileme

Önceki derslerde her aşamayı ayrı ayrı çalıştırdık; bu, veri katmanlarının
görevini öğrenmek için doğruydu. Günlük kullanımda ise sıralamayı unutmamak ve
yalnız tamamen güncel Gold'dan rapor üretmek için bir **orchestrator** (iş
akışı yöneticisi) kullanırız.

Önce güvenli prova çalıştır:

```bash
scripts/refresh-iceberg-dashboard.sh --dry-run \
  spark/warehouse/validation-real-data-stale
```

Bu komut MongoDB `raw_positions` koleksiyonundan zaman damgalı bir yerel
export alır; ardından export ile Bronze'u `event_id` üzerinden karşılaştırır.
Iceberg tablolarına ve HTML raporuna yazmaz. Dolayısıyla yeni export'un
Bronze'a etkisini önce görebiliriz.

Sonuç beklenildiği gibiyse gerçek batch'i başlat:

```bash
scripts/refresh-iceberg-dashboard.sh --apply \
  spark/warehouse/validation-real-data-stale
```

`--apply` sırası şudur:

```text
MongoDB export -> Bronze append -> Silver/Rejected -> Gold -> yeni HTML rapor
```

Script `set -e` kullanır: Bir komut hata verirse iş hemen durur, Gold ve rapor
adımları çalışmaz. Bronze, Silver ve Rejected aşamalarının `event_id`
anti-join'leri nedeniyle aynı batch'i yeniden çalıştırmak güvenlidir; daha
önce yazılmış olaylar yeniden eklenmez. Buna rağmen üç tablo tek bir ortak
transaction değildir: örneğin Silver yazılıp Rejected yazımı hata verirse
scripti tekrar çalıştırarak eksik sınıflandırmayı tamamlarız.

Her başarılı çalıştırma `spark/reports/iceberg-dashboard-<UTC-zaman>.html`
adıyla yeni, statik bir dosya üretir. Bu tasarım eski raporu ezmez; istenirse
sonraki derste yalnız "en güncel rapor" için ayrı bir erişim noktası ekleriz.

## Ders 10 — Incremental export ve overlap window

Her batch'te bütün MongoDB geçmişini export etmek çalışır ama gereksiz disk ve
zaman harcar. Bu nedenle dashboard yöneticisi önce Bronze'daki en yeni
`ingested_at` değerini okur. Buna **watermark** denir.

`observed_at` uçağın konum ölçüm zamanıdır; geç veya eski konumlar gelebilir.
`ingested_at` ise olayın MongoDB'ye yazıldığı zamandır. "En son hangi Mongo
olayını aldım?" sorusunun doğru sınırı bu yüzden `ingested_at` olur.

Sınırdaki olayları kaçırmamak için export tam watermark'tan değil, beş dakika
öncesinden başlar:

```text
Mongo export başlangıcı = Bronze MAX(ingested_at) - 5 dakika
```

Bu **overlap window** (çakışma penceresi) son beş dakikayı yeniden okur. Bu
zararsızdır: Bronze append işi `event_id` anti-join kullandığından daha önce
yazılan kayıtları tekrar eklemez. Buna karşılık zaman sınırında gecikmiş veya
aynı zamana sahip event kaçırma riskini azaltır.

Watermark'ı tek başına görmek için:

```bash
scripts/read-iceberg-bronze-watermark.sh \
  spark/warehouse/validation-real-data-stale
```

Sadece seçilmiş yeni zaman aralığını MongoDB'den export etmek için:

```bash
scripts/export-spark-raw-positions.sh \
  --since-ingested-at 2026-08-26T11:42:00.000Z \
  spark/data/raw_positions-incremental.jsonl.gz
```

`refresh-iceberg-dashboard.sh` artık bu iki adımı otomatik olarak uygular.
Önce `--dry-run` ile export boyutunu ve yeni `event_id` sayısını kontrol etmek
gerekir; ancak sonuç uygunsa `--apply` ile Bronze, Silver, Gold ve rapor
yenilenir.

## Hata ve geri alma

İş yalnız input export'unu okur; MongoDB, Kafka ve mevcut Parquet çıktıları
değişmez. Var olan warehouse'a yazma isteği güvenli biçimde hata verir. Bu
laboratuvarı geri almak için yalnız oluşturduğun ilgili `spark/warehouse/...`
klasörünü silebilirsin; kaynak sistemde veri kaybı oluşmaz.
