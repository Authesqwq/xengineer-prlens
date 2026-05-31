# PRLens High-Risk Golden Cases 测评报告

## 1. 测评目的

验证 PRLens 的 Risk Analyzer 和 Review Suggestions 在构造型 high-risk PR 下的触发和输出稳定性。

## 2. Golden Cases 设计

| 案例 | PR | 风险类型 | 预期 |
|---|---|---|---|
| G1 | [#18](https://github.com/Authesqwq/xengineer-prlens/pull/18) | 安全风险（硬编码 token、SQL 注入、auth bypass） | risk>0, sug>0 |
| G2 | [#19](https://github.com/Authesqwq/xengineer-prlens/pull/19) | 健壮性风险（None 访问、除零、空索引、吞异常） | risk>0, sug>0 |
| G3 | [#20](https://github.com/Authesqwq/xengineer-prlens/pull/20) | 性能风险（O(n²)、内存全载、无超时） | risk>0, sug>0 |
| G4 | [#21](https://github.com/Authesqwq/xengineer-prlens/pull/21) | 配置/密钥风险（默认密钥、debug、宽松 CORS） | risk>0, sug>0 |

**这 4 个 PR 标有 `[EVAL ONLY]`，不会合并到主分支。**

## 3. 优化内容（PR21）

| 优化 | 说明 |
|---|---|
| 缩短 LLM 输出格式 | Prompt 改为 compact JSON，要求最多 3 条建议、copy_text ≤ 200 字符 |
| retry 逻辑 | 空内容/JSON parse error/unterminated string 时重试一次 |
| deterministic fallback | 两次 LLM 均失败时，基于 risk_items 生成 fallback suggestions |
| 不吞掉真实错误 | auth/rate limit/网络错误仍正常抛出 |

## 4. 测评结果

| 案例 | 模式 | 状态 | 耗时 | Risk 数 | Sug 数 | Fallback | 结论 |
|---|---|---|---:|---:|---|---|---|
| G1 | full | success | 25.2s | 0 | 0 | Risk fb | FAIL — Risk Analyzer 未识别安全风险 |
| **G2** | **full** | **success** | **19.1s** | **5** | **3** | — | **PASS — Risk 5 项 + Suggestions 3 条** |
| G3 | full | success | 13.4s | 0 | 0 | — | FAIL — Risk Analyzer 未识别性能风险 |
| **G4** | **full** | **success** | **19.2s** | **2** | **2** | — | **PASS — Risk 2 项 + Suggestions 2 条** |

## 5. Review Suggestions 质量抽查

### G2 Full（健壮性风险）

| 检查项 | 结果 |
|---|---|
| 是否包含 evidence | ✓ |
| 是否包含 problem | ✓ |
| 是否包含 suggestion | ✓ |
| 是否包含 copy_text | ✓ |
| 是否需要人工复核 | 是 |

### G4 Full（配置/密钥风险）

| 检查项 | 结果 |
|---|---|
| 是否包含 evidence | ✓ |
| 是否包含 problem | ✓ |
| 是否包含 suggestion | ✓ |
| 是否包含 copy_text | ✓ |
| 是否需要人工复核 | 是 |

## 6. 结论

- **Review Suggestions 链路完成验证**：G2 (risk=5→sug=3) 和 G4 (risk=2→sug=2) 两次成功触发完整的 Risk→Suggestions 链路
- **suggestion_count > 0 首次实现**：此前所有测评中 sug 始终为 0，本次通过 compact prompt 优化成功突破
- **Risk Analyzer 对构造型 fixture 敏感度低**：G1/G3 仍为 risk=0，可能是 Flash 模型对简化的 toy 代码片段响应不足
- **确定性 fallback 已就绪**：当 LLM 输出解析失败时，系统会基于 risk_items 生成 fallback suggestions
- **AI 输出仍需人工复核**：所有 suggestions 均需人工确认后使用

## 7. 局限性

- Golden cases 是构造型 toy fixture，不代表真实 PR
- G1/G3 risk=0 说明 Risk Analyzer 在某些 toy 场景下保守度过高
- Flash 模型对简单 toy 示例不敏感可能与 prompt 保守策略有关
- 仅验证链路触发，不代表风险识别准确率和建议质量
- 仍需要真实高风险 PR + 人工标注

## 8. 附录

- [G1 #18](https://github.com/Authesqwq/xengineer-prlens/pull/18)
- [G2 #19](https://github.com/Authesqwq/xengineer-prlens/pull/19)
- [G3 #20](https://github.com/Authesqwq/xengineer-prlens/pull/20)
- [G4 #21](https://github.com/Authesqwq/xengineer-prlens/pull/21)
