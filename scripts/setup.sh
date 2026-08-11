#!/bin/sh
set -eu

MIN_DOCKER_MAJOR=24
MIN_COMPOSE_MAJOR=2
REQUIRED_MEMORY_BYTES=4294967296
REQUIRED_DISK_GB=10

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
cd "$project_root"

command -v docker >/dev/null 2>&1 || fail "Docker bulunamadı. Docker Desktop/Engine kurulmalı."
docker info >/dev/null 2>&1 || fail "Docker servisi çalışmıyor."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 bulunamadı."

docker_major=$(docker version --format '{{.Server.Version}}' | cut -d. -f1)
compose_major=$(docker compose version --short | sed 's/^v//' | cut -d. -f1)
[ "$docker_major" -ge "$MIN_DOCKER_MAJOR" ] || fail "Docker 24 veya daha yeni olmalı."
[ "$compose_major" -ge "$MIN_COMPOSE_MAJOR" ] || fail "Docker Compose v2 gerekli."

docker_memory=$(docker info --format '{{.MemTotal}}' 2>/dev/null || printf '0')
case "$docker_memory" in
  ''|*[!0-9]*) fail "Docker bellek miktarı okunamadı." ;;
esac
[ "$docker_memory" -ge "$REQUIRED_MEMORY_BYTES" ] || fail "Docker için en az 4 GB bellek ayrılmalı."

arch=$(uname -m)
case "$arch" in
  x86_64|amd64) platform=amd64 ;;
  arm64|aarch64) platform=arm64 ;;
  *) fail "Desteklenmeyen CPU mimarisi: $arch" ;;
esac

if [ ! -f .env ]; then
  cp .env.example .env
  printf '.env oluşturuldu. OpenSky bilgilerini bu dosyaya yazabilirsiniz.\n'
fi

app_port=$(sed -n 's/^APP_PORT=//p' .env | tail -n 1)
app_port=${app_port:-5173}
case "$app_port" in
  ''|*[!0-9]*) fail "APP_PORT pozitif bir sayı olmalı." ;;
esac
if [ "$app_port" -lt 1 ] || [ "$app_port" -gt 65535 ]; then
  fail "APP_PORT 1-65535 arasında olmalı."
fi

area_mode=$(sed -n 's/^OPENSKY_AREA_MODE=//p' .env | tail -n 1)
area_mode=${area_mode:-turkey}
case "$area_mode" in
  turkey) ;;
  global) REQUIRED_DISK_GB=30 ;;
  *) fail "OPENSKY_AREA_MODE turkey veya global olmalı." ;;
esac

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$app_port" -sTCP:LISTEN >/dev/null 2>&1; then
  fail "127.0.0.1:${app_port} kullanımda."
elif command -v ss >/dev/null 2>&1 && ss -ltn | awk '{print $4}' | grep -Eq "(^|:)${app_port}$"; then
  fail "127.0.0.1:${app_port} kullanımda."
elif docker ps --format '{{.Ports}}' | grep -Eq "(^|[^0-9])${app_port}->|:${app_port}->"; then
  fail "127.0.0.1:${app_port} başka bir container tarafından kullanılıyor."
fi

available_kb=$(df -Pk . | awk 'NR==2 {print $4}')
required_kb=$((REQUIRED_DISK_GB * 1024 * 1024))
[ "$available_kb" -ge "$required_kb" ] || fail "En az ${REQUIRED_DISK_GB} GB boş disk alanı gerekli."

offline_archive="offline-images-${platform}.tar.gz"
if [ -f "$offline_archive" ]; then
  if [ -f SHA256SUMS.txt ]; then
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum -c SHA256SUMS.txt >/dev/null || fail "Paket içi SHA-256 doğrulaması başarısız."
    else
      shasum -a 256 -c SHA256SUMS.txt >/dev/null || fail "Paket içi SHA-256 doğrulaması başarısız."
    fi
  fi
  printf 'Offline image arşivi Docker içine yükleniyor...\n'
  docker load --input "$offline_archive" >/dev/null || fail "Offline image arşivi yüklenemedi."

  docker compose config --images | while IFS= read -r image; do
    docker image inspect "$image" >/dev/null 2>&1 || fail "Offline pakette image eksik: $image"
  done
fi

docker compose config --quiet || fail "Compose yapılandırması geçersiz."

printf 'Kontroller başarılı: mimari=%s, port=%s, gereken_disk=%sGB\n' "$platform" "$app_port" "$REQUIRED_DISK_GB"
printf 'Başlatmak için: docker compose up -d\n'
