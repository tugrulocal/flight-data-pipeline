# Kubernetes Lesson 02

Bu ders, Kafka broker'ı Kubernetes üzerinde nasıl düşündüğümüzü gösterir.

## Ana fikir

- `StatefulSet` kullanıyoruz, çünkü Kafka'nın kalıcı disk ve sabit kimlik ihtiyacı var.
- `Headless Service` kullanıyoruz, çünkü StatefulSet pod'una sabit DNS adı vermek istiyoruz.
- `Service` kullanıyoruz, çünkü cluster içindeki istemciler `kafka:29092` diye konuşabilsin istiyoruz.
- `Job` kullanıyoruz, çünkü topic oluşturma bir kere çalışan kurulum işidir.

## Veri akışı

`topic-init Job` -> `kafka` Service -> `kafka` StatefulSet

Sonra sonraki derslerde:

- producer Kafka'ya yazar
- consumer Kafka'dan okuyup MongoDB'ye yazar
- backend Kafka ve MongoDB'yi okur

## Neden headless Service?

StatefulSet pod'ları sıradan Deployment pod'ları gibi rastgele isim almaz. Kafka tarafında broker'ın DNS adının sabit olması çok işimize yarar. Bu yüzden `kafka-headless` ile pod DNS'i üretiriz.

## Neden Job?

Topic oluşturmak, uygulamanın sürekli çalışan kısmı değildir. Bu yüzden `Deployment` değil `Job` kullanırız.

## Nasıl uygulanır?

```bash
kubectl apply -k k8s/lesson-02
```

## Ne kontrol ederiz?

```bash
kubectl get pods,svc,pvc -n flight-data-pipeline
kubectl logs statefulset/kafka -n flight-data-pipeline
kubectl logs job/kafka-topic-init -n flight-data-pipeline
```

Topic'lerin oluştuğunu görmek için job log'larında `topic.ready` benzeri çıktı bekleriz.

## Hata olursa ne olur?

- Volume sahibi yanlışsa Kafka pod'u başlasa bile yazamaz.
- `KAFKA_CONTROLLER_QUORUM_VOTERS` yanlışsa KRaft ayağa kalkmaz.
- `kafka:29092` DNS adı çözülmezse topic-init ve diğer istemciler broker'a bağlanamaz.

## Bu derste ne öğrendik?

- Stateful servisler için `Deployment` yerine `StatefulSet` düşünürüz.
- Kalıcı disk `PVC` ile gelir.
- `Job`, bir kere yapılacak kurulum işleri içindir.
- DNS adı, Kubernetes'te ağ kadar önemlidir.
