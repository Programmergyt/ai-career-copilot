"""Streamlit Web UI — 第一期预留骨架"""

import streamlit as st


def main():
    st.set_page_config(page_title="AI Career Copilot", page_icon="🎯", layout="wide")
    st.title("🎯 AI Career Copilot")
    st.info("Web UI 将在第三期实现。当前请使用 CLI：`python main.py --jd <jd_file> --docs <files...>`")


if __name__ == "__main__":
    main()
