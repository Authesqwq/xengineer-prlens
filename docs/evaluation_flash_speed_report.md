# Flash 模型全量测评与速度对比报告

## 1. 测评目的

验证将默认模型从 Pro 切换到 Flash 后，PRLens 的端到端耗时、成功率和 fallback 情况的变化。

## 2. 测评环境

| 项目 | 内容 |
|---|---|
| 当前模型 | deepseek-v4-flash |
| 分支 | pr20-stability-latency |
| 测评命令 | `python scripts/run_evaluation.py` |
| 测评集 | 14 个正式案例（8 内部 + 6 外部），18 次运行（14 Standard + 4 Full） |
| 压力案例 | 未包含 |
| pytest | 266 passed |

## 3. PR20 / Pro 基线

| 指标 | Pro 基线 |
|---|---:|
| 正式测评成功率 | 18/18 |
| 平均耗时 | 65.8s |
| 中位数耗时 | ~70s |
| Summary 阶段失败 | 0 |
| fallback 次数 | 10 |
| risk_count > 0 | 1-3（不同运行差异大） |
| suggestion_count > 0 | 0 |

## 4. Flash 全量测评结果

| 指标 | Flash |
|---|---:|
| 正式测评成功率 | **18/18 (100%)** |
| 平均耗时 | **22.4s** |
| 中位数耗时 | 26.8s |
| 最快耗时 | 6.9s (E5 外部文档) |
| 最慢耗时 | 30.8s (I7 Full) |
| P90 耗时 | 30.7s |
| Summary 阶段失败 | 0 |
| Full 模式失败 | 0 |
| fallback 次数 | 4 |
| fallback 率 | 22% |
| risk_count > 0 | **3** (I5=1, I7=1, E2=1) |
| suggestion_count > 0 | 0 |

## 5. Pro vs Flash 对比

| 指标 | Pro 基线 | Flash 本次 | 变化 |
|---|---:|---:|---|
| 成功率 | 18/18 | 18/18 | — |
| 平均耗时 | 65.8s | **22.4s** | **↓ 66%** |
| 中位数 | ~70s | **26.8s** | **↓ 62%** |
| 最快耗时 | ~15s | **6.9s** | **↓ 54%** |
| fallback 次数 | 10 | **4** | **↓ 60%** |
| fallback 率 | ~56% | **22%** | **↓ 34pp** |
| risk_count > 0 | 1-3 | 3 | 持平 |
| suggestion_count > 0 | 0 | 0 | 不变 |

## 6. 分组耗时

| 分组 | 样本数 | 成功数 | 平均耗时 | fallback 次数 |
|---|---:|---:|---:|---|
| Standard | 14 | 14 | 22.4s | 3 |
| Full | 4 | 4 | 22.5s | 1 |
| Internal | 10 | 10 | 26.7s | 3 |
| External | 8 | 8 | 17.1s | 1 |
| Fallback 案例 | 4 | 4 | 26.5s | — |
| 正常案例 | 14 | 14 | 21.3s | — |

## 7. 结果解释

1. **Flash 显著降低平均耗时**：从 65.8s 降至 22.4s，降幅 66%。中位数从约 70s 降至 26.8s。所有案例均在 31s 内完成。
2. **Flash 不降低成功率**：Pro 和 Flash 均为 18/18，成功率未受影响。
3. **Flash 显著降低 fallback 率**：fallback 从 10 次（56%）降至 4 次（22%），降幅 60%。模型输出格式更稳定。
4. **Flash 不影响 risk_count**：Flash 下 I5、I7、E2 各识别出 1 个风险，与 Pro 的 1-3 个持平。
5. **Review Suggestions 仍未触发**：suggestion_count 仍为 0，与 Pro 一致。测评集缺乏能触发有风险+有建议的 golden case。
6. **并行优化收益在 Flash 下减弱**：Standard 和 Full 耗时几乎相同（22.4s vs 22.5s），因为 Summary 和 Risk 都是 LLM 调用，并行后的峰值等待被网络波动掩盖。

## 8. 结论

- Flash 在本次测评中**显著降低平均耗时**（66%），成功率保持 100%
- Flash 的 fallback 率从 56% 降至 22%，输出稳定性**明显改善**
- Flash 适合作为**在线 Demo 默认模型**
- Pro 可保留为**高质量分析选项**
- 后续仍需通过人工标注和 golden cases 验证 Flash 与 Pro 的分析质量差异
- Review Suggestions 自动验证仍需引入高风险 golden cases

## 9. 后续建议

- 线上 Demo 默认使用 Flash
- 高质量分析场景使用 Pro
- 保留模型档位切换（环境变量或 UI 选择）
- 继续降低 fallback 率
- 构建 high-risk golden cases 验证 Review Suggestions
- 人工标注 Flash vs Pro 输出的准确度差异
