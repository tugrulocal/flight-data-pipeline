# Local monitoring: Prometheus ve Grafana

Bu local eğitim ortamında metrikler ayrı bir `monitoring` namespace'inde
toplanır. Uygulama pod'ları metric üretir; Prometheus bunları toplar; Grafana
zaman içindeki durumu dashboard olarak gösterir.

```text
uygulama /metrics -> Service -> ServiceMonitor -> Prometheus -> Grafana
```

`argocd/monitoring-application.yaml`, sabit sürümlü
`kube-prometheus-stack` chart'ını Argo CD ile kurar. Chart; Prometheus
Operator, Prometheus, Grafana, kube-state-metrics ve node exporter içerir.
Prometheus Operator CRD'leri büyük olduğu için Application, Argo CD'nin
server-side apply seçeneğini kullanır; bu sayede Kubernetes'in client-side
annotation boyut sınırına takılmaz.

## İlk kurulum öncesi secret

Grafana admin parolası Git'e yazılmaz. Argo Application uygulanmadan önce
namespace'i ve Secret'ı local cluster'da oluştur:

```bash
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
read -s GRAFANA_ADMIN_PASSWORD
kubectl create secret generic grafana-admin-credentials \
  --namespace monitoring \
  --from-literal=admin-user=admin \
  --from-literal=admin-password="$GRAFANA_ADMIN_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -
unset GRAFANA_ADMIN_PASSWORD
```

`read -s`, parolayı ekranda göstermeden alır. Değer terminal geçmişine veya
Git'e düşmez.

Mac'in `/etc/hosts` dosyasındaki local host listesine Grafana'yı da ekle:

```text
127.0.0.1 app.flight.test argo.flight.test grafana.flight.test
```

## Doğrulama

Argo `monitoring` Application'ı sync ettikten sonra:

```bash
kubectl get pods -n monitoring
kubectl get pvc -n monitoring
curl -I http://grafana.flight.test/
```

Grafana: http://grafana.flight.test/

Prometheus ve Alertmanager bu aşamada Ingress ile dışarı açılmaz. Prometheus
gerektiğinde yalnız local port-forward ile incelenir:

```bash
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
```

## Sıradaki uygulama metriği

İlk stack kurulunca backend'e `/metrics` endpoint'i eklenir. `ServiceMonitor`,
backend Service'ini etiketi ve isimli `http` portu üzerinden keşfeder.
`icao24` ve `event_id` gibi çok sayıda farklı değer metric label'ı yapılmaz;
aksi halde Prometheus gereksiz sayıda zaman serisi üretir.
