# 来源与采用范围

核对日期：2026-09-17。以下为官方文档、原始仓库与论文；没有声称完整运行或复现这些项目。链接指向当时查阅的默认分支/页面，不是固定 commit，因此之后可能变化。包内工作流与代码为本任务原创，没有复制第三方 agent 源代码。

## OpenAI / Agent Plugins

- 插件创建、portable `plugin.json`、`extensions.com.openai`、local marketplace、兼容 overlay：<https://developers.openai.com/plugins/build/plugins>
- Portable schema：<https://agent-plugins.org/schemas/1.0.0/plugin.schema.json>
- Skills、目录、显式 `$` 调用、元数据：<https://developers.openai.com/codex/build-skills>
- 原生子代理、skill 请求分派、内建角色与并发：<https://developers.openai.com/codex/multi-agent>
- Worktree 隔离 checkout：<https://developers.openai.com/codex/app/worktrees/>

官方文档当前有部分页面重定向至 learn.chatgpt.com。OpenAI 允许手工打包；本版没有运行宿主 `@plugin-creator`，没有冒称已通过插件目录审核。根 portable manifest 与 `.codex-plugin/plugin.json` 同时存在；inline OpenAI extension 取代 fallback overlay，而非合并。

## 仓库 / 原始论文

1. **karpathy/autoresearch**：<https://github.com/karpathy/autoresearch>
   - 实验协议：<https://raw.githubusercontent.com/karpathy/autoresearch/master/program.md>
   - 支持的描述：单代理 program.md / 固定评估 / keep-discard；不是多角色团队的依据。
2. **AIDE / aideml**：<https://github.com/WecoAI/aideml>
   - 源文件：<https://raw.githubusercontent.com/WecoAI/aideml/main/aide/agent.py>
   - 支持的描述：Agent 的 draft/debug/improve 搜索操作与节点策略。
3. **RD-Agent**：<https://github.com/microsoft/RD-Agent>
   - 源文件：<https://raw.githubusercontent.com/microsoft/RD-Agent/main/rdagent/components/workflow/rd_loop.py>
   - 支持的描述：hypothesis、experiment proposal、coder、runner、feedback/Trace 流程。
4. **AI-Scientist-v2**：<https://github.com/SakanaAI/AI-Scientist-v2>
   - 源文件：<https://raw.githubusercontent.com/SakanaAI/AI-Scientist-v2/main/ai_scientist/treesearch/agent_manager.py>
   - 支持的描述：AgentManager、ParallelAgent、多阶段实验搜索。
5. **MLEvolve**：<https://github.com/InternScience/MLEvolve>
   - 原始论文 HTML，特别是 Appendix A：<https://arxiv.org/html/2606.06473v1>
   - 角色细节采用论文附录，未声称读取并复现完整 engine。图搜索/记忆是来源机制，本插件并不实现完整 MCGS。
6. **Agent Laboratory**：<https://github.com/SamuelSchmidgall/AgentLaboratory>
   - 源文件：<https://raw.githubusercontent.com/SamuelSchmidgall/AgentLaboratory/main/agents.py>
   - 支持的描述：PhDStudent/Postdoc/MLEngineer/SWEngineer/Professor/Reviewers 角色。
7. **OpenEvolve**：<https://github.com/algorithmicsuperintelligence/openevolve>
   - 支持的描述：进化代码候选、population/island 与 evaluator；本版仅借鉴机制，不接其外部模型 backend。

上述事实与本包 engineering choices 在 DESIGN 中分开陈述。没有复用先前聊天中的 star 数、流行度、成功率或 Claude CLI 凭证兼容性断言作为设计前提。
