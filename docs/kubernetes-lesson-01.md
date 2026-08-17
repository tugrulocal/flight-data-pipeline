# Kubernetes Lesson 01

Bu belge, [k8s/lesson-01](../k8s/lesson-01) paketinin neden bu şekilde kurulduğunu kısa notlarla açıklar.

## Sade eşleştirme

- `Namespace` = proje için ayrı klasör gibi düşün.
- `ConfigMap` = uygulama ayarları.
- `Deployment` = çalışacak kopya sayısı ve yeniden başlatma kuralı.
- `Service` = sabit ağ adı.
- `StatefulSet` = kalıcı disk isteyen servis.

## Bu projede neden MongoDB var?

Çünkü backend açılırken MongoDB ping'i yapıyor. Mongo yoksa backend daha başta hata verir. Bu yüzden ilk derste MongoDB'yi StatefulSet olarak eklemek, gerçek davranışı daha iyi gösterir.

## Bu projede neden Kafka yok?

Çünkü ilk derste amaç ağ isimleri, pod yaşam döngüsü ve kalıcı disk mantığını öğrenmek. Kafka sonradan eklenince aynı desenin broker için de nasıl çalıştığını daha rahat görürsün.

## Öğrenme notu

`/health` her zaman "pod hazır mı?" sorusunun aynı cevabı değildir. Bu projede backend'in readiness probe'u `/` kullanıyor, çünkü `/health` Kafka eksikse degrade dönebiliyor. Yani uygulama çalışırken dış bağımlılıklarının bir kısmı eksik olabilir. Bu ayrımı görmek Kubernetes öğrenirken önemlidir.
