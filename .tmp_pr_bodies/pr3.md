## 功能描述

新增 GitHub Pull Request URL 解析能力，将用户输入的 PR 链接解析为 owner、repo 和 pull_number，为后续 GitHub API 请求提供结构化参数。

## 实现思路

通过正则和 URL 结构校验识别合法 GitHub PR 链接，只接受 `github.com/{owner}/{repo}/pull/{number}` 格式。非法链接返回明确错误，避免后续 API 请求失败。

## 测试方式

- [x] pytest -q
- [x] 验证合法 GitHub PR URL 可正确解析
- [x] 验证非法 URL、缺失 PR 编号、非 GitHub 链接会被拒绝
