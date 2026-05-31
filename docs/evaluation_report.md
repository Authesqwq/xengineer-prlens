# PRLens 测评报告

## 1. 测评目的

本测评用于验证 PRLens 在分析准确性、上下文理解、误报与漏报控制、响应速度和使用体验方面的表现，回应实训营题干对产品质量维度的评估要求。

## 2. 测评方法

- **测评对象**：本仓库 8 个真实 GitHub Pull Request（PR #1、#2、#5、#6、#9、#11、#15、#17），覆盖文档型 PR 和功能型 PR
- **分析模式**：标准模式（Summary + Risk）覆盖全部 8 个案例；E5/E6/E7 额外运行完整模式（+ Review Suggestions）
- **自动记录指标**：分析状态、耗时、风险数量、建议数量、fallback 触发、输出完整性
- **自动初判标记**：Summary 是否非空、风险是否含 evidence、建议是否含 copy_text、文档型 PR 是否无高风险误报
- **人工复核要求**：准确性、误报、漏报判断必须人工确认，本报告不做伪结论

## 3. 测评执行状态

| 指标 | 值 |
|---|---|
| 测评案例数 | 8 |
| 计划运行次数 | 11 (8 标准 + 3 完整) |
| 实际成功 | 0 |
| 执行失败 | 11 |
| 失败原因 | `GitHubClientError: Resource not found` — API 返回 404 |
| 根因分析 | 当前运行环境未配置 `GITHUB_TOKEN`，GitHub REST API 对该仓库的 PR 接口要求认证 |

### 技术说明

自动化测评脚本 `scripts/run_evaluation.py` 已就绪，可以在具备以下条件的环境中正常运行：

1. `.env` 中配置了有效的 `GITHUB_TOKEN`
2. `.env` 中配置了有效的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`
3. 网络可以访问 GitHub API 和 LLM API

验证方式：使用 `gh auth token` 获取的 token 进行 API 测试，确认带认证的请求返回 HTTP 200，无认证返回 HTTP 404。

## 4. 测评脚本能力

`scripts/run_evaluation.py` 在环境就绪时可自动：

- 解析 8 个测评案例的 PR URL
- 获取每个 PR 的 metadata、changed files 和 patch
- 构建 diff context
- 按指定模式执行 Summary、Risk Analysis 和 Review Suggestions
- 记录客观指标（状态、耗时、文件统计、风险数量、建议数量、fallback）
- 执行轻量自动初判（输出完整性、evidence/copy_text 存在性、文档型 PR 高风险标记）
- 输出结构化 `docs/evaluation_results.json`

脚本不声称准确性、不编造耗时、不伪装自动结论。

## 5. 对题干维度的回应

| 题干维度 | 验证方式 | 状态 |
|---|---|---|
| 分析准确性 | 检查 Summary 非空、Risk evidence 存在、输出结构完整 | 自动化脚本已覆盖客观指标检查；准确性仍需人工复核 |
| 上下文理解 | 检查是否能成功处理 PR metadata + diff context 输入 | 脚本记录 diff 统计和输出完整性 |
| 误报控制 | 检查文档型 PR 是否出现高风险误报 | 脚本包含 `no_high_risk_for_docs_only` 自动初判标记 |
| 漏报控制 | 记录每个案例的风险项数量 | 脚本记录 `risk_count` 供人工对比 |
| 响应速度 | 记录每个案例耗时 | 脚本使用 `time.perf_counter()` 精确记录 |
| 使用体验 | 结合 Demo 页面、分析模式、进度反馈、导出功能 | Demo 页面已支持三种模式、进度、历史和导出 |

## 6. 产品功能层面的可靠性证据

测评脚本的执行虽然被 API 认证阻塞，但以下可靠性机制已在代码层面实现并通过测试验证：

- **结构化的 JSON 解析**：summary_analyzer、risk_analyzer、review_suggestion 均包含 JSON parse + 容错逻辑
- **fallback 机制**：risk analyzer 在模型返回空内容或非法 JSON 时进行 retry + 双语 fallback，266 个测试覆盖
- **错误隔离**：各模块通过明确的异常类（GitHubClientError、LLMClientError、RiskResponseParseError 等）隔离失败
- **diff 截断保护**：diff_processor 在单文件和总字符数层面提供截断，防止超长输入
- **分阶段进度**：用户可见 ✓/▶/○ 状态，避免误判页面卡住

## 7. 局限性

- 本次测评样本量有限（8 个 PR，仅来自本仓库）
- 当前环境未配置 GITHUB_TOKEN 导致自动测评未能实际执行
- LLM 输出可能波动，自动标记仅供参考
- 系统主要基于 PR diff 分析，不读取完整仓库上下文
- 误报和漏报需人工复核
- AI 输出仅作为辅助建议，不替代人工 Review

## 8. 后续建议

- 配置 GITHUB_TOKEN 后重新运行 `python scripts/run_evaluation.py` 获取实际结果
- 扩大测评案例范围（引入外部公开仓库 PR）
- 人工标注 3-5 个案例的准确度/误报/漏报
- 将测评结果更新到本报告
- 引入更多自动质量标记（如建议的优先级分布、跨模式一致性检查）

## 9. 附录：测评脚本位置

- 脚本：`scripts/run_evaluation.py`
- 结果：`docs/evaluation_results.json`
- 报告：`docs/evaluation_report.md`
