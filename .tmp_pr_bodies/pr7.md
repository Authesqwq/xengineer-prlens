## 功能描述
新增 OpenAI-compatible LLM client，统一封装模型调用，为 Summary、Risk 和 Review Suggestion 模块提供可复用的调用能力。

## 实现思路
通过环境变量读取 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL。封装请求构造、响应解析和错误处理。

## 测试方式
- [x] pytest -q
- [x] 验证正常响应解析、缺少配置、网络错误和异常响应
