# Codex runtime adapter

## Host interface versus this plugin

The public component is one skill. `plugin.json` packages that skill. A plugin metadata field does not create an agent pool. Current Codex supports delegation requested by applicable skill instructions; use that mechanism rather than inventing an `agents` manifest field.

The native host may expose tools such as `spawn_agent`, `send_input`, `wait`, and `close_agent`. Use their actual descriptions and current schema. These names are examples of runtime capabilities, not callable tools implemented by this plugin. Do not print pseudo-tool calls as evidence of execution.

Prefer built-in `explorer` for the read-heavy Researcher/Analyst, and `worker`/`default` for Engineers and a Verifier that must run tests. Supply the role contract explicitly. Do not request custom agent names that the host has not registered. A prompt that says “do not edit” is an instruction boundary, not an OS-level read-only sandbox. Native sandbox defaults and live parent overrides still apply.

## Handoff packet

Every child gets a compact, self-contained packet:

```text
ROLE: <researcher | engineer | analyst | verifier>
Read: <absolute role file path>
TASK_DIR: <absolute task directory>
BRIEF: <absolute brief path>
NODE / PHASE: <ID and mode>
WORKSPACE / CWD: <exact absolute registered baseline/A/B path; or read-only snapshot>
SOURCE_BINDING: <sealed manifest/hash; or pending implementation>
LEASE: <slot, writer thread ID, lease_epoch, editing/yielded/evaluation state>
PROJECT_INSTRUCTIONS: <explicit applicable AGENTS.md/instruction paths>
INPUTS: <precise source, code snapshot, prior run IDs or analysis paths>
MISSION: <one bounded outcome>
WRITE_SCOPE: <specific authorized source paths or assigned report file; no shared state or other workspaces>
EVALUATION_AUTH: <protocol hash, allowed node/stage/seeds, allocated runs>
DO_NOT_CHANGE: <fixed evaluator, data split, shared interfaces, other workspaces>
RETURN: verdict, artifact references, run IDs, blockers, next-action suggestion.
COMMUNICATION: Return to Owner; do not ask the user or spawn further agents.
```

The Owner saves the actual child thread ID and return path in `team.json` and the matching node/decision record. Check inputs/results before moving dependent work forward. Delegate a verifier independently of candidate builders. Start fresh verification context where the host supports it; do not assert that the context is blind if the host inherits history.

## Concurrency and lifetime

Three child threads is a scheduling baseline. A verified host config can impose a stricter cap with `[agents] enabled = true` and `max_concurrent_threads_per_session = 3`. Do not silently replace project or user config. Two Engineers plus one specialist exhaust the baseline; close a finished Researcher before creating an Analyst. One evaluation per task is enforced only for calls through `researchctl.py`; direct commands and other tasks are outside that lock. Allocate GPU resources across tasks explicitly.

`wait` for real completion; read the returned evidence. Steer with native follow-up instructions. Close completed children. Before the Owner yields, stop or reconcile all owned jobs and save the next action. Never infer running subprocesses from an old conversation summary. Do not start an API harness or independent Codex CLI subprocess as a fake substitute for a native child.

## Installation and invocation

The package supplies the supported portable Agent Plugins root manifest plus a Codex compatibility manifest. Local installation uses a repo marketplace. Do not imply local installation publishes to the public directory.

In a UI that supports `@` selection, select AutoResearch Team from the actual picker. In Codex CLI use `/skills` or `$auto-research`; a literal `@auto-research-team` string in a shell is not a universal invocation command. The IDE fallback is the standalone skill; plugin availability differs by surface. This release has not been end-to-end tested inside a live Codex client.

Official references (checked 2026-09-17):
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/codex/build-skills
- https://developers.openai.com/codex/multi-agent

Repository extension (0.1.1): a worktree outside the original checkout may not inherit its uncommitted instruction files. Explicitly pass applicable project instructions and verify the native child uses the assigned cwd/paths. If isolated native writing is unavailable, serialize source writers; do not simulate isolation by changing branches in one shared directory. The script does not authenticate leases or thread IDs.
