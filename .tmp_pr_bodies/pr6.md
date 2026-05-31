## 功能描述
新增 diff processor，清洗 changed files、统计 diff 信息、截断过长 patch 并组装 LLM 上下文。

## 实现思路
将文件变更转换为统一 diff context，控制文件数量和单文件/总字符数限制，避免上下文过长影响模型稳定性。

## 测试方式
- [x] pytest -q
- [x] 验证 diff context 组装、文件数限制、patch 截断和字符统计
