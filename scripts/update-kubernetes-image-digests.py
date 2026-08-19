#!/usr/bin/env python3
"""Release image digest'lerini GitOps deployment manifestlerine yazar."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SERVICES = ("producer", "consumer", "backend", "frontend")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
VERSION_PATTERN = re.compile(r"v\d+\.\d+\.\d+(?:-rc\.\d+)?")


def read_digest(digest_directory: Path, service: str) -> str:
    digest_path = digest_directory / f"{service}.txt"
    digest = digest_path.read_text(encoding="utf-8").strip()
    if not DIGEST_PATTERN.fullmatch(digest):
        raise ValueError(
            f"{digest_path} geçerli bir image digest içermiyor: {digest!r}"
        )
    return digest


def update_deployment(manifest_directory: Path, service: str, digest: str) -> bool:
    deployment_path = manifest_directory / f"{service}-deployment.yaml"
    content = deployment_path.read_text(encoding="utf-8")
    image = f"ghcr.io/tugrulocal/flight-data-pipeline-{service}"
    pattern = re.compile(
        rf"^(?P<prefix>\s*image:\s*{re.escape(image)})(?::|@)[^\s]+\s*$",
        re.MULTILINE,
    )
    replacement = rf"\g<prefix>@{digest}"
    updated, substitutions = pattern.subn(replacement, content)
    if substitutions != 1:
        raise RuntimeError(
            f"{deployment_path}: tam olarak bir image satırı bekleniyordu, "
            f"bulunan: {substitutions}"
        )

    if updated == content:
        return False
    deployment_path.write_text(updated, encoding="utf-8")
    return True


def replace_exactly_once(path: Path, pattern: str, replacement: str) -> bool:
    content = path.read_text(encoding="utf-8")
    updated, substitutions = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if substitutions != 1:
        raise RuntimeError(
            f"{path}: tam olarak bir sürüm satırı bekleniyordu, bulunan: {substitutions}"
        )
    if updated == content:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def update_version_metadata(manifest_directory: Path, version: str) -> None:
    replace_exactly_once(
        manifest_directory / "backend-configmap.yaml",
        r"^(\s*APP_VERSION:\s*)v[^\s]+$",
        rf"\g<1>{version}",
    )
    replace_exactly_once(
        manifest_directory / "kustomization.yaml",
        r"^(\s*app\.kubernetes\.io/version:\s*)v[^\s]+$",
        rf"\g<1>{version}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-directory", type=Path, required=True)
    parser.add_argument("--digest-directory", type=Path, required=True)
    parser.add_argument("--version", required=True)
    arguments = parser.parse_args()
    if not VERSION_PATTERN.fullmatch(arguments.version):
        raise ValueError(f"Geçersiz release sürümü: {arguments.version!r}")

    changed = []
    for service in SERVICES:
        digest = read_digest(arguments.digest_directory, service)
        if update_deployment(arguments.manifest_directory, service, digest):
            changed.append(service)

    update_version_metadata(arguments.manifest_directory, arguments.version)

    print(
        "Güncellenen image manifestleri: "
        + ", ".join(changed or ["yok"])
        + f"; release sürümü: {arguments.version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
