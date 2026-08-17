# Kubernetes Lesson 03

Bu ders, akışın aktif çalışan parçalarını ekler: producer ve consumer.

## Ana fikir

- `Deployment` kullanıyoruz, çünkü iki container da dışarıdan trafik almaz.
- `ConfigMap` kullanıyoruz, çünkü Kafka, MongoDB ve OpenSky ayarlarını image içine gömmek istemiyoruz.
- Bu iki servis için `Service` yazmıyoruz, çünkü başka pod'lar onlara HTTP ile bağlanmıyor.

## Veri akışı

`producer Deployment` -> `kafka` Service -> `consumer Deployment` -> `mongodb` Service

Burada önemli şey şu:

- Producer OpenSky'dan veri çeker ve Kafka'ya yazar.
- Consumer Kafka'dan okur ve MongoDB'ye yazar.

## Neden Deployment?

Çünkü producer ve consumer:

- sürekli çalışan süreçlerdir
- tek görevli container'lardır
- ölürlerse Kubernetes tekrar başlatmalıdır

Bu yüzden `Deployment` doğru araçtır.

## Neden Service yok?

Service, başkalarının gelip bağlandığı sabit ağ kapısıdır.

Bu iki container'ın görevi dışarıdan istek karşılamak değil:

- producer veri toplar
- consumer veri işler

O yüzden onları içeriden dışarı bağlanan işçiler gibi düşünürüz.

## ConfigMap neyi taşıyor?

- Producer için: `KAFKA_*`, `POLL_INTERVAL_SECONDS`, `OPENSKY_*`
- Consumer için: `KAFKA_*`, `MONGODB_*`, retry ayarları

Bu sayede image aynı kalır, ortam değişince manifest değişir.

## Nasıl uygulanır?

```bash
kubectl apply -k k8s/lesson-03
```

## Ne kontrol ederiz?

```bash
kubectl get pods -n flight-data-pipeline
kubectl logs deploy/producer -n flight-data-pipeline
kubectl logs deploy/consumer -n flight-data-pipeline
```

## Hata olursa ne olur?

- Kafka yoksa producer veri gönderemez.
- Kafka topic'leri yoksa producer/consumer bağlantı hatası verir.
- MongoDB yoksa consumer yazma aşamasında hata alır.
- OpenSky erişimi yoksa producer veri çekemez.

## Bu derste ne öğrendik?

- `Deployment`, çalışan işçi container'lar için uygundur.
- `ConfigMap`, ayarların yönetim yeridir.
- Her container'ın Service'e ihtiyacı yoktur.
- Veri akışı node değil, uygulama seviyesinde düşünülmelidir.
