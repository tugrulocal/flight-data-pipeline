# Kubernetes Lesson 05

Bu ders, önceki tüm parçaları tek bir çalışan sistem olarak birleştirir.

## Ana fikir

- `StatefulSet` ile Kafka ve MongoDB'yi kalıcı diskli servisler olarak kuruyoruz.
- `Job` ile Kafka topic'lerini bir kere hazırlıyoruz.
- `Deployment` ile producer, consumer, backend ve frontend'i ayakta tutuyoruz.
- `Service` ile pod'lara sabit iç ağ adı veriyoruz.
- `Ingress` ile dış dünyayı frontend'e bağlıyoruz.
- `ConfigMap` ile frontend Nginx ayarını Kubernetes DNS'e uygun hale getiriyoruz.

## Veri akışı

```text
OpenSky -> producer -> Kafka -> consumer -> MongoDB
                          └-> backend -> frontend -> Ingress -> tarayıcı
```

Buradaki önemli nokta şu:

- Producer veri üretir.
- Consumer veriyi kalıcı hale getirir.
- Backend kalıcı ve canlı veriyi REST/WebSocket ile sunar.
- Frontend kullanıcıya görünen tek kapıdır.

Frontend image'ı Compose ortamında Docker DNS kullandığı için, Kubernetes dersinde
aynı image'ı değiştirmeden Nginx config'ini `ConfigMap` ile mount ediyoruz.

## Neden bu paket tam sistem sayılıyor?

Çünkü artık sadece tek tek bileşenleri değil, hepsinin birbirine nasıl bağlandığını görüyoruz:

- Kafka ve MongoDB kendi diskleriyle yaşar.
- Producer ve consumer iç işçilerdir.
- Backend, veri katmanını API'ye çevirir.
- Frontend, tarayıcıya konuşur.

## En önemli DNS isimleri

- `kafka:29092`
- `mongodb:27017`
- `backend:8000`
- `frontend:80`

Kubernetes'te uygulamalar bu sabit isimler üzerinden konuşur.

## Neden MongoDB için iki Service var?

- `mongodb-headless`: StatefulSet pod'unun sabit DNS kimliği için
- `mongodb`: backend ve consumer'ın kolay bağlanması için

Bu ayrım pratikte çok önemlidir.

## Nasıl uygulanır?

```bash
kubectl apply -k k8s/lesson-05
```

## Local tarayıcı adresleri

Docker Desktop'ın Ingress controller'ı Mac'te `127.0.0.1:80` üzerinden
erişilebilir. Gerçek bir domain satın almadan önce aşağıdaki local isimleri
kullanıyoruz:

```text
app.flight.test  -> frontend Service
argo.flight.test -> argocd-server Service
```

Bu iki adı yalnız kendi Mac'imizde çözmek için `/etc/hosts` dosyasına tek satır
ekleriz:

```text
127.0.0.1 app.flight.test argo.flight.test
```

`app.flight.test` kullanıcı uygulamasına, `argo.flight.test` ise yönetim
paneline gider. MongoDB ve Kafka için Ingress veya dış host oluşturulmaz;
pod'lar onlara yalnız Kubernetes DNS'iyle (`mongodb:27017`, `kafka:29092`)
bağlanır.

## Ne kontrol ederiz?

```bash
kubectl get pods,svc,ingress,pvc -n flight-data-pipeline
kubectl logs statefulset/kafka -n flight-data-pipeline
kubectl logs statefulset/mongodb -n flight-data-pipeline
kubectl logs job/kafka-topic-init -n flight-data-pipeline
kubectl logs deploy/producer -n flight-data-pipeline
kubectl logs deploy/consumer -n flight-data-pipeline
kubectl logs deploy/backend -n flight-data-pipeline
kubectl logs deploy/frontend -n flight-data-pipeline
```

## Hata olursa ne olur?

- Kafka volume sahibi düzeltilmezse broker yazamaz.
- Topic-init başarısızsa producer ve consumer topic bulamaz.
- MongoDB Service adı yanlışsa consumer ve backend bağlanamaz.
- Ingress controller yoksa dış trafik frontend'e ulaşmaz.
- CORS origin uyuşmazsa tarayıcı WebSocket bağlantısını reddedebilir.

## Bu dersin öğretici mesajı

Kubernetes'te "bütün sistem" aslında ayrı kaynaktan oluşan bir sözleşmedir:

- disk
- DNS
- Service
- Deployment
- StatefulSet
- Job
- Ingress

Bu parçalar doğru bağlanınca uygulama kendi kendine ayakta kalır.
