# PRLens 自动测评与人工复核报告

## 1. 测评目的

验证 PRLens 在分析准确性、上下文理解、误报与漏报控制、响应速度和使用体验方面的表现。

## 2. 测评集设计

测评集覆盖 **14 个正式案例**（8 内部 + 6 外部）和 **2 个压力案例**。

- **内部 PR (I1-I8)**：PRLens 自身仓库文档型、工具型变更，重点检查高风险误报
- **外部 PR (E1-E6)**：psf/requests、pallets/click、pandas-dev/pandas、fastapi 等真实项目 bug fix/测试/兼容性/文档 PR
- **压力案例 (S1-S2)**：nodejs/node 跨语言变更、apache/seatunnel 大型安全 PR，单独附录统计

## 3. 测评方法

- 标准模式覆盖所有案例；Full 模式覆盖 I5/I6/E1/E2（共执行 20 次 LLM 调用）
- diff 限制：max_files=8, max_patch_chars=6000, max_total_chars=30000
- 记录耗时、风险数量、fallback、suggestion 数量
- **准确性、误报、漏报仅做自动初判，必须人工复核**

## 4. 测评结果总览

### 4.1 正式测评

| 指标 | 第一次运行 | 第二次运行 | 说明 |
|---|---|---|---|
| 正式案例 | 18 次 | 18 次 | — |
| 成功 | 14 | 15 | 3 次 LLM 输出波动 |
| 失败 | 4 | 3 | I3/I7/E4 各 1 次 |
| 平均耗时 | ~66s | 65.1s | 受模型服务商影响 |
| risk_count > 0 | 3 案例 (I2, E2, E3) | 0 案例 | **LLM 输出不稳定** |

**关键发现**：两次运行的 risk_count 结果不一致。第一次 I2=2、E2=1、E3=1；第二次全部为 0。这说明**同一 PR 的 LLM 风险识别输出存在明显波动**，受模型随机性、截断和 prompt 稳定性影响。

### 4.2 压力案例

| 案例 | 状态 | 耗时 | 说明 |
|---|---|---|---|
| S1 (nodejs#48829) | 成功 | 69.6s | risk=0, fallback |
| S2 (seatunnel#10468) | 成功 | 76.6s | risk=0, fallback |

压力案例用于边界观察，不计入正式测评均值。

### 4.3 失败案例

| 案例 | 模式 | 阶段 | 错误 | 原因 |
|---|---|---|---|---|
| I3 | standard | Summary | empty content | diff 截断后模型返回空 |
| I7 | standard | Summary | unterminated string | 模型 JSON 输出被截断 |
| E4 | standard | Summary | unterminated string | 模型 JSON 输出被截断 |
| I2 | full | Suggestions | 网络错误 | LLM API 连接波动（仅 1 次运行） |
| E3 | full | Suggestions | 网络错误 | LLM API 连接波动（仅 1 次运行） |

所有失败发生在 LLM 交互阶段（非 GitHub API 或代码逻辑错误），属于模型服务波动和输出格式不稳定问题。

### 4.4 Review Suggestions

suggestion_count 在所有 20 次运行中**均为 0**。原因：

- 大部分案例 risk_count=0，无风险项无法触发 Suggestions
- 少数有风险的案例（I2/E2/E3）在 Full 模式下或 fallback（导致 risk=0），或因网络波动失败

**结论**：Review Suggestions 在自动测评中未能被稳定触发。该功能主要依赖 25 个单元测试（`test_review_suggestion.py`）和手动 Demo 验证。后续需引入高风险 golden cases。

### 4.5 fallback 率

正式测评中 9/18 触发 fallback（50%）。主要原因是 diff 截断导致模型输出不稳定。结合两次运行时有时有风险有时无风险的波动，**Risk Analyzer 的结构化输出稳定性仍需提升**。

## 5. 分类观察

### 文档型 PR
I1、I8、E5 均为文档型 PR，均成功且 risk=0，无高风险误报。符合预期。

### 小型 bug fix
E1 (requests#7004) 两次运行均成功。第二次运行未生成风险项，第一次也如此——极小 diff 确实难以触发有意义的 risk。

### 波动案例
I2 (内部 URL parser)、E2 (外部 click)、E3 (pandas) 在第一次运行中出现了 risk>0，第二次运行中全部为 0。这说明模型输出不够稳定，diff 截断可能是影响因素之一。

## 6. 对题干维度的回应

| 题干维度 | 如何验证 | 当前证据 | 仍需人工判断 |
|---|---|---|---|
| 分析准确性 | Summary 是否生成、Risk evidence | Summary 15/18，风险 evidence 检查 | **是** |
| 上下文理解 | PR metadata + diff 处理 | 文件统计、截断标记 | **是** |
| 误报控制 | 文档 PR 无高风险 | I1/I8/E5 risk=0 | **是** |
| 漏报控制 | 外部 bug fix PR risk 记录 | 第一次运行 I2/E2/E3 有风险，第二次全部为 0 | **是** |
| 响应速度 | 每个案例耗时 | 平均 65.1s | 否 |
| 使用体验 | 进度、模式、历史、导出 | Demo 已验证 | 部分 |

## 7. 人工复核记录

| 案例 | 模式 | Summary | 上下文 | 风险合理性 | 误报 | 漏报 | 结论 |
|---|---|---|---:|---:|---:|---|---|
| I1 | standard | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| I2 | standard | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E2 | standard/full | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |
| E3 | standard | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 | 待复核 |

*注：仅列出风险>0 或有代表性的案例。完整清单见前次报告。*

## 8. 局限性

- **LLM 输出不稳定**：两次运行风险结果不一致，同一 PR 可能有时识别出风险有时不能
- **fallback 率偏高**（~50%），主要由 diff 截断和模型输出格式不稳定导致
- **Review Suggestions 未触发**：suggestion_count 在所有运行中均为 0，Suggestions 功能主要依赖单元测试验证
- 自动测评不能替代人工 Review
- 测评样本 14 个案例，以小型 bug fix 为主，类型覆盖有限
- 系统仅基于 PR diff 分析，不读取完整仓库上下文
- 平均 65s 可接受但仍有优化空间（并行 Summary+Risk 可降至 ~max(t_summary, t_risk)）

## 9. 后续优化方向

- 引入高风险 golden cases，确保 Suggestions 可被稳定触发
- 人工标注 5-10 个案例
- 降低 fallback 率（优化 risk analyzer prompt）
- 并行 Summary + Risk 调用，降低延迟
- diff 上下文限制可配置化
- 增加仓库级上下文检索
- 建立反馈闭环

## 10. 附录

- 正式案例配置：`docs/evaluation_cases.json`
- 压力案例配置：`docs/evaluation_stress_cases.json`
- 原始数据：`docs/evaluation_results.json`
- 测评脚本：`scripts/run_evaluation.py`
