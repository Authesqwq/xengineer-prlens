# PRLens Demo 验证案例

## 文档目的

本文档用于记录 PRLens 的 Demo 验证案例。
它不是严格学术评测集，而是用于保证演示流程可复现，并说明每个案例的预期表现。

## Case 1：octocat/Hello-World #6

- URL：https://github.com/octocat/Hello-World/pull/6
- 推荐模式：快速模式或标准模式
- 选择原因：
  - 公开 PR
  - 变更较小
  - 适合验证基础端到端链路
- 预期表现：
  - PR URL 可以正常解析
  - PR 基本信息可以获取
  - 变更文件可以展示
  - 可以生成变更总结
- Demo 备注：
  - 适合快速现场演示
- 已知风险：
  - 该 PR 很小，可能不会产生有意义的风险项

## Case 2：fastapi/fastapi #12000

- URL：https://github.com/fastapi/fastapi/pull/12000
- 推荐模式：标准模式
- 选择原因：
  - 真实公开项目
  - 适合展示 diff 上下文、风险分析和 fallback
- 预期表现：
  - PR 基本信息和变更文件可以获取
  - Summary 应能说明主要变更
  - Risk Analysis 应返回结构化结果，或在模型输出异常时进入 fallback
- Demo 备注：
  - 适合展示系统鲁棒性
- 已知风险：
  - 风险分析可能因模型输出触发 fallback
  - 这是可接受结果，因为 PRLens 已实现 fallback

## Case 3：中等复杂度自选 PR

- URL：待验证
- 推荐模式：完整模式
- 选择原因：
  - 用于展示 Review Suggestions
- 预期表现：
  - 可以生成 Summary、Risk Analysis 和 Review Suggestions
- Demo 备注：
  - 最终录屏前补充

## 验证清单

- [ ] PR URL 可以解析
- [ ] GitHub PR 信息可以获取
- [ ] 变更文件可以展示
- [ ] Diff 上下文统计可以展示
- [ ] 分析进度正常更新
- [ ] 分析耗时正常显示
- [ ] Summary 可以生成
- [ ] Risk Analysis 表现正常
- [ ] 完整模式下，在存在风险项时可以生成 Review Suggestions
- [ ] 导出报告可用
- [ ] 历史记录恢复可用
