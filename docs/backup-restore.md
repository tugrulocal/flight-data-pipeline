# MongoDB backup ve restore

Backup yalnız uygulama verisini taşır. Kafka volume, cluster metadata ve consumer offsetleri özellikle taşınmaz.

    ./scripts/backup-mongodb.sh
    ./scripts/backup-mongodb.sh my-flightdb.archive.gz

Backup önce aynı klasörde geçici bir arşiv üretir ve yalnız `mongodump` başarılıysa hedef ada taşır. Var olan dosyanın üzerine yazmaz; hata halinde yarım arşiv bırakmaz.

Restore varsayılan olarak yalnız boş flightdb kabul eder:

    docker compose stop consumer
    ./scripts/restore-mongodb.sh my-flightdb.archive.gz
    docker compose up -d consumer

Consumer çalışırken restore yarış durumunu önlemek için işlem değişiklik yapmadan durur. Hedef doluysa da işlem durur. Mevcut collection'ları bilinçli değiştirmek için iki açık bayrak gerekir:

    docker compose stop consumer
    ./scripts/restore-mongodb.sh my-flightdb.archive.gz --replace --yes
    docker compose up -d consumer

Restore yalnız `flightdb.*` namespace'ini kabul eder ve ilk MongoDB hatasında durur. Producer restore sırasında çalışabilir; consumer kapalıyken Kafka'da oluşan backlog consumer yeniden başladığında işlenir.

Restore'dan sonra yeni ve boş Kafka cluster başlatılır. Yeni event'ler UUID event_id kullandığı için eski offset tabanlı Mongo _id değerleriyle çakışmaz. Retention nedeniyle Kafka'dan süresi dolmuş mesajlar backup ile geri getirilemez.

Önceki sürüme dönüş için .env içindeki APP_VERSION önceki etikete alınır ve docker compose up -d çalıştırılır. Şema geri dönüşü gerektiren sürümlerde önce MongoDB backup alınmalıdır.
