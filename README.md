# PRLens

## 项目简介

PRLens 是一个面向开发者的 AI PR Review 助手。用户输入 GitHub PR 链接后，系统将自动获取 PR 变更内容，并生成 PR 变更总结、风险代码识别和结构化 Review 建议。

## 选题

本项目对应 XEngineer 实训选题三：AI PR Review 助手。

## MVP 功能规划

后续将逐步实现：

1. GitHub PR 链接解析
2. PR 基本信息获取
3. PR changed files 和 patch 获取
4. Diff 清洗与截断
5. AI PR 变更总结
6. 风险代码识别
7. Review 建议生成
8. 示例 PR 与错误处理
9. README 和 Demo 指南完善

## Current Progress

- PR1: Project initialized
- PR2: AI product documents added
- PR3: GitHub PR URL parser added
- PR4: GitHub PR basic info client added
- PR5: GitHub PR changed files client added
- PR6: Diff processor added
- PR7: LLM client added
- PR8: PR summary analyzer added
- PR9: Minimal Streamlit demo added
- PR10: Risk analyzer added
- PR11: Risk analysis integrated into demo
- PR12: Review suggestion generator added

## Run Tests

```bash
pytest -q
```

## Run Demo

1. Copy `.env.example` to `.env`.
2. Fill in LLM configuration.
3. Run:

```bash
streamlit run app.py
```

The demo currently calls the LLM twice: once for change summary and once for risk analysis.

## Environment Variables

Copy `.env.example` and configure local secrets in `.env`.

Required for GitHub API:
- `GITHUB_TOKEN` optional for public repositories, recommended to avoid rate limits

Required for LLM calls:
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL`

## 当前状态

当前 PR 仅完成项目初始化和最小可运行页面。后续功能将在独立 PR 中逐步实现。

## 技术栈

- Python
- Streamlit
- GitHub REST API
- LLM API
- python-dotenv
- pydantic

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 环境变量

复制 `.env.example` 为 `.env`，并填写必要变量。当前 PR 不会读取这些变量，后续 PR 会使用。

## Product Documents

- [PRD](docs/prd.md)
- [Evaluation Plan](docs/evaluation.md)

## Prompt Documents

- [Summary Prompt](prompts/summary_prompt.md)
- [Review Prompt](prompts/review_prompt.md)
- [Output Schema](prompts/output_schema.md)

## 开发规范

- 每个 PR 只实现一个功能；
- 每个 PR 合并后 main 分支保持可运行；
- 不提交 `.env` 和任何密钥；
- 调研原始数据不进入正式项目仓库。
