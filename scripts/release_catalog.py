#!/usr/bin/env python3
"""Project the complete published GitHub release inventory into the docs.

Remote release prose is data, never MDX. The inventory records a body digest so
edited notes also trigger healing, and links readers to the full upstream notes.
Fetch and validate everything before replacing either generated file.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPO = "supernovae-st/nika"
DATA = Path("snippets/data/releases.json")
PAGE = Path("changelog/releases.mdx")
TAG = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def api(endpoint):
    return json.loads(subprocess.run(
        ["gh", "api", endpoint], check=True, capture_output=True, text=True,
        timeout=60).stdout)


def utc(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ValueError("release publication date must be a UTC timestamp")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return value


def highlights(body):
    """Use complete upstream change headings, not guessed or truncated summaries."""
    headings = re.findall(r"(?ms)^[-*] \*\*(.+?)\*\*", body)
    return [re.sub(r"\s+", " ", heading.replace('`', '')).strip()
            for heading in headings[:3]]


def fetch(fetcher=api):
    rows = []
    # Explicit pagination also catches a malformed/error response on later pages.
    for page in range(1, 101):
        batch = fetcher(f"repos/{REPO}/releases?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("GitHub release response is not an array")
        for release in batch:
            if not isinstance(release, dict):
                raise ValueError("malformed release row")
            if release.get("draft") is True or release.get("prerelease") is True:
                continue
            if release.get("draft") is not False or release.get("prerelease") is not False:
                raise ValueError("release visibility is missing")
            tag = release.get("tag_name", "")
            if not isinstance(tag, str) or not TAG.fullmatch(tag):
                raise ValueError("published stable release has no stable semver tag")
            url = f"https://github.com/{REPO}/releases/tag/{tag}"
            if release.get("html_url") != url:
                raise ValueError("release URL does not match its repository and tag")
            name = release.get("name") or tag
            body = release.get("body") or ""
            assets = release.get("assets")
            if not isinstance(name, str) or not isinstance(body, str) or not isinstance(assets, list):
                raise ValueError("malformed release title, notes or assets")
            rows.append({"tag": tag, "name": name,
                         "publishedAt": utc(release.get("published_at")),
                         "url": url, "assetCount": len(assets),
                         "highlights": highlights(body),
                         "notesSha256": hashlib.sha256(body.encode()).hexdigest()})
        if len(batch) < 100:
            break
    else:
        raise ValueError("release pagination exceeded its bound")
    rows.sort(key=lambda row: tuple(map(int, TAG.fullmatch(row["tag"]).groups())), reverse=True)
    result = {"schemaVersion": 1, "repository": REPO, "releases": rows}
    validate(result)
    return result


def validate(data):
    if data.get("schemaVersion") != 1 or data.get("repository") != REPO:
        raise ValueError("unexpected catalog schema or repository")
    rows = data.get("releases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("release catalog is empty")
    seen = set()
    previous = None
    for row in rows:
        tag = row.get("tag", "")
        match = TAG.fullmatch(tag)
        if not match or tag in seen:
            raise ValueError("invalid or duplicate release tag")
        version = tuple(map(int, match.groups()))
        if previous is not None and version >= previous:
            raise ValueError("release catalog is not in descending semantic version order")
        seen.add(tag)
        previous = version
        utc(row.get("publishedAt"))
        if row.get("url") != f"https://github.com/{REPO}/releases/tag/{tag}":
            raise ValueError("invalid release URL")
        if not isinstance(row.get("name"), str) or any(ord(c) < 32 for c in row["name"]):
            raise ValueError("invalid release title")
        if type(row.get("assetCount")) is not int or row["assetCount"] < 0:
            raise ValueError("invalid release asset count")
        if not re.fullmatch(r"[a-f0-9]{64}", row.get("notesSha256", "")):
            raise ValueError("invalid release notes digest")
        summaries = row.get('highlights')
        if not isinstance(summaries, list) or len(summaries) > 3 or any(
                not isinstance(s, str) or not s or any(ord(c) < 32 for c in s) for s in summaries):
            raise ValueError('invalid release highlights')


def text(value):
    # Numeric entities make even braces, Markdown and JSX inert text in MDX.
    return "".join(c if c.isalnum() or c in " .,:/—–·" else f"&#{ord(c)};" for c in value)


def render(data):
    validate(data)
    rows = data["releases"]
    out = ['---', 'title: "Releases"',
           'description: "Published engine releases, their dates and downloads. Find current installation instructions, release notes and historical milestones."',
           'sidebarTitle: "Releases"', 'icon: "clock-rotate-left"', '---', '',
           '{/* AUTO-GENERATED by scripts/release_catalog.py from snippets/data/releases.json. */}', '',
           'import { STATUS } from "/snippets/_status-snapshot.mdx";',
           'import { SDK } from "/snippets/_sdk-contract.mdx";', '',
           '## Choose the version you use', '',
           '| Product | Documentation targets | Start here |',
           '| --- | --- | --- |',
           '| Native CLI | v{STATUS.version} | [Install Nika](/getting-started/installation) |',
           '| TypeScript SDK | {SDK.package}@{SDK.sourceVersion} | [SDK quickstart](/sdk/start/quickstart) |', '',
           'The SDK bundles its own engine. A new CLI release does not update an installed npm package.', '',
           '<Info>',
           'This index comes from the complete [published GitHub release list](https://github.com/supernovae-st/nika/releases),',
           'ordered by semantic version. Drafts and prereleases are excluded. Dates are UTC publication dates;',
           'an asset count describes attachments, not a guarantee that every platform or distribution channel is available.',
           '</Info>', '',
           '## Recent releases', '',
           'Open a release for its additions, fixes, breaking changes and download assets.',
           'For new projects, follow the current installation guide rather than commands in older release notes.', '',]
    for row in rows[:8]:
        date = row['publishedAt'][:10]
        label = 'release' if row['assetCount'] else 'record without assets'
        out += [f'<Update label="{row["tag"]}" description="{date} UTC" tags={{["{label}"]}}>',
                f'  **{text(row["name"])}**', '',
                f'  Published {date}. ' + (f'{row["assetCount"]} attached assets.' if row['assetCount'] else '**No attached assets.**'), '',
                *[f'  - {text(summary)}' for summary in row['highlights']], '',
                f'  [Read release notes and downloads]({row["url"]})', '</Update>', '']
    out += ['## All published releases', '', '| Release | Published (UTC) | Attached assets |',
            '| --- | --- | --- |']
    for row in rows:
        count = str(row['assetCount']) if row['assetCount'] else '**None — release record only**'
        out.append(f'| [{row["tag"]}]({row["url"]}) | {row["publishedAt"][:10]} | {count} |')
    out += ['', '## History and next steps', '',
            '- [Historical milestones](/changelog/history) preserve the original dated accounts, including unsuccessful release attempts.',
            '- [Roadmap](/changelog/roadmap) separates what you can use from future release gates.',
            '- [Timeline and evidence](/reference/timeline) explains the sources behind historical claims.',
            '- [Current status](/reference/status) identifies the released binary used to check these docs.', '',
            '## How this stays current', '',
            'An hourly release sync refreshes this index and the released-binary snapshot, opens a generated change,',
            'runs the documentation gates and merges only when those checks and branch protection allow it.',
            'Failed validation leaves the change unmerged and the workflow red; a failed fetch never clears the existing index.',
            'Publication follows the documentation deployment. See the',
            '[sync runs](https://github.com/supernovae-st/nika-docs/actions/workflows/release-heal.yml)',
            'and [source catalog](https://github.com/supernovae-st/nika-docs/blob/main/snippets/data/releases.json).', '']
    return '\n'.join(out)


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(value)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def project(root, *, refresh=False, check=False, fetcher=api):
    data = fetch(fetcher) if refresh else json.loads((root / DATA).read_text())
    page = render(data)
    outputs = {DATA: json.dumps(data, ensure_ascii=False, indent=2) + '\n', PAGE: page}
    drift = [str(path) for path, value in outputs.items()
             if not (root / path).exists() or (root / path).read_text() != value]
    if check and drift:
        raise ValueError('release catalog drift: ' + ', '.join(drift))
    if not check:
        for path, value in outputs.items():
            if str(path) in drift:
                atomic_write(root / path, value)
    return len(data['releases']), drift


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='fetch every public stable release from GitHub')
    parser.add_argument('--check', action='store_true', help='fail on drift without modifying files')
    args = parser.parse_args()
    try:
        count, drift = project(ROOT, refresh=args.refresh, check=args.check)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'release-catalog: {error}', file=sys.stderr)
        return 1
    print(f'release-catalog: {count} published stable releases; ' + (', '.join(drift) if drift else 'current'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
