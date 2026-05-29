# PRLens 模型输出 Schema

## 1. SummaryResult

| 字段 | 类型 | 含义 | 必填 | 来源 |
|---|---|---|---|---|
| summary | string | PR 变更概述 | 是 | 模型输出 |
| main_changes | string[] | 主要变更条目 | 是 | 模型输出 |
| affected_areas | string[] | 影响范围（模块/功能） | 是 | 模型输出 |
| uncertainties | string[] | 无法确认的信息 | 是 | 模型输出 |

前端展示：以卡片形式展示 summary，以列表展示 main_changes 和 affected_areas；
uncertainties 在"分析限制"区域展示。

## 2. RiskItem

| 字段 | 类型 | 含义 | 必填 | 来源 |
|---|---|---|---|---|
| risk_type | enum | 风险类型 | 是 | 模型输出 |
| severity | enum(high/medium/low) | 严重程度 | 是 | 模型输出 |
| file_path | string | 关联文件路径 | 是 | 模型输出 |
| evidence | string | 风险依据（diff 引用） | 是 | 模型输出 |
| explanation | string | 风险解释 | 是 | 模型输出 |
| impact | string | 影响范围说明 | 是 | 模型输出 |
| suggestion | string | 修改建议 | 是 | 模型输出 |
| confidence | enum(high/medium/low) | 置信度 | 是 | 模型输出 |
| need_human_check | boolean | 是否需要人工确认 | 是 | 模型输出 |

前端展示：高风险优先排列；severity 用颜色区分；
confidence 低时灰色展示；need_human_check 为 true 时显示"需要人工确认"标签。

## 3. TestSuggestion

| 字段 | 类型 | 含义 | 必填 | 来源 |
|---|---|---|---|---|
| related_file | string | 关联文件 | 是 | 模型输出 |
| test_gap | string | 测试缺失描述 | 是 | 模型输出 |
| suggested_test | string | 建议的测试方向 | 是 | 模型输出 |
| priority | enum(high/medium/low) | 优先级 | 是 | 模型输出 |

前端展示：以独立"测试建议"卡片展示。

## 4. ReviewComment

| 字段 | 类型 | 含义 | 必填 | 来源 |
|---|---|---|---|---|
| title | string | 建议标题 | 是 | 模型输出 |
| problem | string | 问题描述 | 是 | 模型输出 |
| evidence | string | 依据 | 是 | 模型输出 |
| impact | string | 影响说明 | 是 | 模型输出 |
| suggestion | string | 修改建议 | 是 | 模型输出 |
| priority | enum(high/medium/low) | 优先级 | 是 | 模型输出 |
| copy_text | string | 一键复制文本 | 是 | 模型输出 |

前端展示：每条 Review 建议以卡片展示，提供"复制"按钮将 copy_text 写入剪贴板。

## 5. AnalysisResult

| 字段 | 类型 | 含义 | 必填 | 来源 |
|---|---|---|---|---|
| pr_info | object | PR 基本信息 | 是 | GitHub API |
| summary | SummaryResult | 变更总结 | 是 | 模型输出 |
| risks | RiskItem[] | 风险列表 | 是 | 模型输出 |
| test_suggestions | TestSuggestion[] | 测试建议 | 否 | 模型输出 |
| review_comments | ReviewComment[] | Review 建议列表 | 是 | 模型输出 |
| limitations | string[] | 分析限制说明 | 是 | 模型输出 |
| metadata | object | 分析元数据 | 是 | 混合 |

metadata 字段：

| 字段 | 类型 | 来源 |
|---|---|---|
| analyzed_at | string(ISO8601) | 系统生成 |
| prompt_version | string | 系统配置 |
| model_name | string | 系统配置 |
| diff_truncated | boolean | 系统判断 |
| truncation_info | string | 系统生成 |
