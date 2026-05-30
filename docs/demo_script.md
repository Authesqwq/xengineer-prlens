# PRLens Demo 讲解稿

## 1. 两分钟版本

### 开场

PR Review 的耗时主要来自三个环节：理解变更、判断风险、组织反馈。
PRLens 希望把这些步骤结构化，让 Reviewer 更快完成第一轮理解和风险初筛。

### 演示步骤

1. 打开 PRLens
2. 在侧栏选择中文和标准模式
3. 输入一个公开 GitHub PR 链接
4. 点击「开始分析」
5. 展示分阶段进度和分析耗时
6. 展示 PR 概览和变更文件
7. 展示 AI 变更总结
8. 展示风险分析
9. 展示历史记录
10. 导出 Markdown 报告

### 收尾

PRLens 是一个轻量级 AI Review 辅助工具。它不替代人工 Review，也不会自动写回 GitHub。
它的价值在于帮助 Reviewer 更快形成结构化的第一轮判断。

## 2. 五分钟版本

### 1. 问题背景

PR Review 需要 Reviewer 理解变更目的、查看 diff、识别风险并给出可执行反馈。
随着 AI 生成代码增加，PR 数量和 Review 压力也会提高。

### 2. 产品流程

PRLens 的流程很简单：

1. 输入公开 GitHub PR 链接
2. 获取 PR 基本信息和变更文件
3. 构建 diff 上下文
4. 生成变更总结、风险分析和 Review 建议
5. 展示结构化结果，并支持导出报告

### 3. 系统架构

系统由以下模块组成：

- Streamlit UI
- PR URL Parser
- GitHub Client
- Diff Processor
- LLM Client
- Summary Analyzer
- Risk Analyzer
- Review Suggestion Generator
- Session History
- Markdown Export

### 4. 核心功能

- 快速 / 标准 / 完整三种分析模式
- 中文 / English 双语界面
- 会话级历史记录
- Markdown 报告导出
- 分阶段进度反馈
- 分析耗时展示
- 风险分析 fallback

### 5. 稳定性设计

PRLens 使用结构化输出解析、fallback、错误提示、diff 截断和自动化测试来提高稳定性。
即使模型返回空内容或非法 JSON，页面也不会直接崩溃。

### 6. 能力边界

PRLens 只分析公开 GitHub PR。它不能访问完整仓库上下文，不能运行测试，不能编译代码，
也不会把评论写回 GitHub。所有 AI 输出都需要人工确认。

### 7. 结束语

PRLens 的目标是成为轻量级 AI Review 工作台，帮助用户快速理解 PR、完成风险初筛，
并整理 Review 评论草稿。
