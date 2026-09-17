# 实验代码管理：0.1.1 定制增量

## 当前结论

不是在“文件夹管理”和“分支管理”之间二选一。沿用原设计的 `.autoresearch/<task>/nodes/`，
以**固定工作区槽位 + 单写入租约 + 不覆盖的候选源码快照**补全执行边界。
两个假设可以并发开发，正式评估仍遵守每任务单进程。

`docs/DESIGN.md` 保留上传包的 0.1.0 原设计；本页及 skill 的 repository policy 是本次新增设计。
未重新评估原设计中引用的所有科研仓库，也未将本包改成另一套模型 API harness。

## 三个设计选择及其代价

| 问题 | 本版选择 | 代价/不保证 |
|---|---|---|
| 分支多、忘记用途 | nodes 保存目的/状态/解释，`repoctl catalog` 从已有记录派生视图 | Owner 仍要写清 reason；脚本不会代替研究判断 |
| 多代理同时写代码 | 冻结前建立 baseline/A/B 三个固定路径，每候选槽位单写入者；node 可增长 | 槽位复用需交接；worktree 不隔离 GPU、环境和共享 Git 配置 |
| 旧代码与旧结果失联 | 每个正式运行节点先保存 tracked_paths 的实际字节；新版运行器核对封存绑定 | 源码清单完整性仍需审计；快照占磁盘，不自动保存数据和完整环境 |

冻结后禁止漂移是这套协议的一致性约束，不是 Git 自身限制。普通候选源码变更形成新 node；
改变 baseline、评测含义或共同冻结依赖则新建 linked task，不自动 rebase 所有候选到 main。

## 与原包的接口关系

保留 Owner/Researcher/Engineer/Analyst/Verifier、真实原生子线程、最多三子线程/两候选/单任务单运行、
原研究 loop、预算与确认门禁、原安装器和宿主 manifest 结构。

新增 `repoctl.py seal/check/catalog`；新增可选协议字段 `source_snapshot_policy`。
新协议模板为 `required`。缺省/`legacy` 保留原执行行为，因此原 0.1.0 冻结任务可接续，
但不会因为更新插件文件而被宣称拥有新封存门禁。升级门禁使用新 linked task。

新增节点字段 `branch`、`slot`、`source_hash`、`snapshot_manifest_sha256`；
`source_commit_or_snapshot` 在 seal 后指向实际保存的 source 目录。
`team.json` 新增 `workspaces` 来承载现有调度中的工作区所有权，不另建 registry 文件。

源码 writer lease 由 Owner 维护，`repoctl seal` 由 Owner 调用；Engineer 完成实现后先交出租约，
Owner seal 后再按原角色规则授权 Engineer 运行。Verifier 只评估已停止源码写入的已封存版本。

## 交付文件

- skill 中 `references/repository-policy.md`：完整执行契约。
- skill 中 `references/repository-examples.md`：两个假设并发开发、config-only 分支选择、节点迭代与归档恢复例子。
- skill 中 `assets/AGENTS.md`：与契约正文相同，供项目根使用；已有 AGENTS.md 时合并，不覆盖。
- skill 中 `scripts/repoctl.py`：源码封存、完整性检查、派生目录。
- `tests/test_repository_policy.py`：新增本地 fixture。

插件版通过 SKILL 入口显式加载规范；无需为了启用它再复制一份 AGENTS.md。
独立 AGENTS.md 提供指令层规范，但其中封存命令依赖定制版 0.1.1 脚本；不是仅凭 Markdown 自动安装工具。

## 检查能力边界

required profile 会拒绝没有快照的正式 run、旧 node 对应新代码、工作区与节点不符、
快照文件/manifest 损坏、运行前后的源码和文件 mode 改变，以及改变了冻结基线的快照。
旧节点快照可在工作区被复用或移除后核验；最终 finish 仍检查当前候选工作区。

执行器从工作区运行，不从只读镜像运行。前后 hash 检查不等于防止并发写入，
不防同账户攻击者临时修改再还原，也不证明依赖清单包含所有行为输入。
仍依赖原生宿主与 Owner 落实权限、真实身份、租约交接、资源隔离和研究结论有效性。

快照是每节点的声明源码副本，不是 Git 的完整历史备份。只保存 commit hash 并删除未合并 branch，
不足以保证以后还能恢复；Git 对象可达性和备份另管。确需保留 Git 历史可用明确任务 refs 的 bundle，
但它不替代未提交文件、外部数据、LFS payload 和运行证据的归档。

本包没有自动升级已冻结任务、自动删除分支、自动上传归档或跨机器路径重写。
外部机器重现时建立新 linked task，不改写历史记录。快照/node 写入不是多文件事务；
Owner 按规范处理异常中断时留下的 staging 或孤立 snapshot。

## 来源与核对范围

本次依据用户上传的 `auto-research-team-0.1.0.zip` 中的实际 skill、角色、contracts、
workflow、researchctl、安装器及测试设计增量；原资料见 `docs/DESIGN.md` 与 `docs/INSTALL.md`。
没有把前面对话中提出的 Hxxx/experiments 结构强加到已存在的 node 模型。

以下为 2026-09-17 核对的官方文档，用于确认底层工具语义，不表示本版已在所有宿主端测试：

- Git worktree：<https://git-scm.com/docs/git-worktree>。多个 checkout 分开 HEAD/index；refs 与默认配置仍共享；worktree lock 不等于源代码互斥。
- Git bundle：<https://git-scm.com/docs/git-bundle>。Git 对象打包、依赖前提与 verify；不是工作目录/数据备份。
- Git GC：<https://git-scm.com/docs/git-gc>。对象保留与不可达对象清理的关系。
- Codex AGENTS.md：<https://developers.openai.com/codex/guides/agents-md>。指令发现与作用域；已有指令采用合并而非覆盖。

本地测试输出与未验证项见 `TEST_REPORT.md`。角色标签在 fixture 中是虚构标识，不代表真实 native agent。
