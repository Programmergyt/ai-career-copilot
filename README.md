# AI Career Copilot

基于多轮对话、结构化状态管理与记忆机制的多 Agent 求职辅助系统，覆盖岗位理解、候选人画像构建、简历内容生成、简历渲染、面试准备全流程。

---

## 快速启动

当前仓库采用前后端分离目录：后端代码、配置、模板、SQL 与测试均位于 `backend/`，前端代码位于 `frontend/`。

### Docker 部署

适用于一键启动 `frontend + backend + MySQL + Redis` 的完整环境。

#### 1. 准备 Docker 环境变量

在项目根目录复制 Docker 环境变量模板：

```bash
cp .env.docker.example .env.docker
```

PowerShell 可用：

```powershell
Copy-Item .env.docker.example .env.docker
```

至少补充以下变量：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
MYSQL_ROOT_PASSWORD=change_me
MYSQL_DATABASE=ai_career_copilot
```

说明：

- `backend/config_loader.py` 现在支持通过环境变量覆盖 MySQL / Redis / FastAPI 地址，因此 Docker 内会自动连接 `mysql` 和 `redis` 服务，而不会继续使用 `backend/config.yaml` 中的公网 IP。

#### 2. 构建并启动容器

```bash
docker compose --env-file .env.docker up --build -d
```

启动后：

- 前端访问：`http://localhost:3000`
- 后端健康检查：`http://localhost:8000/health`
- MySQL：`localhost:3306`
- Redis：`localhost:6379`

首次启动时，`backend` 容器会自动执行 `python sql/init_db.py` 初始化数据库表结构。

#### 3. 查看运行状态

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

#### 4. 停止并清理

```bash
docker compose down
```

如果需要同时清理数据库和 Redis 持久化数据卷：

```bash
docker compose down -v
```

### 1. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 2. 配置环境变量

在 `backend/` 目录创建 `.env` 文件。

`backend/config_loader.py` 会固定从 `backend/.env` 和 `backend/config.yaml` 读取配置，不依赖当前工作目录。

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
MYSQL_PASSWORD=Gyt2003@GYTsecure
```

### 3. 初始化数据库

在 MySQL 服务器上执行 SQL 脚本：

```bash
mysql -u root -p < backend/sql/init_schema.sql
```

或直接执行初始化脚本：

```bash
python backend/sql/init_db.py
```

该脚本是幂等的，可重复执行。它会创建 `ai_career_copilot` 数据库及所有表。

### 4. 启动后端服务

```bash
python backend/main.py
```

服务默认监听 `http://0.0.0.0:8000`。

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 `http://localhost:3000`，API 请求自动代理到后端 `http://localhost:8000`。

生产构建：

```bash
cd frontend
npm run build
npm run preview
```

### 6. 测试 API

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
├── backend/                   # 后端代码、配置、模板、SQL、测试
│   ├── main.py                # FastAPI 入口
│   ├── config.yaml            # 全局配置
│   ├── config_loader.py       # 配置加载器
│   ├── agents/                # Agent 实现
│   ├── api/                   # API 路由
│   ├── log/                   # 日志模块（分类记录）
│   ├── models/                # LLM / Embedding / Rerank
│   ├── prompts/               # Prompt 模板
│   ├── sql/                   # 数据库脚本
│   ├── storage/               # 数据访问层
│   ├── templates/             # HTML 简历模板
│   ├── test/                  # 后端测试
│   ├── tools/                 # 工具（文件解析、模板渲染）
│   └── workflow/              # LangGraph 状态与图编排
├── docker/                    # Docker 构建与 Nginx 代理配置
│   ├── backend/
│   │   ├── Dockerfile
│   │   └── entrypoint.sh
│   └── frontend/
│       ├── Dockerfile
│       └── nginx.conf
├── docs/                      # 设计文档
├── frontend/                  # 前端工程目录（Vue3 + Vite）
│   ├── src/
│   │   ├── api/               # 后端 API 封装
│   │   ├── assets/            # 全局样式
│   │   ├── components/        # 组件
│   │   │   ├── ChatPanel.vue  # 左侧对话面板
│   │   │   ├── ResultPanel.vue# 右侧结果面板（Tabs）
│   │   │   └── tabs/          # 各 Tab 页组件
│   │   ├── utils/             # 工具函数
│   │   ├── App.vue            # 根组件
│   │   └── main.js            # 入口
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
├── .env.docker.example
├── README.md
└── 生成结果.html              # 示例输出
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

- [x] **日志系统** — 分类日志（位于 `backend/log/`），控制台+文件双输出
- [x] **配置管理** — `backend/config.yaml` + `backend/config_loader.py`，支持 Redis/MySQL/FastAPI 配置
- [x] **数据库存储层** — Redis 会话状态管理 + MySQL 持久化存储（连接池）
- [x] **SQL 脚本** — 幂等建库建表脚本 `backend/sql/init_schema.sql`
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
- [ ] 前端界面 (`frontend/`，Vue3)

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


