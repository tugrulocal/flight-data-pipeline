# Operasyon ve hata çözme

## Başlatma ve gözlem

    docker compose up -d
    docker compose ps -a
    docker compose logs --tail=50 producer consumer backend frontend

Normal uygulama logları tek satırlık JSON'dur: UTC zaman, seviye, servis, olay/mesaj ve güvenli bağlam. Secret ve raw payload loglanmaz.

## Sağlık

    curl http://127.0.0.1:5175/health

Yanıt sürüm, MongoDB/Kafka durumu, işlenen/atlanan mesaj ve batch sayaçları ile veri tazeliğini içerir. Veri eskiliği bilgi amaçlıdır; tek başına container'ı unhealthy yapmaz.

## Harita zemini eksik yükleniyorsa

Uçaklar backend'den, zemin parçaları tarayıcıdan doğrudan harita sağlayıcısından
gelir. Uçaklar güncellenirken zeminde boşluk oluşması Kafka veya MongoDB'nin
durduğunu göstermez. Tarayıcının Network panelinde `tile.openstreetmap.org`
isteklerini incele: başarısız/uzun bekleyen istek ile başarılı indirilip ekrana
çizilmeyen parçayı ayır. Başarısız isteklerde haritadaki yeniden yükleme
düğmesini kullan; bu işlem seçili uçağı, rotayı ve kamera konumunu korur.
Zoom sırasında önceki seviyenin bekleyen parçaları iptal edilmez ve raster
saydamlık geçişi kapalıdır; yeni ayrıntılar gelene kadar eski zemin kullanılabilir.

Yerel frontend düzeltmesini release etiketlerine dokunmadan çalıştırmak için:

    docker compose -f compose.yaml -f compose.local.yaml up -d --build --no-deps frontend

`--build` kaynak koddan yerel image üretir; `--no-deps` diğer servisleri yeniden
başlatmaz. Normal release frontend'ine dönüş: `docker compose up -d --no-deps frontend`.

Bu bilgisayardaki Docker Desktop Kubernetes kurulumu yerel image'ı da kullanabilir:

    kubectl patch application flight-data-pipeline -n argocd --type=merge --patch-file argocd/local-frontend-patch.yaml

Bu, Argo CD'nin yerel image seçimini açık bir Kustomize override olarak izlemesini
sağlar. Image yalnız bu Docker host'unda bulunur; başka cluster için release
üretmek gerekir. Kaynak kod değişikliği henüz release değildir. Önceki Git'teki
image seçimine dönmek için aşağıdaki komuttan sonra Argo CD'de Sync çalıştır:

    kubectl patch application flight-data-pipeline -n argocd --type=merge -p '{"spec":{"source":{"kustomize":null}}}'

## Kafka topic ve lag

    docker compose run --rm --no-deps topic-init topics
    docker compose run --rm --no-deps topic-init group flight-mongodb-writer-v1
    docker compose run --rm --no-deps topic-init group flight-realtime-gateway-v1

Native Kafka broker image'ı Java yönetim scriptlerini içermez. Bu komutlar aynı Kafka protokolüne producer image'ındaki `confluent-kafka` istemcisiyle bağlanır. Topic çıktısında partition sayısı ve retention değerleri; group çıktısında `total_lag` görülür. Normal durumda iki group için de `total_lag: 0` beklenir.

Consumer MongoDB ağ hatasında en fazla 3 kez dener; denemeler arasında 1 ve 2 saniye bekler. Üçüncü deneme de başarısızsa geçerli mesajı DLQ'ya atmaz, offseti ilerletmez ve non-zero çıkar; Compose yeniden başlatır. MongoDB döndüğünde backlog işlenir.

Kalıcı veri hataları UTF-8, JSON, alan doğrulama veya InvalidDocument olabilir. Bunlar DLQ'ya gider. DLQ acks=all teslimi doğrulanmadan ana offset commit edilmez.

## MongoDB

    docker compose exec mongodb mongosh --quiet flightdb --eval 'printjson({raw:db.raw_positions.countDocuments(),live:db.live_positions.countDocuments()})'
    docker compose exec mongodb mongosh --quiet flightdb --eval 'printjson(db.live_positions.find({observed_at:{$gte:new Date(Date.now()-1200000)}}).sort({observed_at:-1}).explain("executionStats").queryPlanner.winningPlan)'

Canlı sorgunun planında IXSCAN görülmelidir. TTL silme anlık değildir; MongoDB TTL monitor periyodik çalışır.

Log ayrımı:

- INFO: normal başlangıç, teslim, batch veya kontrollü kapanış.
- WARNING: geçici durum, yeniden deneme, eski veri veya kota yaklaşımı.
- ERROR: mesajın işlenememesi, DLQ ya da bağlantı hatası.

docker compose down -v hem Kafka hem MongoDB verisini siler; normal operasyonda kullanılmaz.
