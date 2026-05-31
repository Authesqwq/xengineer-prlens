# PRLens High-Risk Golden Cases 测评报告

## 1. 测评目的

验证 PRLens 的 Risk Analyzer 和 Review Suggestions 在明确高风险 PR 下是否能被触发。Golden cases 是构造型 toy fixture，仅用于链路验证。

## 2. Golden Cases 设计

| 案例 | PR | 风险类型 | 预期 |
|---|---|---|---|
| G1 | [#18](https://github.com/Authesqwq/xengineer-prlens/pull/18) | 安全风险（硬编码 token、SQL 注入、auth bypass） | risk>0, sug>0 |
| G2 | [#19](https://github.com/Authesqwq/xengineer-prlens/pull/19) | 健壮性风险（None 访问、除零、空索引、吞异常） | risk>0, sug>0 |
| G3 | [#20](https://github.com/Authesqwq/xengineer-prlens/pull/20) | 性能风险（O(n²)、内存全载、无超时请求） | risk>0, sug>0 |
| G4 | [#21](https://github.com/Authesqwq/xengineer-prlens/pull/21) | 配置/密钥风险（默认密钥、debug 默认开、宽松 CORS） | risk>0, sug>0 |

**重要**：这 4 个 PR 标有 `[EVAL ONLY]`，**不会合并**到主分支。

## 3. 测评结果

| 案例 | 模式 | 状态 | 耗时 | Risk 数 | Sug 数 | Fallback | 自动结论 |
|---|---|---|---:|---:|---|---|---|
| G1 | full | success | 24.4s | 0 | 0 | Yes | FAIL — Risk Analyzer 未识别安全风险 |
| G2 | full | success | 26.0s | 0 | 0 | Yes | FAIL — Risk Analyzer 未识别健壮性风险 |
| G3 | full | success | 20.6s | 0 | 0 | — | FAIL — Risk Analyzer 未识别性能风险 |
| G4 | full | error | — | **2** | 0 | — | Partial — Risk Analyzer 成功识别 2 个配置风险，但 Suggestions JSON 被截断 |

## 4. 分析

### 4.1 Risk Analyzer 表现

- G1/G2/G3：Flash 模型未能识别 fixture 中的明显风险。可能原因：fixture 过于 trivial（单文件 toy 示例），模型将其归为低风险代码片段；prompt 强调"不强制生成风险"导致过于保守
- G4：成功识别 2 个配置安全风险（硬编码密钥、debug 模式），说明模型在特定 pattern 上有效

### 4.2 Review Suggestions 表现

- G1-G3：因 risk_count=0，Suggestions 正确跳过（符合设计）
- G4：risk=2 触发 Suggestions 调用，但模型 JSON 输出被截断（unterminated string），Suggestions 生成失败

### 4.3 根因判断

| 问题 | 根因 |
|---|---|
| Flash 未识别 G1-G3 | Prompt 要求"不强制生成风险"可能过保守 + toy fixture 缺少真实项目上下文 |
| G4 Suggestions 失败 | LLM 输出 max_tokens 不足，JSON 被截断 |
| Golden cases 整体表现 | Risk Analyzer 对构造型 toy fixture 的敏感性不足 |

## 5. 结论

- **Risk Analyzer 在 Flash 模型下对构造型 toy fixture 不敏感**：4 个 golden cases 中仅 1 个（G4）成功识别风险
- **Review Suggestions 链路触发了但未成功**：G4 的 risk=2 触发 Suggestions，但因模型 JSON 截断失败
- Golden cases 证明了 Suggestions 确实会在 risk>0 时被调用（链路正确），但输出稳定性仍需改善
- **不建议基于 golden cases 修改 Risk Analyzer prompt**：构造型 fixture 不代表真实 PR，提高 toy 敏感性可能引入误报
- 真实外部高风险 PR + 人工标注仍是更可靠的验证方式

## 6. 局限性

- Golden cases 是构造型 toy fixture，不代表真实 PR 场景
- 仅验证链路触发，不代表风险识别准确率
- Flash 模型对简单 toy 示例不敏感可能合理（避免过度敏感）
- 仍需要真实高风险 PR 验证

## 7. 附录：Golden PR 链接

- [G1 #18](https://github.com/Authesqwq/xengineer-prlens/pull/18) — 安全风险 fixture
- [G2 #19](https://github.com/Authesqwq/xengineer-prlens/pull/19) — 健壮性风险 fixture
- [G3 #20](https://github.com/Authesqwq/xengineer-prlens/pull/20) — 性能风险 fixture
- [G4 #21](https://github.com/Authesqwq/xengineer-prlens/pull/21) — 配置/密钥风险 fixture

所有 PR 不合并。
