# Third-Party Notices

Bu dosya proje lisansını değiştirmez. Runtime ve geliştirme bağımlılıklarının tam sürüm ve hash kaydı Python requirements dosyalarında ve frontend/package-lock.json içindedir. Release workflow'u ayrıca image başına SPDX SBOM üretir.

| Bileşen | Paket/image | Lisans ailesi |
|---|---|---|
| Python | confluent-kafka | Apache-2.0 |
| Producer | requests | Apache-2.0 |
| Consumer/backend | pymongo | Apache-2.0 |
| Backend | FastAPI, Uvicorn, websockets | MIT/BSD |
| Frontend | React, React DOM | MIT |
| Frontend | Leaflet | BSD-2-Clause |
| Frontend | MapLibre GL JS | BSD-3-Clause |
| Altyapı | Apache Kafka | Apache-2.0 |
| Altyapı | MongoDB Community Server | SSPL-1.0 |
| Frontend runtime | Nginx | BSD-2-Clause |

Dağıtılan gerçek transitive bileşenler ve lisans metinleri için release SBOM'u esas alınmalıdır. Kaynak projelerin telif ve lisans bildirimleri kendi paketlerinde korunur.
