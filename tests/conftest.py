"""conftest.py — 测试夹具与公共配置"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_dir(tmp_path):
    """提供一个临时目录。"""
    return tmp_path


@pytest.fixture
def sample_jd_text():
    """提供一段示例 JD 文本。"""
    return """
【岗位名称】AI 工程师实习生
【公司】美团
【职责】
1. 参与大模型应用开发，包括 RAG、Agent 等方向
2. 负责 Prompt 工程和模型评测
3. 参与数据处理和模型训练流水线建设

【要求】
- 本科及以上学历，计算机相关专业
- 熟悉 Python，了解 PyTorch 或 TensorFlow
- 了解 LLM、RAG、LangChain 等技术
- 有 NLP 或大模型相关项目经历优先
- 良好的沟通能力和团队协作精神
"""


@pytest.fixture
def sample_jd_analysis():
    """提供一个已解析的 JD 分析结果。"""
    return {
        "company_info": {"industry": "互联网", "company_type": "大厂"},
        "position_title": "AI 工程师实习生",
        "core_responsibilities": [
            "大模型应用开发（RAG、Agent）",
            "Prompt 工程和模型评测",
            "数据处理和模型训练流水线",
        ],
        "hard_requirements": {
            "education": "本科及以上",
            "experience": "实习",
            "required_skills": ["Python", "PyTorch", "LLM", "RAG", "LangChain"],
        },
        "soft_requirements": ["沟通能力", "团队协作"],
        "tech_stack": ["Python", "PyTorch", "TensorFlow", "LangChain", "RAG"],
        "ability_model": ["大模型应用开发", "RAG 系统设计", "Prompt 工程"],
        "keywords": ["AI", "LLM", "RAG", "Agent", "Python", "NLP"],
    }


@pytest.fixture
def sample_md_file(tmp_path):
    """创建一个临时 Markdown 文件并返回路径。"""
    content = """# 我的项目经历

## 项目A：RAG 故障诊断系统
- 使用 LangChain + ChromaDB 构建 RAG 问答系统
- 技术栈：Python, LangChain, ChromaDB, OpenAI API
- 实现了文档检索、Rerank、答案生成全流程

## 技能
- Python (熟练)
- PyTorch (了解)
- LangChain (熟练)
- RAG 系统开发
"""
    fpath = tmp_path / "personal.md"
    fpath.write_text(content, encoding="utf-8")
    return str(fpath)


@pytest.fixture
def sample_txt_file(tmp_path):
    """创建一个临时 txt 文件。"""
    content = "这是一段纯文本个人介绍。熟悉 Python 和机器学习。本科专业人工智能，硕士专业控制工程。"
    fpath = tmp_path / "intro.txt"
    fpath.write_text(content, encoding="utf-8")
    return str(fpath)
