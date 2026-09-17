#!/usr/bin/env python3
"""Local bookkeeping and guarded evaluation for AutoResearch Team.

No model calls, no autonomous scheduler, no security sandbox. Python >= 3.11.
Managed evaluation uses POSIX process groups and advisory file locks (Linux/macOS).
The Codex Owner, not this utility, schedules native subagents.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import stat
import subprocess
import sys
import tempfile
import time
import uuid


class ResearchError(Exception):
    """An actionable, fail-closed workflow error."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value):
        raise ResearchError("Use a 1–80 character task/node identifier: letters, numbers, _ or -.")
    return value


def read_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResearchError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ResearchError(f"Expected a JSON object: {path}")
    return obj


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(obj, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def digest_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ResearchError(f"Expected a regular, non-symlink file: {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def inside(base: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not relative:
        raise ResearchError(f"Expected a safe relative path: {relative}")
    candidate = base / p
    if not candidate.resolve().is_relative_to(base.resolve()):
        raise ResearchError(f"Path escapes its root: {relative}")
    return candidate


def workspace_hash(workspace: Path, paths: list[str]) -> str:
    records: dict[str, str] = {}
    for rel in paths:
        path = inside(workspace, rel)
        if not path.exists() or path.is_symlink():
            raise ResearchError(f"Missing or symlinked tracked path: {path}")
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for f in files:
            if f.is_symlink():
                raise ResearchError(f"Symlink in tracked source tree: {f}")
            if f.is_file():
                records[str(f.relative_to(workspace))] = digest_file(f)
    if not records:
        raise ResearchError("No tracked source files; cannot bind results to a candidate.")
    return canonical_hash(records)


def source_files(workspace: Path, paths: list[str]) -> dict:
    """Declared source closure; regular files only, including Unix mode bits.

    A declaration is not dependency discovery. The Owner/Verifier still audit
    whether tracked_paths covers everything used by the evaluator.
    """
    result = {}
    for rel in paths:
        path = inside(workspace, rel)
        if path.is_symlink() or not path.exists():
            raise ResearchError(f"Missing or symlinked source path: {path}")
        for f in sorted(path.rglob("*")) if path.is_dir() else [path]:
            if f.is_symlink():
                raise ResearchError(f"Symlink in declared source: {f}")
            if f.is_dir():
                continue
            if not f.is_file():
                raise ResearchError(f"Non-regular source file: {f}")
            result[str(f.relative_to(workspace))] = {
                "sha256": digest_file(f), "mode": stat.S_IMODE(f.stat().st_mode)}
    if not result:
        raise ResearchError("No declared source files.")
    return result


def verify_source_snapshot(task: Path, node_id: str, source_hash: str,
                           workspace: Path | None = None,
                           expected_manifest_hash: str | None = None) -> str:
    """Check sealed node identity and its recoverable source, not actor identity.

    With workspace=None, validate old evidence without requiring a reused slot
    to still contain the old candidate. This preserves historical comparisons.
    """
    identifier(node_id)
    sealed = checked_protocol(task)
    node = read_json(task / "nodes" / f"{node_id}.json")
    directory = inside(task, f"snapshots/{node_id}")
    manifest_path = directory / "manifest.json"
    fingerprint = digest_file(manifest_path)
    if (node.get("id") != node_id or
            node.get("source_commit_or_snapshot") != f"snapshots/{node_id}/source" or
            node.get("source_hash") != source_hash or
            node.get("snapshot_manifest_sha256") != fingerprint):
        raise ResearchError("Node source binding is missing/changed; seal a NEW node before running.")
    if expected_manifest_hash is not None and expected_manifest_hash != fingerprint:
        raise ResearchError("Sealed snapshot manifest changed after the recorded run.")
    manifest = read_json(manifest_path)
    p = sealed["protocol"]
    if (manifest.get("schema_version") != 1 or
            manifest.get("node_id") != node_id or
            manifest.get("task_id") != read_json(task / "state.json")["task_id"] or
            manifest.get("protocol_hash") != sealed["protocol_hash"] or
            manifest.get("tracked_paths") != p["tracked_paths"] or
            manifest.get("source_hash") != source_hash or
            node.get("workspace") != manifest.get("workspace")):
        raise ResearchError("Snapshot does not match this node/task/protocol.")
    if node_id == "baseline" and manifest.get("files") != sealed.get("baseline_files"):
        raise ResearchError("Baseline snapshot modes/content differ from the frozen baseline.")
    source = directory / "source"
    if source.is_symlink():
        raise ResearchError("Snapshot source must not be a symlink.")
    if (workspace_hash(source, p["tracked_paths"]) != source_hash or
            source_files(source, p["tracked_paths"]) != manifest.get("files")):
        raise ResearchError("Saved source snapshot is missing or modified.")
    if workspace is not None:
        workspace = workspace.resolve()
        if (str(workspace) != manifest["workspace"] or
                source_files(workspace, p["tracked_paths"]) != manifest["files"]):
            raise ResearchError("Workspace no longer matches its sealed node; create a NEW node.")
    return fingerprint


@contextmanager
def lock(task: Path, name: str):
    if os.name != "posix":
        raise ResearchError("Managed evaluation requires Linux/macOS/WSL; no unsafe Windows fallback.")
    import fcntl
    task.mkdir(parents=True, exist_ok=True)
    with (task / name).open("a+", encoding="utf-8") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ResearchError(f"BUSY: {name}; do not start a competing Owner/evaluation.") from exc
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def emit(task: Path, event: str, **details) -> None:
    # Caller holds the relevant task lock; separate events have unique filenames.
    write_json(task / "events" / f"{time.time_ns()}-{uuid.uuid4().hex[:8]}.json",
               {"time": now(), "event": event, **details})


def init_task(root: Path, task_id: str, goal: str, insights: list[Path]) -> Path:
    identifier(task_id)
    root = root.resolve()
    if not root.is_dir() or not goal.strip():
        raise ResearchError("An existing project directory and a nonempty goal are required.")
    # Preflight before creating anything.
    for source in insights:
        if not source.is_file():
            raise ResearchError(f"Insight document not found: {source}")
    task = root / ".autoresearch" / task_id
    try:
        task.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ResearchError("Task already exists. Resume it or choose a new task ID.") from exc
    for name in ["input", "nodes", "reviews", "analysis", "runs", "events"]:
        (task / name).mkdir()
    (task / ".gitignore").write_text("*\n", encoding="utf-8")
    (task / "input" / "request.md").write_text(goal, encoding="utf-8")
    sources = [{"kind": "user_request", "path": "input/request.md",
                "sha256": digest_file(task / "input/request.md")}]
    for i, source in enumerate(insights, 1):
        destination = task / "input" / f"insight-{i:02d}{source.suffix or '.txt'}"
        shutil.copyfile(source, destination)
        sources.append({"kind": "user_document", "original_path": str(source.resolve()),
                        "path": str(destination.relative_to(task)), "sha256": digest_file(destination)})
    write_json(task / "input" / "sources.json", {"sources": sources})
    write_json(task / "state.json", {"schema_version": 1, "task_id": task_id,
               "project_root": str(root), "phase": "intake", "created_at": now(),
               "owner_agent_id": None, "next_action": "Read inputs; create brief and verification protocol."})
    (task / "brief.md").write_text(
        "# Research brief\n\n## Goal\n" + goal +
        "\n\n## Explicit constraints\n\n## Hypotheses and insight provenance\n"
        "\n## Scope and authorization\n\n## Acceptance evidence\n\n## Budget and stop conditions\n",
        encoding="utf-8")
    (task / "insights.md").write_text(
        "# Insights\n\nPreserve source/line or message references. Distinguish explicit constraints, "
        "hypotheses, observations and suggested mechanisms. Do not promote a hypothesis to a fact.\n",
        encoding="utf-8")
    emit(task, "created")
    return task


def positive_number(x, label: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0:
        raise ResearchError(f"{label} must be a positive finite number.")
    return float(x)


def validate_protocol(p: dict) -> None:
    if p.get("schema_version") != 1 or p.get("mode") not in {"engineering", "algorithm", "hybrid"}:
        raise ResearchError("Unsupported protocol schema/mode.")
    if not isinstance(p.get("evaluation_command"), list) or not p["evaluation_command"]:
        raise ResearchError("evaluation_command must be a nonempty argv array, not a shell string.")
    if any(not isinstance(x, str) or not x for x in p["evaluation_command"]):
        raise ResearchError("Every command argument must be a nonempty string.")
    for token in ["{workspace}", "{output}"]:
        if not any(token in x for x in p["evaluation_command"]):
            raise ResearchError(f"Evaluator command must include {token}.")
    for key in ["allowed_workspaces", "tracked_paths", "protected_files", "required_checks"]:
        values = p.get(key)
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x for x in values):
            raise ResearchError(f"{key} must be a nonempty string array.")
    policy = p.get("source_snapshot_policy", "legacy")
    if policy not in {"legacy", "required"}:
        raise ResearchError("source_snapshot_policy must be legacy or required.")
    if policy == "required":
        for rel in p["tracked_paths"]:
            parts = Path(rel).parts
            if not parts or parts[0] in {".git", ".autoresearch", ".autoresearch-worktrees"}:
                raise ResearchError("Declare source paths explicitly; do not track '.', Git metadata or task outputs.")
        roots = [Path(x).resolve() for x in p["allowed_workspaces"]]
        if len(roots) != len(set(roots)) or any(
                a != b and a.is_relative_to(b) for a in roots for b in roots):
            raise ResearchError("Snapshot profile requires distinct, non-nested workspace roots.")
        for protected in p["protected_files"]:
            if any(Path(protected).resolve().is_relative_to(root) for root in roots):
                raise ResearchError("Keep frozen evaluator/data manifests outside candidate/baseline workspaces.")
    for x in p["allowed_workspaces"]:
        if not Path(x).is_absolute() or not Path(x).is_dir():
            raise ResearchError(f"Workspace must be an existing absolute directory: {x}")
    baseline = p.get("baseline_workspace")
    if not isinstance(baseline, str) or str(Path(baseline).resolve()) not in [str(Path(x).resolve()) for x in p["allowed_workspaces"]]:
        raise ResearchError("baseline_workspace must identify one of the allowed workspaces.")
    expected = p.get("baseline_expected_failures", [])
    if not isinstance(expected, list) or any(x not in p["required_checks"] for x in expected):
        raise ResearchError("baseline_expected_failures must be a subset of required_checks.")
    if expected and p["mode"] == "algorithm":
        raise ResearchError("Algorithm optimization requires a correct baseline; no expected-failure exemption.")
    for rel in p["tracked_paths"]:
        inside(Path(p["allowed_workspaces"][0]), rel)
    for x in p["protected_files"]:
        if not Path(x).is_absolute():
            raise ResearchError("Protected files must use absolute paths.")
        digest_file(Path(x))
    seeds = p.get("confirmation_seeds")
    if (not isinstance(seeds, list) or not seeds or
            any(type(x) is not int for x in seeds) or len(seeds) != len(set(seeds))):
        raise ResearchError("confirmation_seeds must be a nonempty array of unique integers.")
    b = p.get("budget", {})
    if type(b.get("max_runs")) is not int or b["max_runs"] < 1:
        raise ResearchError("budget.max_runs must be a positive integer.")
    for key in ["max_run_seconds", "max_total_seconds"]:
        positive_number(b.get(key), key)
    reserve = b.get("confirmation_reserve_fraction", 0.3)
    if isinstance(reserve, bool) or not isinstance(reserve, (int, float)) or not 0 < reserve < 1:
        raise ResearchError("confirmation_reserve_fraction must be strictly between 0 and 1.")
    m = p.get("primary_metric")
    if p["mode"] != "engineering" and m is None:
        raise ResearchError("Algorithm/hybrid mode requires a primary metric.")
    if m is not None:
        if not isinstance(m, dict) or not m.get("name") or m.get("direction") not in {"min", "max"}:
            raise ResearchError("Invalid primary_metric definition.")
        delta = m.get("minimum_improvement", 0)
        if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(delta) or delta < 0:
            raise ResearchError("minimum_improvement must be finite and nonnegative.")
        target = m.get("target")
        if target is not None and (isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target)):
            raise ResearchError("Metric target must be null or a finite number.")


def freeze(task: Path, protocol_path: Path) -> dict:
    p = read_json(protocol_path)
    validate_protocol(p)
    with lock(task, ".control.lock"):
        if (task / "protocol.lock.json").exists():
            raise ResearchError("Protocol already frozen. A changed protocol needs a NEW task and fresh baseline.")
        if p.get("source_snapshot_policy") == "required" and any(
                task.resolve().is_relative_to(Path(x).resolve()) for x in p["allowed_workspaces"]):
            raise ResearchError("Keep task control/evidence outside all execution workspaces.")
        for workspace in p["allowed_workspaces"]:
            workspace_hash(Path(workspace).resolve(), p["tracked_paths"])
        sealed = {"protocol": p, "protocol_hash": canonical_hash(p),
                  "protected_hashes": {x: digest_file(Path(x)) for x in p["protected_files"]},
                  "baseline_hash": workspace_hash(Path(p["baseline_workspace"]).resolve(), p["tracked_paths"]),
                  "frozen_at": now()}
        if p.get("source_snapshot_policy") == "required":
            sealed["baseline_files"] = source_files(Path(p["baseline_workspace"]).resolve(), p["tracked_paths"])
        write_json(task / "protocol.lock.json", sealed)
        state = read_json(task / "state.json")
        state.update(phase="baseline", next_action="Evaluate the unmodified baseline.")
        write_json(task / "state.json", state)
        emit(task, "protocol_frozen", protocol_hash=sealed["protocol_hash"])
        return sealed


def checked_protocol(task: Path) -> dict:
    sealed = read_json(task / "protocol.lock.json")
    if canonical_hash(sealed["protocol"]) != sealed.get("protocol_hash"):
        raise ResearchError("Protocol snapshot has changed; evidence is invalid.")
    for path, expected in sealed["protected_hashes"].items():
        if digest_file(Path(path)) != expected:
            raise ResearchError(f"Protected evaluator/data-manifest changed: {path}")
    return sealed


def records(task: Path) -> list[dict]:
    return [read_json(f) for f in sorted((task / "runs").glob("*/record.json"))]


def validate_result(result: dict, p: dict, baseline: bool = False) -> bool:
    if type(result.get("valid")) is not bool:
        raise ResearchError("Result must contain an explicit boolean valid field.")
    checks, metrics = result.get("checks"), result.get("metrics")
    if not isinstance(checks, dict) or not isinstance(metrics, dict):
        raise ResearchError("Result must contain checks and metrics objects.")
    for name in p["required_checks"]:
        if type(checks.get(name)) is not bool:
            raise ResearchError(f"Missing/non-boolean correctness check: {name}")
    for name, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ResearchError(f"Non-finite or non-numeric metric: {name}")
    primary = p.get("primary_metric")
    if primary is not None and primary["name"] not in metrics:
        raise ResearchError("Required primary metric is missing.")
    expected = set(p.get("baseline_expected_failures", [])) if baseline else set()
    return result["valid"] and all(checks[name] or name in expected for name in p["required_checks"])


def stop_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    # Also remove ordinary descendants left after a supervisor has exited.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def run_evaluation(task: Path, node: str, workspace: Path, seed: int, stage: str, actor: str) -> dict:
    identifier(node)
    if stage not in {"search", "confirm"} or not actor.strip():
        raise ResearchError("Use search/confirm stage and the real Codex agent/thread ID.")
    workspace = workspace.resolve()
    with lock(task, ".run.lock"):
        sealed = checked_protocol(task)
        p, previous = sealed["protocol"], records(task)
        phase = read_json(task / "state.json")["phase"]
        if phase not in {"baseline", "search", "verification"}:
            raise ResearchError("Task is not in an executable phase; resolve blockers or start a new task.")
        if str(workspace) not in [str(Path(x).resolve()) for x in p["allowed_workspaces"]]:
            raise ResearchError("Workspace is outside this task's frozen allowlist.")
        if any(r["status"] == "running" for r in previous):
            raise ResearchError("Interrupted run exists. Inspect jobs and use recover before continuing.")
        b = p["budget"]
        if len(previous) >= b["max_runs"]:
            raise ResearchError("BUDGET: maximum run count reached (failed runs count too).")
        used = sum(float(r.get("elapsed_seconds", r.get("timeout_seconds", 0))) for r in previous)
        ceiling = b["max_total_seconds"]
        if stage == "search":
            reserved_runs = 2 * len(p["confirmation_seeds"])
            if len(previous) >= b["max_runs"] - reserved_runs:
                raise ResearchError("BUDGET: remaining run slots reserved for baseline/candidate confirmation.")
            ceiling *= 1 - b.get("confirmation_reserve_fraction", 0.3)
        remaining = ceiling - used
        if remaining <= 0:
            raise ResearchError("BUDGET: time allowance reached for this stage.")
        timeout = min(b["max_run_seconds"], remaining)
        before = workspace_hash(workspace, p["tracked_paths"])
        if node == "baseline" and (workspace != Path(p["baseline_workspace"]).resolve() or before != sealed["baseline_hash"]):
            raise ResearchError("Baseline workspace/source differs from the frozen baseline snapshot.")
        if node != "baseline" and workspace == Path(p["baseline_workspace"]).resolve():
            raise ResearchError("The frozen baseline workspace cannot be used as a mutable candidate.")
        snapshot_hash = None
        if p.get("source_snapshot_policy") == "required":
            snapshot_hash = verify_source_snapshot(task, node, before, workspace)
        run_id = f"{node}-{uuid.uuid4().hex[:12]}"
        folder = task / "runs" / run_id
        output = folder / "output"
        output.mkdir(parents=True)
        substitutions = {"{workspace}": str(workspace), "{output}": str(output),
                         "{seed}": str(seed), "{stage}": stage}
        command = []
        for arg in p["evaluation_command"]:
            for key, value in substitutions.items():
                arg = arg.replace(key, value)
            command.append(arg)
        rec = {"run_id": run_id, "node_id": node, "stage": stage, "actor_id": actor,
               "workspace": str(workspace), "workspace_hash": before, "seed": seed,
               "protocol_hash": sealed["protocol_hash"], "command": command,
               "status": "running", "started_at": now(), "timeout_seconds": timeout,
               "valid": False, "host": {"platform": sys.platform, "python": sys.version.split()[0]}}
        if snapshot_hash is not None:
            rec["source_snapshot_manifest_sha256"] = snapshot_hash
        write_json(folder / "record.json", rec)
        start, proc = time.monotonic(), None
        try:
            env = os.environ.copy()
            env.update(ART_WORKSPACE=str(workspace), ART_OUTPUT_DIR=str(output),
                       ART_SEED=str(seed), ART_STAGE=stage, PYTHONDONTWRITEBYTECODE="1")
            with (folder / "stdout.log").open("wb") as log:
                proc = subprocess.Popen(command, cwd=workspace, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
                rec["process_group_id"] = proc.pid
                write_json(folder / "record.json", rec)
                try:
                    rec["returncode"] = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    stop_group(proc)
                    rec.update(status="timeout", returncode=proc.returncode)
                else:
                    stop_group(proc)
                    rec["status"] = "finished" if proc.returncode == 0 else "failed"
            checked_protocol(task)
            after = workspace_hash(workspace, p["tracked_paths"])
            if before != after:
                raise ResearchError("Tracked candidate source changed DURING evaluation.")
            if snapshot_hash is not None:
                verify_source_snapshot(task, node, before, workspace, snapshot_hash)
            if rec["status"] == "finished":
                result_path = output / "metrics.json"
                result = read_json(result_path)
                rec["valid"] = validate_result(result, p, baseline=(node == "baseline"))
                rec["result"] = result
                rec["result_sha256"] = digest_file(result_path)
                if not rec["valid"]:
                    rec["status"] = "invalid"
        except KeyboardInterrupt:
            if proc is not None:
                stop_group(proc)
            rec.update(status="interrupted", error="Interrupted by user/host", valid=False)
        except (ResearchError, OSError, ValueError) as exc:
            if proc is not None and proc.poll() is None:
                stop_group(proc)
            rec.update(status="invalid", error=str(exc), valid=False)
        finally:
            rec.update(elapsed_seconds=time.monotonic() - start, ended_at=now())
            write_json(folder / "record.json", rec)
            emit(task, "evaluation_finished", run_id=run_id, status=rec["status"])
        return rec


def verify_record(task: Path, run_id: str) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", run_id):
        raise ResearchError("Invalid run ID.")
    rec = read_json(task / "runs" / run_id / "record.json")
    sealed = checked_protocol(task)
    if rec.get("protocol_hash") != sealed["protocol_hash"] or not rec.get("valid"):
        raise ResearchError(f"Invalid or incomparable run: {run_id}")
    if sealed["protocol"].get("source_snapshot_policy") == "required":
        fingerprint = rec.get("source_snapshot_manifest_sha256")
        if not fingerprint:
            raise ResearchError("Run has no sealed source binding.")
        verify_source_snapshot(task, rec["node_id"], rec["workspace_hash"],
                               expected_manifest_hash=fingerprint)
    output = task / "runs" / run_id / "output" / "metrics.json"
    if digest_file(output) != rec.get("result_sha256"):
        raise ResearchError("Result file was modified after execution.")
    actual = read_json(output)
    if actual != rec.get("result"):
        raise ResearchError("Stored metrics differ from the recorded result artifact.")
    if not validate_result(actual, sealed["protocol"], baseline=(rec.get("node_id") == "baseline")):
        raise ResearchError("Correctness gates failed.")
    if rec.get("node_id") == "baseline" and rec.get("workspace_hash") != sealed["baseline_hash"]:
        raise ResearchError("Baseline evidence does not match the frozen baseline snapshot.")
    return rec


def compare(task: Path, baseline_id: str, candidate_id: str) -> dict:
    baseline, candidate = verify_record(task, baseline_id), verify_record(task, candidate_id)
    if (baseline["stage"], baseline["seed"]) != (candidate["stage"], candidate["seed"]):
        raise ResearchError("Compare matched stages and seeds only.")
    metric = checked_protocol(task)["protocol"].get("primary_metric")
    result = {"baseline": baseline_id, "candidate": candidate_id,
              "scope": "screening comparison only; not significance, proof, or final acceptance"}
    if metric is None:
        return {**result, "decision": "correctness_passes_review_required"}
    name = metric["name"]
    a, c = baseline["result"]["metrics"][name], candidate["result"]["metrics"][name]
    gain = (a - c) if metric["direction"] == "min" else (c - a)
    return {**result, "gain": gain, "decision": "promising" if gain > 0 and gain >= metric.get("minimum_improvement", 0) else "no_gain"}


def checkpoint(task: Path, phase: str, next_action: str, owner: str) -> dict:
    if phase not in {"intake", "contract", "baseline", "search", "verification", "blocked"}:
        raise ResearchError("Use finish, not checkpoint, to enter a terminal state.")
    with lock(task, ".control.lock"):
        state = read_json(task / "state.json")
        if state["phase"] in {"completed", "no_gain", "inconclusive"}:
            raise ResearchError("Terminal task cannot be silently reopened.")
        state.update(phase=phase, next_action=next_action, owner_agent_id=owner, updated_at=now())
        write_json(task / "state.json", state)
        emit(task, "checkpoint", phase=phase, next_action=next_action)
        return state


def finish(task: Path, review_path: Path) -> dict:
    review = read_json(review_path)
    with lock(task, ".run.lock"), lock(task, ".control.lock"):
        sealed = checked_protocol(task)
        p = sealed["protocol"]
        if read_json(task / "state.json")["phase"] in {"completed", "no_gain", "inconclusive"}:
            raise ResearchError("Terminal task cannot be silently overwritten.")
        if review.get("verdict") not in {"pass", "no_gain", "inconclusive"}:
            raise ResearchError("Review verdict must be pass/no_gain/inconclusive.")
        reviewer = review.get("reviewer_agent_id")
        builders = review.get("builder_agent_ids")
        if not isinstance(reviewer, str) or not reviewer or not isinstance(builders, list) or not builders or reviewer in builders:
            raise ResearchError("Record a distinct real reviewer thread ID and nonempty builder IDs.")
        if review.get("protocol_hash") != sealed["protocol_hash"]:
            raise ResearchError("Review refers to a different protocol.")
        if not isinstance(review.get("limitations"), list) or not review.get("summary") or not review.get("claim_scope"):
            raise ResearchError("Review requires a summary, claim_scope and explicit limitations array.")
        valid_runs = [verify_record(task, x) for x in review.get("evidence_run_ids", [])]
        if review["verdict"] == "pass":
            if review.get("blocking_issues") != []:
                raise ResearchError("Pass requires an explicit empty blocking_issues array.")
            target = review.get("candidate_node_id")
            if not isinstance(target, str) or not target or target == "baseline":
                raise ResearchError("Pass requires a distinct candidate node, not baseline itself.")
            selected = [r for r in valid_runs if r["node_id"] == target and r["stage"] == "confirm"]
            baselines = [r for r in valid_runs if r["node_id"] == "baseline" and r["stage"] == "confirm"]
            needed = set(p["confirmation_seeds"])
            for group in [selected, baselines]:
                if len(group) != len(needed) or {r["seed"] for r in group} != needed:
                    raise ResearchError("Pass requires one matched baseline/candidate confirmation run per specified seed.")
                if any(r["actor_id"] != reviewer for r in group):
                    raise ResearchError("Confirmation runs must be executed by the independent reviewer.")
                if len({r["workspace_hash"] for r in group}) != 1:
                    raise ResearchError("Cannot combine confirmation results from different source snapshots.")
            candidate = selected[0]
            if workspace_hash(Path(candidate["workspace"]), p["tracked_paths"]) != candidate["workspace_hash"]:
                raise ResearchError("Candidate changed after verification; rerun verification on the new version.")
            if p.get("source_snapshot_policy") == "required":
                verify_source_snapshot(task, candidate["node_id"], candidate["workspace_hash"],
                                       Path(candidate["workspace"]),
                                       candidate["source_snapshot_manifest_sha256"])
            metric = p.get("primary_metric")
            if metric is not None:
                name = metric["name"]
                a = statistics.mean(r["result"]["metrics"][name] for r in baselines)
                c = statistics.mean(r["result"]["metrics"][name] for r in selected)
                gain = (a - c) if metric["direction"] == "min" else (c - a)
                if not (gain > 0 and gain >= metric.get("minimum_improvement", 0)):
                    raise ResearchError("Confirmation mean does not meet the configured improvement requirement.")
                target_value = metric.get("target")
                if target_value is not None and ((metric["direction"] == "min" and c > target_value) or (metric["direction"] == "max" and c < target_value)):
                    raise ResearchError("Configured target was not met.")
        if review["verdict"] == "no_gain" and not valid_runs:
            raise ResearchError("no_gain requires valid observed evidence; otherwise use inconclusive.")
        phase = "completed" if review["verdict"] == "pass" else review["verdict"]
        write_json(task / "reviews" / "final.json", review)
        state = read_json(task / "state.json")
        state.update(phase=phase, next_action=None, finished_at=now(), final_review="reviews/final.json")
        write_json(task / "state.json", state)
        emit(task, "finished", phase=phase)
        return state


def recover(task: Path, confirmed_stopped: bool) -> dict:
    if not confirmed_stopped:
        raise ResearchError("Inspect host processes first, then pass --confirm-jobs-stopped.")
    count = 0
    with lock(task, ".run.lock"):
        for rec in records(task):
            if rec["status"] != "running":
                continue
            pgid = rec.get("process_group_id")
            if pgid:
                try:
                    os.killpg(pgid, 0)
                except ProcessLookupError:
                    pass
                except PermissionError as exc:
                    raise ResearchError("Cannot verify previous process group has stopped.") from exc
                else:
                    raise ResearchError(f"Process group {pgid} still exists; do not duplicate its job.")
            rec.update(status="interrupted", valid=False, ended_at=now(),
                       elapsed_seconds=rec["timeout_seconds"], error="Recovered orphan record; full reserved time charged.")
            write_json(task / "runs" / rec["run_id"] / "record.json", rec)
            count += 1
        emit(task, "recovered", count=count)
    return {"recovered_runs": count}


def status(task: Path) -> dict:
    rs = records(task)
    return {"state": read_json(task / "state.json"), "run_count": len(rs),
            "managed_seconds": sum(r.get("elapsed_seconds", r.get("timeout_seconds", 0)) for r in rs),
            "runs": [{k: r.get(k) for k in ["run_id", "node_id", "stage", "status", "valid", "seed"]} for r in rs]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", type=Path, required=True)
    init.add_argument("--task", required=True)
    goal = init.add_mutually_exclusive_group(required=True)
    goal.add_argument("--goal")
    goal.add_argument("--goal-file", type=Path)
    init.add_argument("--insight", type=Path, action="append", default=[])
    for name in ["freeze", "run", "status", "compare", "checkpoint", "finish", "recover"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--task-dir", type=Path, required=True)
        if name == "freeze": cmd.add_argument("--protocol", type=Path, required=True)
        if name == "run":
            cmd.add_argument("--node", required=True)
            cmd.add_argument("--workspace", type=Path, required=True)
            cmd.add_argument("--seed", type=int, default=0)
            cmd.add_argument("--stage", choices=["search", "confirm"], default="search")
            cmd.add_argument("--actor", required=True)
        if name == "compare":
            cmd.add_argument("--baseline", required=True)
            cmd.add_argument("--candidate", required=True)
        if name == "checkpoint":
            cmd.add_argument("--phase", required=True)
            cmd.add_argument("--next-action", required=True)
            cmd.add_argument("--owner", required=True)
        if name == "finish": cmd.add_argument("--review", type=Path, required=True)
        if name == "recover": cmd.add_argument("--confirm-jobs-stopped", action="store_true")
    args = parser.parse_args()
    try:
        task = args.task_dir.resolve() if hasattr(args, "task_dir") else None
        if task is not None and not (task / "state.json").is_file():
            raise ResearchError("Task directory is not initialized.")
        if args.command == "init":
            text = args.goal if args.goal is not None else args.goal_file.read_text(encoding="utf-8")
            result = {"task_dir": str(init_task(args.root, args.task, text, args.insight))}
        elif args.command == "freeze": result = freeze(task, args.protocol)
        elif args.command == "run": result = run_evaluation(task, args.node, args.workspace, args.seed, args.stage, args.actor)
        elif args.command == "status": result = status(task)
        elif args.command == "compare": result = compare(task, args.baseline, args.candidate)
        elif args.command == "checkpoint": result = checkpoint(task, args.phase, args.next_action, args.owner)
        elif args.command == "finish": result = finish(task, args.review)
        else: result = recover(task, args.confirm_jobs_stopped)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0 if args.command != "run" or result["valid"] else 1
    except (ResearchError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
