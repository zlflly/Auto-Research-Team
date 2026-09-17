#!/usr/bin/env python3
"""Source snapshots and a derived node catalog for AutoResearch Team.

No agent scheduler, Git mutation, source checkout, cleanup, or security sandbox.
Only the Owner invokes seal after the writer has yielded. Python >= 3.11;
seal uses the existing POSIX task locks. check/catalog are read-only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import researchctl as r


def git_metadata(workspace: Path) -> dict:
    def get(*args: str) -> str | None:
        try:
            out = subprocess.run(["git", "-C", str(workspace), *args],
                                 capture_output=True, text=True, timeout=15, check=False,
                                 env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            return out.stdout.strip() if out.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    return {"commit": get("rev-parse", "--verify", "HEAD"),
            "branch": get("symbolic-ref", "--quiet", "--short", "HEAD"),
            "status": get("status", "--porcelain=v1", "--untracked-files=all"),
            "note": "Context only. Declared-source bytes, not this Git label, bind the experiment."}


def seal(task: Path, node_id: str) -> dict:
    """Save the exact declared source closure once; never overwrite a seal.

    The .run.lock prevents overlap with managed evaluation. The .control.lock
    serializes helper/Owner bookkeeping. Neither can stop an uncooperative writer.
    """
    r.identifier(node_id)
    with r.lock(task, ".run.lock"), r.lock(task, ".control.lock"):
        sealed = r.checked_protocol(task)
        p = sealed["protocol"]
        if p.get("source_snapshot_policy") != "required":
            raise r.ResearchError("seal requires a NEW task frozen with source_snapshot_policy=required; do not edit old locks.")
        state = r.read_json(task / "state.json")
        if state["phase"] not in {"baseline", "search", "verification"}:
            raise r.ResearchError("Seal only in an executable task phase.")
        if any(x.get("status") == "running" for x in r.records(task)):
            raise r.ResearchError("Reconcile the interrupted/live run before sealing source.")
        node_path = task / "nodes" / f"{node_id}.json"
        node = r.read_json(node_path)
        if (node.get("id") != node_id or not node.get("hypothesis") or
                not node.get("author_agent_id") or not isinstance(node.get("workspace"), str)):
            raise r.ResearchError("Node needs matching id, hypothesis, author_agent_id and absolute workspace.")
        if not Path(node["workspace"]).is_absolute():
            raise r.ResearchError("Node workspace must be absolute.")
        workspace = Path(node["workspace"]).resolve()
        if str(workspace) not in [str(Path(x).resolve()) for x in p["allowed_workspaces"]]:
            raise r.ResearchError("Node workspace is outside the frozen allowlist.")
        baseline = Path(p["baseline_workspace"]).resolve()
        if (node_id == "baseline") != (workspace == baseline):
            raise r.ResearchError("Only baseline may bind the frozen baseline workspace.")
        for parent in ([node.get("parent")] if node.get("parent") else []) + node.get("reference_nodes", []):
            r.identifier(parent)
            if parent == node_id or not (task / "nodes" / f"{parent}.json").is_file():
                raise r.ResearchError(f"Invalid/missing local lineage reference: {parent}")
        root = r.inside(task, "snapshots")
        destination = root / node_id
        if destination.exists() or node.get("snapshot_manifest_sha256"):
            raise r.ResearchError("Node is already sealed. Reuse it unchanged or create a NEW node ID.")
        before = r.workspace_hash(workspace, p["tracked_paths"])
        if node_id == "baseline" and before != sealed["baseline_hash"]:
            raise r.ResearchError("Baseline changed since protocol freeze.")
        files = r.source_files(workspace, p["tracked_paths"])
        if node_id == "baseline" and files != sealed.get("baseline_files"):
            raise r.ResearchError("Baseline file modes/content changed since protocol freeze.")
        root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".incomplete-{node_id}-", dir=root))
        try:
            source = staging / "source"
            source.mkdir()
            for rel in p["tracked_paths"]:
                if r.inside(workspace, rel).is_dir():
                    r.inside(source, rel).mkdir(parents=True, exist_ok=True)
            for rel in files:
                target = r.inside(source, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(r.inside(workspace, rel), target)
            if (r.workspace_hash(source, p["tracked_paths"]) != before or
                    r.source_files(source, p["tracked_paths"]) != files or
                    r.source_files(workspace, p["tracked_paths"]) != files):
                raise r.ResearchError("Source changed while sealing; stop its writer and retry a fresh seal.")
            r.checked_protocol(task)
            manifest = {"schema_version": 1, "task_id": state["task_id"],
                        "node_id": node_id, "workspace": str(workspace),
                        "protocol_hash": sealed["protocol_hash"],
                        "tracked_paths": p["tracked_paths"], "source_hash": before,
                        "files": files, "git": git_metadata(workspace), "created_at": r.now(),
                        "scope": "Only declared tracked_paths, not datasets, credentials, or the whole Git repository."}
            r.write_json(staging / "manifest.json", manifest)
            # A crash after rename but before node update leaves an orphan seal.
            # Preserve it for Owner reconciliation rather than overwriting evidence.
            staging.rename(destination)
            node.update(workspace=str(workspace), source_hash=before,
                        source_commit_or_snapshot=f"snapshots/{node_id}/source",
                        snapshot_manifest_sha256=r.digest_file(destination / "manifest.json"))
            r.write_json(node_path, node)
            r.emit(task, "source_sealed", node_id=node_id, source_hash=before)
            return {"node_id": node_id, "source_hash": before,
                    "snapshot": str(destination), "file_count": len(files)}
        finally:
            if staging.exists():
                shutil.rmtree(staging)  # Only this invocation's uncommitted staging directory.


def check(task: Path, node_id: str, live: bool = False) -> dict:
    r.identifier(node_id)
    node = r.read_json(task / "nodes" / f"{node_id}.json")
    fingerprint = r.verify_source_snapshot(task, node_id, node.get("source_hash", ""),
                                          Path(node["workspace"]) if live else None)
    return {"node_id": node_id, "valid": True, "scope": "live_workspace" if live else "saved_source",
            "snapshot_manifest_sha256": fingerprint}


def catalog(task: Path) -> dict:
    """Derived view, not another independently edited branch registry."""
    runs = r.records(task)
    team = r.read_json(task / "team.json") if (task / "team.json").exists() else {}
    entries = []
    for path in sorted((task / "nodes").glob("*.json")):
        node = r.read_json(path)
        entries.append({k: node.get(k) for k in
                        ["id", "parent", "hypothesis", "status", "reason", "workspace", "branch",
                         "author_agent_id", "source_commit_or_snapshot", "source_hash"]})
        entries[-1]["run_ids"] = [x["run_id"] for x in runs if x["node_id"] == node.get("id")]
    return {"task_id": r.read_json(task / "state.json")["task_id"],
            "nodes": entries, "workspaces": team.get("workspaces", []),
            "note": "Recorded state only. On resume, reconcile Git, native threads, jobs and leases."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["seal", "check", "catalog"]:
        command = sub.add_parser(name)
        command.add_argument("--task-dir", required=True, type=Path)
        if name != "catalog":
            command.add_argument("--node", required=True)
        if name == "check":
            command.add_argument("--live", action="store_true", help="Also compare the current assigned workspace.")
    args = parser.parse_args()
    try:
        task = args.task_dir.resolve()
        if not (task / "state.json").is_file():
            raise r.ResearchError("Task is not initialized.")
        if args.command == "seal":
            result = seal(task, args.node)
        elif args.command == "check":
            result = check(task, args.node, args.live)
        else:
            result = catalog(task)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (r.ResearchError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
