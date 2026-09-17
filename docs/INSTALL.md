# 安装与调用

## 适用范围

本版面向具有原生 subagents 与本地 shell 的 Codex。辅助脚本 Python >=3.11；受控实验执行需要 Linux/macOS/WSL 的进程组与文件锁。本包没有额外 LLM API 配置，也不会启动外部 API harness；原生 Codex 使用仍受你的账户额度与宿主权限约束。

没有为 Claude Code 做宿主适配或端到端验证。可移植 manifest 不等于其原生分派调用已适配所有客户端。

## 1. 准备本地插件

解压后，在有 `tools/`、`plugins/` 的包根目录执行，目标是你的研究项目，而不是本下载包：

```bash
python3 tools/install.py --repo /absolute/path/to/research-project
python3 tools/install.py --repo /absolute/path/to/research-project --apply
```

第一行 dry-run，不写任何文件。`--apply` 准备以下结构：

```text
research-project/
├── .agents/plugins/marketplace.json
├── .codex/config.toml
└── plugins/auto-research-team/
    ├── plugin.json
    ├── .codex-plugin/plugin.json
    └── skills/auto-research/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/
        ├── assets/
        └── scripts/researchctl.py
```

安装器保留已有 marketplace 的 name/其他条目与现有 TOML 文本，对修改的配置留备份。不同内容的已安装版本、同名冲突、显式禁用配置、符号链接目标、坏 TOML 都会拒绝覆盖。安装器不是跨文件事务，I/O 中断后检查文件与备份再重试。

新 marketplace 默认 `personal-research`，source 为 `./plugins/auto-research-team`，相对项目根/marketplace root，不相对 `.agents/plugins`。插件配置形如：

```toml
[plugins."auto-research-team@personal-research"]
enabled = true
```

已有 marketplace 名不同则自动使用已有名字。没有改变宿主模型、沙箱、审批或全局并发配置。

## 2. 在宿主发现并启用

在支持本地插件的桌面端打开/信任目标研究项目，重启客户端，在 Plugins 中选择本地 marketplace，安装或启用 AutoResearch Team，再开新会话验证。项目配置的 trust 与组织策略可能阻止自动加载，按宿主正常审批处理；不要放宽 sandbox 来绕过。

本安装器只准备本地文件，未替你发布到公共目录或修改你的在线账户。若你的客户端未提供本地 plugin UI，使用下面的单技能入口；不会谎称任意版本都支持 `@` 插件。

## 3. 调用

有 `@` 选择器的客户端：选中实际出现的 **AutoResearch Team** 后直接输入目标。Codex CLI：通过 `/skills` 找到技能，或在 Codex 对话内写 `$auto-research`。不要把它作为 shell 变量命令执行。

```text
$auto-research
目标：为当前项目实现……，并对比现有 baseline 验证……。
Insight：读取 docs/insight.md；另外，我怀疑……。
约束：保留公共 API / 数据划分，使用现有本地资源，不自动 push。
```

可随后直接给新 insight、询问状态、暂停，或再次调用要求恢复 `.autoresearch/T001`。没有必要指定每个子角色；Owner 根据阶段决定。原始语音应先由客户端转写为对话文本，插件不处理音频文件。

## 4. 只装 skill 的兼容路径

在尚未安装插件版的项目中执行：

```bash
python3 tools/install.py --repo /absolute/path/to/research-project --skill-only --apply
```

它只复制 `.agents/skills/auto-research/`，不写 marketplace 与 plugin enable 配置。全部角色/脚本在 skill 内部，工作流相同。重启客户端后检查 `/skills` / `$auto-research`。避免与插件版同名 skill 并存。

## 5. 原生子代理与运行条件

插件的角色 Markdown 在分派时加载，**不会**被误当成 `.codex/agents/*.toml` 自动注册。Owner 使用当前宿主真实工具 schema 与 built-in role。`agents/openai.yaml` 仅设置显示信息、显式调用策略。

首次任务验证 `team.json` 中确实有 native child thread IDs。没有实际子代理工具时，插件应保存已做的 intake 并明确报告能力阻塞，不假装一个线程演了四个角色。

如需在宿主额外设置并发上限，可在确认当前配置规范后合并（本安装器不自动改）：

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
```

这是子线程上限，不含 Owner；更低宿主上限优先。只读 role prompt 并非硬只读沙箱。保留现有权限与审批；外部云运行需要另行授权/调度器。

## 6. 本地验证、升级与卸载

```bash
python3 -m unittest discover -s tests -v
```

测试使用本地虚构 fixture，不需要联网、GPU 或模型 API；结果不是算法 benchmark。完整宿主检查见 [ACCEPTANCE.md](ACCEPTANCE.md)。

升级：备份你的插件定制和配置，显式移走旧目录后再装新版；安装器默认不覆盖不同内容。卸载优先使用宿主正常插件管理界面；本包不提供自动清除用户目录的命令。研究产物位于 `.autoresearch/`，不因插件文件被移除而自动清除。

规范来源：[OpenAI 插件打包](https://developers.openai.com/plugins/build/plugins)、[技能](https://developers.openai.com/codex/build-skills)、[Subagents](https://developers.openai.com/codex/multi-agent)。核对日期：2026-09-17。

## 7. 本定制版 0.1.1 的安装与旧任务处理

原安装器与命令保持不变。插件中已包含 repository policy、AGENTS.md 模板和 repoctl，standalone skill 同样完整。
SKILL 入口会加载该规范，无需复制第二个同名 skill；安装器不修改研究项目已有的 AGENTS.md。
仅使用规范文件时，合并 `assets/AGENTS.md` 到现有项目指令，别覆盖用户已有约束。源码封存门禁仍依赖本版脚本。

已有不同内容的 0.1.0 插件仍会被安装器拒绝覆盖。保留旧目录/定制，按上一节既有升级流程显式迁移，
不删除 `.autoresearch/`。旧冻结协议不会自动增加 `source_snapshot_policy`；需要新门禁时新建 linked task 并重跑，
不要修改 `protocol.lock.json`。详细设计与脚本边界见 [实验代码管理](REPOSITORY-MANAGEMENT.md)。
