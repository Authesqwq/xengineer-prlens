## 功能描述

新增 GitHub PR 基础信息获取能力，根据 owner、repo 和 pull_number 获取 PR 标题、描述、作者、状态等 metadata。支持可选 GitHub Token 提升 API 频率限制。

## 实现思路

使用 GitHub REST API 获取公开 PR 信息，封装请求构造、响应解析和错误处理。异常分类为 Unauthorized、NotFound、RateLimit 和通用 ClientError。

## 测试方式

- [x] pytest -q
- [x] 使用 mock response 验证 PR 信息字段解析
- [x] 验证 401/403/404/500 和网络异常路径
