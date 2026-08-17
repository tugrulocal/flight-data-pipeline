# Kubernetes Lesson 04

Bu ders, uygulamanın kullanıcıya görünen giriş katmanını gösterir.

## Ana fikir

- `Service` ile backend ve frontend'e sabit ağ adı veriyoruz.
- `Deployment` ile bu iki web katmanını sürekli çalışır tutuyoruz.
- `Ingress` ile dış dünyanın tek bir giriş noktasını frontend'e bağlıyoruz.
- `ConfigMap` ile frontend Nginx ayarını Kubernetes DNS'e uygun hale getiriyoruz.

## Veri akışı

Tarayıcı -> `Ingress` -> `frontend` Service -> `frontend` Pod -> `backend` Service -> `backend` Pod

Aradaki önemli ayrım şu:

- Kullanıcı önce frontend'e gelir.
- Frontend, `/api`, `/health` ve `/ws` isteklerini backend'e proxy eder.
- Backend de Kafka ve MongoDB ile konuşur.

Frontend image'ı Compose ortamında Docker DNS kullanır. Kubernetes dersinde aynı image'ı
bozmadan, Nginx config'ini `ConfigMap` olarak mount edip `backend:8000` Service adına
proxy yaptırıyoruz.

## Neden Ingress?

Service pod'lar arasında konuşmak için iyidir.
Ingress ise dış dünyadan HTTP girişini yönetir.

Bu projede tarayıcıyı doğrudan backend'e açmak yerine frontend'i tek kapı yapıyoruz. Böylece:

- statik dosyalar frontend'den servis edilir
- API çağrıları aynı origin üzerinden gider
- WebSocket akışı da aynı giriş noktasından devam eder

## Neden backend için Service var?

Frontend Nginx, Kubernetes DNS üzerinden doğrudan `backend:8000` adresine proxy yapar.
Bu yüzden backend'in sabit bir Service adı olmalıdır.

## Neden frontend için Service var?

Ingress, backend değil frontend Service'e bağlanır.
Frontend Service de pod değişse bile sabit kalır.

## Nasıl uygulanır?

```bash
kubectl apply -k k8s/lesson-04
```

## Ne kontrol ederiz?

```bash
kubectl get pods,svc,ingress -n flight-data-pipeline
kubectl logs deploy/backend -n flight-data-pipeline
kubectl logs deploy/frontend -n flight-data-pipeline
```

Eğer cluster'da NGINX Ingress Controller yoksa `Ingress` nesnesi tek başına yetmez. O durumda eğitim için `kubectl port-forward` ile frontend Service'i açmak yeterlidir.

## Hata olursa ne olur?

- Ingress controller yoksa dışarıdan trafik gelmez.
- Backend Service adı yanlışsa frontend proxy hatası verir.
- CORS origin listesi ingress host ile eşleşmezse WebSocket bağlantısı reddedilebilir.

## Bu derste ne öğrendik?

- `Ingress`, dış HTTP giriş kapısıdır.
- `Service`, pod'lara sabit iç ağ adı verir.
- Frontend ve backend'i birlikte düşünmek gerekir.
- WebSocket de aynı ağ mimarisinin parçasıdır; sadece uzun ömürlü bir bağlantıdır.
