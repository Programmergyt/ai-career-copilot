# System Design

架构设计、模块划分、数据流、存储设计、技术栈。

---

## 1. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 前端 | Vue3 | 3.x |
| 后端框架 | FastAPI | 0.115+ |
| Agent 编排 | LangGraph | 1.0+ |
| LLM 调用 | LangChain + langchain-openai | 1.2+ |
| 可观测性 | LangSmith | - |
| 向量数据库 | ChromaDB | 1.4+ |
| Embedding | DashScope (text-embedding-v4) | - |
| Rerank | DashScope (gte-rerank-v2) | - |
| LLM Provider | DeepSeek (deepseek-chat) | - |
| 会话存储 | Redis | 7.0+ |
| 持久化存储 | MySQL | 8.0+ |
| 文件解析 | pdfplumber, python-docx | - |
| 配置 | PyYAML + python-dotenv | - |
| HTML→PDF | WeasyPrint | - |
| 测试 | pytest | 9.0+ |
| Python | >= 3.10 | - |

---

## 2. 模块划分

```
ai-career-copilot/
├── backend/                   # 后端工程根目录
│   ├── main.py                # FastAPI 入口
│   ├── config.yaml            # 全局配置
│   ├── config_loader.py       # 配置加载
│   ├── agents/                # Agent 实现
│   ├── api/                   # API 路由
│   ├── log/                   # 日志模块
│   ├── models/                # LLM / Embedding / Rerank 工厂
│   ├── prompts/               # Prompt 模板
│   ├── sql/                   # 数据库初始化脚本
│   ├── storage/               # 数据访问层
│   ├── templates/             # HTML 简历模板
│   ├── test/                  # 后端测试
│   ├── tools/                 # 文件解析与模板渲染工具
│   └── workflow/              # LangGraph 状态与图编排
├── frontend/                  # 前端工程目录（Vue3）
├── docs/                      # 设计与需求文档
├── README.md
└── 生成结果.html              # 本地生成示例
```

---

## 3. 数据流

### 3.1 内容链路

```
用户输入（文本/文件）
  ↓
FastAPI /api/chat
  ↓
Planner Agent
  ├─ Intent Classifier → intent
  ├─ State Diff Planner → execution_plan
  └─ Execution Orchestrator
       ↓
     JD Agent → state.job
       ↓
     Profile Agent → state.candidate_profile
       ↓
     Gap Analysis Agent → state.gaps, state.questions_to_ask
       ↓
     Resume Content Agent → state.resume_content_json
       ↓
     Resume Render Agent → state.render_config, state.resume_html
       ↓
     Interview Agent → state.interview_qa
       ↓
  Planner/Agents → state.section_rationales（运行时，不持久化）
       ↓
  Respond 节点 → state.reply_message
  ↓
返回响应（含所有更新后的状态字段）
```

### 3.2 渲染链路

```
用户渲染指令
  ↓
FastAPI /api/chat 或 /api/resume/render
  ↓
Planner Agent → intent = render_edit
  ↓
Resume Render Agent
  ├─ 解析渲染指令 → 更新 state.render_config
  └─ resume_content_json + render_config → 生成 state.resume_html
  ↓
返回 render_config + resume_html
```

### 3.3 导出链路

```
用户导出请求
  ↓
FastAPI /api/export
  ↓
读取 state.resume_content_json + state.render_config
  ↓
Export Service
  ├─ format=html → 返回 resume_html.html
  ├─ format=pdf → WeasyPrint 转换 HTML → PDF
  ├─ format=json → 返回 resume_content_json
  └─ format=markdown → JSON 转 Markdown
  ↓
返回文件
```

---

## 4. 存储设计

### 4.1 Redis

用途：会话状态管理、缓存。

| Key 模式 | 值 | TTL |
|----------|-----|-----|
| `session:{session_id}:state` | 完整 state JSON | 24h |
| `session:{session_id}:events` | conversation_events 列表（历史事件扩展用） | 24h |
| `session:{session_id}:lock` | 分布式锁（防并发写入）| 30s |

### 4.2 MySQL

用途：持久化存储。

**表设计：**

```sql
-- 会话表
CREATE TABLE sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    status ENUM('active', 'archived') DEFAULT 'active'
);

-- JD 表
CREATE TABLE jobs (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 候选人画像表
CREATE TABLE candidate_profiles (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 简历内容表
CREATE TABLE resume_contents (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    data JSON NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 渲染配置表
CREATE TABLE render_configs (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- HTML 快照表
CREATE TABLE resume_htmls (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    html LONGTEXT NOT NULL,
    derived_from_content_version INT NOT NULL,
    derived_from_render_version INT NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 面试问答表
CREATE TABLE interview_qas (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- 事件流表
CREATE TABLE conversation_events (
    event_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    message_id VARCHAR(64) NOT NULL,
    intent VARCHAR(32) NOT NULL,
    triggered_agents JSON NOT NULL,
    state_diff_summary JSON,
    status ENUM('success', 'failed', 'partial') NOT NULL,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

### 4.3 本地文件

用途：运行时临时文件。

| 路径 | 用途 | 生命周期 |
|------|------|----------|
| `data/uploads/{session_id}/` | 用户上传文件暂存 | 会话结束后清理 |
| `data/tmp/{session_id}/` | 文件解析中间产物 | 解析完成后清理 |

---

## 5. API 详细设计

### `POST /api/chat`

```json
// Request
{
  "session_id": "string",
  "message": "string",
  "attachments": [
    {
      "filename": "string",
      "content_type": "string",
      "data": "base64"
    }
  ]
}

// Response
{
  "session_id": "string",
  "job": {},
  "gaps": [],
  "questions_to_ask": [],
  "resume_content_json": {},
  "render_config": {},
  "resume_html": {},
  "interview_qa": [],
  "triggered_agents": [],
  "reply_message": "string"
}
```

`reply_message` 由 workflow 的 Respond 节点统一生成。Respond 读取本轮运行时 `section_rationales`，用稳定 Markdown 模板输出用户输入、意图识别、各 Agent 的用户可见决策依据和最终结果；`section_rationales` 暂不持久化到 Redis/MySQL。

### `POST /api/resume/render`

```json
// Request
{
  "session_id": "string",
  "render_instruction": "string"
}

// Response
{
  "render_config": {},
  "resume_html": {}
}
```

### `GET /api/resume/content?session_id={id}`

```json
// Response
{
  "resume_content_json": {}
}
```

### `GET /api/resume/html?session_id={id}`

```json
// Response
{
  "resume_html": {}
}
```

### `POST /api/export`

```json
// Request
{
  "session_id": "string",
  "format": "html | pdf | markdown | json"
}

// Response
// 文件流
```

---

## 6. 并发控制

| 机制 | 用途 |
|------|------|
| asyncio.Semaphore | 限制 LLM 并发调用数 |
| Redis 分布式锁 | 防止同一 session 并发写入状态 |
| Resume Render Agent 幂等 | 相同 content_version + render_version 不重复渲染 |

---

## 7. 日志系统

### 7.1 日志分类

| 日志文件 | Logger 名称 | 内容 |
|----------|-------------|------|
| `log/app.log` | `app` | 应用主日志：启动、配置加载、文件解析 |
| `log/agent.log` | `agent` | Agent 调用日志：意图分类、执行计划、各 Agent 输入/输出 |
| `log/api.log` | `api` | API 请求/响应日志：路由、参数、耗时 |
| `log/storage.log` | `storage` | 数据库操作日志：Redis/MySQL 读写、连接状态 |
| `log/error.log` | *(all)* | 所有来源的 ERROR 及以上级别汇总 |

### 7.2 日志级别

| 环境 | 控制台 | 文件 |
|------|--------|------|
| 开发 | INFO | DEBUG |
| 生产 | WARNING | INFO |

### 7.3 使用方式

```python
from log import setup_logging, get_logger

setup_logging()  # 在 backend/main.py 入口调用一次
logger = get_logger("agent")  # 在各模块中获取分类 logger
logger.info("JD Agent started for session %s", session_id)
```

### 7.4 日志格式

```
2026-04-12 10:30:00 | INFO    | agent | JD Agent started for session sess_abc123
```
