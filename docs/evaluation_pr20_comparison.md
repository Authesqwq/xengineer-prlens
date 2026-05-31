# PR20 稳定性与速度优化评测

## 1. 评测目的

验证 PR20 的 Summary fallback、Summary/Risk 并行执行和 Full 模式 Risk 复用是否改善了端到端稳定性、成功率和耗时。

## 2. PR19 基线

| 指标 | PR19 |
|---|---:|
| 正式测评成功率 | 15/18 (83%) |
| 平均耗时 | 65.1s |
| fallback 率 | ~50% |
| Summary 阶段失败 | I3, I7, E4 |
| suggestion_count > 0 | 0 |
| pytest | 266 passed |

## 3. PR20 测评结果

| 指标 | PR20 |
|---|---:|
| pytest | 266 passed |
| 正式测评成功率 | 18/18 (100%, 含补跑 I3/I8) |
| 主跑成功率 | 16/18 → 补跑后 18/18 |
| 平均耗时 | 65.8s |
| Summary 阶段失败 | 0（I3/I8 初次失败为 NameError bug，已修复；修复后全通过） |
| Full 模式失败 | 0 |
| risk_count > 0 | 1 (I8 risk=1) |
| suggestion_count > 0 | 0 |
| fallback 次数 | 10 |

## 4. 优化前后对比

| 指标 | PR19 | PR20 | 变化 |
|---|---:|---:|---|
| 正式测评成功率 | 15/18 | **18/18** (补跑后) | **+17%** |
| 平均耗时 | 65.1s | 65.8s | 持平（并行未在此测评集显著体现，模型耗时为主要瓶颈） |
| Summary 阶段失败 | 3 (I3/I7/E4) | **0** (修复后) | **全部修复** |
| fallback 率 | ~50% | ~56% | 持平（fallback 现在更安全，不再崩溃） |
| suggestion_count > 0 | 0 | 0 | 不变 |
| pytest | 266 | 266 | 不变 |

## 5. 重点案例回归

| 案例 | PR19 问题 | PR20 结果 | 结论 |
|---|---|---|---|
| I3 standard | Summary empty content | ✅ 成功 (83.8s, fallback) | Summary fallback 生效 |
| I7 standard | JSON unterminated string | ✅ 成功 (73.8s, fallback) | Summary fallback 生效 |
| E4 standard | JSON unterminated string | ✅ 成功 (85.6s, fallback) | Summary fallback 生效 |
| I8 standard | JSON expect value | ✅ 成功 (43.4s, risk=1) | 修复后正常 |

## 6. 结论

**Summary fallback 有效**：PR19 中 3 个因 Summary JSON 解析失败而报错的案例（I3/I7/E4）在 PR20 中全部成功，回退到 fallback 或正常输出。初测有 2 个因 `NameError: LLMClientError not defined` 失败 —— 这是新增代码的导入遗漏，不是 fallback 逻辑错误，修复后通过。

**并行 Summary+Risk**：平均耗时未显著变化（65.1s→65.8s），LLM 调用耗时是主要瓶颈，并行优化在测评集中未体现明显收益，但在网络波动场景下可降低个别运行的峰值等待时间。

**Full 模式 Risk 复用**：Full 模式全部成功（I5/I6/E1/E2），risk_count 在 Standard 和 Full 间一致（均为 0），不再出现不一致。

**Review Suggestions 仍未触发**：suggestion_count=0 在所有案例中不变。测评集缺乏能触发有风险+有建议的 golden case，该功能仍需手动 Demo 验证。

**准确性、误报、漏报仍需人工复核**。
