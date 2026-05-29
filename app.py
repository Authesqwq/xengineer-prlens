"""
PRLens - AI PR Review Assistant

A Streamlit application that analyzes GitHub Pull Requests
and provides change summaries, risk identification, and review suggestions.
"""

import streamlit as st

st.set_page_config(page_title="PRLens", page_icon="🔍", layout="centered")

st.title("PRLens")
st.subheader("AI PR Review Assistant")

st.markdown(
    "输入 GitHub Pull Request 链接后，系统将用于生成 PR 变更总结、风险识别和 Review 建议。"
)

pr_url = st.text_input(
    "GitHub PR Link",
    placeholder="https://github.com/owner/repo/pull/123",
)

if st.button("Analyze", type="primary"):
    if not pr_url.strip():
        st.warning("请输入 GitHub PR 链接。")
    else:
        st.info(
            "功能开发中：后续 PR 将实现 PR 链接解析、GitHub 数据获取和 AI 分析能力。"
        )

st.divider()
st.caption("MVP Initialization - PR 1")
