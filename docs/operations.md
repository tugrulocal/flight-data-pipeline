# Operasyon ve hata çözme

## Başlatma ve gözlem

    docker compose up -d
    docker compose ps -a
    docker compose logs --tail=50 producer consumer backend frontend

Normal uygulama logları tek satırlık JSON'dur: UTC zaman, seviye, servis, olay/mesaj ve güvenli bağlam. Secret ve raw payload loglanmaz.

## Sağlık

    curl http://127.0.0.1:5173/health

Yanıt sürüm, MongoDB/Kafka durumu, işlenen/atlanan mesaj ve batch sayaçları ile veri tazeliğini içerir. Veri eskiliği bilgi amaçlıdır; tek başına container'ı unhealthy yapmaz.

## Kafka topic ve lag

    docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:29092 --describe
    docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:29092 --describe --group flight-mongodb-writer-v1
    docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:29092 --describe --group flight-realtime-gateway-v1

Consumer MongoDB ağ hatasında en fazla 3 kez dener; denemeler arasında 1 ve 2 saniye bekler. Üçüncü deneme de başarısızsa geçerli mesajı DLQ'ya atmaz, offseti ilerletmez ve non-zero çıkar; Compose yeniden başlatır. MongoDB döndüğünde backlog işlenir.

Kalıcı veri hataları UTF-8, JSON, alan doğrulama veya InvalidDocument olabilir. Bunlar DLQ'ya gider. DLQ acks=all teslimi doğrulanmadan ana offset commit edilmez.

## MongoDB

    docker compose exec mongodb mongosh --quiet flightdb --eval 'printjson({raw:db.raw_positions.countDocuments(),live:db.live_positions.countDocuments()})'
    docker compose exec mongodb mongosh --quiet flightdb --eval 'printjson(db.live_positions.find({observed_at:{$gte:new Date(Date.now()-600000)}}).sort({observed_at:-1}).explain("executionStats").queryPlanner.winningPlan)'

Canlı sorgunun planında IXSCAN görülmelidir. TTL silme anlık değildir; MongoDB TTL monitor periyodik çalışır.

Log ayrımı:

- INFO: normal başlangıç, teslim, batch veya kontrollü kapanış.
- WARNING: geçici durum, yeniden deneme, eski veri veya kota yaklaşımı.
- ERROR: mesajın işlenememesi, DLQ ya da bağlantı hatası.

docker compose down -v hem Kafka hem MongoDB verisini siler; normal operasyonda kullanılmaz.
