## 功能描述
新增 PR changed files 获取能力，读取变更文件的路径、状态、增删行数和 patch 内容，支持分页和文件数量上限。

## 实现思路
调用 GitHub REST API 的 PR files 接口，封装分页请求、字段解析和异常处理。默认每页 100 条，最大 3000 文件。

## 测试方式
- [x] pytest -q
- [x] 验证 changed files 字段解析、无 patch、分页和异常响应
