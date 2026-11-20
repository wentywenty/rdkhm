#!/usr/bin/env python3
"""Apply or revert the patch manifest in config/patches.json idempotently.

A per-collection state file under out/patches-state records the patch hash and
repository HEAD after a successful apply. Every apply is still verified with
`git apply --reverse --check`, because HEAD does not change when a patch is
applied and a reset tree would otherwise keep looking patched. Stacked patches
can fail both the reverse and forward checks; the recorded state is used only
in that ambiguous case, and never when the patch applies forward again.
The optional kernel RT patch is a separate `kernel-rt` collection so the
default profile never applies it; `--revert --only kernel-rt` removes it.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "out/patches-state"
OPT_IN_COLLECTIONS = {"kernel-rt"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def head(repo):
    result = git(repo, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def load_state(collection):
    path = STATE_DIR / f"{collection}.json"
    if path.is_file():
        return json.loads(path.read_text())
    return {"patches": {}}


def save_state(collection, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{collection}.json"
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def selected_collections(collections, only):
    # kernel-rt is opt-in; a bare invocation must not change the default profile.
    return only or [name for name in collections if name not in OPT_IN_COLLECTIONS]


def apply_one(entry, state, dry_run=False, record=False, revert=False, verify=False):
    repo = ROOT / entry["repo"]
    patch = ROOT / "patches" / entry["patch"]
    if not repo.is_dir():
        raise RuntimeError(f"Missing repository: {repo}")
    if not patch.is_file():
        raise RuntimeError(f"Missing patch: {patch}")
    digest = sha(patch)
    revision = head(repo)
    recorded = state["patches"].get(entry["patch"])
    extra = ["--ignore-whitespace"] if entry.get("ignore_whitespace") else []
    if revert:
        if record:
            raise RuntimeError("--record cannot be combined with --revert")
        if git(repo, "apply", "--reverse", "--check", *extra, str(patch)).returncode == 0:
            if dry_run:
                return "would-revert"
            result = git(repo, "apply", "--reverse", *extra, str(patch))
            if result.returncode:
                raise RuntimeError(f"Failed to revert {entry['patch']}:\n{result.stderr.strip()}")
            state["patches"].pop(entry["patch"], None)
            return "reverted"
        # Not applied. Clear stale state only if the patch still applies forward.
        if recorded and recorded.get("sha256") == digest:
            if git(repo, "apply", "--check", *extra, str(patch)).returncode == 0:
                state["patches"].pop(entry["patch"], None)
                return "absent"
            raise RuntimeError(
                f"{entry['patch']} is recorded as applied but neither applies nor reverses; "
                f"review {entry['repo']} manually")
        return "absent"
    recorded_here = (recorded is not None and recorded.get("sha256") == digest and
                     recorded.get("head") == revision)
    # Verify against the tree even when state matches: git apply does not move
    # HEAD, so a repo sync or reset leaves stale state that looks applied.
    if git(repo, "apply", "--reverse", "--check", *extra, str(patch)).returncode == 0:
        state["patches"][entry["patch"]] = {"sha256": digest, "head": revision}
        return "already"
    check = git(repo, "apply", "--check", *extra, str(patch))
    if recorded_here and check.returncode:
        # Neither direction applies cleanly. This is expected for a stacked
        # patch whose context later patches changed; a reset tree would apply
        # forward here instead. Keep state unless the collection is strict.
        if verify:
            raise RuntimeError(
                f"{entry['patch']} is recorded as applied but neither applies nor reverses; "
                f"review {entry['repo']} manually")
        return "already"
    if record:
        state["patches"][entry["patch"]] = {"sha256": digest, "head": revision}
        return "recorded"
    if check.returncode:
        raise RuntimeError(
            f"Cannot apply {entry['patch']} to {entry['repo']}:\n{check.stderr.strip()}\n"
            f"If this tree was patched outside this manifest, run with --record once.")
    if dry_run:
        return "would-apply"
    result = git(repo, "apply", *extra, str(patch))
    if result.returncode:
        raise RuntimeError(f"Failed to apply {entry['patch']}:\n{result.stderr.strip()}")
    state["patches"][entry["patch"]] = {"sha256": digest, "head": revision}
    return "applied"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", choices=["kernel", "kernel-rt", "openharmony"],
                        help="collection to apply or revert (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="check without modifying the trees")
    parser.add_argument("--record", action="store_true",
                        help="record the manifest as applied without invoking git apply")
    parser.add_argument("--revert", action="store_true",
                        help="ensure the selected collection is not applied")
    args = parser.parse_args()
    if args.record and args.dry_run:
        parser.error("--record cannot be combined with --dry-run")
    if args.revert and not args.only:
        raise ValueError("--revert requires --only so unrelated collections are not touched")
    data = json.loads((ROOT / "config/patches.json").read_text())
    collections = data["collections"]
    selected = selected_collections(collections, args.only)
    counts = {"applied": 0, "already": 0, "would-apply": 0, "recorded": 0,
              "reverted": 0, "would-revert": 0, "absent": 0}
    for name in selected:
        entries = collections.get(name)
        if entries is None:
            raise ValueError(f"Unknown collection: {name}")
        state = load_state(name)
        print(f"[{name}] {len(entries)} patches")
        for entry in entries:
            outcome = apply_one(entry, state, dry_run=args.dry_run, record=args.record,
                                revert=args.revert, verify=name in OPT_IN_COLLECTIONS)
            counts[outcome] += 1
            print(f"  {outcome:11} {entry['patch']}")
        if not args.dry_run:
            save_state(name, state)
    print(f"Applied {counts['applied']}, already present {counts['already']}, "
          f"would apply {counts['would-apply']}, recorded {counts['recorded']}, "
          f"reverted {counts['reverted']}, would revert {counts['would-revert']}, "
          f"absent {counts['absent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
