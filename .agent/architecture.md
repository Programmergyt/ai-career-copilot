# AI Career Copilot — 求职 Agent

## 项目定位

一个基于 LangGraph 多 Agent 协作的求职辅助系统。给定岗位 JD 和个人背景材料，自动完成 JD 深度分析、简历定制生成、模拟面试问答三大任务。

### 面试里一句话介绍

> 我做了一个多 Agent 协作的求职辅助系统。用户导入 JD 和个人项目/技能材料后，系统会通过 JD 分析 Agent、简历生成 Agent、模拟面试 Agent 三个专业 Agent 协作完成定制化求职准备，核心用了 LangGraph 做工作流编排、RAG 做个人知识检索、ReAct 做工具调用。

### 为什么做这个项目

1. 直接用 ChatGPT 写简历的问题是：它不了解你的项目细节，只能泛泛而谈
2. 手动调整简历针对不同 JD 非常耗时
3. 这个项目把 Agent、RAG、工具调用、工作流编排、记忆管理串在一起，正好覆盖 AI Agent 实习的核心技术栈

### 这个项目和"直接用大模型"的区别

| 维度       | 直接问大模型    | AI Career Copilot          |
| -------- | --------- | -------------------------- |
| 项目理解     | 靠用户自己描述   | RAG 检索项目源码和文档，自动提取技术细节     |
| JD 分析深度  | 简单列几个关键词  | 结构化拆解行业、技术栈、能力要求、与个人匹配度    |
| 简历生成     | 通用内容，无针对性 | 根据 JD 分析结果 + 个人项目检索结果定制化生成 |
| 面试准备     | 泛泛而谈      | 基于 JD 和简历内容生成针对性技术问答       |
| 可追溯和可解释性 | 无过程记录     | 完整记录 Agent 思考、行动、观察过程      |
| 持续使用     | 每次重新输入    | 有记忆系统，积累用户偏好和历史版本          |


---

## 系统架构

### 整体架构图

```
用户输入（JD + 个人材料）
        │
        ▼
┌─────────────────────────────────┐
│       Orchestrator（LangGraph） │  ← 工作流编排，状态管理
│         工作流状态机             │
└──────┬──────┬──────┬────────────┘
       │      │      │
       ▼      ▼      ▼
  ┌────────┐ ┌────────┐ ┌────────┐
  │JD 分析  │ │简历生成  │ │模拟面试  │   ← 三个专业 Agent
  │ Agent  │ │ Agent  │ │ Agent  │
  └───┬────┘ └───┬────┘ └───┬────┘
      │          │          │
      ▼          ▼          ▼
┌─────────────────────────────────┐
│         Tool Layer              │  ← 工具层
│  文件解析 │ RAG检索 │ 模板渲染     │
│  格式转化 │ 代码分析 │ 结构化输出    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│         Storage Layer           │  ← 存储层
│  ChromaDB（向量） │ SQLite（结构化）│
│  文件系统（输出）                  │
└─────────────────────────────────┘
```
### Agent 架构选择

**整体：Plan-and-Execute + 内部 ReAct**

理由：
- 求职辅助是一个有明确步骤的任务：先分析 JD → 再匹配个人材料 → 再生成简历 → 再准备面试
- 这种"先规划后执行"的模式天然适合 Plan-and-Execute
- 每个子 Agent 内部在执行时，需要动态决定调什么工具、检索什么内容，这部分用 ReAct

面试里可以这样说：

> 整体用 Plan-and-Execute 做任务拆解和顺序编排，每个子 Agent 内部用 ReAct 做工具调用和动态决策。这样既有全局规划性，又有局部灵活性。

### 为什么用 LangGraph 而不是纯 LangChain Chain

- LangChain 的 Chain 是线性的，难以表达条件分支和循环
- LangGraph 基于状态图，可以做条件路由、循环、并行、人工干预
- 求职流程中有多个决策点（比如 JD 分析结果决定走技术岗还是产品岗模板），需要状态机
- LangGraph 是 LangChain 官方推荐的 Agent 编排方案，面试认可度高

---

## 三个核心 Agent 设计

### Agent 1：JD 分析 Agent

**职责**：深度解析岗位描述，输出结构化分析报告

**输入**：JD 文本（从文件解析或用户粘贴）

**输出**：结构化 JD 分析报告（JSON + Markdown）

**分析维度**：

| 维度     | 说明                             |
| ------ | ------------------------------ |
| 行业与公司  | 所属行业、公司类型（互联网/国企/外企等）          |
| 岗位核心职责 | 这个岗位日常做什么                      |
| 硬性要求   | 学历、年限、必须掌握的技术栈                 |
| 软性要求   | 沟通、团队、业务理解等                    |
| 技术栈拆解  | 涉及的语言、框架、工具、平台，按优先级排序          |
| 能力模型   | 这个岗位最看重的 3-5 项能力               |
| 个人匹配度  | 与用户技能/项目的匹配程度（高/中/低），列出匹配项和差距项 |

**内部工具**：
- `parse_file`：解析 JD 文件（pdf/docx/md）
- `search_personal_knowledge`：RAG 检索个人知识库，用于匹配度分析

**Agent 模式**：ReAct — 先读 JD，再检索个人知识库做匹配分析

---

### Agent 2：简历生成 Agent

**职责**：根据 JD 分析结果和个人材料，生成定制化简历

**输入**：
- JD 分析报告（来自 Agent 1）
- 用户个人知识库（RAG 检索）
- 简历模板（LaTeX 或 Markdown）

**输出**：
- 定制化 `.tex` 或 `.md` 简历文件
- 简历修改说明（为什么这样写，针对 JD 的哪些要求）

**核心逻辑**：

1. 根据 JD 分析报告确定简历侧重点
2. 通过 RAG 检索用户项目库，提取与 JD 最相关的项目细节
3. 对每个项目，用 STAR 法则重新组织描述
4. 根据能力模型调整技能排列顺序
5. 填充模板生成最终简历
6. 自检：检查是否覆盖了 JD 的核心要求

**内部工具**：
- `search_personal_knowledge`：RAG 检索项目详情
- `search_code_knowledge`：RAG 检索源码，提取技术细节
- `render_template`：将内容填充到 LaTeX/Markdown 模板
- `self_check`：对生成的简历做 JD 匹配度验证

**Agent 模式**：ReAct + Reflection — 先生成，再自检修正

面试亮点：

> 简历生成 Agent 不是简单填模板，而是会先检索项目源码提取技术细节，再用 STAR 法则组织，最后还会做一轮自检确保覆盖了 JD 核心要求。这体现了 Reflection 架构的思想。

---

### Agent 3：模拟面试 Agent

**职责**：基于 JD 和生成的简历，预测面试问题并生成参考回答

**输入**：
- JD 分析报告
- 生成的简历内容
- 个人知识库（RAG 检索补充细节）

**输出**：模拟面试 Q&A 文档（Markdown）

**问题生成维度**：

| 类型   | 说明                        |
| ---- | ------------------------- |
| 项目深挖 | 针对简历中每个项目的技术选型、难点、优化、量化结果 |
| 技术基础 | JD 中提到的核心技术栈的基础问题         |
| 场景设计 | "如果让你重新设计这个系统，你会怎么做"类型    |
| 行为面试 | STAR 法则的"遇到困难怎么办""团队合作"等  |
| 反问预测 | 面试官可能问的"你有什么想问我的"的参考      |

**内部工具**：
- `search_personal_knowledge`：检索项目细节，让回答更具体
- `search_code_knowledge`：检索源码，回答技术实现细节

**Agent 模式**：ReAct — 根据 JD 和简历内容动态决定需要检索哪些项目细节

---

## LangGraph 工作流设计

### 状态定义

```python
from typing import TypedDict, Optional

class WorkflowState(TypedDict):
    # 输入
    jd_text: str                    # JD 原文
    personal_docs: list[str]        # 个人材料文件路径
    template_path: str              # 简历模板路径
    
    # 中间状态
    jd_analysis: Optional[dict]     # JD 分析结果
    matched_projects: Optional[list]# RAG 匹配到的项目
    resume_draft: Optional[str]     # 简历草稿
    resume_final: Optional[str]     # 自检后的最终简历
    
    # 输出
    resume_file: Optional[str]      # 简历文件路径
    interview_qa: Optional[str]     # 面试 Q&A 内容
    analysis_log: Optional[str]     # 完整分析过程日志
    
    # 控制
    current_step: str               # 当前步骤
    need_human_review: bool         # 是否需要人工确认
```

### 状态图

```
START
  │
  ▼
[文档解析与入库] ── 解析所有输入文件，建立/更新向量知识库
  │
  ▼
[JD 分析] ── JD 分析 Agent 执行
  │
  ├─ 匹配度过低 ──→ [提示用户：该岗位匹配度低，是否继续？]
  │                         │
  │                    用户确认继续
  │                         │
  ▼                         ▼
[简历生成] ── 简历生成 Agent 执行
  │
  ▼
[简历自检] ── Reflection：检查 JD 覆盖度
  │
  ├─ 覆盖度不足 ──→ 回到 [简历生成] 重新调整（最多 2 轮）
  │
  ▼
[模拟面试生成] ── 模拟面试 Agent 执行
  │
  ▼
[输出汇总] ── 生成所有输出文件
  │
  ▼
END
```

---

## 工具设计

### 工具清单

| 工具名                         | 功能                                  | 输入               | 输出             |
| --------------------------- | ----------------------------------- | ---------------- | -------------- |
| `parse_file`                | 解析 pdf/docx/md/tex 文件               | 文件路径             | 纯文本            |
| `parse_code`                | 解析源码文件，提取函数/类/注释/结构                 | 文件路径或目录          | 结构化代码摘要        |
| `vector_store_add`          | 将文本分块后写入向量数据库                       | 文本 + 元数据         | 写入确认           |
| `search_personal_knowledge` | 语义检索个人知识库（项目、技能、经历）                 | 查询文本 + TopK      | 相关文档片段列表       |
| `search_code_knowledge`     | 语义检索代码知识库（源码片段、函数、架构说明）             | 查询文本 + TopK      | 相关代码片段列表       |
| `render_latex_template`     | 将结构化内容填充到 LaTeX 模板                  | 模板路径 + 内容字典      | .tex 文件路径      |
| `render_markdown_template`  | 将结构化内容填充到 Markdown 模板               | 模板路径 + 内容字典      | .md 文件路径       |
| `compile_latex`             | 本地编译 LaTeX 为 PDF（允许失败，失败则直接给tex或md） | .tex 文件路径        | .pdf 文件路径      |
| `save_markdown`             | 保存 Markdown 到指定路径                   | 内容 + 路径          | 文件路径           |
| `jd_match_score`            | 计算个人技能与 JD 的匹配度                     | JD 分析结果 + 个人技能列表 | 匹配度评分 + 匹配/差距项 |

### LaTeX 编译方案

Overleaf 没有公开编译 API，改为本地编译：
- 方案 A：本地安装 TeX Live，用 `latexmk` 编译（推荐，最稳定）
- 方案 B：用 Docker 镜像 `texlive/texlive:latest` 编译（无需本地安装）
- 方案 C：只输出 `.tex` + `.md`，用户自行编译 PDF（最轻量的兜底方案）

项目默认支持方案 A，检测不到 `latexmk` 时降级为方案 C。

---

## RAG 设计

### 知识库设计

项目需要两个独立的向量知识库：

| 知识库     | 存储内容                | 分块策略                          | 用途       |
| ------- | ------------------- | ----------------------------- | -------- |
| 个人文档知识库 | 项目 README、技能描述、实习经历 | 按段落分块，512 tokens，重叠 50 tokens | 纯文本      |
| 代码知识库   | 源码文件                | 按函数/类分块，保留文件路径和函数签名作为元数据      | 检索具体技术实现 |

### 检索策略

```
用户/Agent 查询
      │
      ▼
  Embedding（使用与入库相同的模型）
      │
      ▼
  ChromaDB 向量检索（TopK = 10）
      │
      ▼
  Rerank（用 LLM 或 cross-encoder 对 TopK 结果重排序）
      │
      ▼
  取 Top 3-5 作为上下文注入 prompt
```

### Embedding 模型选择

- text-embedding-v4（阿里云，便宜）

### Rerank模型选择
- gte-rerank-v2（阿里云，便宜）

### 分块策略细节

```python
# 文档分块
from langchain_text_splitters  import RecursiveCharacterTextSplitter

doc_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
    separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；"]
)

# 代码分块（按函数/类级别）
from langchain_text_splitters  import Language, RecursiveCharacterTextSplitter

code_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,  # 也支持 JAVA, JS 等
    chunk_size=1000,
    chunk_overlap=100,
)
```

### 元数据设计

每条向量记录附带元数据，方便过滤和溯源：

```python
metadata = {
    "source_file": "项目A/README.md",     # 来源文件
    "doc_type": "project_readme",          # 文档类型：project_readme / skill / experience / code
    "project_name": "RAG故障诊断系统",       # 所属项目
    "chunk_index": 3,                       # 分块序号
}
```

---

## 记忆设计

### 短期记忆（会话内）

- 用 LangGraph 的 `State` 天然管理，工作流执行过程中状态自动传递
- 包含：当前 JD 分析结果、已检索到的项目片段、生成的简历草稿等

### 长期记忆（跨会话）

存储在 SQLite 中：

| 字段              | 说明                  |
| --------------- | ------------------- |
| user_id         | 用户标识                |
| skill_tags      | 用户技能标签（自动提取 + 手动补充） |
| preferred_style | 偏好的简历风格（简洁/详细/学术）   |
| history_jds     | 分析过的 JD 记录          |
| history_resumes | 生成过的简历版本            |
| feedback        | 用户对生成结果的反馈          |

### 面试里怎么讲记忆

> 短期记忆用 LangGraph 的状态图天然管理，工作流中的中间结果在状态里自动流转；长期记忆用 SQLite 存储用户偏好、历史 JD 和历史简历版本，让系统在多次使用后越来越了解用户。

---

## 输入输出定义

### 输入

| 输入    | 格式                | 备注                          |
| ----- | ----------------- | --------------------------- |
| 岗位描述  | 文件路径/用户输入文本       | 支持 pdf、docx、markdown        |
| 个人技能  | 文件路径/用户输入文本       | 支持 pdf、docx、markdown        |
| 实习项目  | 文件夹路径/文件路径/用户输入文本 | 支持 markdown（README）+ 主流语言源码 |
| 个人项目  | 文件夹路径/文件路径/用户输入文本 | 支持 markdown（README）+ 主流语言源码 |
| 获奖与证书 | 文件路径/用户输入文本       | 支持 pdf、docx、markdown        |
| 简历模板  | 文件路径              | 支持 .tex 和 .md               |

注：源码支持 Python、Java、C++、JavaScript/TypeScript。

### 输出

| 输出     | 格式                 | 备注                              |
| ------ | ------------------ | ------------------------------- |
| JD 分析  | JSON + Markdown    | 结构化分析报告，含匹配度评估                  |
| 定制简历   | .tex + .pdf（或 .md） | 本地 latexmk 编译 PDF，无环境时降级为纯 .tex |
| 模拟面试   | Markdown           | 分类型的面试 Q&A                      |
| 分析过程日志 | Markdown           | Agent 的思考、行动、观察全过程记录            |

---

## 技术栈

| 类别        | 选择                      | 理由                   |
| --------- | ----------------------- | -------------------- |
| Agent 框架  | LangGraph + LangChain   | 状态图编排，支持条件路由/循环/人工干预 |
| 向量数据库     | ChromaDB                | 轻量、纯 Python、无需额外服务   |
| 关系数据库     | SQLite                  | 零配置，适合单用户场景          |
| Embedding | text-embedding-v4       | 阿里云、便宜               |
| LLM       | DeepSeek API / Qwen API | 便宜或免费，中文能力强          |
| LaTeX 编译  | latexmk（本地）             | 稳定可靠                 |
| Web UI    | Streamlit               | 极轻量，Python 原生，快速搭建   |
| Python    | 3.10+                   |                      |

### LLM 选择说明

项目设计为 LLM 可替换：
- 开发调试：用 DeepSeek API（极便宜）或 Qwen 免费额度
- 本地演示：可接 Ollama 跑 Qwen2.5 等开源模型
- 有预算时：可切换为 GPT-4o / Claude

通过 LangChain 的 `ChatModel` 抽象或者openai接口，切换模型只需改配置，不改代码。

---

## 项目目录结构

```
ai-career-copilot/
├── README.md                    # 项目说明（GitHub 展示核心）
├── requirements.txt
├── config.yaml                  # 模型、路径、参数配置
├── main.py                      # 入口：CLI 或 Streamlit 启动
│
├── agents/                      # Agent 定义
│   ├── jd_analyzer.py           # JD 分析 Agent
│   ├── resume_writer.py         # 简历生成 Agent
│   └── interview_coach.py       # 模拟面试 Agent
│
├── workflow/                    # 工作流编排
│   ├── graph.py                 # LangGraph 状态图定义
│   └── state.py                 # 状态类型定义
│
├── tools/                       # 工具实现
│   ├── file_parser.py           # 文件解析（pdf/docx/md/code）
│   ├── vector_store.py          # ChromaDB 读写封装
│   ├── template_renderer.py     # 模板渲染
│   ├── latex_compiler.py        # LaTeX 编译
│   └── match_scorer.py          # 匹配度计算
│
├── rag/                         # RAG 模块
│   ├── indexer.py               # 文档/代码入库
│   ├── retriever.py             # 检索 + Rerank
│   └── embeddings.py            # Embedding 模型封装
│
├── memory/                      # 记忆管理
│   ├── session_memory.py        # 会话内状态
│   └── long_term_memory.py      # SQLite 长期记忆
│
├── prompts/                     # Prompt 模板
│   ├── jd_analysis.py
│   ├── resume_generation.py
│   ├── interview_qa.py
│   └── self_check.py
│
├── templates/                   # 简历模板
│   ├── default.tex
│   └── default.md
│
├── ui/                          # Web UI
│   └── app.py                   # Streamlit 界面
│
├── output/                      # 默认输出目录
│
└── tests/                       # 测试
    ├── test_jd_analyzer.py
    ├── test_resume_writer.py
    └── test_rag.py
```

---

## 开发分期计划

### 第一期：核心流程跑通（MVP）

**目标**：输入 JD + 个人材料，输出定制简历

- [ ] 文件解析工具（pdf/docx/md）
- [ ] 文档 RAG 入库 + 检索
- [ ] JD 分析 Agent（基础版，输出结构化 JSON）
- [ ] 简历生成 Agent（基础版，填充 Markdown 模板）
- [ ] LangGraph 串联 JD 分析 → 简历生成
- [ ] CLI 入口

### 第二期：增强质量

- [ ] 代码解析 + 代码知识库
- [ ] Rerank 模块
- [ ] 简历 Reflection 自检
- [ ] LaTeX 模板支持 + 编译
- [ ] 匹配度评分工具

### 第三期：模拟面试 + UI

- [ ] 模拟面试 Agent
- [ ] Streamlit Web UI
- [ ] 分析过程日志导出
- [ ] 长期记忆（SQLite）

### 第四期：打磨细节

- [ ] 多 JD 批量分析
- [ ] 简历版本对比
- [ ] 单元测试
- [ ] README 完善 + Demo GIF

---

## 面试亮点总结

### 技术亮点

1. **多 Agent 协作**：不是单 Agent 做所有事，而是 JD 分析、简历生成、模拟面试三个专业 Agent 各司其职
2. **LangGraph 状态图编排**：用状态机管理工作流，支持条件分支（匹配度低时提示）、循环（Reflection 自检）、人工干预
3. **双知识库 RAG**：文档知识库 + 代码知识库分开管理，分块策略不同，检索粒度不同
4. **Reflection 自检**：简历生成后会检查 JD 覆盖度，不合格会重新调整
5. **工具调用闭环**：文件解析、向量检索、模板渲染、LaTeX 编译都封装为标准 Tool
6. **LLM 可替换**：通过 LangChain 抽象层，一行配置切换模型

### 工程亮点

1. 模块化设计：agents / tools / rag / memory / workflow 清晰分层
2. 本地优先：向量库用 ChromaDB，关系库用 SQLite，无需外部服务
3. 可演示：Streamlit UI 可以直接展示完整流程

### 面试常见追问准备

**Q：为什么用 LangGraph 而不是直接写 Chain？**
> 因为求职流程有条件分支和循环（如匹配度判断、简历自检），Chain 是线性的处理不了，LangGraph 的状态图天然支持条件路由和循环。

**Q：RAG 检索效果不好怎么办？**
> 三层保障：1) 分块策略针对文档和代码分别设计；2) 检索后加 Rerank 重排序；3) 元数据过滤，先按项目名/文档类型缩小范围再做语义匹配。

**Q：简历生成的质量怎么保证？**
> 两层保证：1) 输入端用 RAG 检索真实项目细节而不是让模型编；2) 输出端用 Reflection 自检，检查是否覆盖了 JD 核心要求，不合格会重新生成。

**Q：这个项目和直接用 ChatGPT 写简历有什么区别？**
> 三个核心区别：1) ChatGPT 不了解你的项目源码细节，我的系统会 RAG 检索源码提取技术实现；2) ChatGPT 没有结构化的 JD 分析，我的系统会拆解 JD 并做匹配度评估；3) ChatGPT 没有持久化记忆，我的系统会记住用户偏好和历史版本。

**Q：你这个项目体现了哪些 Agent 的核心能力？**
> 覆盖了 Agent 的六大模块：感知（接收 JD 和材料）、记忆（短期状态 + 长期 SQLite）、规划（Plan-and-Execute 任务拆解）、决策（根据匹配度选择策略）、工具（文件解析/RAG/模板渲染/编译）、行动（生成简历和面试 Q&A）。

---

## 可直接背的项目介绍

> 这个项目是一个基于 LangGraph 的多 Agent 求职辅助系统。用户导入岗位 JD 和个人项目材料后，系统通过三个专业 Agent 协作完成求职准备：JD 分析 Agent 做结构化岗位解析和匹配度评估，简历生成 Agent 通过 RAG 检索项目源码和文档细节来定制简历并做 Reflection 自检，模拟面试 Agent 基于 JD 和简历生成针对性面试问答。技术上，整体用 Plan-and-Execute 架构做任务编排，每个子 Agent 内部用 ReAct 做工具调用，RAG 层分为文档知识库和代码知识库分别管理，记忆层用 LangGraph 状态 + SQLite 实现。