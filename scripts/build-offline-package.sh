#!/bin/sh
set -eu

: "${VERSION:?VERSION gerekli (örnek: v1.0.0-rc.1)}"
: "${PLATFORM:?PLATFORM gerekli (amd64 veya arm64)}"
case "$PLATFORM" in amd64|arm64) ;; *) exit 2 ;; esac
echo "$VERSION" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$' || {
  printf 'HATA: Geçersiz VERSION: %s\n' "$VERSION" >&2
  exit 2
}

checksum_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1"
  else
    shasum -a 256 "$1"
  fi
}

version_number=${VERSION#v}
owner=${GITHUB_REPOSITORY_OWNER:-tugrulocal}
prefix="ghcr.io/${owner}/flight-data-pipeline"
images="
${prefix}-producer:${version_number}
${prefix}-consumer:${version_number}
${prefix}-backend:${version_number}
${prefix}-frontend:${version_number}
apache/kafka:4.3.1@sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837
mongo:8.0.28@sha256:98605bfa1bb2a15dd82109e1d78ad31527a9a744909fab4606076fa71a0ae515
"

output_dir=${OUTPUT_DIR:-release-out}
mkdir -p "$output_dir"
stage="$output_dir/flight-data-pipeline-${version_number}-${PLATFORM}"
[ ! -e "$stage" ] || {
  printf 'HATA: Geçici paket klasörü zaten var: %s\n' "$stage" >&2
  exit 1
}

cleanup() {
  if [ -d "$stage" ]; then
    find "$stage" -depth -delete
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "$stage/scripts" "$stage/kafka" "$stage/docs"
if [ "${OFFLINE_SKIP_PULL:-0}" != "1" ]; then
  for image in $images; do
    docker pull --platform "linux/$PLATFORM" "$image"
  done
fi

for image in $images; do
  docker image inspect "$image" >/dev/null
done

# shellcheck disable=SC2086
docker save $images | gzip -9 > "$stage/offline-images-${PLATFORM}.tar.gz"

bundle="$output_dir/flight-data-pipeline-${version_number}-${PLATFORM}.tar.gz"
cp compose.yaml compose.global.yaml .env.example README.md SECURITY.md THIRD_PARTY_NOTICES.md "$stage/"
cp kafka/init-topics.sh "$stage/kafka/"
cp scripts/setup.sh scripts/setup.ps1 scripts/backup-mongodb.sh scripts/restore-mongodb.sh "$stage/scripts/"
cp docs/operations.md docs/global-mode.md docs/backup-restore.md docs/release.md docs/release-acceptance.md "$stage/docs/"
for versioned_file in "$stage/compose.yaml" "$stage/.env.example"; do
  sed "s/1.0.0-rc.1/${version_number}/g" "$versioned_file" > "${versioned_file}.tmp"
  mv "${versioned_file}.tmp" "$versioned_file"
done

(
  cd "$stage"
  for packaged_file in \
    "offline-images-${PLATFORM}.tar.gz" \
    compose.yaml compose.global.yaml .env.example \
    scripts/setup.sh scripts/setup.ps1 \
    kafka/init-topics.sh
  do
    checksum_file "$packaged_file"
  done > SHA256SUMS.txt
)

tar -czf "$bundle" -C "$output_dir" "$(basename "$stage")"

(cd "$output_dir" && checksum_file \
  "flight-data-pipeline-${version_number}-${PLATFORM}.tar.gz" \
  > "SHA256SUMS-${PLATFORM}.txt")

cleanup
trap - EXIT INT TERM
