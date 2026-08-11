#!/bin/sh
set -eu

: "${VERSION:?VERSION gerekli (örnek: v1.0.0-rc.2)}"
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
apache/kafka-native:4.3.1@sha256:2885898ba17065023f1bd605f3a81efcfa986014f062b73b91ef5462485f9060
mongodb/mongodb-community-server:8.0.28-ubi9-slim@sha256:905f93fe770819a134dd8f74e14caf319735d068da86ff9c2e7c80dec140f191
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

mkdir -p "$stage/scripts" "$stage/docs"
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
cp compose.yaml .env.example README.md SECURITY.md THIRD_PARTY_NOTICES.md "$stage/"
cp scripts/setup.sh scripts/setup.ps1 scripts/backup-mongodb.sh scripts/restore-mongodb.sh "$stage/scripts/"
cp docs/operations.md docs/global-mode.md docs/backup-restore.md docs/release.md docs/release-acceptance.md "$stage/docs/"
for versioned_file in "$stage/compose.yaml" "$stage/.env.example"; do
  sed "s/1.0.0-rc.2/${version_number}/g" "$versioned_file" > "${versioned_file}.tmp"
  mv "${versioned_file}.tmp" "$versioned_file"
done

(
  cd "$stage"
  for packaged_file in \
    "offline-images-${PLATFORM}.tar.gz" \
    compose.yaml .env.example \
    scripts/setup.sh scripts/setup.ps1
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
