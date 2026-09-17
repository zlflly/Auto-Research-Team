# AutoResearch Team

**一个 Owner，四类按需子代理，一个受控实验执行器。**

面向真实项目里的工程实现与算法研究：你给目标和可选 insight，主线程作为 Owner 组织宿主的真实原生子代理
完成方案、实现与实验，独立验证后交一张结项卡。日常迭代不找人搬砖，只在结项或真正需要你决定时汇报。

- 不是自动科研平台，也不是论文生成器：它不预知你的研究问题，任务 evaluator 由 Owner/Verifier 按你的现有测试建立。
- 不是 API 编排 harness：不引入额外模型凭证、MCP 服务、外部遥测或后台守护进程。
- 不是角色扮演：子代理必须是宿主真实创建的线程，`team.json` 里要能查到真实 thread ID。

本仓库是 **0.1.1 仓库管理定制版**：在 0.1.0 的团队模型之上，补了一层"实验代码到底怎么管"的执行契约。

## 三件事，先说结论

1. **文件管理和版本控制**：`nodes/` 管研究历史，branch 管开发历史，worktree 只提供执行目录，
   正式跑之前把源码按字节封存成不可覆盖的快照。节点数可以一直涨，候选工作区始终是固定的 baseline/A/B 三个槽位。
2. **专做 auto + research + subagent 这件事**：自主性只在你授权的范围内；研究口径先冻结再跑，
   baseline 和候选用同一套协议；子代理按事件创建、用完关闭，不常驻、不递归。
3. **没有常驻 agent，也没有 memory agent**：团队记忆落在磁盘上的任务目录里，不在任何活着的进程里。

---

## 一、文件管理与版本控制：node + worktree

研究代码最容易烂在三件事上：分支多到忘记用途、多个 agent 同时改动同一份代码、以及"这个分数到底是哪版代码跑出来的"。
这一层的做法是**不新增一套实验数据库**，用已有的 `.autoresearch/<task>/nodes/` 承载研究历史，
再补上固定工作区槽位、单写入租约和不覆盖的源码封存。

### 五层分工

| 概念 | 回答的问题 | 存在哪 |
|---|---|---|
| **Task** | 我们在评估什么问题 | `.autoresearch/T001/` 的协议与 brief |
| **node** | 这是哪一版候选（假设是什么、父节点是谁） | `nodes/N001-shuffle.json` |
| **branch** | 这条路线怎么开发的 | `art/T001/A-shuffle` 这类开发分支 |
| **worktree** | 代码从哪个目录执行 | 授权的 baseline / A / B 三槽位 |
| **run** | 这一次实际怎么跑的 | `runs/<run-id>/record.json` |

一句话：**Task 固定评估问题，node 标识一次候选版本，branch 保存开发历史，worktree 提供执行目录，run 标识一次实际执行。**

### 目录长什么样

```text
PROJECT/                          # 你现有的 checkout，不作为候选工作区
├── src/、configs/、tests/…        # 沿用原项目布局，不为套模板重构
└── .autoresearch/T001/            # 任务控制与证据，在候选目录之外
    ├── input/、brief.md、insights.md
    ├── protocol.json、protocol.lock.json
    ├── evaluator.py、data-and-dependencies.json
    ├── team.json                  # Owner 维护线程、工作区租约与调度状态
    ├── nodes/N001-shuffle.json    # Owner 维护假设、父节点、版本、状态与解释
    ├── snapshots/N001-shuffle/
    │   ├── manifest.json          # 协议/源码 hash、文件清单、Git 上下文
    │   └── source/                # tracked_paths 声明的源码与配置的实际字节
    ├── handoffs/、analysis/、reviews/
    ├── runs/<run-id>/             # 运行记录、原始日志、独立输出
    └── decisions.md

授权工作区根/T001/
├── baseline/                      # 固定基线，默认 detached worktree
├── A/                             # 固定路径；最多一个拿到租约的源码写入者
└── B/                             # 固定路径；最多一个拿到租约的源码写入者
```

`state.json` 保存阶段，`team.json` 保存当前调度，`nodes/` 保存研究决策，`runs/` 保存执行事实。
**不要再让子代理维护第二份总表。** `repoctl.py catalog` 从这些既有文件派生一份可读清单
（假设、状态、branch、workspace、作者、源码快照、真实 run IDs），它是只读视图，不是新的可编辑数据库。

### 三个设计选择，以及各自的代价

| 问题 | 这一版的选择 | 代价 / 不保证 |
|---|---|---|
| 分支多、忘记用途 | 用途写在 node 的 `hypothesis`/`reason` 里，`repoctl catalog` 派生视图 | Owner 仍要写清 reason；脚本不会替你做研究判断 |
| 多代理同时写代码 | 冻结前就建好 baseline/A/B 三个固定路径，每槽位单写入者；node 可增长 | 槽位复用需要交接；worktree 不隔离 GPU、环境和共享 Git 配置 |
| 旧代码与旧结果失联 | 每个正式运行的节点先按字节保存 `tracked_paths`，新版运行器核对封存绑定 | 源码清单完整性仍需人工审计；快照占磁盘，不自动保存数据和完整环境 |

### 节点不覆盖，源码要封存

- **改代码就是新节点。** 任何会改变方法的源码、配置或搜索超参数变化都创建新 node，旧节点的源码绑定不重写。
  只有 seed / 预声明重复次数变化，才算同一个 node 的多个 run。
- **跑之前先 `seal`。** `repoctl.py seal` 把声明路径里的实际文件字节和文件 mode 复制进 `snapshots/<node>/source/`，
  写 manifest，再把节点绑定到它。`source_snapshot_policy: "required"`（新任务默认）会在这些情况下直接拒跑：
  未封存、节点与工作区不符、快照或 manifest 损坏、运行前后源码或文件 mode 变化。
- **封存后不追随 main。** 冻结之后不为了"保持最新"rebase 活跃候选。改变评测含义、数据划分、baseline
  或共同依赖环境时，创建 linked task 重新建立 baseline，而不是在原地换口径。
- **槽位复用不擦除证据。** A 槽位可以接着开发下一个节点，但旧节点的 `workspace` 保留历史执行路径，
  旧快照和 run 记录不动；`repoctl check` 在槽位被复用后仍能核验旧源码，`--live` 才额外检查历史工作区。

### 写入所有权与租约

Owner 是 `team.json`、节点决策字段和任务状态的唯一写入者。每个槽位登记
`slot` / `path` / `branch` / `node_id` / `writer_agent_id` / `lease_epoch` / `state`，
生命周期是 `idle → editing → yielded → sealed → evaluating/verification → parked/released`。

Engineer 交出写租约之后 Owner 才封存；正式运行和独立确认期间**没有**源码写入者。只有 Owner 管理
worktree 的创建回收、分支拓扑、租约转移和共享 Git 配置；Engineer 不自行 `checkout/switch/rebase/reset/merge`。
只读的 Researcher/Analyst 优先读已封存的快照，避免读到改了一半的代码。

### 明说边界：worktree 不是容器

各 worktree 的 HEAD/index 独立，但 refs 和通常的仓库配置是共享的；`git worktree lock` 保护的是
worktree 管理信息，不是源码互斥锁。虚拟环境、GPU、共享缓存和外部服务也不会因为 worktree 分开而隔离。
同样地，源码封存是**合作式契约加本地完整性检查**：它拦的是常见错误，不是同一账户下的恶意篡改，
也不等于防篡改认证。快照保存的是声明范围内的源文件，不是 Git 完整历史备份——要留历史得另建稳定 ref 或 bundle。

细节与命令示例见 [仓库管理说明](docs/REPOSITORY-MANAGEMENT.md) 和
[执行契约](plugins/auto-research-team/skills/auto-research/references/repository-policy.md)、
[并发开发示例](plugins/auto-research-team/skills/auto-research/references/repository-examples.md)。

---

## 二、为什么专门做 auto + research + subagent

通用 agent 框架解决的是"怎么调度多个模型"，这里要解决的是"怎么在一个真实仓库里把一次研究做完并且可信"。
三件事各自的落点：

### auto：自主，但只在授权范围内

- Owner 接管任务直到终态、显式暂停，或碰到实质决策/权限边界；**不会**在每轮迭代后问你"要继续吗"。
- 只在这些情况汇报：任务到达终态（含负结果）、需要范围/口径/预算/数据访问/破坏性操作/对外发布决策、
  预算耗尽、两轮返修后验证仍有争议、宿主能力缺失，或你主动问状态。
- 内部计划、实验、返修和团队消息留在任务文件里，不逐条搬给你；宿主自己的工具/权限弹窗不受控制。
- 没有守护进程：宿主或会话停了，任务就停。状态文件支持你之后显式恢复，不承诺自动重启或定时运行。
- 买云算力、升级依赖、push、开 PR、合入你的主分支、删除你的工作——都需要对得上的授权。

### research：先把口径冻结，再谈分数

主循环是
`intake → 契约/evaluator → baseline → 候选搜索 → 分析 → 独立验证 → completed | no_gain | inconclusive | blocked`。

- 冻结 evaluator、数据 manifest、指标方向和预算，**然后**才跑 baseline；baseline 和候选必须同一套协议。
- 便宜的确定性输出用来筛选，Analyst 负责解释，Verifier 负责结论验收——三件事不混。
- `no_gain` 和 `inconclusive` 是保留的正当结果。低分不等于实现有 bug，一轮好分数也不等于结论。
- 候选结论由**独立的真实 Verifier 线程**对 baseline 和候选按同一预声明 confirmation 协议重跑，
  并检查一个有意义反例或替代解释；批准绑定到确切源码 hash，集成后的版本要重新验证，不继承分支级批准。
- benchmark 通过不是正确性证明，也不是新颖性证据。这个包不实现 MCGS/MAP-Elites，只是一套有界的 beam/tree 策略。
- 默认 pilot 额度是 12 次受控评估、每次至多 300 秒、总计 1800 秒，其中 30% 预留给确认。
  真需要更大额度时，正确做法是报给你决定，而不是拿一个没有意义的迷你实验冒充完成。

### subagent：真实原生线程，按需创建，不是人格列表

- 主线程永远是 Owner。默认上限是**最多 3 个同时打开的子线程、2 个候选写工作区、每任务 1 个受控评估进程**；
  关掉完成的线程才能补新的，子代理不再创建子代理。
- 四类角色按事件触发，而不是轮流发言：

  | 角色 | 何时创建 | 交付 |
  |---|---|---|
  | Researcher | 初始方案、分支停滞 | 少量可证伪的候选方案，含反证条件 |
  | Engineer | 每个活跃候选工作区一个 | 实现、源码快照、run IDs、失败原因 |
  | Analyst | 一批结果之后、停滞或异常 | 可比性、噪声/混淆、分支决策建议 |
  | Verifier | 冻结协议前、形成结论后、高风险变更时 | 独立重跑、反例、最终 review |

- 角色文件是**分派时显式读取的职责契约，不是宿主自动注册的自定义 agent**。
  插件元数据字段不会创建 agent 池；`agents/openai.yaml` 只是调用与展示元数据。
- 宿主没有原生子代理能力时，这是能力阻塞：保存已做的 intake 并如实报告，
  **不用几个带角色标签的段落假装跑了一支团队**。

---

## 三、没有常驻 agent，也没有 memory agent：上下文怎么管

这套设计里没有常驻 Reporter、Memory、Runner，也没有辩论委员会。原话是：
**报告由 Owner 写，命令由脚本跑，记忆由记录承担。**（见 [workflow.md](plugins/auto-research-team/skills/auto-research/references/workflow.md)）

具体做法有五条：

**1. 记忆落盘，而不是留在上下文里。**
任何值得记住的东西都写进 `.autoresearch/<task>/`：阶段在 `state.json`，调度和租约在 `team.json`，
研究决策在 `nodes/`，执行事实在 `runs/`，判断在 `decisions.md` 和 `analysis/`、`reviews/`。
任务不依赖某个 agent 一直活着，也不依赖谁"记得"。

**2. 指令按需加载，不是一次性灌进上下文。**
`SKILL.md` 是路由器：入口只加载 workflow、runtime adapter、contracts 和 repository policy；
每次分派前只读**那一个**角色文件；具体命令示例只在需要时读。
主线程的上下文里装的是指针和紧凑结论，不是整个代码库和全部日志。

**3. 子代理拿到的是自包含 handoff 包，不是共享的不断增长的历史。**
每个子线程收到一份紧凑包：角色、要读的角色文件、任务目录、brief、节点或阶段、精确的 workspace 与 cwd、
源码绑定、租约、适用的项目指令路径、输入、单一使命、可写范围、评估权限、不可更改项、返回要求。
子代理回的是判定、产物路径、run IDs 和阻塞点，不是叙事。这也让上下文可以在需要时是干净的：
宿主支持就开一个新的验证上下文；宿主会继承历史时，不假称验证是"盲"的。

**4. 子线程用完就关，"团队"以文件形式存在。**
最多 3 个同时打开的线程，关掉之后才能补新的；真实 thread ID 记进 `team.json`。
线程是临时的，`team.json` 加 `nodes/` 才是持久的组织形态。

**5. 汇报节流既是体验选择，也是上下文预算选择。**
迭代不逐条汇报，常规计划、实验、返修、团队消息留在任务文件里。
恢复时也不靠"我记得"：先读 `state.json`、`team.json`、protocol lock、节点和 run records，
再核对真实 Git worktree、真实原生线程 ID、工作区改动和进程组；
聊天摘要、过期租约或过期 PID **不单独构成存活证明**，不确定上一个作业是否结束时不会重跑。

### 这套办法的代价

诚实列出来，因为它们是真的：

- **没有跨任务学习。** T001 的经验不会自动进入 T002；每个任务从文件开始。想复用就得自己把它写进 brief 或项目指令。
- **没有后台连续性。** 没有 daemon，宿主停下就停下。恢复要靠显式调用，且依赖状态写得足够好。
- **重建成本转嫁给了纪律。** 没写下来的决定就等于没有；取消 memory agent 的代价是 Owner 必须写 checkpoint
  （每批之后、阶段变化时、交还控制权之前）。
- **隔离程度取决于宿主。** 角色文件里的"只读"是指令边界，不是操作系统级只读沙箱；真需要隔离要宿主或容器提供。
- **为什么不干脆做个 memory agent：** 它需要自己的上下文、自己的过期策略和自己的可信度说辞；
  磁盘上的文件可以被审计、被 diff、被人工检查，一个活着的记忆进程不行。

---

## 安装

需要有原生子代理和本地 shell 的 Codex；辅助脚本要 Python 3.11+；
受控实验执行需要 Linux/macOS/WSL 的进程组和文件锁。

```bash
# 在包根目录执行，目标是你的研究项目（第一行只显示计划，不写文件）
python3 tools/install.py --repo /absolute/path/to/research-project
python3 tools/install.py --repo /absolute/path/to/research-project --apply
```

不支持插件分发的客户端可以只装同一工作流的 standalone skill：

```bash
python3 tools/install.py --repo /absolute/path/to/research-project --skill-only --apply
```

安装器保留你已有的 marketplace 名和配置文本，并拒绝覆盖内容不同的已装版本；
它**不会**修改或覆盖你项目里已有的 `AGENTS.md`。完整步骤、调用方式与旧任务处理见
[安装与调用](docs/INSTALL.md)。

## 使用

```text
$auto-research
目标：改进当前项目的算法实现，并验证相对现有 baseline 的收益。
Insight：读取 docs/insight.md；我还怀疑瓶颈在……
约束：保留 API 和数据划分；使用现有本地资源；不要自动 push。
```

之后可以直接补新 insight、问状态、暂停，或用同一条入口要求恢复 `.autoresearch/T001`。
不需要你指定哪个子角色——Owner 按阶段决定。

## 这个仓库里有什么

```text
README.md            本文件
CHANGELOG.md         0.1.1 相对 0.1.0 的改动
docs/                DESIGN（0.1.0 原始设计）、INSTALL、ACCEPTANCE、REPOSITORY-MANAGEMENT
plugins/auto-research-team/
                     plugin.json、SKILL.md、四角色指令、模板、repoctl.py、researchctl.py
tests/               90 个本地测试，含源码封存与并发 worktree fixture
tools/install.py     安装器
SOURCES.md           设计核对过的官方文档与仓库
TEST_REPORT.md       本地测试范围与未验证项
SHA256SUMS           包内文件校验和
```

## 验证状态与不保证

`python3 -m unittest discover -s tests -v` 覆盖安装器、受控运行器、新增源码封存/证据绑定/worktree
fixture 和包完整性；本地 fixture 里包含真实 Git worktree 与两个并发写入者，
核对原 checkout 的文件、HEAD 和分支没有被改动。测试使用微型本地输出，**不是**算法 benchmark。

明确未验证：真实 Codex 客户端的安装可发现性、原生子代理创建与 cwd 绑定、租约遵从、
跨回合接续，以及任何科研成功率、人工审查耗时或漏错率改善。宿主验收清单见
[宿主验收](docs/ACCEPTANCE.md)，本地范围见 [测试记录](TEST_REPORT.md)。

这个包不是安全沙箱、不是常驻服务、不是通用 AutoML 平台。同账户的恶意进程可以绕过
hash 和声明 ID 检查；普通 POSIX 进程组清理不保证杀掉主动 detach 的任务；
GPU、RAM、磁盘和 model token 的硬限额不在它手里。内部角色一致、脚本退出码为 0、
JSON 格式正确，都不是科研结论。

## 来源

设计与机制核对过的官方文档、开源仓库和论文（含明确标注的取用与不取用范围）见
[SOURCES.md](SOURCES.md) 和 [原始设计](docs/DESIGN.md)。
包内工作流与代码为本任务原创，未复制第三方 agent 源代码。

## 变更

见 [CHANGELOG.md](CHANGELOG.md)。0.1.1 是叠加在 0.1.0 上的仓库管理增量：
旧冻结任务保留 legacy 行为，不会因为更新插件文件而被宣称拥有新的封存门禁。

## License

[MIT](LICENSE)
