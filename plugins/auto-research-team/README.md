# AutoResearch Team 0.1.1

Codex-native Owner + on-demand Researcher / Engineer / Analyst / Verifier, for engineering and algorithm research. One public skill (`auto-research`), native child threads, and a local deterministic evaluation helper. No external model API, MCP service, hidden hooks or unattended daemon.

Install through the supplied repo marketplace. Current portable `plugin.json` is canonical; `.codex-plugin/plugin.json` is a compatibility fallback for older local packaging. Both describe the same skill. In a supporting app, select **AutoResearch Team** using the actual `@` picker. In Codex CLI use `$auto-research` or `/skills`.

Example request:

```text
作为 Owner，为当前项目实现并验证我的算法改动。
目标：……
Insight：见 docs/idea.md；另一个猜想是……
保持现有数据划分和接口不变。在既有本地资源内运行。
只在需要我决定研究口径、资源或权限，以及结项时汇报。
```

All operation-specific references live under `skills/auto-research/references/`. The Owner generates a task-specific evaluator from your existing tests and objective; the package does not bundle a universal scientific oracle. The script enforces only managed local evaluations. Codex consumes its normal plan/API usage, depending on how your Codex session is authenticated; no additional model endpoint is introduced here.

Local unit and fault-injection tests are included in the distribution. A live Codex install, `@` routing, native subagent dispatch, and a real research run still require host-side acceptance testing. Role prompts are not equivalent to registered custom agents or isolated OS permissions.

## 0.1.1 repository-management customization

Owner now reads `skills/auto-research/references/repository-policy.md` at entry. New protocols require sealed source nodes; see `references/repository-examples.md`. Older frozen tasks retain legacy behavior. `assets/AGENTS.md` is an optional project-instruction copy, not a second skill. Installer does not edit existing AGENTS.md. No host end-to-end validation is claimed.
