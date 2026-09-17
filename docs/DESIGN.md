# AutoResearch Team：设计与来源核对

版本：0.1.0。资料核对日期：2026-09-17。实现定位：Codex 原生 Owner skill 的插件包装；不是另一个调用模型 API 的 Python harness。

## 1. 当前决策与约束

**用户约束**：真实多智能体；工程实现与算法研究；目标可附口述文本/Markdown insight；授权范围内自主运行；必要决策与结项才汇报；先在 Codex 使用。不把“多智能体对所有自动科研任务都是必要条件”作为普遍事实，只将它作为本项目明确需求。

**工程 baseline**：当前主线程是 Owner；四类子代理按事件调用；最多三个子线程、两个候选写工作区、每任务一个受控评估进程。采用有界分支搜索，不复制大型 harness，不增加 MCP 或单独模型凭证。

**待宿主验证**：安装可发现性、真实子线程创建/回收、角色遵从、静默程度、跨回合接续。**待任务实验验证**：是否减少人的审查时间且不提高漏错率、分支搜索是否比单分支划算。这里不把工作流存在等同于已经证明科研有效。

## 2. 仓库实际如何分工

以下只描述本次查阅的主仓库/源文件或论文附录；不是 star 排名、生产采用率或复现实验。

| 项目 | 查到的实际组织 | 本插件取用 / 不取用 |
|---|---|---|
| karpathy/autoresearch | `program.md` 驱动单 coding-agent 改实现、固定预算运行、测量、keep/discard；不是一套多角色团队 | 固定 evaluator 和实验台账；不照搬无限循环与对用户 checkout 的 destructive reset |
| WecoAI/AIDE | `aide/agent.py` 中一个 Agent 调用 search policy，在 draft/debug/improve 操作间选择；实验节点不等于独立子代理 | 三种操作内化为 Engineer 模式；保留候选 lineage，不为每个模式开常驻 agent |
| Microsoft RD-Agent | `rdagent/components/workflow/rd_loop.py` 将 HypothesisGen、Hypothesis2Experiment、coder、runner、summarizer/feedback 与 Trace 连接起来 | 分开假设、实现与反馈；不搬入其 API backend 和完整平台 |
| AI-Scientist-v2 | `agent_manager.py` 中 Manager 组织 ParallelAgent，经过 initial implementation、baseline tuning、creative research、ablation 等阶段 | Owner 管阶段与实验分支；不强制每项工程任务产论文或跑 ablation |
| MLEvolve | 论文 Appendix A：Draft/Improve/Debug、Evolution/Fusion/Aggregation、Code Review/Data Leakage/Result Parse；另有 planner–coder 分离。此行角色细节来自论文，不声称读取/复现了全部 engine 实现 | 事件触发、跨分支经验和验证职能；本版不实现 MCGS、不把九种操作全变成常驻线程 |
| Agent Laboratory | `agents.py` 有 PhDStudent、Postdoc、MLEngineer、SWEngineer、Professor、Reviewers 等角色，覆盖文献、计划、数据、实验、分析、写作 | 采用职责隔离；不用学术职衔当权限边界，不默认调论文作者/多评委委员会 |
| OpenEvolve | LLM 生成代码变化，population/island 与 evaluator 选择；不等同于人格化团队 | 接受“候选生成与客观选择分离”；不声称实现 MAP-Elites 或接入该 harness |

精确链接见 [SOURCES.md](../SOURCES.md)。这些项目并没有同一种 subagent API；本插件是对组织与闭环机制的再设计，而非声称已嵌入全部项目。

## 3. 团队：一层 Owner，四类按需子代理

| 角色 | 何时创建 | 交付 | 权限边界与主要风险 |
|---|---|---|---|
| Owner（主线程） | 入口与接续 | brief、阶段状态、调度决策、结项卡 | 处理范围内可逆选择；不擅改目标/指标/预算。风险是上下文过载，故只接紧凑交付与证据入口 |
| Researcher | 初始方案、分支停滞、必要检索 | 最多两个可区分假设，含 insight 对应关系和反证条件 | 读代码/原文，不写候选实现。风险是泛化脑暴，故每项假设绑定可运行比较 |
| Engineer（每候选一个） | 有任务依赖或候选授权时 | source snapshot、实现、run IDs、失败原因 | 一个工作区一个写入者；draft/improve/debug 是其模式；不改冻结 evaluator、不自签验收。风险是评估过拟合 |
| Analyst | 一批结果、停滞、异常指标 | 可比较性、噪声/混淆、branch/drop/verify 建议 | 查看原始结果，不仅改写 Engineer 总结；不负责最终通过。风险是为噪声编故事 |
| Verifier | 冻结协议前；形成结论后；高风险变更时 | 检查协议、独立重跑、反例/替代解释、最终 review | 与候选作者不同真实线程；不悄悄帮作者修实现。风险是同模型相关误差，分角色并不能保证独立性 |

不设常驻 Runner/Memory/Reporter：运行交给受控脚本，记忆落盘，报告由 Owner 写。子代理不再创建子代理，防止递归膨胀。

`references/roles/*.md` 是分派时显式读取的职责说明，不是宿主会自动注册的自定义 agent。Owner 用宿主实际暴露的 native spawn/send/wait/close 能力与已存在 built-in roles，并记录真实 thread ID。`agents/openai.yaml` 是技能展示/调用元数据，不是代理池。

## 4. 调度：先区分工程与算法任务

共同入口：读取目标与 insight → 固化来源 → brief 与评估协议 → 初始 Verifier 检查 → baseline。

**工程任务**按依赖图执行。接口清晰时并行独立模块与测试设计；不是为了并行而写两套竞争实现。组合进入任务分支后，再验证组合版本。新功能/修 bug 时允许 baseline 的已知测试失败：在冻结协议中明确 `baseline_expected_failures`，候选仍需通过所有 required checks。

**算法任务**在正确 baseline 上保留最多两个活跃假设。候选实施、受控运行、客观 screening；小批次后 Analyst 检查，再由 Owner 选择改进、剪枝、迁移已验证组件或停止。当前是有界 beam/tree，不是完整 MCTS/MCGS。单次好分数只晋级，不等于结论。

形成候选结论后，由 Verifier 对 **baseline 和 candidate** 按相同预声明 confirmation protocol/seeds 重跑，检查反例或替代解释。三个配对种子只是随机任务的初始诊断配置，不保证统计显著；真实性、泛化或数学正确性超出 benchmark 所能支持的范围时缩小 claim。

默认两次局部调试、两轮有证据的验收返修。假设被反驳可结项为 no_gain，证据不足可结项 inconclusive；不为制造正结果无限返修。

## 5. Insight 与自主权限

聊天文本及已有语音转写保存为原始请求；Markdown 复制原字节并记录 hash/来源路径。缺少附件时不猜其内容。单独维护 insight 的“明确约束、用户假设、代理假设、观测证据”，以忠实测试替代迎合。插件不提供音频转写服务。

已有明确目标与验收标准时，不要求你重复确认计划。只有矛盾会改变目标、判定、资源授权，或缺少关键资源时提出合并后的决策问题。必要汇报是：目标/口径/预算变更、权限与资源阻塞、两轮验收仍未收敛、用户查询状态，以及结项；宿主工具 UI 和权限弹窗不受 skill 静默指令控制。

不自动 push、开 PR、合入主分支、清除用户工作、购买云算力、升级依赖/系统或外传数据。已经明确授权的范围内操作按任务契约执行，不另设无意义确认。

## 6. 实验护栏与非保证

`researchctl.py` 不调用模型、不选择下一研究方向。它执行原生 Owner 分派的固定 argv 命令，并提供状态与证据检查。任务 evaluator 由 Owner/Verifier 根据真实项目建立，而不是本插件预知用户的研究问题。

已实现：协议/评估文件 hash 固定、baseline source 固定、工作区 allowlist、候选 source hash、单任务运行锁、每次独立输出、超时及预算、失败也计费、确认预算预留、有限数值/正确性检查、结果改动检查、独立声明 ID 与配对确认记录、旧版本验收拒绝、异常接续检查。

默认 pilot：12 次受控评估，每次至多 300 秒，总受控命令 1800 秒；确认阶段预留 30% 时间及 baseline/candidate 对应 run slots。实际训练需要更大额度时升级给用户，不能把无意义的小实验包装成完成。该额度不限制 Codex 模型 token、不限制绕过脚本的进程，也不是研究耗时承诺。

**不是安全沙箱**：同一账户可改文件和声明 ID，hash/role prompt 不是敌对攻击下的防篡改/身份认证；worktree 只隔离 checkout。执行继承环境；敏感凭证应由宿主隔离。普通 POSIX 进程组清理不保证杀掉主动 detach 或外部调度的任务；不负责硬 GPU/RAM/磁盘限额。保留 Codex 宿主的 sandbox/approvals，有条件时使用隔离容器。本版未自动部署容器或 Slurm。

**不是常驻服务**：宿主/会话停止后没有 daemon 继续运行。状态文件支持再次调用时接续，不承诺自动重启/定时运行。

## 7. 交付与验收范围

包内包含标准 manifest、marketplace、入口 skill、四角色指令、合同模板、受控运行脚本、安装器、单元/集成 fixture 测试与宿主验收清单。本地结果见 [TEST_REPORT.md](../TEST_REPORT.md)。本环境没有 Codex 可执行程序及真实原生 subagent 工具，未执行宿主端到端测试，也未证明科研成功率。

使用者验收只看必要结果：真实 thread IDs 与证据路径、人工审查耗时、抽检漏错、总成本。若只有角色名和总结没有原生分派记录，这不算本插件要求的多智能体运行。
