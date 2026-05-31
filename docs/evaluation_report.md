# PRLens 测评报告

## 1. 测评目的

本测评用于验证 PRLens 在分析准确性、上下文理解、误报与漏报控制、响应速度和使用体验方面的表现，回应实训营题干对产品质量维度的评估要求。

## 2. 测评方法

- **测评对象**：本仓库 8 个真实 GitHub Pull Request（PR #1 文档型、#2 URL Parser、#5 diff processor、#6 LLM client、#9 risk analyzer、#11 review suggestion generator、#15 workspace sidebar、#17 final docs）
- **分析模式**：标准模式（Summary + Risk）覆盖全部 8 个案例；E5/E6/E7 额外运行完整模式（+ Review Suggestions），共 11 次运行
- **自动记录指标**：分析状态、耗时、风险数量、建议数量、fallback 触发、输出完整性
- **自动初判标记**：Summary 非空、风险含 evidence、建议含 copy_text、文档型 PR 无高风险误报
- **人工复核要求**：准确性、误报、漏报判断必须人工确认

## 3. 测评案例

| 案例 | PR | 类型 | 模式 | 状态 | 耗时 | Risk 数 | Suggestion 数 | Fallback | 自动初判 |
|---|---|---|---|---|---|---|---|---|---|
| E1 | #1 | 文档型 | Standard | success | 39.6s | 0 | 0 | — | Summary 非空，文档型无高风险 |
| E2 | #2 | URL Parser | Standard | success | 72.4s | 0 | 0 | Yes | Summary 非空 |
| E3 | #5 | Diff Processor | Standard | success | 85.0s | 0 | 0 | — | Summary 非空 |
| E4 | #6 | LLM Client | Standard | success | 80.1s | 0 | 0 | Yes | Summary 非空 |
| E5 | #9 | Risk Analyzer | Standard | success | 58.0s | 0 | 0 | — | Summary 非空 |
| E5 | #9 | Risk Analyzer | Full | success | 76.4s | 0 | 0 | Yes | Summary 非空 |
| E6 | #11 | Suggestion Gen | Standard | success | 59.2s | 0 | 0 | — | Summary 非空 |
| E6 | #11 | Suggestion Gen | Full | error | — | 0 | 0 | — | 执行失败 |
| E7 | #15 | Workspace | Standard | success | 84.0s | 0 | 0 | Yes | Summary 非空 |
| E7 | #15 | Workspace | Full | success | 84.4s | 0 | 0 | — | Summary 非空 |
| E8 | #17 | 文档型 | Standard | success | 55.3s | 0 | 0 | — | Summary 非空，文档型无高风险 |

## 4. 自动测评结果

| 指标 | 值 |
|---|---|
| 成功案例数 | 10 / 11 |
| 失败案例数 | 1（E6 Full 模式） |
| 平均耗时 | 69.4s |
| 最快耗时 | 39.6s（E1 文档型 PR） |
| 最慢耗时 | 85.0s（E3 diff processor） |
| Fallback 触发次数 | 4 / 11 |
| Summary 全部生成 | 是（10/10 成功案例） |
| Risk 全部生成 | 是（10/10 成功案例） |
| Suggestions 生成 | 0（所有案例 risk_count 均为 0，未触发建议生成） |

### 关键观察

1. **Summary 稳定性**：10 个成功案例中 Summary 全部非空生成，模型能正常返回结构化输出。
2. **Risk 分析稳定性**：10 个成功案例中 Risk 结果全部返回，但 4 个触发了 fallback（空内容或非法 JSON 被自动重试后仍失败，返回低风险兜底）。这说明对这些 PR 的 diff 内容，部分模型输出不够稳定。
3. **无高风险误报**：测评 PR 均为文档型或工具型 PR，模型未对它们生成高风险误报（risk_count=0 或仅 fallback）。
4. **响应速度**：平均 69.4s/次，最快 39.6s，最慢 85.0s。作为包含 GitHub API + LLM 调用的全链路分析，在可接受范围内。
5. **E6 失败**：Full 模式下 E6（review suggestion generator PR）执行失败，需进一步排查。

### 自动质量标记

| 标记 | 通过率 |
|---|---|
| summary_non_empty | 10/10 (100%) |
| risk_has_evidence_when_present | 0/0 (无 risk items，不适用) |
| no_high_risk_for_docs_only | E1、E8 均通过 |
| completed_without_exception | 10/11 (90.9%) |

## 5. 对题干维度的回应

| 题干维度 | 本次测评如何验证 | 当前结果 | 仍需人工判断 |
|---|---|---|---|
| 分析准确性 | 检查 Summary 是否生成 | 10/10 Summary 非空 | 是 — 内容准确度需人工评估 |
| 上下文理解 | 检查是否能处理 PR metadata 与 diff context | 10/10 成功处理 | 是 — 理解深度需人工评估 |
| 误报控制 | 检查文档型 PR 是否出现高风险输出 | E1、E8 均无高风险误报 | 是 — 需更多样本 |
| 漏报控制 | 记录风险项覆盖情况 | risk_count=0 在所有案例 | 是 — 本仓库 PR 风险较少，需外部样本验证 |
| 响应速度 | 记录每个案例耗时 | 平均 69.4s | 否 — 客观数据 |
| 使用体验 | 结合 Demo 页面、分析模式、进度反馈 | Demo 可操作，支持三种模式和进度 | 部分需人工体验 |

## 6. 局限性

- **样本来源单一**：8 个测评案例均来自本仓库，类型偏向文档和工具 PR，缺乏复杂的多文件业务逻辑变更
- **Risk 0 导致建议未触发**：本仓库 PR 的 diff 主要是文档和简单代码变更，模型未识别出风险项，导致 Review Suggestions 在所有成功案例中均为空（除 E6 失败外）
- **Fallback 率偏高**：4/11 触发 fallback，说明部分 LLM 输出仍需 prompt 优化
- **自动测评不能替代人工 Review**：本报告仅记录客观指标和自动初判，准确性、误报和漏报需人工复核
- **LLM 输出可能波动**：同一 PR 多次运行可能得到不同结果
- **未测试大 PR**：测评 PR 的 diff 均较小，未覆盖长 diff 截断场景

## 7. 后续优化方向

- 扩大测评案例范围（引入外部公开仓库的中大型 PR）
- 引入人工标注（准确度 1-5 分、误报/漏报标记）
- 添加 cross-mode 一致性检查（标准模式 vs 完整模式的 Risk 结果是否一致）
- 优化 risk analyzer prompt 以降低 fallback 率
- 增加仓库级上下文检索能力
- 记录用户反馈，建立误报/漏报优化闭环

## 8. 附录

- 测评脚本：`scripts/run_evaluation.py`
- 测评原始数据：`docs/evaluation_results.json`
- 运行命令：`GITHUB_TOKEN=$(gh auth token) python scripts/run_evaluation.py`
