# AutoResearch Team

AutoResearch Team 是一套面向 **自动科研（Auto Research）+ 原生 Subagent** 的研究执行框架。

它不是一个长期运行的多 Agent 聊天系统，也不是额外的模型 API harness。它主要解决三个问题：

1. **实验代码如何版本化**：用 Node 表示“真正接受实验评估的候选版本”，用 Git Worktree 隔离并发开发目录；branch 只保留开发历史，不承担实验身份。
2. **Auto Research + Subagent 如何并发而不互相污染**：一个 Owner 调度按需创建的 Researcher / Engineer / Analyst / Verifier；多个候选可以并行开发，但正式实验由统一 evaluator 控制。
3. **没有常驻 Memory Agent 时如何管理上下文**：上下文不依赖某个 Agent 长期记忆，而是持续压缩成 task state、node、handoff、run、analysis、review 和 decision 等持久化研究状态。

## Node + Worktree：实验版本与开发环境分离

我们区分五个对象：

```text
Task       = 一个固定研究问题与评价口径
Node       = 一个具体、不可覆盖的候选版本
Branch     = 开发该候选时使用的 Git 历史
Worktree   = 某个 Engineer 当前实际写代码的隔离目录
Run        = 某个 Node 的一次真实实验执行
```

因此：

```text
Branch / Worktree
       │
       │ 开发
       ▼
      Node
       │
       │ seal
       ▼
   Snapshot
       │
       │ run
       ▼
      Run(s)
       │
       ▼
    Evidence
```

**Branch 不是实验身份，Worktree 也不是版本身份。Node 才是研究版本。**

只更换 seed 时，可以继续属于同一个 Node：

```text
N003
 ├── run seed=0
 ├── run seed=1
 └── run seed=2
```

如果代码、配置或算法行为发生改变，则创建新的 Node：

```text
N003
  │
  └── N007
```

旧 Node 不被覆盖。

这样某个实验结果永远可以回答：

> 它到底对应哪一个版本的代码？

## Worktree：让多个 Subagent 可以同时写代码

如果两个 Engineer 共用同一个 checkout：

```text
Engineer A: git checkout candidate-A
Engineer B: git checkout candidate-B
```

第二个 Agent 会直接改变第一个 Agent 的工作目录状态。

因此一个任务准备固定候选工作区：

```text
WORKTREES/T001/
├── baseline/
├── A/
└── B/
```

例如：

```text
Engineer A
  workspace = A
  branch    = art/T001/A-uncertainty

Engineer B
  workspace = B
  branch    = art/T001/B-timestep
```

两个 Engineer 可以同时开发，因为它们拥有不同的 checkout、HEAD 和 index。

但 Worktree 不是容器，它不会自动隔离 GPU、Python environment、cache、checkpoint、数据库或外部服务。因此当前设计采用：

```text
代码开发：可以并行
正式实验：统一受控
```

一个 active workspace 同时只有一个源码写入者；正式 benchmark 通过统一 runner 执行，避免两个候选因为 GPU contention、cache interference 等因素失去可比性。

## Auto Research + Subagent，而不是常驻 Agent 集群

AutoResearch Team 的结构是：

```text
                       Owner
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   Researcher        Engineer         Analyst
                         │
                      Verifier
```

但这些角色不是长期存在的进程。

典型流程是：

```text
用户目标
   ↓
Owner 建立 Task / Protocol
   ↓
Researcher       # 需要提出或修正假设时创建
   ↓
Engineer A / B   # 有候选需要实现时创建
   ↓
Runner           # 固定实验执行，不是 Agent
   ↓
Analyst          # 一批结果产生后调用
   ↓
Verifier         # 协议冻结或准备形成 claim 时调用
   ↓
Owner 结项
```

所以这里的 Agent 更接近：

> **按研究事件创建的执行角色。**

而不是长期在线维护自身状态的虚拟团队成员。

## 我们没有 Memory Agent

AutoResearch Team 不设置一个长期运行的 Memory Agent。

因为对于 Auto Research，真正需要永久保存的不是“某个 Agent 记得什么”，而是：

```text
研究问题
版本关系
实验协议
运行事实
分析结果
关键决策
证据入口
```

这些内容全部显式落盘：

```text
.autoresearch/T001/
├── brief.md
├── insights.md
├── protocol.json
├── state.json
├── team.json
├── nodes/
├── snapshots/
├── handoffs/
├── runs/
├── analysis/
├── reviews/
└── decisions.md
```

不同文件承担不同类型的上下文：

| 内容                              | 持久化位置           |
| ------------------------------- | --------------- |
| 用户目标、范围、约束                      | `brief.md`      |
| 用户 insight                      | `insights.md`   |
| 实验评价口径                          | `protocol.json` |
| 当前研究阶段                          | `state.json`    |
| 当前 subagent / workspace 状态      | `team.json`     |
| hypothesis、parent、status、reason | `nodes/`        |
| Agent 间必要交接                     | `handoffs/`     |
| 原始实验执行事实                        | `runs/`         |
| 结果解释                            | `analysis/`     |
| 独立确认                            | `reviews/`      |
| Owner 的关键研究决策                   | `decisions.md`  |

因此：

```text
Agent 可以结束
Thread 可以被回收
Conversation 可以被压缩

但 Research State 不能只存在于上下文窗口里
```

新 Agent 接手时，也不需要重新读取整个历史对话。

它只读取当前职责需要的最小上下文：

```text
Engineer:
brief + protocol + assigned node + handoff + workspace

Analyst:
protocol + relevant nodes + raw runs

Verifier:
protocol + sealed snapshot + confirmation evidence

Owner:
state + team + node graph + decisions + evidence index
```

这就是 AutoResearch Team 的上下文管理策略：

> **把长期聊天历史持续压缩成结构化 Research State，而不是依赖一个 Agent 长期记住整个项目。**

## 一个完整例子

假设研究问题是：

> adaptive sampler 的收益来自 uncertainty signal，还是 timestep redistribution？

Owner 创建 Task：

```text
T001
```

Researcher 提出两个候选：

```text
N001
hypothesis = uncertainty information is causal
workspace  = A

N002
hypothesis = timestep redistribution explains the gain
workspace  = B
```

两个 Engineer 同时开发：

```text
worktree A                 worktree B
    │                          │
Engineer A                 Engineer B
    │                          │
N001 implementation       N002 implementation
```

完成后分别形成不可覆盖的实验版本：

```text
N001 → snapshot S001
N002 → snapshot S002
```

正式 runner 再执行：

```text
R001 = N001, seed 0
R002 = N002, seed 0
R003 = baseline, seed 0
```

如果 N001 后续需要修改，则：

```text
N001
  │
  └── N003
```

N001 对应的源码、Run 和实验结论保持不变。

最终我们得到的不是一堆难以理解的 branch，而是一张研究 lineage：

```text
N000 baseline
├── N001 uncertainty-v1
│      └── N003 uncertainty-v2
└── N002 timestep-control
```

Branch 可以清理，Worktree 可以复用，Agent 可以销毁。

Node、Snapshot、Run、Decision 和 E
