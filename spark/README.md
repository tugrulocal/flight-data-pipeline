# Spark ders 01: yerel batch analiz

Bu ders Spark'ı Kubernetes'e kurmaz. Docker içindeki tek Spark süreci
`local[2]` ile en fazla iki CPU kullanır; Docker `--memory=3g` ile toplam bellek
sınırı da 3 GiB'dir. Böylece mevcut Kafka, MongoDB, Prometheus ve Grafana
pod'ları için kaynak korunur.

## Veri akışı

```text
Kubernetes MongoDB raw_positions
        |  (salt-okunur export)
        v
spark/data/raw_positions-...jsonl.gz
        |  Spark local[2]
        +--> Parquet bronze_positions (tüm tiplenmiş olaylar)
        +--> Parquet silver_positions (kalite kurallarını geçen olaylar)
        +--> Parquet silver_rejected_positions (red nedeni ile olaylar)
        +--> CSV gold_hourly_traffic_csv (Silver'dan saatlik/ülkeli özet)
```

Bu aşamada Spark Kafka'yı tüketmez ve MongoDB'ye yazmaz. Canlı frontend yolu
aynen kalır:

```text
Kafka -> Python consumer -> MongoDB -> FastAPI -> frontend
```

## 1. Ham veriyi güvenli biçimde dışa aktar

```bash
scripts/export-spark-raw-positions.sh
```

Komut, Kubernetes'teki `flight-data-pipeline/mongodb-0` pod'unda yalnız
`raw_positions.find({})` sorgusunu çalıştırır. Sonuç `spark/data/` altına
sıkıştırılmış Canonical Extended JSONL olarak iner. Bu klasör `.gitignore`
altındadır; gerçek uçuş verisi commit edilmez. Komut hiçbir MongoDB belgesini,
Kafka mesajını veya offset'i değiştirmez.

Farklı namespace/pod gerekiyorsa:

```bash
K8S_NAMESPACE=flight-data-pipeline MONGODB_POD=mongodb-0 \
  scripts/export-spark-raw-positions.sh spark/data/ilk-lab.jsonl.gz
```

## 2. Spark batch işini başlat

Export'un ürettiği dosya adını kullan:

```bash
scripts/run-spark-local.sh \
  spark/data/raw_positions-YYYYMMDDTHHMMSSZ.jsonl.gz \
  spark/output/ilk-lab
```

Bu komut Apache Spark `4.0.1` Python image'ını sabit image digest'iyle çalıştırır.
Mac'e Java veya PySpark kurulması gerekmez. `--master local[2]` tek makinede iki
iş parçacıklı Spark çalıştırır; bu bir Kubernetes veya çok-makineli Spark
cluster'ı değildir.

Silver hız eşiğini değiştirmek gerekirse komuta değil environment variable'a
verilir; örneğin yalnız eğitim deneyi için 450 m/s:

```bash
SPARK_MAX_VELOCITY_MPS=450 scripts/run-spark-local.sh \
  spark/data/ilk-lab.jsonl.gz spark/output/ilk-lab-450
```

## Ne üretir?

- `bronze_positions/`: Spark'ın okuyup tiplendirebildiği tüm ham olaylar.
  `observed_date` ile gün bazında partition edilir; kalite filtresi uygulanmaz.
- `silver_positions/`: uçak kimliği, zaman, koordinat ve hız kalite kurallarını
  geçen detaylı olaylar.
- `silver_rejected_positions/`: Silver'a alınmayan olaylar ile
  `quality_reason` alanı. Varsayılan hız eşiği 400 m/s'dir; bu fiziksel bir
  yasa değil, değiştirilebilir ilk analiz kuralıdır. Ayrıca `ingested_at` ile
  `observed_at` farkı 20 dakikayı aşarsa olay `stale_observation` olarak
  reddedilir.
- `gold_hourly_traffic_csv/`: yalnız Silver verisinden saat ve ülkeye göre konum olayı, farklı uçak,
  havadaki olay, ortalama barometrik irtifa ve hız özeti.
- `gold_data_quality_csv/`: kabul/red sayıları ve red nedenlerinin özeti.

Bronze ham detaydır. Silver, bu detayın analiz için güvenilir hâlidir. Gold ise
Silver'dan üretilen, ekranın veya raporun kolayca kullanacağı özettir.

İş aynı değerlendirilmiş veriyi Bronze, Silver, red kayıtları ve Gold raporları
için kullandığından bu DataFrame'i geçici olarak cache'ler. Bu, aynı JSONL
dosyasının her çıktı için yeniden okunmasını önler; iş sonunda cache temizlenir.

Tazelik eşiğini yalnız eğitim deneyi için değiştirmek gerekirse:

```bash
SPARK_MAX_OBSERVATION_LAG_MINUTES=30 scripts/run-spark-local.sh \
  spark/data/ilk-lab.jsonl.gz spark/output/ilk-lab-30dk
```

## Doğrulama

Başarılı sonunda terminalde `Girdi satırı`, `geçerli konum olayı` ve ilk 20
saatlik özet görünür. Çıktıyı kontrol et:

```bash
find spark/output/ilk-lab -type f | sort
```

Hata halinde güvenli geri alma: Yalnız oluşturulan ilgili `spark/output/ilk-lab`
klasörünü silmek yeterlidir. Kaynak MongoDB/Kafka verisi bu laboratuvarda hiç
değişmez.
