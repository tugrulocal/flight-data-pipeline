# Kubernetes'e ilk adım

Bu paket, mevcut Docker Compose mimarisini Kubernetes'e çevirirken ilk öğrenilecek parçaları gösterir.

## Bu derste ne var?

- `Namespace`: kaynakları tek bir proje alanında toplar.
- `ConfigMap`: backend ayarlarını container dışına taşır.
- `Deployment`: `backend` ve `frontend` gibi stateless servisleri ayakta tutar.
- `Service`: pod'lara sabit bir ağ adı verir.
- `StatefulSet`: MongoDB gibi kalıcı disk isteyen sistemleri yönetir.

## Neden önce bunlar?

Çünkü bu projede Kubernetes'i öğrenmenin en kolay yolu, önce ağ isimlerini ve çalıştırma modelini anlamaktır.

- `frontend` tarayıcıya sunulan stateless katmandır.
- `backend` REST ve WebSocket sunar.
- `mongodb` kalıcı veriyi tutar.

Bu ilk sürümde Kafka'yı bilerek eklemiyoruz. Böylece önce "pod, service, statefulset, configmap" ilişkisini öğreniyoruz. Backend açılabilir, MongoDB'ye bağlanır ve Kafka eksik olduğu için `/health` içinde degrade durumunu gösterir. Bu davranış sonraki derste Kafka eklendiğinde daha anlamlı hale gelir.

MongoDB için iki adres kuruyoruz:

- `mongodb-headless`: StatefulSet pod'unun DNS kimliği için
- `mongodb`: backend'in ve ileride consumer'ın kolay bağlanması için

## Veri akışı

Tarayıcı -> `frontend` Service -> `frontend` Deployment -> `backend` Service -> `backend` Deployment -> MongoDB StatefulSet

Kafka bu derste yoktur. O yüzden backend'in WebSocket tarafı tam canlı veri üretmez; burada asıl amaç ağ ve yaşam döngüsü modelini görmek.

## Uygulama sırası

```bash
kubectl apply -k k8s/lesson-01
```

## Ne kontrol ederiz?

```bash
kubectl get namespaces
kubectl get pods,svc,pvc -n flight-data-pipeline
kubectl logs deploy/backend -n flight-data-pipeline
kubectl logs statefulset/mongodb -n flight-data-pipeline
```

Frontend'e yerelden ulaşmak için:

```bash
kubectl port-forward service/frontend 5175:80 -n flight-data-pipeline
```

Sonra tarayıcıda `http://127.0.0.1:5175` açılır.

Backend'i ayrı görmek istersen:

```bash
kubectl port-forward service/backend 8000:8000 -n flight-data-pipeline
```

## Hata olursa ne olur?

- MongoDB pod'u sağlıklı değilse backend başlangıçta Mongo ping aşamasında takılır.
- Backend ayağa kalksa bile Kafka yoksa `/health` yanıtı degraded kalır.
- Service adı yanlışsa pod çalışsa bile DNS çözülmez ve uygulama birbirine ulaşamaz.

## Bu derste ne öğrendik?

- `Deployment` uygulamayı çoğaltır ve yeniden başlatır.
- `Service` pod IP'sine değil sabit isme bağlanmamızı sağlar.
- `StatefulSet` kalıcı veri tutan sistemler içindir.
- `ConfigMap` ile ayarlar image içine gömülmez.

## Sıradaki ders

Kafka'yı ekleyip `backend` ile `consumer` arasındaki akışı göstereceğiz. Ondan sonra istersen `producer` ve `consumer` için ayrı Kubernetes manifestleri yazabiliriz.
