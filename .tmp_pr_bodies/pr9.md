## 功能描述
新增最小可用 Streamlit Demo 页面，串联 URL 解析、PR 信息获取、changed files、diff context 和 AI Summary。

## 实现思路
单页面串联后端模块，展示 PR 信息、diff 统计和模型 Summary。

## 测试方式
- [x] pytest -q
- [x] streamlit run app.py 手动验证主流程
