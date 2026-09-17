# AutoResearch Team — 实验代码管理契约

版本：0.1.1。适用：项目中的 AutoResearch Team 任务及其原生子代理。
这是可直接使用的 `AGENTS.md` 正文，也由 `$auto-research` 入口显式加载。
已有项目指令不由本文件替换；出现影响目标、评估或授权的冲突，由 Owner 处理。
仅复制此文件提供指令约束；源码封存门禁需要本定制版 0.1.1 的 `repoctl.py` 与 `researchctl.py`。
缺少脚本时报告该能力缺口，不捏造命令已执行或退回无证据的自动研究。

## 1. 设计边界

沿用原设计：一个 Owner；Researcher / Engineer / Analyst / Verifier 四类按需子代理；
默认最多三个活跃子线程、两个候选写工作区、每任务一个受控评估进程。较低宿主上限优先。
不新增研究调度器，不把所有阶段改为并行，不自动 push、开 PR、合入用户主分支或删除用户工作。

以下是这套仓库规范选定的执行约束，不是对所有科研项目的普遍规定：

- 研究历史使用已有 `.autoresearch/<task>/nodes/`；不另建独立的 `experiments/`、`Hxxx` 数据库或手写 `BRANCHES.md`。
- **Task 固定评估问题，node 标识一次候选版本，branch 保存开发历史，worktree 提供执行目录，run 标识一次实际执行。**
- 两个假设可同时开发，但各自在 A/B 工作区；评估继续通过同一 `researchctl.py` 排队。
- 节点数可以增长，候选工作区数不随节点数增长。一个假设的实现迭代通过 `parent` 串联，不通过改写旧节点身份表示。
- `no_gain` 与 `inconclusive` 是保留的研究结果；低分不自动等于实现错误。

## 2. 唯一状态源与目录

```text
PROJECT/                         # 用户现有 checkout；不作为候选工作区
├── src/、configs/、tests/…       # 沿用原项目布局，不为套模板重构
└── .autoresearch/T001/           # 任务控制与证据；在候选目录之外
    ├── input/、brief.md、insights.md
    ├── protocol.json、protocol.lock.json
    ├── evaluator.py、data-and-dependencies.json
    ├── team.json                 # Owner 维护线程、工作区租约及调度状态
    ├── nodes/N001-shuffle.json   # Owner 维护假设、父节点、版本、状态及解释
    ├── snapshots/N001-shuffle/
    │   ├── manifest.json        # 协议/源码 hash、文件清单、Git 上下文
    │   └── source/              # tracked_paths 所声明的源码与配置实际字节
    ├── handoffs/、analysis/、reviews/
    ├── runs/<run-id>/           # 原脚本生成的记录、原始日志、独立输出
    └── decisions.md

AUTHORIZED_WORKTREE_ROOT/T001/  # 授权且尚未占用的位置；常取项目旁目录
├── baseline/                   # 固定基线，默认 detached worktree
├── A/                          # 固定路径；最多一个获租约的源码写入者
└── B/                          # 固定路径；最多一个获租约的源码写入者
```

`state.json` 保存阶段；`team.json` 保存当前调度；`nodes/` 保存研究决策；`runs/` 保存执行事实。
不要让子代理再维护另一份总表。`repoctl.py catalog` 从这些文件派生可读清单，显示假设、状态、
branch、workspace、作者、源码快照和实际 run IDs；该清单不是新的可编辑数据库。

`.autoresearch/` 默认被 Git 忽略，**不等于已备份**。结项交付包含任务记录、源码快照、
冻结 evaluator/manifest 和必要原始结果；大型数据、权重及环境镜像的外部位置和校验值另记。
不把密钥、私有凭证、整份环境变量或未经授权的数据写入快照、日志或远程存储。

## 3. 工作区与写入所有权

Owner 在冻结协议前创建 baseline/A/B 的实际目录，并登记精确绝对路径到 `allowed_workspaces`。
采用固定槽位是为了兼容原脚本的冻结 allowlist；后续新增 node 不临时添加新的执行路径。
一个只读 baseline 不计入“两个候选写工作区”。未使用的槽位可以留空闲状态。

Owner 是 `team.json`、节点决策字段和任务状态的单一写入者。每个槽位登记：
`slot`、`path`、`branch`、`node_id`、`writer_agent_id`、`lease_epoch`、`state`。
每次交接递增 `lease_epoch`；把租约和写入范围写进子代理 handoff。过期写入者停止写入并返回 Owner。
不要凭租约过期时间判断进程已死；先核对真实子线程和进程。

工作区生命周期为 `idle → editing → yielded → sealed → evaluating/verification → parked/released`。
Engineer 交出源码写入权后，Owner 才封存；正式运行及独立确认期间没有源码写入者。
另一个槽位可以继续开发。只读 Researcher/Analyst 优先读取已封存快照，避免读取修改一半的代码。
Verifier 接收已封存版本的评估权限，不接收修复候选实现的权限。

只有 Owner 管理 worktree 创建/回收、分支拓扑、租约转移、共享 Git 配置与 refs。
Engineer 可在自己的开发分支对授权文件作普通提交，但不自行 checkout/switch/rebase/reset/merge、
不操作其他工作区、不改全局/共享 Git 配置、不启动 Git 清理。提交时明确列出文件，避免 `git add .` 混入产物。
现有 hooks/签名/审批失败时返回 Owner，不通过禁用它们绕过。

**worktree 不是容器。** 各 worktree 的 HEAD/index 独立，但 refs 和通常的仓库配置共享。
`git worktree lock` 保护 worktree 管理信息，不是源码写入互斥锁。
虚拟环境、GPU、共享缓存、数据库和外部服务也不因 worktree 分开而隔离。
不可变数据可共享读取；可写缓存/编译输出/临时文件使用每槽位或每 run 的独立路径。
更改依赖时使用隔离环境，并遵守原有升级授权；不要修改另一候选正在使用的环境。

若宿主不能将原生子代理绑定至不同工作区，Owner 先安排其每次工具调用使用明确绝对路径和 cwd；
如果仍无法维持隔离，串行源码写入并记录能力限制。不要假定角色名称自动提供 OS 级隔离。
项目根以外的 worktree 不保证继承原 checkout 的未提交 `AGENTS.md`：handoff 显式给出适用指令路径，
并要求读取目标子目录已有指令；不依赖隐式继承。

## 4. 分支、节点与备选想法

先在 Researcher 交付或 `decisions.md` 的待办段记录尚未实施的想法。没有分配实施工作就不建分支。
进入实施时创建 node，填写 `hypothesis`、`parent`、`reference_nodes`、`operator`、
`author_agent_id`、`workspace`、`branch`、`status`、`reason`。
短 ID 便于引用，具体目的由 `hypothesis` 与 `reason` 表达，不依赖记住名字。

建议开发分支名 `art/<task>/<slot>-<purpose>`，例如 `art/T001/A-shuffle`。
同一路线的 N001、N003 可以依次在同一分支与槽位上开发；不是“一 node 一 branch”，
也不是“一 agent 永久占有一个 branch”。Engineer 更换不改变研究节点身份。

只有 seed 或预声明重复次数变化：同 node 的不同 run。
任何会改变方法的源码、配置或搜索超参数变化：新 node；旧 node 的源码绑定不覆盖。
仅更改状态、解释、`run_ids` 不改变候选版本。不要为了减少节点把多次改码跑分塞进同一 ID。

config-only 变体依然需要记录并封存配置，配置文件纳入 `tracked_paths`。
它可以复用现有分支，或在 Owner 准备的 detached worktree 中改变配置并用快照保存；
不强制为参数组合建分支，也不共享一份可修改的 `config.yaml`。
当前 runner 没有额外 `--config` 参数：通过冻结 evaluator 读取工作区约定的配置路径。
新增未声明的 CLI override 不属于冻结协议。

## 5. 源码与配置封存

新任务采用 `source_snapshot_policy: "required"`。Owner/Verifier 在冻结前审查 `tracked_paths`：
包含实际会影响运行的源码、入口脚本、配置、候选侧测试和依赖锁文件；排除日志、缓存、输出、
大型数据/权重、`.git` 和任务目录。不要用 `.` 代替明确声明。
冻结评估端的测试/helper 位于工作区外，并列入 `protected_files`，不从候选目录悄悄导入可改评测逻辑。
`tracked_paths` 是协议声明的路径范围，不是 `git ls-files`；范围内未提交/未跟踪的源文件同样会封存。

数据划分、checkpoint、依赖环境和硬件约束以实际项目的 manifest 固定。
配置继承在运行前解析并保存最终值；配置默认值来自源码时也纳入封存范围。
共享数据的 checksum 清单只记录身份，不证明数据存储不会改变；在适合的数据版本机制下核验。

在冻结之后、首个 run 之前，先为 `baseline` 创建节点并封存；其他候选同样处理：

```bash
# S = 实际已安装 skill 根；T = 现有任务的绝对路径。
# 由 Owner 执行；节点文件已填写，源码写入者已交出租约。
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node N001-shuffle
python3 "$S/scripts/researchctl.py" run --task-dir "$T" --node N001-shuffle \
  --workspace "$WORKTREE_A" --seed 0 --stage search --actor "$REAL_ENGINEER_THREAD_ID"
```

`seal` 保存实际文件字节及 mode，并把节点绑定到 `snapshots/<node>/source`。
运行器核对节点、协议、快照、当前工作区；运行前后核对源文件内容与 mode，并在 run 中记录快照 manifest hash。
`compare`/`finish` 再核验归档源码与证据；`finish` 还检查当前待交付版本。
不能仅凭 exit code、branch 名或一个无对应字节的 commit hash 宣称可复现。

`seal` 不执行 Git commit，不收集未声明文件，不解析完整依赖，也不把执行目录变成只读。
runner 仍从注册工作区执行，不是从不可写镜像执行；前后比对无法识别共享账号恶意的“改后还原”。
不可变封存是合作式契约加本地完整性检查，不是敌对防篡改保证。

封存后的节点绑定与 `snapshots/<node>/` 不重写；修改实现时创建子节点。
`run_ids` 可由 Owner 更新，但实际执行记录以 `runs/*/record.json` 为准。
快照复制会消耗磁盘；`tracked_paths` 只放足以重建候选的轻量源文件。

## 6. 两个假设如何比较与组合

算法分叉 A/B 从同一明确 baseline commit 或完整基线快照开始，使用同一冻结协议。
冻结之后不自动追随 main，不为“保持最新”rebase 活跃候选。
迁入另一分支的代码、融合两个方案或工程模块集成，形成新的 node，并记录精确 parent/reference_nodes。
父节点的分数及 verifier approval 不转移给组合版本。

普通候选源码修改在原协议覆盖时可产生新 node；改变评价含义、数据划分、baseline、
共同依赖环境或其他冻结比较条件时创建 linked task，重新建立 baseline。
发现评测缺陷时先记录影响并停止使用受影响证据，不在旧任务原地换 evaluator。
不把全部工具函数都认定为 infra：只有改变冻结对照条件的变更才需要重开任务。

工程任务优先按依赖图拆模块，不为了占满 A/B 写两个同义方案。
跨模块接口由 Owner 先固定；组合在任务拥有的集成分支/槽位中完成并验证。
集成也计入最多两个候选槽位；先释放一个，再集成，而非悄悄新增第三个写工作区。
用户主分支仍不自动修改。

开发并发不等于测量并发。每任务的 managed run 使用原有单锁；BUSY 就排队，不绕过脚本另跑正式实验。
廉价本地语法/单测可在授权内先运行，但训练、正式计分或消耗受控实验预算的检查仍走 runner。
延迟/吞吐 benchmark 期间避免另一个 agent 的高负载编译/测试争用同一资源。
跨任务 GPU/CPU 配额由 Owner 或已授权调度器协调，当前单任务锁不提供跨任务隔离。

## 7. 结果保留、工作区复用与交付

复用槽位的顺序：停止并核对原写入者/相关进程 → 保留所有已评估 node 的快照和原始结果 →
检查未提交、未跟踪、被忽略的用户/研究文件 → 更新 `team.json` 租约 → 准备新版本 → 新 node。
旧节点 `workspace` 保留历史执行路径，不为指向新位置而修改旧 run。
需要恢复旧候选确认时，在其原注册槽位重建准确版本，核验 `repoctl check --live` 后运行。
无法安全恢复到冻结路径时，创建 linked task 重跑；不编辑已有 allowlist 或 run 路径蒙混恢复。

负结果至少保留：假设与反证条件、源码/配置快照、协议、run IDs、原始输出、判定理由和局限。
节点可标记 `dropped`，分支不急于删。仅在已有授权且写入者和进程均结束、所有有价值文件已归档、
恢复核验通过后，Owner 才回收任务专属工作区/分支。`git branch -d` 拒绝未合并分支时不改用 `-D` 硬删。
不把“记下 commit hash”当作删除未合并分支的充分条件；需要保存源码快照，若要保留 Git 历史还需稳定 ref 或 bundle。
大文件外部对象、submodule 与 LFS payload 不因 Git bundle 存在就自动得到备份。

任务结项与代码合入是两个决定。交付保留已验证源码快照、关联 commit（有则记）、配置、原始证据、
结论范围及复现命令。后续整理/移植若改变受测实现，则作为新版本重新验证，不复用原批准。
本包不自动清理、不自动上传备份，也不自动把研究档案提交进用户主分支。

## 8. 中断、恢复与冲突

恢复先读 `state.json`、`team.json`、节点、protocol lock 和 run records，再查实际 Git worktrees、
真实 native thread IDs、工作区修改与进程组。聊天摘要、旧租约或过期 PID 不单独构成存活证明。
不在不确定上个作业是否结束时重新运行。原 `researchctl recover` 的显式核查要求保持不变。

`repoctl seal` 使用任务锁和临时快照目录，但快照目录与 node 更新不是跨文件事务。
发现 `snapshots/.incomplete-*` 或已有 snapshot 而 node 尚未绑定时，保留现场；Owner 对比 manifest、
协议、文件字节和原工作区，记录恢复决定。不覆盖已有快照，不通过手改 hash 让未知版本通过。
确定快照完整且归属无误后才补齐该 node 的绑定字段；有歧义则保留旧现场并创建新 node。

已有 0.1.0 冻结任务不原地升级协议。可继续按原口径接续，或创建带 `source_snapshot_policy: required`
的 linked task 重跑。省略该字段时执行器保留 legacy 行为，不声称旧任务已自动具备封存门禁。

## 9. 已实现与仍依赖角色遵从的边界

已实现的 required-profile 检查：未封存/错节点/工作区内容不符拒跑；节点快照不覆盖；原始快照损坏拒用；
运行前后源码与 mode 检查；固定基线、协议及 allowlist；单任务运行锁与原预算；独立声明 ID 的确认门禁。
`repoctl catalog` 是派生视图，`repoctl check` 是只读完整性核查。

仍由 Owner/原生宿主落实：真实身份与源码写权限、最多两个候选、租约交接、Git 操作范围、依赖闭包完整性、
资源干扰控制、研究结论有效性、归档备份及真正的子代理创建/回收。
本包不检测全部外部导入、数据变化或恶意写入；同账户不能靠 prompt/hash 变成安全隔离环境。

## 10. 核对依据

此规范以随包的原 0.1.0 `docs/DESIGN.md`、Owner skill、contracts、workflow 与 researchctl 接口为基础；
固定槽位、节点封存和派生目录是 0.1.1 的工程选择，不声称原设计已经实现这些功能。
Git 行为参照官方 `git-worktree`、`git-bundle`、`git-gc` 文档；工作区隔离不等于权限隔离。
官方链接及本次核对范围见包内 `docs/REPOSITORY-MANAGEMENT.md`，本地验证范围见 `TEST_REPORT.md`。
