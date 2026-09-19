#!/usr/bin/env python3
"""Publish only generated release files, qualify their exact commit, then merge.

GITHUB_TOKEN-created pull requests do not run CI unattended. Explicit
workflow_dispatch starts the qualification run; never infer checks from PR
creation or bypass branch protection.
No remote branch code is executed by this script.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = "supernovae-st/nika-docs"
ALLOWED = {"snippets/_status-snapshot.mdx", "snippets/data/releases.json",
           "changelog/releases.mdx", "estate.yaml"}
REQUIRED = {"link-audit", "oracle-sweep", "oracle-sweep (migrated engine pin)",
            "The estate tool is the shared one", "Spec to documentation reference"}


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120).stdout.strip()


def api(endpoint, *args):
    return json.loads(run("gh", "api", f"repos/{REPO}/{endpoint}", *args))


def check_files(paths):
    if not paths or set(paths) - ALLOWED:
        raise ValueError("release proposal must contain only the generated release surfaces")


def check_pr(pr, head):
    if (pr.get("state") != "OPEN" or pr.get("isCrossRepository") is not False
            or pr.get("baseRefName") != "main" or pr.get("headRefOid") != head):
        raise ValueError("proposal identity changed; refusing to merge")
    check_files([entry["path"] for entry in pr["files"]])


def check_jobs(jobs):
    names = {job["name"] for job in jobs}
    if not REQUIRED <= names or any(job.get("conclusion") != "success" for job in jobs):
        raise ValueError("all documentation gates must succeed on the selected commit")


def main():
    # The workflow has already projected and validated these files. Refuse any
    # unexpected staged file before publishing, including a workflow/code edit.
    run("git", "add", *sorted(ALLOWED))
    paths = run("git", "diff", "--cached", "--name-only").splitlines()
    if not paths:
        print("release-heal: release index and binary snapshot already current")
        return
    check_files(paths)
    tree = run("git", "write-tree")
    tag = json.loads(Path("snippets/data/releases.json").read_text())["releases"][0]["tag"]
    branch = f"nika-release-heal/{tag}-{tree[:12]}"
    remote = run("git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if remote:
        head = remote.split()[0]
        run("git", "fetch", "origin", f"refs/heads/{branch}")
        if run("git", "rev-parse", "FETCH_HEAD^{tree}") != tree:
            raise ValueError("existing proposal does not have the validated tree")
    else:
        run("git", "switch", "-c", branch)
        run("git", "config", "user.name", "nika-release[bot]")
        run("git", "config", "user.email", "nika@supernovae.studio")
        run("git", "commit", "-m", f"docs: synchronize published releases through {tag}",
            "-m", "Co-Authored-By: Nika 🦋 <nika@supernovae.studio>")
        head = run("git", "rev-parse", "HEAD")
        run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
    prs = json.loads(run("gh", "pr", "list", "--repo", REPO, "--head", branch,
                         "--base", "main", "--state", "open", "--json", "number"))
    if not prs:
        body = Path(os.environ["RUNNER_TEMP"]) / "release-heal-pr.md"
        body.write_text(f"Refresh the complete published release index and the verified native snapshot through {tag}.\n\n"
                        "Only generated release surfaces change. The full documentation workflow is dispatched on the exact commit; "
                        "merge requires every gate to succeed and normal main protection to allow it.\n")
        run("gh", "pr", "create", "--repo", REPO, "--head", branch, "--base", "main",
            "--title", f"docs: synchronize published releases through {tag}", "--body-file", str(body))
        prs = json.loads(run("gh", "pr", "list", "--repo", REPO, "--head", branch,
                             "--base", "main", "--state", "open", "--json", "number"))
    if len(prs) != 1:
        raise ValueError("expected exactly one release proposal")
    number = str(prs[0]["number"])
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run("gh", "workflow", "run", "gate.yml", "--repo", REPO, "--ref", branch)
    print(f"release-heal: PR #{number}, validating {head}", flush=True)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        runs = api(f"actions/workflows/gate.yml/runs?event=workflow_dispatch&head_sha={head}&per_page=100")["workflow_runs"]
        selected = [r for r in runs if r["head_sha"] == head and r["head_branch"] == branch and r["created_at"] >= started]
        if selected:
            selected_run = max(selected, key=lambda r: r["id"])
            if selected_run["status"] == "completed":
                if selected_run["conclusion"] != "success":
                    raise ValueError(f"documentation checks failed: {selected_run['html_url']}")
                check_jobs(api(f"actions/runs/{selected_run['id']}/jobs?per_page=100")["jobs"])
                break
        time.sleep(20)
    else:
        raise ValueError("documentation checks timed out; proposal remains open")
    pr = json.loads(run("gh", "pr", "view", number, "--repo", REPO, "--json",
                        "state,isCrossRepository,baseRefName,headRefOid,files"))
    check_pr(pr, head)
    # REST merge honors normal protection; there is no admin bypass or force.
    result = api(f"pulls/{number}/merge", "--method", "PUT", "-f", "merge_method=squash", "-f", f"sha={head}")
    if result.get("merged") is not True:
        raise ValueError("branch protection did not allow the merge; proposal remains open")
    print(f"release-heal: merged PR #{number} at {result['sha']}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f"release-heal: {error}", file=sys.stderr)
        sys.exit(1)
