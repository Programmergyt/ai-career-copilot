# 使用样例
```bash
conda activate rag_workflow && D: && cd D:\Py_Projects\ai-career-copilot && python main.py --jd "D:\研究生\Agent测试\JD合集\SAP_AIGC工程师.md" --docs "D:\研究生\Agent测试\个人材料"
```
# 测试脚本
```bash
conda activate rag_workflow
d:
cd D:\Py_Projects\ai-career-copilot 
python main.py --jd "D:\研究生\Agent测试\JD合集\SAP_AIGC工程师.md" --docs "D:\研究生\Agent测试\个人材料"

conda activate rag_workflow && D: && cd D:\Py_Projects\ai-career-copilot && python main.py --jd "D:\研究生\Agent测试\JD合集\SAP_AIGC工程师.md" --docs "D:\研究生\Agent测试\个人材料"
```

# 文件类型
- profile（基本信息，不参与RAG）
- project（个人项目信息，参与RAG）
- internship（实习项目信息，参与RAG）
- skill（个人技能以及掌握的知识点，参与RAG）
- paper（论文，参与RAG）

# 已经完成的改进点（每次改进后都需要更新一下）
- 使用md模板进行渲染
- 使用config.yaml作为配置文件
- 对比不同 Prompt 设计或检索策略，对生成结果进行评估（如准确性、相关性）
- 各内容板块独立生成（每次 LLM 调用只看到该类型的材料）
- 工作流重排序：analyze_jd → classify →（可选提炼）→ build_index → retrieve，技能材料入库前先基于JD进行LLM提炼
- LLM调用改为LangChain（ChatOpenAI），集成LangSmith追踪，在日志中输出LangSmith面板URL
- API Key读取优先级：.env文件 > 系统环境变量（使用python-dotenv）
- 去除工作流中旧接口兼容逻辑（_raw_markdown路径、单Prompt路径）
- Rerank流程优化：embedding recall(top_k=20) → cross-encoder rerank（带JD全文）→ 取top5
- 日志输出详细匹配原因：每个检索到的材料都有LLM生成的匹配理由和选择原因
- 所有日志即时输出到控制台（不再全部做完后统一输出）

# 目前的工作流（每次改进后都需要更新一下）
- 输入JD文件路径、个人材料文件夹路径
- 流程: parse_docs → analyze_jd → classify_docs → extract_profile → refine_skills → build_index → retrieve → generate → self_check → save

# 目前的问题与设想的解决
1. 在最后的selfcheck模块中，如果自检发现覆盖度过低或关键要求未满足，系统应该返回重写或重新检索，而不是直接保存草稿。如果覆盖率太低需要重写，则退回generate_resume结点。
2. 目前你只在 node_refine_skills 对“专业技能”进行了提炼。然而在实际投递中，项目经历的侧重点调整才是最核心的。需要增加 node_refine_projects，在 RAG 检索后、最终生成前，对召回的 Top-K 项目经历进行一次 “JD 对齐重写”。

# 技术栈（对齐requirements.txt）
# Python >= 3.10.19

# LLM 调用（通过 LangChain 统一调用）
langchain-openai>=1.1.7

# LangChain / LangGraph 生态
langchain>=1.2.6
langchain-community>=0.4.1
langgraph>=1.0.6

# .env 文件支持
python-dotenv>=1.2.1

# Embedding & Rerank（阿里云 DashScope）
dashscope==1.25.12

# 向量数据库
chromadb==1.4.1

# 文件解析
pdfplumber==0.11.9
python-docx==1.2.0

# 配置
pyyaml==6.0.3

# Web UI（第三期，先装好）
streamlit==1.55.0

# 测试
pytest==9.0.2