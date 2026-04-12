<h1 align="center">🎯 AI Career Copilot</h1>

<p align="center">
  基于 LangGraph 多 Agent 协作的智能求职辅助系统
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/LangGraph-1.0-green" alt="LangGraph">
  <img src="https://img.shields.io/badge/LangChain-0.3-orange" alt="LangChain">
  <img src="https://img.shields.io/badge/ChromaDB-1.4-purple" alt="ChromaDB">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

---

## ✨ 项目简介

AI Career Copilot 是一个智能求职辅助系统。给定岗位 JD 和个人背景材料，系统通过多 Agent 协作自动完成：

1. **JD 深度分析** — 结构化拆解岗位要求、技术栈、关键词
2. **定制化简历生成** — RAG 检索个人材料 + Reflection 自检 JD 覆盖度
3. **防守型面试 Q&A** — 针对简历薄弱点和 JD 核心要求生成问答

### 与直接使用大模型的区别

| 维度       | 直接问大模型    | AI Career Copilot                      |
| -------- | --------- | -------------------------------------- |
| 项目理解     | 靠用户自己描述   | RAG 检索个人文档，自动提取技术细节                    |
| JD 分析    | 简单列关键词    | 结构化拆解，输出 JSON                          |
| 简历生成     | 通用内容      | 每段经历独立检索 → 独立生成 → LLM 选优              |
| 质量保证     | 无         | Reflection 自检覆盖度，不通过自动重写               |
| 可追溯性     | 无过程记录     | 完整分析日志 + LangSmith 全链路追踪              |

---

## 🏗️ 系统架构

```
用户输入（CLI: --jd / --profile / --skills / --internships / --projects / --papers）
  │
  ▼
┌─────────────────────────────────────┐
│     Orchestrator（LangGraph）        │  ← 状态图编排，条件路由
│     WorkflowState 贯穿全流程           │
└──────┬──────────┬──────────┬────────┘
       │          │          │
       ▼          ▼          ▼
  ┌─────────┐ ┌─────────┐ ┌──────────┐
  │JD 分析   │ │简历生成   │ │模拟面试    │  ← 三个专业 Agent
  │Agent    │ │Agent    │ │Agent     │
  └────┬────┘ └────┬────┘ └────┬─────┘
       │           │           │
       ▼           ▼           ▼
┌─────────────────────────────────────┐
│           Tool Layer                │
│  文件解析 │ RAG检索+Rerank │ 模板渲染    │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│          Storage Layer              │
│  ChromaDB（向量，按类型分库） │ SQLite    │
└─────────────────────────────────────┘
```

### 工作流（11 个节点）

```
parse_documents → analyze_jd → extract_profile → refine_skills
→ build_index → retrieve → generate_sections → generate_resume
→ self_check ─(pass)→ interview_qa → save_output
              └─(fail)→ generate_resume（回退重写，最多 1 次）
```

> 详细架构设计见 [.agent/architecture.md](.agent/architecture.md)

---

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- [DeepSeek API Key](https://platform.deepseek.com/)（LLM 调用）
- [DashScope API Key](https://dashscope.console.aliyun.com/)（Embedding + Rerank）

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/your-username/ai-career-copilot.git
cd ai-career-copilot

# 2. 创建虚拟环境
conda create -n career-copilot python=3.10 -y
conda activate career-copilot

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key（在项目根目录创建 .env 文件）
echo "DEEPSEEK_API_KEY=your_deepseek_key" >> .env
echo "DASHSCOPE_API_KEY=your_dashscope_key" >> .env
# 可选：LangSmith 追踪
echo "LANGCHAIN_API_KEY=your_langchain_key" >> .env
```

### 运行

```bash
python main.py \
  --jd "path/to/jd.md" \
  --profile "path/to/个人信息/" \
  --skills "path/to/知识点/" \
  --internships "path/to/实习经历A/" "path/to/实习经历B/" \
  --projects "path/to/项目A/" "path/to/项目B/"
```

运行完成后，输出文件在 `./output/` 目录下：

| 文件                 | 说明              |
| ------------------ | --------------- |
| `resume.md`        | 定制化简历           |
| `resume_data.json` | 简历结构化数据         |
| `jd_analysis.json` | JD 结构化分析报告      |
| `interview_qa.md`  | 防守型面试 Q&A       |
| `analysis_log.txt` | 全程分析日志          |

---

## 📖 CLI 参数说明

| 参数             | 必填 | 说明                                           |
| -------------- | -- | -------------------------------------------- |
| `--jd`         | ✅  | JD 文件路径（支持 pdf/docx/md/txt）或直接文本              |
| `--profile`    | ✅  | 个人信息文件夹路径（递归遍历，含基本信息/教育经历/获奖经历）              |
| `--skills`     | ❌  | 技能材料文件夹路径（递归遍历，全部加入同一向量库）                    |
| `--internships`| ❌  | 实习经历路径列表（每个路径=一段实习，各自独立向量库）                  |
| `--projects`   | ❌  | 个人项目路径列表（每个路径=一个项目，各自独立向量库）                  |
| `--papers`     | ❌  | 论文文件夹路径（递归遍历，全部加入同一向量库）                      |
| `--template`   | ❌  | 简历模板路径（默认 `./templates/default.md`）           |

### 支持的文件类型

| 类型   | 说明                | 参与 RAG |
| ---- | ----------------- | ------ |
| 个人信息 | 基本信息、教育经历、获奖      | ❌      |
| 专业技能 | 掌握的知识点和技能         | ✅      |
| 实习经历 | 实习项目文档            | ✅      |
| 项目经历 | 个人项目文档            | ✅      |
| 论文成果 | 论文材料              | ✅      |

---

## ⚙️ 配置

所有配置集中在 `config.yaml`，API Key 通过 `.env` 文件管理。

```yaml
# LLM 配置（支持任意 OpenAI 兼容接口）
llm:
  model: "deepseek-chat"
  api_base: "https://api.deepseek.com"
  api_key_env: "DEEPSEEK_API_KEY"
  temperature: 0.3
  max_tokens: 8192

# Embedding 配置
embedding:
  model: "text-embedding-v4"
  api_key_env: "DASHSCOPE_API_KEY"

# Rerank 配置
rerank:
  model: "gte-rerank-v2"
  api_key_env: "DASHSCOPE_API_KEY"
  top_n: 5

# RAG 参数
rag:
  chunk_size: 512
  chunk_overlap: 50
  search_top_k: 20
  rerank_top_n: 5

# 简历生成控制
resume:
  max_internships: 1    # 最终简历包含的实习经历数量
  max_projects: 1       # 最终简历包含的项目经历数量
```

### 切换 LLM 模型

只需修改 `config.yaml` 中的 `llm` 配置段，无需改代码：

```yaml
# 使用 Qwen
llm:
  model: "qwen-plus"
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key_env: "DASHSCOPE_API_KEY"

# 使用 GPT-4o
llm:
  model: "gpt-4o"
  api_base: "https://api.openai.com/v1"
  api_key_env: "OPENAI_API_KEY"
```

---

## 🔧 技术栈

| 类别          | 技术                                 | 说明                          |
| ----------- | ----------------------------------- | --------------------------- |
| Agent 编排    | LangGraph + LangChain               | 状态图编排，条件路由 + 循环              |
| LLM 调用      | LangChain ChatOpenAI                | OpenAI 兼容接口，一行配置切换模型         |
| LLM 模型      | DeepSeek Chat（默认）                   | 可切换 Qwen/GPT-4o 等           |
| Embedding   | DashScope text-embedding-v4         | 阿里云 Embedding               |
| Rerank      | DashScope gte-rerank-v2             | Cross-Encoder 重排序            |
| 向量数据库       | ChromaDB                            | 轻量本地持久化，按经历分库               |
| 长期记忆        | SQLite                              | JD/简历历史存储                   |
| 文件解析        | pdfplumber + python-docx            | PDF/DOCX/MD/TXT 解析           |
| 配置管理        | PyYAML + python-dotenv              | YAML 配置 + .env 环境变量          |
| 追踪          | LangSmith                           | LLM 全链路追踪（可选）               |
| Web UI      | Streamlit                           | 轻量 Web 界面（开发中）               |

---

## 📁 项目结构

```
ai-career-copilot/
├── main.py                      # CLI 入口
├── config.yaml                  # 全局配置
├── config_loader.py             # 配置加载器
├── requirements.txt             # 依赖清单
│
├── agents/                      # Agent 层
│   ├── jd_analyzer.py           #   JD 分析 Agent
│   ├── resume_writer.py         #   简历生成 + 自检 + 经历选优
│   ├── interview_coach.py       #   模拟面试 Agent
│   ├── doc_classifier.py        #   个人信息提取 + 技能提炼
│   └── llm.py                   #   LLM 统一调用 + LangSmith
│
├── workflow/                    # 工作流
│   ├── graph.py                 #   LangGraph 状态图（11 节点）
│   └── state.py                 #   WorkflowState 类型定义
│
├── rag/                         # RAG 模块
│   ├── indexer.py               #   两级分块 + ChromaDB 入库
│   ├── retriever.py             #   Embedding Recall + Rerank
│   └── embeddings.py            #   DashScope Embedding 封装
│
├── tools/                       # 工具层
│   ├── file_parser.py           #   文件解析（pdf/docx/md/txt/tex）
│   ├── template_renderer.py     #   Markdown 模板渲染
│   ├── match_scorer.py          #   匹配度计算
│   ├── latex_compiler.py        #   LaTeX 编译（可选）
│   └── vector_store.py          #   ChromaDB 封装
│
├── memory/                      # 记忆管理
│   ├── session_memory.py        #   会话内 KV 存储
│   └── long_term_memory.py      #   SQLite 长期记忆
│
├── prompts/                     # Prompt 模板
│   ├── jd_analysis.py
│   ├── resume_generation.py
│   ├── interview_qa.py
│   ├── self_check.py
│   ├── skill_refinement.py
│   └── doc_classification.py
│
├── templates/                   # 简历模板
│   ├── default.md
│   └── default.tex
│
├── ui/app.py                    # Streamlit UI（开发中）
├── data/                        # ChromaDB + SQLite 数据
├── output/                      # 输出目录
└── tests/                       # 单元测试（8 个测试文件）
```

---

## 🧪 测试

```bash
pytest tests/ -v
```

---

## 🗺️ Roadmap

- [x] CLI 入口 + 完整工作流（11 个节点）
- [x] JD 结构化分析
- [x] 多向量库 RAG（每段经历独立库）
- [x] Embedding Recall + Cross-Encoder Rerank
- [x] 分板块独立生成简历 + 经历选优
- [x] Reflection 自检 + 回退重写
- [x] 防守型面试 Q&A 生成
- [x] 技能材料基于 JD 的 LLM 预提炼
- [x] LangSmith 全链路追踪
- [x] SQLite 长期记忆
- [x] config.yaml 统一配置管理
- [ ] Streamlit Web UI
- [ ] 多 JD 批量分析
- [ ] 简历版本对比
- [ ] LaTeX 模板完善 + PDF 输出

---

## 📄 License

MIT





































