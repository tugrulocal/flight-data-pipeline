# Capstone Progress

Son güncelleme **2026-11-26**. Başlangıç referansı `main` üzerindeki `cf3b28e`.

## Tamamlanan işler

| Tarih | Phase | Sonuç |
|---|---|---|
| 2026-11-26 | 0 · Repository Audit | Kaynak, veri akışı, dört yerel export ve Iceberg metadata'sı incelendi. 65 Python ve 6 frontend unit testi geçti. Frontend build ve statik Compose/Kustomize başarılı. Mock Playwright 5/6, mobil senaryo izole tekrarda 1/2. Canlı entegrasyon doğrulanmadı. [Audit](docs/capstone/REPOSITORY_AUDIT.md) |
| 2026-11-26 | 1 · Project Initialization and Persistent Context | Kalıcı çalışma kuralları, proje bağlamı, roadmap ve capstone belgeleri oluşturuldu. Yerel Git başlangıcı doğrulandı. [Profiling ve toplama planı](docs/capstone/DATA_PROFILING_AND_COLLECTION_PLAN.md) hazırlandı. |
| 2026-11-26 | Geliştirme dalı | Kullanıcı onayıyla `capstone-development`, `cf3b28e` commit'inden yerelde oluşturuldu ve etkinleştirildi. Dal, commit ve bekleyen belge değişiklikleri `git status --short --branch` ve `git rev-parse` ile doğrulandı. [Karar kaydı](docs/capstone/DECISIONS.md) |

## Mevcut aşama ve sıradaki görev

Phase 1 dokümantasyon teslimi tamamlandı. Sıradaki kodlama görevi, ayrı yetkiyle mevcut export'ları salt okunur okuyup agregat bir **Data Profiling Report** üretmek. Bu görev Phase 3 veri mühendisliğinin ilk adımı olarak Phase 2 literature review ile paralel yürütülebilir. Sonraki koşuda girdi manifest'i ve tekrar üretilebilir ölçüm çıktısı, [planın kabul ölçütlerine](docs/capstone/DATA_PROFILING_AND_COLLECTION_PLAN.md#teslim-ve-acceptance-criteria) göre değerlendirilecek.

## Phase 1 doğrulaması

`git diff --check` ve yerel Markdown bağlantı kontrolü geçti. Liste ve başlık kontrolü Phase 0–9 roadmap satırlarını ve 14 audit başlığını doğruladı. Git durumundaki değişiklikler 11 Markdown dosyasıyla sınırlı. `main` ve `cf3b28e` başlangıç referansı doğrulandı. Phase 0 uygulama testleri yukarıda tarihsel sonuç olarak kayıtlı. Phase 1 doğrulaması belge kapsamı, Git durumu ve bağlantılar üzerinden yapıldı.

## Açık konular

| Konu | Durum |
|---|---|
| Stajda üretilen kodun ve verinin akademik kullanımı, danışmanla paylaşımı ve yayın kapsamı | İzin teyidi bekliyor. [Karar kaydı](docs/capstone/DECISIONS.md) |
| Coğrafi kapsam, uçuş fazları ve uzun vadeli kaynak | Profil, kota, izin ve araştırma hedefiyle değerlendirilecek. |
| Anomali tanımı ve ground truth | Phase 2'de danışman ve literature review ile belirlenecek. |
| Prediction horizon | 2, 4 ve 6 dakika aday. Seçim, hedef bulunabilirliği ve akademik gerekçeye bağlı. |
| Arşiv mekanizması ve maliyet | Profil ve kesinti/replay testi tasarımına bağlı. |
| Uygulama çalışma zamanı | Phase 0'da Docker daemon erişimi yoktu. Canlı uçtan uca test, mobil tile testi ve bağımsız release kabulü açık. |
