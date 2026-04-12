# AI Career Copilot

基于多轮对话、结构化状态管理与记忆机制的多 Agent 求职辅助系统，覆盖岗位理解、候选人画像构建、简历内容生成、简历渲染、面试准备全流程。

---

## 快速启动

### 1. 安装依赖

> **注意**：旧的 `requirements.txt` 是 UTF-16 编码，请删除后用 `requirements_new.txt` 替代：
> ```bash
> del requirements.txt
> ren requirements_new.txt requirements.txt
> pip install -r requirements.txt
> ```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
MYSQL_PASSWORD=Gyt2003@GYTsecure
```

### 3. 初始化数据库

在 MySQL 服务器上执行 SQL 脚本：

```bash
mysql -u root -p < sql/init_schema.sql
```

该脚本是幂等的，可重复执行。它会创建 `ai_career_copilot` 数据库及所有表。

### 4. 启动服务

```bash
python main.py
```

服务默认监听 `http://0.0.0.0:8000`。

### 5. 测试 API

```bash
# 健康检查
curl http://localhost:8000/health

# 上传 JD
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你的JD内容..."}'

# 上传个人材料
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "返回的session_id", "message": "你的个人信息..."}'

# 预览简历 HTML
curl http://localhost:8000/api/resume/preview?session_id=xxx
```

---

## 项目结构

```
ai-career-copilot/
├── main.py                    # FastAPI 入口
├── config.yaml                # 全局配置
├── config_loader.py           # 配置加载器
├── log/                       # 日志模块（分类记录）
│   ├── logger.py              # 日志配置
│   ├── app.log                # 应用日志
│   ├── agent.log              # Agent 日志
│   ├── api.log                # API 日志
│   ├── storage.log            # 存储日志
│   └── error.log              # 错误汇总
├── models/                    # LLM / Embedding / Rerank
├── agents/                    # Agent 实现
│   ├── planner.py             # 意图分类 + 执行调度
│   ├── jd_agent.py            # JD 解析
│   ├── profile_agent.py       # 候选人画像
│   ├── content_agent.py       # 简历内容生成
│   └── render_agent.py        # 简历渲染
├── workflow/                  # LangGraph 状态与图编排
│   ├── state.py               # 全局状态 Schema
│   └── graph.py               # 图定义
├── prompts/                   # Prompt 模板
├── tools/                     # 工具（文件解析、模板渲染）
├── templates/                 # HTML 简历模板
├── storage/                   # 数据访问层
│   ├── redis_client.py        # Redis 会话状态
│   └── mysql_client.py        # MySQL 持久化
├── api/                       # API 路由
│   ├── chat.py                # POST /api/chat
│   ├── resume.py              # GET/POST /api/resume/*
│   └── export.py              # POST /api/export
├── sql/                       # 数据库脚本
│   └── init_schema.sql        # 建库建表（幂等）
├── test/                      # 测试
└── docs/                      # 设计文档
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/chat` | 主对话接口（JD上传/材料上传/内容编辑/渲染编辑）|
| GET | `/api/resume/content?session_id=` | 获取简历内容 JSON |
| GET | `/api/resume/html?session_id=` | 获取简历 HTML 数据 |
| GET | `/api/resume/preview?session_id=` | 浏览器预览简历 HTML |
| POST | `/api/resume/render` | 渲染指令接口 |
| POST | `/api/export` | 导出简历（html/json）|

---

## MVP 进度

### ✅ 已完成（第一阶段 — 核心）

- [x] **日志系统** — 分类日志（app/agent/api/storage/error），控制台+文件双输出
- [x] **配置管理** — config.yaml + config_loader.py，支持 Redis/MySQL/FastAPI 配置
- [x] **数据库存储层** — Redis 会话状态管理 + MySQL 持久化存储（连接池）
- [x] **SQL 脚本** — 幂等建库建表脚本 `sql/init_schema.sql`
- [x] **全局状态 Schema** — Pydantic 模型定义，覆盖所有状态字段
- [x] **LangGraph 工作流** — 状态图编排，支持意图路由和条件分支
- [x] **Planner Agent** — 意图分类（6 种意图）+ 执行计划生成 + 跳过逻辑
- [x] **JD Agent** — JD 解析，输出结构化 Job
- [x] **Profile Agent** — 候选人材料解析，增量合并画像
- [x] **Resume Content Agent** — 简历内容 JSON 生成/局部更新
- [x] **Resume Render Agent** — 渲染配置管理 + HTML 生成
- [x] **Prompt 模板** — 意图分类/JD分析/画像提取/简历生成/渲染指令
- [x] **HTML 简历模板** — 支持主题/布局/字号/行距/边距自定义
- [x] **文件解析工具** — PDF / DOCX / Markdown / TXT 解析
- [x] **API 路由** — chat / resume / export 接口
- [x] **FastAPI 入口** — CORS 支持，自动重载
- [x] **对话输入** — POST /api/chat 接口
- [x] **实时预览** — GET /api/resume/preview 接口
- [x] **内容指令/渲染指令路由** — Planner Agent 自动分类

### 🔲 未完成（第二阶段）

- [ ] Gap Analysis Agent — 能力缺口分析
- [ ] Interview Agent — 面试问答生成
- [ ] 主动追问机制 — questions_to_ask 流转
- [ ] 局部更新 diff 展示
- [ ] 前端界面 (Vue3)

### 🔲 未完成（第三阶段）

- [ ] 跨会话记忆（MySQL 持久化用户偏好）
- [ ] 多模板支持
- [ ] Section 级渲染控制
- [ ] HTML → PDF 精细导出（WeasyPrint）
- [ ] Markdown 导出
- [ ] RAG 检索增强

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI |
| Agent 编排 | LangGraph |
| LLM | DeepSeek (deepseek-chat) via LangChain |
| Embedding | DashScope (text-embedding-v4) |
| Rerank | DashScope (gte-rerank-v2) |
| 会话存储 | Redis |
| 持久化存储 | MySQL 8.0+ |
| 日志 | Python logging（分类文件输出）|
| 配置 | PyYAML + python-dotenv |