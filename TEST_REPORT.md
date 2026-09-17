# 本地测试记录 — 0.1.1 仓库管理定制版

日期：2026-09-17。运行环境：Linux；Python 3.13.5；Git 2.47.3。
基础脚本仍以 Python >=3.11 为目标；本环境未对 Python 3.11/macOS/WSL 分别执行矩阵测试。

## 实际执行结果

按模块执行，共 **90 tests passed**；无失败、无跳过。
fixture 中的 Owner/Engineer/Verifier ID 均为测试标签，不是实际原生代理。

| 模块 | 测试数 | 结果 | 原始输出 |
|---|---:|---|---|
| 原安装器 | 11 | PASS | `tests/install-output.txt` |
| 原受控运行器回归 | 41 | PASS | `tests/runtime-output.txt` |
| 新增源码封存、证据绑定、worktree fixture | 32 | PASS | `tests/repository-output.txt` |
| 新增模板、指令及包完整性 | 6 | PASS | `tests/packaging-output.txt` |

合并输出：`tests/test-output.txt`，每段保留该模块真实 unittest 输出，不伪装成单次整套运行。
本会话的整套单次 discover 曾被工具执行限时中断，未将中断调用记为通过；随后按模块完整执行上述测试。

实际命令，在包根执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_install.py -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_researchctl.py -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_repository_policy.py -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_repository_docs.py -v
```

在没有此工具会话限时的本地环境，也可沿用 `python3 -m unittest discover -s tests -v`。

## 已覆盖的新增行为

未封存节点拒跑且不消耗未启动作业的预算；旧节点拒绝修改后的源码；新节点复用原槽位不破坏旧证据；
快照/manifest/节点绑定损坏拒用；状态/解释/run ID 索引更新不误作改码；
源码字节与文件 mode 的运行前后核验；冻结后 baseline 的源码/mode 改变拒绝；
二进制源文件按字节保存；符号链接拒绝；错工作区、非法 ID、未知父节点拒绝；
seal 遵守原 task run lock 并拒绝未核对的运行记录；工作区被移除后旧源码快照仍可核验；
required profile 的独立 confirmation 与 finish；legacy 协议兼容；CLI seal/check/catalog。

真实本地 Git fixture 建立两个 worktree，并由两个本地 Python worker 并发修改各自文件，
核对原用户 checkout 的文件、HEAD 和分支未变化。这验证文件目录隔离，不代表实际 Codex 子代理分派。

安装与打包检查覆盖 standalone skill 自包含、规范正文与 AGENTS.md 副本一致、
模板默认 required profile、manifest 版本一致、Markdown 本地链接可解析、安装时不覆盖用户 AGENTS.md。
所有包内 Python 文件通过 AST 解析，JSON 文件通过解析。原 `tools/install.py` 与 `docs/DESIGN.md` 原文保留。

## 未验证/不保证

未执行真实 Codex 原生子代理的创建、cwd 绑定、租约遵从、停止/接续及完整宿主验收；
未进行真实 GPU/训练/算法 benchmark；未证明科研成功率、人工审查时间或漏错率改善；
未验证生产网络文件系统、跨机器恢复、完整断电事务或针对共享账号恶意修改的安全性。

测试使用微型本地输出，不将 fixture 分数作为算法效果。源码快照覆盖声明路径，不自动发现依赖闭包。
进程清理、预算、声明 ID、锁与 hash 的非安全沙箱边界继续遵循原设计。
