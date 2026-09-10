#!/usr/bin/env python3
"""Install one published Nika release privately, verified before unpacking.

Stdlib + curl + gh. stdout contains NIKA_TAG and absolute NIKA_BIN only after
success (suitable for GITHUB_ENV); diagnostics go to stderr. The release owner
attests tarballs with actions/attest-build-provenance in release.yml; SHA256SUMS
is a separate published asset. We require BOTH, including the tag certificate
identity and source commit, not merely any attestation in the repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

REPO = "supernovae-st/nika"
WORKFLOW = f"{REPO}/.github/workflows/release.yml"
TAG_PATTERN = r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_UNPACKED = 256 * 1024 * 1024
MAX_SUMS = 1024 * 1024
PLATFORMS = {("Linux", "x86_64"): "linux-x64", ("Linux", "aarch64"): "linux-arm64",
             ("Darwin", "x86_64"): "macos-x64", ("Darwin", "arm64"): "macos-arm64"}


def command(args: list[str], timeout: int = 20, **kwargs) -> str:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True,
                              timeout=timeout, **kwargs).stdout.strip()
    except subprocess.CalledProcessError as error:
        # gh's diagnostic distinguishes missing provenance from identity mismatch.
        print((error.stderr or "")[-4000:], file=sys.stderr)
        raise


def stable_tag(tag: str) -> str:
    if not isinstance(tag, str) or not re.fullmatch(TAG_PATTERN, tag):
        raise ValueError("expected an exact stable vMAJOR.MINOR.PATCH release tag")
    return tag


def release_metadata(requested: str | None, target: str) -> tuple[str, dict]:
    args = ["gh", "release", "view"]
    if requested is not None:
        args.append(stable_tag(requested))
    release = json.loads(command(args + ["--repo", REPO, "--json",
                                        "tagName,publishedAt,isDraft,isPrerelease,assets"]))
    if not isinstance(release, dict) or release.get("isDraft") is not False or release.get("isPrerelease") is not False:
        raise ValueError("release is not published and stable")
    tag = stable_tag(release.get("tagName"))
    if requested is not None and tag != requested:
        raise ValueError("release metadata does not match the requested tag")
    published = release.get("publishedAt")
    if not isinstance(published, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", published):
        raise ValueError("release has no publication timestamp")
    datetime.fromisoformat(published.replace("Z", "+00:00"))
    asset_name = f"nika-{target}-{tag[1:]}.tar.gz"
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ValueError("release has no assets")
    selected = {}
    for name, limit in ((asset_name, MAX_ARCHIVE), ("SHA256SUMS", MAX_SUMS)):
        rows = [row for row in assets if isinstance(row, dict) and row.get("name") == name]
        if len(rows) != 1:
            raise ValueError(f"release must have exactly one asset named {name}")
        row = rows[0]
        url = f"https://github.com/{REPO}/releases/download/{tag}/{name}"
        if row.get("state") != "uploaded" or row.get("url") != url:
            raise ValueError(f"asset is not uploaded at its expected release URL: {name}")
        if type(row.get("size")) is not int or not 0 < row["size"] <= limit:
            raise ValueError(f"asset size is absent or exceeds the download bound: {name}")
        selected[name] = row
    return tag, selected


def tag_commit(tag: str) -> str:
    ref = json.loads(command(["gh", "api", f"repos/{REPO}/git/ref/tags/{tag}"]))
    if not isinstance(ref, dict) or ref.get("ref") != f"refs/tags/{tag}":
        raise ValueError("release tag reference mismatch")
    obj = ref.get("object")
    for _ in range(5):
        if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", obj["sha"]):
            raise ValueError("release tag has no full commit identity")
        if obj.get("type") == "commit":
            return obj["sha"]
        if obj.get("type") != "tag":
            break
        annotation = json.loads(command(["gh", "api", f"repos/{REPO}/git/tags/{obj['sha']}"]))
        obj = annotation.get("object") if isinstance(annotation, dict) else None
    raise ValueError("release tag does not resolve within five objects")


def download(row: dict, destination: Path, limit: int) -> None:
    command(["curl", "--fail", "--silent", "--show-error", "--location",
             "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "3",
             "--connect-timeout", "10", "--max-time", "90", "--max-filesize", str(limit),
             "--output", str(destination), row["url"]], timeout=100)
    if destination.stat().st_size != row["size"]:
        raise ValueError(f"download size differs from selected release metadata: {row['name']}")


def verify(archive: Path, sums: Path, tag: str, commit: str) -> None:
    matches = []
    for line in sums.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *]([^\r\n]+)", line)
        if not match:
            raise ValueError("malformed SHA256SUMS record")
        if match[2] == archive.name:
            matches.append(match[1].lower())
    if len(matches) != 1:
        raise ValueError("SHA256SUMS must name the selected archive exactly once")
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != matches[0]:
        raise ValueError("published SHA256SUMS checksum mismatch")
    command(["gh", "attestation", "verify", str(archive), "--repo", REPO,
             "--cert-identity", f"https://github.com/{WORKFLOW}@refs/tags/{tag}",
             "--source-ref", f"refs/tags/{tag}", "--source-digest", commit,
             "--predicate-type", "https://slsa.dev/provenance/v1",
             "--deny-self-hosted-runners"], timeout=90)


def unpack(archive: Path, target: Path) -> None:
    """Bound decompression and validate EVERY member; copy only regular nika."""
    allowed = {"nika", "completions", "completions/nika.bash", "completions/_nika", "completions/nika.fish"}
    deadline = time.monotonic() + 30
    with tempfile.TemporaryFile() as plain:
        size = 0
        with gzip.open(archive, "rb") as zipped:
            while chunk := zipped.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UNPACKED or time.monotonic() > deadline:
                    raise ValueError("archive exceeds decompression bounds")
                plain.write(chunk)
        plain.seek(0)
        with tarfile.open(fileobj=plain, mode="r:") as tar:
            seen = {}
            for member in tar:
                if time.monotonic() > deadline or len(seen) >= len(allowed):
                    raise ValueError("archive exceeds member bounds")
                name = member.name
                if name not in allowed or name in seen:
                    raise ValueError(f"unsafe or duplicate archive member: {name}")
                if (name == "completions" and not member.isdir()) or (name != "completions" and not member.isreg()):
                    raise ValueError(f"archive links and special members are forbidden: {name}")
                if member.size < 0 or member.size > MAX_UNPACKED or member.mode & 0o7000:
                    raise ValueError(f"unsafe archive member metadata: {name}")
                seen[name] = member
            binary = seen.get("nika")
            if binary is None or binary.size == 0 or not binary.mode & 0o111:
                raise ValueError("archive has no executable regular nika")
            source = tar.extractfile(binary)
            if source is None:
                raise ValueError("archive binary cannot be read")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o700)


def install(destination: Path, requested: str | None, target: str) -> tuple[str, Path]:
    if not destination.is_absolute() or any(ord(char) < 32 for char in str(destination)):
        raise ValueError("destination must be an absolute path without control characters")
    # Resolve the parent (including /tmp on macOS), then reserve a fresh private
    # directory. Existing files/directories/symlinks are never followed/replaced.
    destination = destination.parent.resolve(strict=True) / destination.name
    destination.mkdir(mode=0o700)
    try:
        tag, assets = release_metadata(requested, target)
        commit = tag_commit(tag)
        name = f"nika-{target}-{tag[1:]}.tar.gz"
        with tempfile.TemporaryDirectory(prefix=".download-", dir=destination) as temporary:
            archive, sums = Path(temporary) / name, Path(temporary) / "SHA256SUMS"
            download(assets[name], archive, MAX_ARCHIVE)
            download(assets["SHA256SUMS"], sums, MAX_SUMS)
            verify(archive, sums, tag, commit)
            unpack(archive, destination / "nika")
            with tempfile.TemporaryDirectory(dir=temporary) as home:
                env = {"HOME": home, "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1", "NIKA_KEYCHAIN": "off"}
                banner = command([str(destination / "nika"), "--version"], timeout=15, cwd=home, env=env)
            match = re.fullmatch(r"nika (\d+\.\d+\.\d+) \(([0-9a-f]{7,40})\)", banner)
            if not match or match[1] != tag[1:] or not commit.startswith(match[2]):
                raise ValueError("verified artifact's binary banner does not match the selected release tag/build")
        return tag, destination / "nika"
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="new private install directory (absolute path)")
    parser.add_argument("--tag", help="exact stable published tag; omit to resolve latest once")
    parser.add_argument("--platform", choices=sorted(set(PLATFORMS.values())),
                        help="release platform (default: this host)")
    args = parser.parse_args()
    try:
        target = args.platform or PLATFORMS.get((platform.system(), platform.machine()))
        if target is None:
            raise ValueError("unsupported host platform")
        tag, binary = install(args.dest, args.tag, target)
    except (OSError, ValueError, EOFError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f"install-release: RED — {error}", file=sys.stderr)
        return 1
    print(f"NIKA_TAG={tag}\nNIKA_BIN={binary}")
    print(f"install-release: verified checksum and release workflow/tag attestation for {tag}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
