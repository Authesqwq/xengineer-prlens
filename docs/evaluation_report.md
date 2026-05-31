# PRLens 自动测评与人工复核报告

## 1. 测评目的

验证 PRLens 在分析准确性、上下文理解、误报与漏报控制、响应速度和使用体验方面的表现。

## 2. 测评集设计

测评集共 18 次运行，覆盖 8 个内部 PR 和 6 个外部 PR。

- **内部 PR** (I1-I8)：验证 PRLens 对自身仓库文档型、工具型变更的理解，重点检查是否产生高风险误报
- **外部 PR** (E1-E6)：覆盖 bug fix、测试变更、平台兼容性、API 设计争议、外部文档 PR
- Full 模式仅对 I5/I6/E1/E2 启用，控制测评成本

## 3. 测评方法

- 标准模式 (Summary + Risk) 覆盖所有案例；Full (Summary + Risk + Suggestions) 仅覆盖 4 个案例
- 测评层面 diff 限制: max_files=8, max_patch_chars=6000, max_total_chars=30000
- 记录耗时、风险数量、fallback 次数、suggestion 数量等客观指标
- 准确性、误报、漏报仅做自动初判，必须人工复核

## 4. 测评结果总览

| 案例 | 类型 | 模式 | 状态 | 耗时(s) | Risk数 | Sug数 | Fallback | 截断 | 自动初判 |
|---|---|---|---|---|---:|---:|---:|---|---|---|
| I1 | 文档型 PR | standard | success | 31.43 | 0 | 0 | - | Yes | Summary=✓ |
| I2 | 小型功能 PR | standard | success | 84.07 | 0 | 0 | Yes | - | Summary=✓ |
| I3 | 上下文处理 PR | standard | success | 77.56 | 0 | 0 | Yes | Yes | Summary=✓ |
| I4 | API client PR | standard | success | 82.6 | 0 | 0 | Yes | Yes | Summary=✓ |
| I5 | 风险分析模块 PR | standard | success | 74.37 | 0 | 0 | Yes | Yes | Summary=✓ |
| I5 | 风险分析模块 PR | full | success | 78.14 | 0 | 0 | Yes | Yes | Summary=✓ |
| I6 | Review suggestion PR | standard | success | 70.82 | 0 | 0 | Yes | Yes | Summary=✓ |
| I6 | Review suggestion PR | full | success | 78.41 | 0 | 0 | Yes | Yes | Summary=✓ |
| I7 | UI / 工作区 PR | standard | success | 76.3 | 0 | 0 | - | Yes | Summary=✓ |
| I8 | 最终文档 PR | standard | success | 69.17 | 0 | 0 | - | Yes | Summary=✓ |
| E1 | 小型 bug fix | standard | success | 26.48 | 1 | 0 | - | - | Summary=✓ |
| E1 | 小型 bug fix | full | error | - | 1 | 0 | - | - | Summary=✓ |
| E2 | bug fix + tests | standard | success | 104.79 | 0 | 0 | Yes | - | Summary=✓ |
| E2 | bug fix + tests | full | success | 97.93 | 0 | 0 | Yes | - | Summary=✓ |
| E3 | 数据解析 bug | standard | success | 75.35 | 0 | 0 | Yes | - | Summary=✓ |
| E4 | 平台兼容性 bug | standard | success | 95.55 | 0 | 0 | Yes | - | Summary=✓ |
| E5 | 外部文档 PR | standard | success | 15.17 | 0 | 0 | - | - | Summary=✓ |
| E6 | API 行为 / 设计争议 PR | standard | success | 68.41 | 0 | 0 | Yes | - | Summary=✓ |

**统计**: 17 成功 / 1 失败 / 0 跳过 | 平均耗时 71.0s | Fallback 12 次 | risk>0: 1 案例 | sug>0: 0 案例 | 截断: 9 次

## 5. 分类观察

### 5.1 文档型 PR
内部文档型 PR (I1, I8) 和外部文档 PR (E5): 检查 Summary 是否生成，是否无高风险误报。

### 5.2 小型 bug fix
E1 (requests#7004): 极小 diff 的边界条件修复，检查风险识别是否合理。

### 5.3 测试与兼容性变更
E2 (click#3126), E4 (click#2969): 含测试变更的 bug fix，检查测试缺失提示。

### 5.4 API / 设计争议 PR
E6 (fastapi#10694): 含大量讨论的 API 行为变更，检查是否理解 PR 背景。

### 5.5 完整模式与 Review Suggestions
I5, I6, E1, E2 运行 Full 模式，检查 Suggestions 是否在存在风险时生成。

## 6. 对题干维度的回应

| 题干维度 | 如何验证 | 当前证据 | 仍需人工判断 |
|---|---|---|---|
| 分析准确性 | Summary 是否生成、Risk evidence 是否有 | Summary 生成率, evidence 检查 | 是 |
| 上下文理解 | PR metadata + diff 是否被正确处理 | 文件统计、截断标记 | 是 |
| 误报控制 | 文档型 PR 是否有高风险 | no_high_risk_for_docs 标记 | 是 |
| 漏报控制 | 外部 bug fix PR 是否识别出风险 | risk_count 统计 | 是 |
| 响应速度 | 每个案例耗时 | 平均 71.0s | 否 |
| 使用体验 | 进度反馈、模式、导出 | Demo 已验证 | 部分 |

## 7. 人工复核记录

| 案例 | Summary准确性 | 上下文理解 | 风险合理性 | 明显误报 | 明显漏报 | 人工结论 |
|---|---:|---:|---:|---|---|---|
| I1 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I2 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I3 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I4 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I5 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I5 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I6 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I6 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I7 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I8 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E1 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E1 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E2 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E2 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E3 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E4 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E5 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E6 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |

## 8. 局限性

- 自动测评不能替代人工 Review
- 测评样本 14 个案例，类型覆盖有限
- LLM 输出可能波动
- 外部 PR 类型仍有限（小型 bug fix 为主）
- 大型 PR 可能受 diff 截断影响（测评限制为 8 文件 / 30000 字符）
- Review Suggestions 触发依赖于 Risk 先识别出风险项

## 9. 后续优化方向

- 扩大 golden cases 集合，引入人工标注
- 增加仓库级上下文检索
- 接入团队规则库
- 建立反馈闭环
- 降低 fallback 率，提升响应速度
