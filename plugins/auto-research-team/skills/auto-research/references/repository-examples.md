# 示例：同一任务内同时验证两个假设

这些是仓库操作例子，不是已观察到的算法结果；命令中的路径、配置开关和真实 thread IDs 由 Owner 根据项目填写。
不要为了照抄示例而更改现有公共接口。S 始终取实际已安装的 skill 根，而非猜测插件缓存位置。

## A. 创建一次任务，预留三个稳定执行路径

假设项目已有一个采样器和可运行 evaluator，待验证两个不同问题：

- A：打乱 uncertainty 信号后是否仍有收益；需要修改一小段方法实现。
- B：不用 uncertainty、只改时间步分配是否有效；假设现有实现已有配置开关。

这里保留原设计：Engineer A 与 Engineer B 可同时写各自目录；正式评估一次只跑一个。
Owner 不在用户 checkout 中切换分支。原生子线程创建与真实 ID 记录仍走原 skill 的宿主接口，以下 shell 不创建代理。

```bash
# 下列位置均为 Owner 已核对/获授权的实际路径。
PROJECT=/absolute/path/to/project
S=/absolute/path/to/installed/auto-research
TASK_ID=T001
T="$PROJECT/.autoresearch/$TASK_ID"
WROOT=/absolute/authorized/worktrees/T001

# 原项目可有无关未提交修改；先核对它们是否属于待研究基线。
# 本例选用 HEAD 的已提交内容，不自动纳入用户未提交改动。
git -C "$PROJECT" status --short
BASE=$(git -C "$PROJECT" rev-parse --verify HEAD)

python3 "$S/scripts/researchctl.py" init --root "$PROJECT" --task "$TASK_ID" \
  --goal-file /absolute/path/to/request.md
mkdir -p "$WROOT"
git -C "$PROJECT" worktree add --detach "$WROOT/baseline" "$BASE"
git -C "$PROJECT" worktree add -b art/T001/A-shuffle "$WROOT/A" "$BASE"
git -C "$PROJECT" worktree add --detach "$WROOT/B" "$BASE"
```

若基线要包含未提交的用户变更，由 Owner 在独立授权目录保存完整源字节及来源 manifest，
不自动 stash/commit/reset 用户 checkout。该方式可以没有 Git branch，`seal` 仍以实际源文件为准。
worktree/branch 路径已存在时命令应失败，先核对归属；不要用 `-B`/`--force` 覆盖。

B 是 config-only，所以使用 detached worktree；没有给它新建分支，但仍拥有自己的配置副本和源码快照。
更偏好统一分支操作的项目，也可为 B 分配一个任务分支。这是实现选择，不改变 node/run 规则。

## B. 冻结协议，登记节点与工作区租约

Owner 基于项目生成 evaluator，Verifier 检查后，protocol 至少包含以下新增/相关字段。
这只是字段片段，不是可直接 freeze 的完整协议；完整必填项见 `assets/protocol.template.json`。

```json
{
  "source_snapshot_policy": "required",
  "allowed_workspaces": [
    "/absolute/authorized/worktrees/T001/baseline",
    "/absolute/authorized/worktrees/T001/A",
    "/absolute/authorized/worktrees/T001/B"
  ],
  "baseline_workspace": "/absolute/authorized/worktrees/T001/baseline",
  "tracked_paths": ["src", "configs", "scripts", "pyproject.toml", "requirements.lock"],
  "protected_files": [
    "/absolute/path/to/project/.autoresearch/T001/evaluator.py",
    "/absolute/path/to/project/.autoresearch/T001/data-and-dependencies.json"
  ]
}
```

以上文件需真实存在；项目用其他入口或 lock 格式就按实际声明。不要添加不存在的示例路径。
`configs/experiment.json` 是本例 evaluator 的约定读取位置；A/B 各写自己的副本。
解析后的配置保存到 run output 作为证据，同时确保其输入配置及解析逻辑位于已封存范围。

Owner 写 `team.json` 的 `workspaces`，例如下面的单个条目；真实 thread ID 来自 native dispatch，
不是通过改一个字符串制造角色独立性：

```json
{
  "slot": "A",
  "path": "/absolute/authorized/worktrees/T001/A",
  "branch": "art/T001/A-shuffle",
  "node_id": "N001-shuffle",
  "writer_agent_id": "REPLACE_WITH_ACTUAL_NATIVE_THREAD_ID",
  "lease_epoch": 1,
  "state": "editing"
}
```

节点元数据继续使用原实体，只补充执行位置与封存绑定字段：

```json
{
  "id": "N001-shuffle",
  "parent": "baseline",
  "reference_nodes": [],
  "hypothesis": "打乱 uncertainty 后收益是否保留，用以检验收益对该信息的依赖",
  "operator": "draft",
  "author_agent_id": "REPLACE_WITH_ACTUAL_NATIVE_THREAD_ID",
  "workspace": "/absolute/authorized/worktrees/T001/A",
  "slot": "A",
  "branch": "art/T001/A-shuffle",
  "source_commit_or_snapshot": null,
  "source_hash": null,
  "snapshot_manifest_sha256": null,
  "run_ids": [],
  "status": "implementing",
  "reason": "与固定 baseline 对照；判定边界以已冻结协议为准"
}
```

`nodes/baseline.json` 同样存在，`parent: null`、`workspace` 指向 baseline，
其 `hypothesis` 可写“本任务原始方法对照”。N002-schedule 的父节点也为 baseline，branch 为 null。
Owner 在 handoff 中明确代码目录、可写文件、指令文件、租约，以及当前还没有正式计分权限。

```bash
python3 "$S/scripts/researchctl.py" freeze --task-dir "$T" --protocol "$T/protocol.json"
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node baseline
```

在 baseline 尚未形成可信结果前，候选可以做授权的独立实现准备，但不要将其分数用于结论或跳过 baseline。
如初始协议审查发现缺陷，在 freeze 前修复，而非用两个不同版本的评测比较候选。

## C. 并发开发、串行运行

A/B 的 Engineer 分别改自己的源码/配置；两者不对同一个工作区执行 checkout。
源码就绪后各自把写租约交还 Owner；Owner 更新 `team.json`，逐个封存再授权运行：

```bash
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node N001-shuffle
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node N002-schedule

python3 "$S/scripts/researchctl.py" run --task-dir "$T" --node baseline \
  --workspace "$WROOT/baseline" --seed 0 --stage search --actor "$REAL_BASELINE_ACTOR_ID"
python3 "$S/scripts/researchctl.py" run --task-dir "$T" --node N001-shuffle \
  --workspace "$WROOT/A" --seed 0 --stage search --actor "$REAL_ENGINEER_A_ID"
python3 "$S/scripts/researchctl.py" run --task-dir "$T" --node N002-schedule \
  --workspace "$WROOT/B" --seed 0 --stage search --actor "$REAL_ENGINEER_B_ID"
```

这些 `run` 由各自获授权的真实线程执行；在文档中顺序展示不等于由 Owner 冒用子线程 ID。
每个命令输出实际 `run_id`；比较时引用该值，不手编看起来像 UUID 的记录。

忘了某条路线做什么时，由 Owner 或只读角色查询：

```bash
python3 "$S/scripts/repoctl.py" catalog --task-dir "$T"
```

输出包含节点问题、状态、reason、branch、workspace、作者和由真实记录汇总的 run IDs。
无需再翻几十个分支名称猜意图。branch 只是开发位置，完整研究解释在节点与分析报告。

## D. A 改了一版实现，不增加第三个工作区

假设 N001 需要一次实现修复，Owner 创建 `N003-shuffle-fix`，`parent: N001-shuffle`，
仍分配槽位 A 与原开发分支，租约 epoch 加一。旧 N001 的 source/run 不修改。
Engineer 在没有该槽位评估进程时改码，交出租约，然后 Owner 对 N003 seal。

```bash
python3 "$S/scripts/repoctl.py" seal --task-dir "$T" --node N003-shuffle-fix
python3 "$S/scripts/repoctl.py" check --task-dir "$T" --node N001-shuffle
# 上行只核验旧快照。此时加 --live 应失败，因为 A 已经是 N003 的代码。
python3 "$S/scripts/repoctl.py" check --task-dir "$T" --node N003-shuffle-fix --live
```

如果仅增加一个 seed，则仍运行原节点，不新建 N003。
如果 A+B 融合，创建一个新 `operator: fuse` 的 node，列出 `parent` 和 `reference_nodes`，
在释放的 A 或 B 槽位中集成，重新评估组合；不存在“把两个分数相加就算收益”的捷径。
若迁入共享 evaluator 修复或更换共同依赖环境，创建 T002，并在 brief/decisions 记 `supersedes: T001`。

## E. 独立确认与恢复保留

Owner 停止候选写入，将真实 Verifier 的评估授权绑定到同一个封存节点与原槽位。
Verifier 用协议中的确认 seeds 分别重跑 baseline/candidate，不开额外的第三个候选目录，
不在旧 allowlist 上补一个“verification worktree”。`finish` 使用原 review 模板。

源码与配置快照是已保存的文件，而不是 Git hash 文字。结项后保留其余必要证据，停止原生子线程和受控进程。
默认保留分支；清理是单独获授权的 Owner 操作，不由脚本自动执行。
若为保留 Git 历史做额外归档，可对**明确列出的任务分支/稳定 ref**创建本地 bundle 并 verify，
不要 `--all` 顺带打包其他无关研究或私有分支。示意命令：

```bash
# 在任务完全静止且该分支已存在时；目标文件不应覆盖已有备份。
git -C "$PROJECT" bundle create /absolute/archive/T001-A.bundle \
  refs/heads/art/T001/A-shuffle
git -C "$PROJECT" bundle verify /absolute/archive/T001-A.bundle
```

bundle 保存被选中的 Git 对象历史，不包括未提交源码、任务运行证据、LFS 外部 payload 或数据集。
本版 snapshots 已单独保存声明源文件；任务 archive 也需独立保存，二者用途不同。
确认所有必要源码均可从归档恢复后，才能讨论任务分支删除；不能把 `git branch -d` 的拒绝当成强删理由。

另一台机器恢复时：先审计档案与外部数据/环境 → 从 source 快照在新授权空目录恢复源文件 →
创建 linked task，记录旧任务/节点/协议 hash 和新环境路径 → 用新冻结协议重跑。
原锁中的绝对路径不具备跨机器可移植性；不改写旧日志假装历史运行发生在新路径。
