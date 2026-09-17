# Owner control policy

## Fixed constraints and configurable choices

Fixed for a task: user-stated invariants, approved scope, evaluation meaning, data protocol, authorization and frozen acceptance contract. Explicit insight hypotheses are not fixed truths. User emphasis on testing a particular idea constrains experimental priority, not the sign of the result.

Baseline choices: one Owner; four on-demand role types; maximum three concurrent child threads; up to two candidate write slots; one active managed evaluation per task; two bounded debugging attempts per candidate; two focused verification repair rounds. No permanent Reporter, Memory Agent, Runner Agent or debate panel. The Owner writes final reports; a script runs commands; records hold memory.

Unspecified budgets default to a conservative pilot: 12 managed evaluations, at most 300 seconds per evaluation, 1,800 seconds total managed command time; no new paid infrastructure. These are configurable resource limits, not runtime estimates and not a promise to finish a research problem. Use existing authorized resources, identify available hardware, and record assumptions in the brief. If a meaningful experiment needs more than this allocation, report that decision rather than substituting an invalid miniature experiment and claiming success. Reserve 30% of managed time and matched baseline/candidate confirmation slots. For deterministic engineering confirmation can use one seed; for stochastic claims baseline three matched seeds is a minimum diagnostic, not a significance guarantee. Experiment/model call budgets are distinct: these scripts cannot enforce Codex token expenditure.

## Intake and protocol

Read project instructions, existing tests, uncommitted changes and source insights. Do not reset, stash, commit or discard pre-existing user changes as a convenience. A dirty in-scope baseline can be copied with a manifest to a separate authorized workspace; preserve the original. Ask only when ambiguity changes the objective/authorization or blocks valid evaluation.

Use Researcher and Verifier for different questions: “what mechanism is worth testing?” and “what evidence would make the claim credible?”. Verifier can inspect/propose evaluator code at this stage. Freeze only after resolving defects. Existing clear user acceptance criteria do not need repeated human approval; new guesses that materially determine success do.

Read [repository policy](repository-policy.md). Create exact baseline/A/B workspace directories before freezing, and use those fixed slots for later nodes. Keep task control/evidence outside all execution roots. New tasks use the required source snapshot profile. Record writer leases in `team.json`; roles/leases are not OS permissions.

Create exact candidate/baseline workspace directories before freezing. Independent Git worktrees are the default for multiple writers. If unavailable, use isolated source copies with hashes. If isolation is not available, serialize writers and record the restriction; still use real Researcher/Verifier children. Never treat worktrees as a container or access-control boundary.

## Scheduling decisions

For engineering work, use the dependency graph. Delegate independent modules only when their interface is specified; integrate in an owned task branch and rerun the complete acceptance suite. Do not generate alternative implementations merely to fill a parallel slot.

For algorithm research, maintain up to two live hypotheses after establishing a credible baseline. Per candidate: draft if no runnable implementation, debug if execution fails, improve if correct but improvable. These are Engineer modes, not mandatory new agents. A node records its parent and reference nodes for borrowed implementation/evidence. Do not overwrite a sealed node when code/config changes, and do not equate node count with worktree count. A merge/fusion creates a new candidate that needs independent evaluation; do not add gains from separate experiments.

Cheap screening: the frozen evaluator checks correctness first, then metrics. Analyst is invoked after a batch (baseline: up to three useful comparisons), at branch stagnation (baseline: three non-improving valid comparisons), or on an anomaly. The Owner can drop a branch, refine the hypothesis, transfer a tested component, or stop. Do not turn negative findings into repetitive implementation repairs. This is a simple bounded beam/tree policy, not an implementation of Monte Carlo graph search or MAP-Elites.

## Verification and publication of a claim

A candidate conclusion triggers Verifier. Pin the sealed node/source manifest, evaluator version, dependency/data versions and exact run IDs. Engineer yields the source write lease before Owner seals the node and before any evaluation. Verifier reads the saved source and uses the matching original registered slot for reruns; do not add a new verification workspace to an already frozen allowlist. No silent rebase to a moving main. Integration creates a new sealed node; changed frozen baselines/protocols create linked tasks. Ask the Verifier to read the source and original output before seeing the Engineer's persuasive narrative where practical. The Verifier reruns BOTH baseline and candidate using the same confirmation protocol/seeds and checks one meaningful counterexample/alternative explanation appropriate to the claim. For noisy performance estimates, inspect dispersion and resource comparability; three seeds alone are not a general statistical guarantee.

Expensive runs need protocol review before execution. Suspicious improvements, data handling changes and threatened invariants trigger early review rather than waiting for the final milestone. Routine cheap successful iterations do not each get a fresh full LLM review.

A disagreement produces a specific evidence request, not majority voting. Budget up to two focused repair/reverification rounds. A changed metric or data split invalidates comparability: record why, then create a new task/protocol and rerun its baseline. Do not re-freeze in place. Approval is bound to the exact verified source hash. Integration changes require verification of the integrated version, not reuse of branch-level approval.

Terminal outcomes: `completed` means the configured acceptance gates plus independent review passed; `no_gain` means no supported gain in the evaluated scope/budget; `inconclusive` means insufficient or conflicting evidence. `blocked` is a checkpoint awaiting a material decision/capability. No outcome asserts global optimality, general mathematical correctness or novelty unless that was separately established.

## Checkpoint and recovery

After every batch record phase, active child IDs, candidate lineage, latest evidence, budget consumed, current best *verified* candidate, and exact next action. The main Owner is the single writer of shared decisions. Every child has an assigned output path.

On resume: inspect `.autoresearch/<id>/state.json`, `team.json`, `protocol.lock.json`, last decisions and run records; query the host for the recorded active children and inspect jobs. A `running` record left after interruption is not a completed experiment. `researchctl recover` refuses recovery while the previous process group still exists. Only mark interrupted jobs after checking they are stopped. A consumed/unknown interrupted allocation is charged conservatively. Keep original evidence; do not start a duplicate experiment to simplify recovery.
