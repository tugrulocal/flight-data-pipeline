import os
import platform
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FAKE_DOCKER = r"""#!/bin/sh
set -eu
command_line="$*"

case "$command_line" in
  "info") exit 0 ;;
  "info --format {{.OSType}}") printf 'linux\n' ;;
  "info --format {{.MemTotal}}") printf '%s\n' "${FAKE_DOCKER_MEMORY:-8589934592}" ;;
  "version --format {{.Server.Version}}") printf '28.3.3\n' ;;
  "compose version") exit 0 ;;
  "compose version --short") printf '2.39.1\n' ;;
  "compose ps --services --status running consumer")
    [ "${FAKE_CONSUMER_RUNNING:-0}" = "1" ] && printf 'consumer\n'
    ;;
  *"mongodb_transfer.py export"*) printf 'fake-mongodb-export' ;;
  *"mongodb_transfer.py count"*) printf '%s\n' "${FAKE_DOCUMENT_COUNT:-0}" ;;
  *"mongodb_transfer.py import"*)
    printf '%s\n' "$command_line" >> "${FAKE_DOCKER_LOG:?}"
    cat > "${FAKE_RESTORE_CAPTURE:?}"
    ;;
  *" mongosh "*) printf '%s\n' "${FAKE_DOCUMENT_COUNT:-0}" ;;
  "compose config --images")
    printf '%s\n' 'example/image:1.0.0'
    ;;
  "compose config --quiet") exit 0 ;;
  "compose ps -q frontend") exit 0 ;;
  "compose pull") exit 0 ;;
  "compose up -d --wait --wait-timeout 240") exit 0 ;;
  "image inspect example/image:1.0.0") exit 0 ;;
  "load --input "*) exit 0 ;;
  "ps --format {{.Ports}}") exit 0 ;;
  *) exit 0 ;;
esac
"""


def make_project(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    project = tmp_path / "project"
    scripts = project / "scripts"
    fake_bin = tmp_path / "fake-bin"
    scripts.mkdir(parents=True)
    fake_bin.mkdir()

    for name in (
        "setup.sh",
        "backup-mongodb.sh",
        "restore-mongodb.sh",
    ):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)

    (project / "compose.yaml").write_text("services: {}\n")
    (project / ".env.example").write_text(
        "APP_PORT=54999\nOPENSKY_AREA_MODE=turkey\n"
    )
    (project / ".env").write_text(
        "APP_PORT=54999\nOPENSKY_AREA_MODE=turkey\n"
    )

    docker = fake_bin / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["FAKE_DOCKER_LOG"] = str(tmp_path / "docker.log")
    environment["FAKE_RESTORE_CAPTURE"] = str(tmp_path / "restored.archive")
    return project, environment


def run_script(
    project: Path,
    environment: dict[str, str],
    script: str,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(project / "scripts" / script), *arguments],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_setup_validates_docker_resources(tmp_path):
    project, environment = make_project(tmp_path)

    result = run_script(project, environment, "setup.sh")

    assert result.returncode == 0, result.stderr
    assert "Kontroller başarılı" in result.stdout
    assert "Uygulama hazır: http://127.0.0.1:54999" in result.stdout


def test_release_defaults_are_global_and_consistent():
    values = {}
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name] = value

    assert values["OPENSKY_AREA_MODE"] == "global"
    assert values["POLL_INTERVAL_SECONDS"] == "120"
    assert values["LIVE_POSITION_WINDOW_MINUTES"] == "20"
    assert values["APP_PORT"] == "5175"
    assert values["APP_VERSION"] == "1.0.0-rc.3"

    compose = (ROOT / "compose.yaml").read_text()
    assert "${OPENSKY_AREA_MODE:-global}" in compose
    assert "${POLL_INTERVAL_SECONDS:-120}" in compose
    assert "${LIVE_POSITION_WINDOW_MINUTES:-20}" in compose
    assert "${APP_PORT:-5175}" in compose
    assert "${APP_VERSION:-1.0.0-rc.3}" in compose
    assert not (ROOT / "compose.global.yaml").exists()


def test_kafka_clean_volume_is_prepared_without_running_broker_as_root():
    compose = (ROOT / "compose.yaml").read_text()

    assert "kafka-volume-init:" in compose
    assert 'user: "0:0"' in compose
    assert 'command: ["chown 1000:1000 /var/lib/kafka/data"]' in compose
    assert "kafka-volume-init:\n        condition: service_completed_successfully" in compose


def test_python_images_use_pinned_alpine_and_native_kafka_versions():
    alpine_base = (
        "python:3.13.14-alpine3.23@sha256:"
        "9fdbf2e3e82628351513560b121e2ee6ce31cac212be9e070c5a5e2769fb5e76"
    )
    for service in ("producer", "consumer", "backend"):
        dockerfile = (ROOT / service / "Dockerfile").read_text()
        requirements_in = (ROOT / service / "requirements.in").read_text()
        assert dockerfile.count(f"FROM {alpine_base}") == 2
        assert "librdkafka=2.12.1-r0" in dockerfile
        assert "librdkafka-dev=2.12.1-r0" in dockerfile
        assert "--no-build-isolation --require-hashes" in dockerfile
        assert "--no-cache-dir --no-index --no-deps /wheels/*.whl" in dockerfile
        assert "confluent-kafka==2.12.1" in requirements_in

    build_lock = (ROOT / "requirements-build.txt").read_text()
    assert "setuptools==84.0.0" in build_lock
    assert "hatchling==1.32.0" in build_lock


def test_ci_scans_both_architectures_with_safe_pinned_trivy_action():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()

    safe_trivy_action = (
        "aquasecurity/trivy-action@"
        "ed142fd0673e97e23eac54620cfb913e5ce36c25"
    )
    assert "aquasecurity/trivy-action@0.33.1" not in workflow
    assert workflow.count(safe_trivy_action) == 6
    assert workflow.count("platform: [amd64, arm64]") == 2
    assert "runner: ubuntu-latest" in workflow
    assert "runner: ubuntu-24.04-arm" in workflow
    assert "runs-on: ${{ matrix.runner }}" in workflow
    assert "TRIVY_PLATFORM: linux/${{ matrix.platform }}" in workflow
    assert "image-ref: flight-data-pipeline-backend:ci-${{ matrix.platform }}" in workflow
    assert "image-ref: apache/kafka-native:4.3.1@sha256:" in workflow
    assert "image-ref: mongodb/mongodb-community-server:8.0.28-ubi9-slim@sha256:" in workflow
    assert workflow.count("ignore-unfixed: false") == 6
    assert workflow.count("version: v0.72.0") == 6


def test_setup_check_only_does_not_start_services(tmp_path):
    project, environment = make_project(tmp_path)

    result = run_script(
        project,
        environment,
        "setup.sh",
        "--check-only",
    )

    assert result.returncode == 0, result.stderr
    assert "servisler başlatılmadı" in result.stdout


def test_setup_rejects_insufficient_docker_memory(tmp_path):
    project, environment = make_project(tmp_path)
    environment["FAKE_DOCKER_MEMORY"] = "2147483648"

    result = run_script(project, environment, "setup.sh")

    assert result.returncode == 1
    assert "en az 4 GB bellek" in result.stderr


def test_setup_rejects_tampered_offline_package(tmp_path):
    project, environment = make_project(tmp_path)
    machine = platform.machine().lower()
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
    archive = project / f"offline-images-{architecture}.tar.gz"
    archive.write_bytes(b"tampered")
    (project / "SHA256SUMS.txt").write_text(
        f"{'0' * 64}  {archive.name}\n"
    )

    result = run_script(project, environment, "setup.sh")

    assert result.returncode == 1
    assert "SHA-256 doğrulaması başarısız" in result.stderr


def test_backup_is_atomic_and_refuses_overwrite(tmp_path):
    project, environment = make_project(tmp_path)
    archive = tmp_path / "flightdb.jsonl.gz"

    first = run_script(
        project,
        environment,
        "backup-mongodb.sh",
        str(archive),
    )
    second = run_script(
        project,
        environment,
        "backup-mongodb.sh",
        str(archive),
    )

    assert first.returncode == 0, first.stderr
    assert archive.read_bytes() == b"fake-mongodb-export"
    assert second.returncode == 1
    assert "üzerine yazılmadı" in second.stderr
    assert not list(tmp_path.glob("flightdb.jsonl.gz.tmp.*"))


def test_restore_rejects_running_consumer(tmp_path):
    project, environment = make_project(tmp_path)
    archive = tmp_path / "flightdb.jsonl.gz"
    archive.write_bytes(b"archive")
    environment["FAKE_CONSUMER_RUNNING"] = "1"

    result = run_script(
        project,
        environment,
        "restore-mongodb.sh",
        str(archive),
    )

    assert result.returncode == 1
    assert "consumer çalışıyor" in result.stderr


def test_restore_requires_replace_confirmation_for_nonempty_target(tmp_path):
    project, environment = make_project(tmp_path)
    archive = tmp_path / "flightdb.jsonl.gz"
    archive.write_bytes(b"archive")
    environment["FAKE_DOCUMENT_COUNT"] = "3"

    result = run_script(
        project,
        environment,
        "restore-mongodb.sh",
        str(archive),
    )

    assert result.returncode == 1
    assert "Hedef flightdb boş değil" in result.stderr


def test_restore_limits_namespace_and_enables_explicit_replace(tmp_path):
    project, environment = make_project(tmp_path)
    archive = tmp_path / "flightdb.jsonl.gz"
    archive.write_bytes(b"archive")
    environment["FAKE_DOCUMENT_COUNT"] = "3"

    result = run_script(
        project,
        environment,
        "restore-mongodb.sh",
        str(archive),
        "--replace",
        "--yes",
    )

    assert result.returncode == 0, result.stderr
    docker_log = Path(environment["FAKE_DOCKER_LOG"]).read_text()
    assert "mongodb_transfer.py import --replace" in docker_log
    assert Path(environment["FAKE_RESTORE_CAPTURE"]).read_bytes() == b"archive"


def test_offline_builder_rejects_invalid_version_before_docker():
    result = subprocess.run(
        ["sh", str(ROOT / "scripts" / "build-offline-package.sh")],
        cwd=ROOT,
        env={
            **os.environ,
            "VERSION": "latest",
            "PLATFORM": "amd64",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Geçersiz VERSION" in result.stderr
