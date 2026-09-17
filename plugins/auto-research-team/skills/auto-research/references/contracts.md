# Contracts and helper commands

`T` below means an existing absolute task directory; `S` means the installed skill directory. Run `python3 "$S/scripts/researchctl.py" --help` to inspect current arguments. The helper uses the Python standard library. Managed execution is POSIX-only (Linux/macOS/WSL); metadata/file operations do not require a model API.

## Task inputs and records

```bash
python3 "$S/scripts/researchctl.py" init --root "$PROJECT" --task "$TASK_ID" \
  --goal-file "$REQUEST_MD" --insight "$INSIGHT_MD"
```

`--insight` is optional and repeatable; `--goal` accepts text instead of `--goal-file`. Do not fabricate paths from an attachment title. Task creation preserves source bytes and SHA-256 values. Keep original text in `input/`; put interpretation, fixed constraints and hypotheses in `insights.md` and `brief.md`.

The Owner maintains `team.json`, `decisions.md` and `nodes/<id>.json`. Node fields: `id`, `parent`, `reference_nodes`, `hypothesis`, `operator` (draft/improve/debug/fuse), `author_agent_id`, `workspace`, `source_commit_or_snapshot`, `run_ids`, `status`, `reason`. Use real paths and IDs. A committed revision or saved complete patch/source snapshot makes a candidate reconstructible; a hash alone is not a backup. The helper records tracked-content hashes but does not copy the whole codebase.

## Repository profile (0.1.1)

Read [repository policy](repository-policy.md). `repoctl.py` adds only `seal`, `check`, and a derived `catalog`; it neither dispatches agents nor creates/switches/deletes Git worktrees. The Owner prepares exact baseline/A/B paths before freeze and owns shared node/team updates. New tasks set `source_snapshot_policy: "required"`; missing/"legacy" preserves the original behavior for existing frozen tasks. Never edit an old protocol lock to enable or disable checks.

For this profile, source paths must be explicit, workspace roots distinct/non-nested, and frozen evaluator/data manifests outside execution workspaces. `tracked_paths` includes source, method config, entry points and dependency locks actually used by the project, not outputs. It is a declared dependency closure, not automatic import analysis. An empty/ignored/unlisted input is not magically archived.

Create the baseline node plus planned candidate nodes using the node template. After freeze and writer handoff:

```bash
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node baseline
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node N001-shuffle
python3 "$S/scripts/repoctl.py" check --task-dir "$T" --node N001-shuffle --live
python3 "$S/scripts/repoctl.py" catalog --task-dir "$T"
```

`seal` copies actual declared source/config files and their modes into `snapshots/<node>/source/`, writes a manifest, then updates node fields `source_commit_or_snapshot`, `source_hash`, and `snapshot_manifest_sha256`. Owner may update status/reason/run IDs afterwards, not the source binding. Re-sealing refuses overwrite; changed code/config uses a new node. A source-only change can use the same existing workspace path/branch; frozen comparison changes start a linked task.

`run` requires a valid node seal before launching and records `source_snapshot_manifest_sha256`. It still executes from the registered workspace, with before/after byte/mode checks, not an immutable OS snapshot. `verify_record` validates archived source even after a slot is reused; `finish` also matches the current deliverable. `check` audits the archive alone; `--live` additionally checks the historical registered workspace. These are integrity checks, not permission enforcement. Snapshot/node updates are not a multi-file transaction; reconcile orphan staging/seals as described in the policy.

## Freeze a task-specific evaluator

Start from `assets/protocol.template.json`, replacing all placeholder paths. The Owner and Verifier create a project-specific evaluator **before** running it. This package does not know your tests, training procedure or research metric. Protect the evaluator and a manifest of dependency/data/split versions outside candidate write scopes. Include each imported evaluator helper in `protected_files`; hashing only a thin launcher does not protect the underlying tests.

The fixed evaluator command is an argv array, not a shell string. Allowed substitutions: `{workspace}`, `{output}`, `{seed}`, `{stage}`. It executes with candidate workspace as CWD. The evaluator should orchestrate the project's authorized test/benchmark/train commands, produce raw evidence, and write `{output}/metrics.json`. It should use process isolation/containerization appropriate to untrusted candidate code; loading candidate code into the evaluator's own Python process does not create a trust boundary.

```json
{
  "valid": true,
  "checks": {"reference_correctness": true, "regression_suite": true},
  "metrics": {"latency_ms": 12.3}
}
```

This is an output-format example, not observed experimental data. `valid` means the evaluation procedure produced usable evidence, not that all tests passed. Declare `baseline_workspace`; its source snapshot is sealed and baseline runs cannot silently use a changed implementation. For a new-feature or bug-fix engineering task, predeclare specific `baseline_expected_failures` (a subset of `required_checks`) before freezing: the unmodified baseline may fail those checks, but candidate acceptance still requires ALL checks to pass. Do not exempt regressions or an incorrect optimization baseline. Pure algorithm mode does not allow this exemption. All required checks must be explicitly boolean. All metrics must be finite numbers; absent results, NaN, Infinity or boolean metrics are rejected. A zero exit code alone is not a pass. `primary_metric: null` is allowed for engineering tasks whose acceptance is correctness-only. Algorithm/hybrid tasks need an explicit metric; metric direction, minimum gain and optional target are frozen. Thresholds have **absolute metric units**; the evaluator may emit a relative-gain metric when that is the intended target.

Use `stage=search` for selection and `stage=confirm` for the predeclared confirmation procedure. Stage can select a reserved dataset/test suite in the fixed evaluator. Different seeds alone do not provide a hidden test set. Local file hashes are integrity checks, not secrecy or adversarial tamper-proofing.

```bash
python3 "$S/scripts/researchctl.py" freeze --task-dir "$T" --protocol "$T/protocol.json"
python3 "$S/scripts/researchctl.py" run --task-dir "$T" --node baseline \
  --workspace "$BASELINE" --seed 0 --stage search --actor "$ACTUAL_AGENT_ID"
python3 "$S/scripts/researchctl.py" run --task-dir "$T" --node hypothesis-a-v1 \
  --workspace "$CANDIDATE_A" --seed 0 --stage search --actor "$ACTUAL_AGENT_ID"
```

The command is always read from the frozen protocol. Each run has its own directory, log, output, source hash, actual actor ID and protocol hash. One task-level lock serializes managed runs. Both failed and successful runs consume run count; timeout and total managed elapsed time are checked. Search cannot consume the reserved confirmation slots/time. No global GPU or model-token accounting is implied. Remote/distributed jobs need an explicitly authorized external scheduler with job cancellation; this runner controls ordinary local process-group descendants only.

Tracked source paths should contain immutable source/config/lock files, not logs, training outputs, caches or checkpoints. Set framework output paths to the per-run output directory. Modifications during execution invalidate the run. Save large dataset versions/checksums in a small protected manifest rather than rehashing an entire dataset every iteration.

## Compare, checkpoint, recover, finish

```bash
python3 "$S/scripts/researchctl.py" compare --task-dir "$T" --baseline "$BASE_RUN_ID" --candidate "$CAND_RUN_ID"
python3 "$S/scripts/researchctl.py" checkpoint --task-dir "$T" --phase search \
  --next-action "Compare nodes A2/B1, then allocate confirmation runs." --owner "$OWNER_ID"
python3 "$S/scripts/researchctl.py" status --task-dir "$T"
```

`compare` screens matched seeds/stages; it does not claim statistical significance. A promising candidate goes to independent verification, not straight to completion. The Verifier executes baseline and candidate confirmation with its own actual agent ID, one run per specified seed. It creates a review matching `assets/review.template.json`, listing exact run IDs, limitations and blocking issues.

```bash
python3 "$S/scripts/researchctl.py" finish --task-dir "$T" --review "$T/reviews/verifier.json"
```

`finish` checks protocol identity, the distinct declared Reviewer/Engineer IDs, fresh result hashes, required matched confirmation runs, candidate source identity, and mean improvement/target where configured. These are deterministic acceptance preconditions, not an authentication system or a mathematical proof checker. The Verifier still judges variance, data leakage, test adequacy, specification coverage and claim scope. Do not forge agent IDs or evidence to satisfy the checker.

An interrupted record requires `recover --task-dir "$T" --confirm-jobs-stopped` only after inspecting actual jobs. Never use recovery to bypass an active job or a budget. Continue a nonterminal task using checkpoint and the native host's resume mechanisms. A materially changed goal/protocol starts a new linked task.
