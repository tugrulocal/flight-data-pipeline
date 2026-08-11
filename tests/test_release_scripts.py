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
  "info --format {{.MemTotal}}") printf '%s\n' "${FAKE_DOCKER_MEMORY:-8589934592}" ;;
  "version --format {{.Server.Version}}") printf '28.3.3\n' ;;
  "compose version") exit 0 ;;
  "compose version --short") printf '2.39.1\n' ;;
  "compose ps --services --status running consumer")
    [ "${FAKE_CONSUMER_RUNNING:-0}" = "1" ] && printf 'consumer\n'
    ;;
  *" mongodump "*) printf 'fake-mongodb-archive' ;;
  *" mongosh "*) printf '%s\n' "${FAKE_DOCUMENT_COUNT:-0}" ;;
  *" mongorestore "*)
    printf '%s\n' "$command_line" >> "${FAKE_DOCKER_LOG:?}"
    cat > "${FAKE_RESTORE_CAPTURE:?}"
    ;;
  "compose config --images")
    printf '%s\n' 'example/image:1.0.0'
    ;;
  "compose config --quiet") exit 0 ;;
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
    archive = tmp_path / "flightdb.archive.gz"

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
    assert archive.read_bytes() == b"fake-mongodb-archive"
    assert second.returncode == 1
    assert "üzerine yazılmadı" in second.stderr
    assert not list(tmp_path.glob("flightdb.archive.gz.tmp.*"))


def test_restore_rejects_running_consumer(tmp_path):
    project, environment = make_project(tmp_path)
    archive = tmp_path / "flightdb.archive.gz"
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
    archive = tmp_path / "flightdb.archive.gz"
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
    archive = tmp_path / "flightdb.archive.gz"
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
    assert "--nsInclude=flightdb.*" in docker_log
    assert "--stopOnError" in docker_log
    assert "--drop" in docker_log
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
