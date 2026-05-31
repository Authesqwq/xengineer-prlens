## 功能描述
新增 PR Summary Analyzer，基于 PR metadata 和 diff context 生成变更摘要、主要影响范围和审查关注点。

## 实现思路
构造面向代码变更总结的 prompt，将 PR 信息和 diff context 传入 LLM，解析结构化 JSON 输出。

## 测试方式
- [x] pytest -q
- [x] 验证 summary prompt 构造、正常/空/异常输出处理
