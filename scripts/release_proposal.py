#!/usr/bin/env python3
"""Publish only generated release files, qualify their exact commit, then merge.

GITHUB_TOKEN-created pull requests do not run CI unattended. Explicit
workflow_dispatch starts one qualification run; the pull_request gate for the
same commit is created held (`action_required`) with an EMPTY pull_requests
payload. This script approves that exact run — only after re-validating the
proposal identity — then waits for BOTH gates and every required job before
the normal exact-SHA merge. Never infer checks from PR creation or bypass
branch protection.
No remote branch code is executed by this script.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = "supernovae-st/nika-docs"
GATE = ".github/workflows/gate.yml"
ALLOWED = {"snippets/_status-snapshot.mdx", "snippets/data/releases.json",
           "changelog/releases.mdx", "estate.yaml"}
REQUIRED = {"link-audit", "oracle-sweep", "oracle-sweep (migrated engine pin)",
            "The estate tool is the shared one", "Spec to documentation reference"}
SECRET = re.compile(r"x-access-token:[^@\s]+@|gh[pousr]_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}")


def run(*args):
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120).stdout.strip()
    except subprocess.CalledProcessError as error:
        detail = SECRET.sub("REDACTED", (error.stderr or error.stdout or "").strip())
        raise ValueError(f"{args[0]} {args[1]} exited {error.returncode}: {detail[:400] or 'no output'}") from None


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


def select_run(runs, *, head, branch, event, since=None):
    """The latest run carrying the exact proposal identity, or None.

    repository and head_repository must both be this repository — a fork's
    gate run is never awaited or approved. The run's pull_requests payload is
    ignored on purpose: GITHUB_TOKEN-created proposals report it empty, so the
    PR identity comes from check_pr and the run identity from these fields.
    """
    selected = [r for r in runs
                if r.get("head_sha") == head and r.get("head_branch") == branch
                and r.get("event") == event and r.get("path") == GATE
                and (r.get("repository") or {}).get("full_name") == REPO
                and (r.get("head_repository") or {}).get("full_name") == REPO
                and (since is None or r.get("created_at", "") >= since)]
    return max(selected, key=lambda r: r["id"]) if selected else None


def gate_run(event, head, branch, since=None):
    runs = api(f"actions/workflows/gate.yml/runs?event={event}&head_sha={head}&per_page=100")["workflow_runs"]
    return select_run(runs, head=head, branch=branch, event=event, since=since)


def approve_gate(number, head, selected):
    """Approve the held pull_request gate after exact identity validation."""
    if selected.get("event") != "pull_request" or selected.get("path") != GATE:
        raise ValueError("only the held pull_request gate may be approved")
    pr = json.loads(run("gh", "pr", "view", number, "--repo", REPO, "--json",
                        "state,isCrossRepository,baseRefName,headRefOid,files"))
    check_pr(pr, head)
    # actions/runs/{id}/approve answers 201 with an empty body; no JSON to parse.
    run("gh", "api", "--method", "POST", f"repos/{REPO}/actions/runs/{selected['id']}/approve")
    print(f"release-heal: approved held pull_request gate {selected['id']} on {head[:12]}", flush=True)


def await_gates(number, head, branch, started):
    """Both gates must complete with every required job green on the exact head."""
    deadline = time.monotonic() + 1200
    approved = set()
    while True:
        states = {}
        for event, since in (("pull_request", None), ("workflow_dispatch", started)):
            selected = gate_run(event, head, branch, since)
            if selected is None:
                states[event] = "missing"
            elif selected["status"] == "action_required":
                if event != "pull_request":
                    raise ValueError(f"unexpected held {event} gate: {selected['html_url']}")
                if selected["id"] not in approved:
                    approve_gate(number, head, selected)
                    approved.add(selected["id"])
                states[event] = "awaiting approval"
            elif selected["status"] != "completed":
                states[event] = selected["status"]
            elif selected["conclusion"] != "success":
                raise ValueError(f"documentation checks failed: {selected['html_url']}")
            else:
                check_jobs(api(f"actions/runs/{selected['id']}/jobs?per_page=100")["jobs"])
                states[event] = "success"
        if all(state == "success" for state in states.values()):
            return
        if time.monotonic() >= deadline:
            raise ValueError(f"documentation checks timed out: {states}; proposal remains open")
        time.sleep(20)


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
    await_gates(number, head, branch, started)
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
