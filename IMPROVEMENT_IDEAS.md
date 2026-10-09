# AutoformBot 改进建议：可借鉴 Reflection AI 公开工程做法的地方

日期：2026-10-03

## 背景与范围

这份文档记录了一次对照分析的结论：把 Reflection AI 在公开渠道体现出来的工程做法，与 AutoformBot 的现状逐项对比，找出值得借鉴的改进点。

- **信息来源**：Reflection AI 的公开 GitHub 组织（`reflectionai`，主要是 NVSentinel、KAI-Scheduler、nydus 等项目的 fork 和其中的 PR）、招聘 JD、高管公开访谈。他们没有公开任何独门技术，这里借鉴的是工程模式。
- **阅读范围**：`autoform_cli/`、`servers/`、`skills/`、CI 模板，以及 `execution` 分支的结构。没有运行实验，下面的"现状"都来自读代码。
- **与已有评审的关系**：[CODE_REVIEW.md](CODE_REVIEW.md) 里的发现 1–3（LSP 把 1 秒静默当作诊断结束、词法扫描丢命名空间、代码块里的 `<!--` 吞掉依赖边）会给出错误答案，优先级高于本文所有建议。本文提到的"发现 N"均指该文件里的编号。

## 建议顺序

| 顺序 | 建议 | 说明 |
| --- | --- | --- |
| 1 | 坏掉的 REPL 在请求路径之外修复 | 顺带关掉 CODE_REVIEW 的发现 6 和 11 |
| 2 | 机器能力的启动前自检 | 独立，可随时做 |
| 3 | 给 agent 评审建带已知答案的评测集 | 独立，可随时做 |
| 4 | 评审结论和证明尝试留下结构化记录 | 需等持久 `article_id` 迁移落地 |
| 5 | 给 skeleton 提供可选的沙箱运行方式 | 可随时插入 |
| 6 | 运行时指标 | 可随时插入 |

## 1. 坏掉的 REPL 在请求路径之外修复

**对应做法**：Reflection 在 NVSentinel 上做的是"持续监控 → 隔离 → 排空 → 修复"，坏节点不让下一个作业去踩。

**现状**：

- [servers/repl/pool.py:115-118](servers/repl/pool.py#L115-L118) 无论 worker 是否健康都放回空闲队列，重启发生在下一次请求里（[servers/repl/core.py:755-757](servers/repl/core.py#L755-L757)）。
- 重启要重新 `import Mathlib`，却只能用下一次请求的 30 秒预算。这就是发现 6。
- 内存只在请求之间检查，`mem_interval_check` 从未被读取（发现 11）。一条命令运行中涨到多少都不会被拦。

**建议**：

- worker 失败后标记为隔离，由后台线程用完整的 180 秒启动预算重建，重建好再放回队列。
- 命令运行期间加一个内存看门狗，超限就终止进程组并返回明确错误。

改动局限在 `servers/repl/`。

## 2. 机器能力的启动前自检

**对应做法**：Reflection 的 preflight 在训练作业启动前检查 GPU 和网络，整组一起验证，带超时，避免一个坏节点拖死整组。

**现状**：

- [autoform_cli/README.md:602](autoform_cli/README.md#L602) 明确写了 `doctor` 只查蓝图契约，机器能力的 preflight 留给将来。
- 环境问题现在是在第一次工具调用时才暴露：`lake exe repl` 没构建、Mathlib 缓存没拉、工具链不匹配，都表现为一次很长的冷启动超时。
- `skeleton` 需要 `.lake` 可写、构建产物新鲜，否则跑到一半才拒绝。

**建议**：加一个只读的环境自检，逐项报告：

- elan 工具链与 `lean-toolchain` 是否一致；
- `lake-manifest.json` 是否存在；
- Mathlib 的 olean 缓存是否已就位；
- REPL 可执行文件是否已构建；
- 可用内存够开几个 worker；
- `.lake` 是否可写。

Cabannes 示例完整构建约 21 分钟，缺缓存这类问题提前发现很划算。`execution` 分支并行派发一批节点前，对所有 worktree 先跑一遍自检，就是整组级别的 fail-fast。

## 3. 给 agent 评审建带已知答案的评测集

**对应做法**：Reflection 的核心论点是"可验证的执行反馈"，团队成员也在 SWE-bench、terminal-bench 这类基准上找错题。

**现状**：

- [faithfulness.md](skills/agent-review/references/faithfulness.md) 和 [proof-integrity.md](skills/agent-review/references/proof-integrity.md) 的评分标准写得很细，还列了常见失败模式（丢结论、量词顺序、把结论塞进无实例的 class、空洞定义）。
- 但没有任何东西衡量 agent 按这些标准评审时到底能抓到多少。测试覆盖的是 CLI 的确定性行为，不覆盖评审质量。
- `autoform skeleton --packets --passages` 已经能产出盲审所需的输入包。

**建议**：做一组"埋雷"夹具。每个是一个小 Lean 项目加一篇文章，故意带一种评分标准里列出的缺陷，并标注期望得分上限。评审技能跑一遍，对照标注算命中率。这样改评分标准、换模型或改提示词时，就有数字可比。现有的 [thesis-review-case.md](skills/agent-review/references/thesis-review-case.md) 可以作为第一个样例。

## 4. 评审结论和证明尝试留下结构化记录

**对应做法**：后训练需要"轨迹加奖励"的数据；Reflection 改 codex fork 时加的也是 token、成本、超时这些记账字段。

**现状**：

- 评审结果是散文报告。skeleton 已经给了 review hash，把证据包、原文段落和 drift hash 绑在一起，但没有约定的机器可读结论格式去引用它。
- `execution` 分支的 `servers/prover/triggers.py` 已经从事件流里算确定性信号（重复构建错误、sorry 数不降、偏离目标、停滞），`servers/prover/verify.py` 给出通过或失败。这些只用于当场纠偏，没有落盘。

**建议**：

- 定义一个评审结论的 JSON 格式：review hash、各项得分、触发的硬上限、运行过的命令。
- 在 `execution` 分支把每次尝试的阶段、触发的信号、验证结果、耗时和 token 记成 JSONL。

**前置条件**：[autoform_cli/README.md:623-628](autoform_cli/README.md#L623-L628) 规定，在持久 `article_id` 迁移落地前，评审和队列记录不得绑定路径派生的 ID，且不得进入发布产物。目前 `autoform migrate article-ids` 只做规划不做应用，所以这一项要排在它后面，记录也应放在蓝图之外。

## 5. 给 skeleton 提供可选的沙箱运行方式

**对应做法**：Reflection 的工程师在给 gVisor 提 PR、研究沙箱隔离，用来跑不可信的 agent 代码。

**现状**：文档反复提醒 `skeleton` 只能在可信检出或操作系统沙箱里跑，因为候选代码的宏和初始化器能做任意 IO、能伪造探针输出，所以哈希只是"建议性"的。但项目没有提供任何沙箱跑法。

**建议**：提供一个可选包装（容器或 bubblewrap：无网络、源码只读、仅 `.lake` 可写），并在报告里记录是否在隔离下运行。这对评审第三方或 agent 生成的 PR 最有用。

## 6. 运行时指标

**对应做法**：Reflection 给 preflight 加了 OTel 指标输出。

**现状**：[servers/lean_runtime.py:779-792](servers/lean_runtime.py#L779-L792) 的 `daemon.status` 只有配置和驻留项目列表，其余靠滚动日志。

**建议**：在 status 里加几个计数器：冷启动耗时、排队等待时间、按原因分类的重启次数、`outcome_unknown` 次数、超时次数。`AUTOFORM_*` 那些上限现在只能凭感觉调，有了这些就有依据。

## 价值较低或把握不足的想法

- **调度公平性**：REPL 池是单个 FIFO 队列，默认每项目 1 个 worker，worker 总数按总内存除以 16GB 估算而非按可用内存。多 agent 并行时可以学 KAI-Scheduler 做按会话的公平排队，但单机场景下收益可能不大。
- **同机构建锁**：`lake-build` 声明走 Git 远端 ref，每次获取都要网络往返。同一台机器上的多个 worktree 可以由常驻运行时提供本地信号量，跨机器再用声明。这是推断，没有测过实际开销。
- **环境缓存**：发现 7 指出 `run_lean_code` 无法引用项目自己的声明。可以按 import 头缓存已加载的环境，类似 nydus 的按需加载思路。REPL 在这方面的能力和实际提速没有验证，需要先做实验。
