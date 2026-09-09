#!/usr/bin/env python3
"""Transaction helper for mintlify-snapshot.sh, not a second snapshot owner.

Only version, engineSha, providers, firstCommand and lastUpdated are projected.
lastUpdated is the selected release's UTC publication date. A matching banner
and release-tag commit establish reported build consistency, not signed binary
provenance; artifact verification belongs to the install/release authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from first_command import KNOWN_LABELS, read_first_command

SNAPSHOT = Path(__file__).resolve().parents[1] / "snippets/_status-snapshot.mdx"
REPOSITORY = "supernovae-st/nika"
PROBE_TIMEOUT = 15
VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"


def resolve_nika() -> Path:
    """Resolve once; an invalid explicit selection never tries PATH."""
    explicit = os.environ.get("NIKA_BIN")
    if explicit is not None:
        candidate = Path(explicit)
        if not candidate.is_absolute():
            raise ValueError("NIKA_BIN must be an absolute executable path")
    else:
        found = shutil.which("nika")
        if not found:
            raise ValueError("nika is absent; set NIKA_BIN to the released binary's absolute path")
        candidate = Path(found).absolute()
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ValueError(f"selected NIKA_BIN/PATH binary is not an executable file: {candidate}")
    return candidate.resolve(strict=True)


def probe(arguments: list[str], **kwargs) -> str:
    return subprocess.run(arguments, capture_output=True, text=True, check=True,
                          timeout=PROBE_TIMEOUT, **kwargs).stdout.strip()


def release_metadata() -> tuple[str, str, str]:
    """Select one published stable release, then resolve THAT tag to a commit."""
    release = json.loads(probe(["gh", "release", "view", "--repo", REPOSITORY,
                               "--json", "tagName,publishedAt,isDraft,isPrerelease"]))
    if not isinstance(release, dict) or release.get("isDraft") is not False or release.get("isPrerelease") is not False:
        raise ValueError("selected release is not a published stable release")
    tag = release.get("tagName")
    if not isinstance(tag, str) or not re.fullmatch(f"v{VERSION}", tag):
        raise ValueError("selected release has no stable semver tag")
    published = release.get("publishedAt")
    if not isinstance(published, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", published):
        raise ValueError("selected release has no valid UTC publication timestamp")
    date = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
    ref = json.loads(probe(["gh", "api", f"repos/{REPOSITORY}/git/ref/tags/{tag}"]))
    if not isinstance(ref, dict) or ref.get("ref") != f"refs/tags/{tag}":
        raise ValueError("release tag reference does not name the selected release")
    obj = ref.get("object")
    # Bound annotation dereferencing; a cycle or missing commit fails.
    for _ in range(5):
        if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", obj["sha"]):
            raise ValueError("release tag has no valid Git object identity")
        if obj.get("type") == "commit":
            return tag[1:], date, obj["sha"]
        if obj.get("type") != "tag":
            break
        annotation = json.loads(probe(["gh", "api", f"repos/{REPOSITORY}/git/tags/{obj['sha']}"]))
        obj = annotation.get("object") if isinstance(annotation, dict) else None
    raise ValueError("release tag does not resolve to a commit within five objects")


def binary_digest(binary: Path) -> str:
    with binary.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def projection(binary: Path) -> dict[str, str | int]:
    before = binary_digest(binary)
    version, date, commit = release_metadata()
    # Release credentials stay with gh, never the selected binary. The ONE
    # first-command reader independently creates the stranger's context.
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as work:
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "TERM": "dumb", "NO_COLOR": "1", "NIKA_KEYCHAIN": "off"}
        banner = probe([str(binary), "--version"], cwd=work, env=env)
        match = re.fullmatch(rf"nika ({VERSION}) \(([0-9a-f]{{7,40}})\)", banner)
        if not match:
            raise ValueError("selected binary has a malformed, unknown, or dirty version/build banner")
        if match[1] != version:
            raise ValueError(f"selected binary version {match[1]} does not match released version {version}")
        sha = match[2]
        if not commit.startswith(sha):
            raise ValueError("selected binary's reported build does not match the release tag commit")
        catalog = json.loads(probe([str(binary), "catalog", "--json"], cwd=work, env=env))
        if not isinstance(catalog, dict) or type(catalog.get("catalog_version")) is not int or catalog["catalog_version"] != 1:
            raise ValueError("selected binary catalog has no supported catalog_version: 1 envelope")
        providers = catalog.get("providers")
        if not isinstance(providers, list) or not providers or any(
            not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip()
            for row in providers
        ):
            raise ValueError("selected binary catalog has no nonempty provider object list")
        if len({row["id"] for row in providers}) != len(providers):
            raise ValueError("selected binary catalog has duplicate provider identities")
    first = read_first_command(str(binary))
    if not first:
        raise ValueError(f"no known first command on the selected binary's screen; known labels: {KNOWN_LABELS}")
    if binary_digest(binary) != before:
        raise ValueError("selected binary changed during projection")
    return {"version": version, "engineSha": sha, "providers": len(providers),
            "firstCommand": first, "lastUpdated": date}


def replace_fields(original: bytes, values: dict[str, str | int]) -> bytes:
    """Replace exact owned scalar values, preserving all unrelated bytes."""
    text = original.decode("utf-8")
    blocks = list(re.finditer(r"(?ms)^export const STATUS = \{\r?\n(.*?)^\};", text))
    if len(blocks) != 1:
        raise ValueError("snapshot must contain exactly one STATUS object")
    block = blocks[0]
    body = block[1]
    for key, value in values.items():
        declarations = re.findall(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*:", body)
        if len(declarations) != 1:
            raise ValueError(f"snapshot must contain exactly one {key} field")
        scalar = r'"(?:[^"\\]|\\.)*"' if isinstance(value, str) else r"[0-9]+"
        pattern = rf"(?m)^([ \t]*{re.escape(key)}:[ \t]*)({scalar})(?=[ \t]*,?[ \t]*(?://[^\r\n]*)?\r?$)"
        body, count = re.subn(pattern, lambda match: match[1] + json.dumps(value), body)
        if count != 1:
            raise ValueError(f"snapshot has a malformed {key} field")
    return (text[:block.start(1)] + body + text[block.end(1):]).encode("utf-8")


def atomic_replace(snapshot: Path, original: bytes, replacement: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{snapshot.name}.", dir=snapshot.parent, delete=False) as output:
            temporary = Path(output.name)
            os.fchmod(output.fileno(), stat.S_IMODE(snapshot.stat().st_mode))
            output.write(replacement)
            output.flush()
            os.fsync(output.fileno())
        if snapshot.read_bytes() != original:
            raise ValueError("snapshot changed during projection; refusing to overwrite it")
        os.replace(temporary, snapshot)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        original = SNAPSHOT.read_bytes()
        binary = resolve_nika()
        values = projection(binary)
        replacement = replace_fields(original, values)
        atomic_replace(SNAPSHOT, original, replacement)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"mintlify-snapshot: RED — no snapshot replacement: {error}", file=sys.stderr)
        return 1
    print(f"mintlify-snapshot: updated five fields from {binary}: {json.dumps(values)}")
    print("Reported version/build matches the selected release tag commit; signed artifact provenance was not verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
