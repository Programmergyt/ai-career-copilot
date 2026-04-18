[English](./README.md) | [简体中文](./README.zh-CN.md)

# AI Career Copilot

![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-1C3C3C?style=flat-square)
![Vue 3](https://img.shields.io/badge/Frontend-Vue_3-42B883?style=flat-square&logo=vuedotjs&logoColor=white)
![MySQL](https://img.shields.io/badge/Database-MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Cache-Redis-DC382D?style=flat-square&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

一个面向求职场景的多 Agent AI Web 应用，支持岗位 JD 分析、候选人画像提取、简历内容生成、HTML 简历渲染、能力缺口分析与面试问答准备。

项目已经成功部署并可直接访问：[http://8.153.79.69:3001](http://8.153.79.69:3001)。如果你想先体验完整流程、再决定是否本地部署，可以直接打开线上站点，从上传目标 JD 开始感受整条多智能体工作流。

## 功能特性

- 支持多轮对话工作流，覆盖 JD 输入、个人材料输入、简历生成与后续编辑。
- 基于 LangGraph 编排多个 Agent，包括 Planner、JD 分析、画像提取、Gap Analysis、内容生成、渲染和面试问答。
- 生成结构化简历内容，并提供 HTML 预览与导出接口。
- 支持通过自然语言调整简历渲染效果，例如布局、样式和展示形式。
- 提供岗位与候选人之间的能力缺口分析，帮助识别重点补强方向。
- 基于当前岗位与简历上下文生成面试问答内容。
- 提供 Vue 3 Web 界面，方便进行对话交互和查看各类结果。
- 使用 Redis 管理会话状态，使用 MySQL 持久化关键业务数据。

## Demo

在线演示：[http://8.153.79.69:3001](http://8.153.79.69:3001)

你可以直接以终端用户视角体验完整产品流程：先上传目标 JD，然后在同一轮会话中继续补充个人基本信息、实习经历、项目材料，或者直接提出后续修改要求。系统会保留当前会话上下文，并持续增量更新生成结果。

### JD 分析

整个流程从目标岗位开始。上传或粘贴 JD 后，系统会抽取岗位职责、关键词和能力要求，为后续简历生成与面试准备提供统一上下文。

![JD 分析演示](./assets/JD_Analysis_Demo.png)

### 简历生成

在补充候选人材料后，内容生成与渲染 Agent 会协同产出结构化简历预览，并支持通过自然语言持续修改和优化。

![简历生成演示](./assets/Resume_Generation_Demo.png)

### 能力缺口分析

能力缺口面板会指出候选人材料与目标 JD 之间缺失、薄弱或证据不足的部分，帮助用户更快判断应该补强哪些信息。

![能力缺口分析演示](./assets/Gap_Analysis_Demo.png)

### 模拟面试

面试问答面板会结合当前岗位和生成后的简历内容，整理更贴近真实投递场景的面试问题，便于用户围绕目标岗位进行准备。

![模拟面试演示](./assets/Mock_Interview_Demo.png)

### 调试视图

为了便于开发和排查问题，调试面板会展示当前会话中的结构化内容、渲染配置以及触发过的 Agent 等中间结果。

![调试视图演示](./assets/Debug_Demo.png)

## 在线体验

已部署的线上实例 [http://8.153.79.69:3001](http://8.153.79.69:3001) 是了解这个项目的最快方式。你可以直接验证多轮工作流、查看各个结果标签页，体验简历编辑、缺失信息补全和面试问答生成的整体效果，再决定是否克隆仓库进一步使用或开发。

如果你想查看源码或参与贡献，可以访问 GitHub 仓库：[https://github.com/Programmergyt/ai-career-copilot](https://github.com/Programmergyt/ai-career-copilot)。

## 项目结构

```text
ai-career-copilot/
├── backend/           # FastAPI 后端、Agents、工作流、存储层、Prompt、测试
├── frontend/          # Vue 3 + Vite 前端
├── docker/            # 前后端 Dockerfile 与 Nginx 配置
├── docs/              # 设计与规划文档
├── docker-compose.yml
└── README*.md
```

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 API | FastAPI, Uvicorn |
| Agent 编排 | LangGraph |
| 大模型接入 | LangChain, DeepSeek |
| Embedding / Rerank | DashScope |
| 前端 | Vue 3, Vite, Axios |
| 会话存储 | Redis |
| 持久化 | MySQL |
| 配置管理 | PyYAML, python-dotenv |
| 测试 | pytest |

## 快速开始

当前更推荐的使用方式是本地开发启动。

仓库中已经提供前后端 Dockerfile 和 `docker-compose.yml`，但现阶段的 Compose 配置仍然要求你自行准备可访问的 MySQL 与 Redis，并不是一个面向公开用户的完整一键部署方案。

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8+
- Redis 6+
- 已准备好对应模型服务的 API Key

### 1. 安装后端依赖

```bash
pip install -r backend/requirements.txt
```

### 2. 配置后端环境变量

在 `backend/` 目录下创建 `.env` 文件。

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change_me
MYSQL_DATABASE=ai_career_copilot
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
FASTAPI_DEBUG=true
```

`backend/config_loader.py` 会读取 `backend/.env`，并允许环境变量覆盖 `backend/config.yaml` 中的默认配置。

### 3. 初始化数据库

可以直接执行 SQL 脚本：

```bash
mysql -u root -p < backend/sql/init_schema.sql
```

也可以运行初始化脚本：

```bash
python backend/sql/init_db.py
```

### 4. 启动后端

```bash
python backend/main.py
```

健康检查：

```bash
curl http://localhost:8000/health
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 `http://localhost:3000`，并代理后端 API 请求。

### 6. 体验主流程

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "在这里粘贴岗位 JD"}'
```

拿到 `session_id` 后，可以继续上传个人材料，并通过下面的接口预览生成后的 HTML 简历：

```bash
curl "http://localhost:8000/api/resume/preview?session_id=YOUR_SESSION_ID"
```

## 配置说明

### 模型与 API 配置

- LLM、Embedding、Rerank 的默认配置定义在 `backend/config.yaml` 中。
- API Key 会从 `backend/.env` 或系统环境变量中读取。
- 当前默认配置使用 DeepSeek 作为对话模型，DashScope 作为 Embedding 和 Rerank 服务。

### 存储配置

- Redis 用于会话状态管理。
- MySQL 用于持久化保存会话、岗位信息、候选人画像、简历内容、渲染配置、HTML 简历和面试问答结果。
- MySQL 与 Redis 的主要连接参数都可以通过环境变量覆盖。

### Docker 说明

- 当前 `docker-compose.yml` 只负责启动应用服务，不会为公开用户自动创建 MySQL 或 Redis。
- 如果后续要面向开源用户提供完整部署体验，建议把“自包含部署方案”作为后续迭代，而不是在当前 README 中包装成已完善能力。

## Roadmap

- 完善候选人信息不完整时的主动追问机制。
- 增加局部简历更新的差异展示能力。
- 支持跨会话记忆与用户偏好持久化。
- 提供更多简历模板和 Section 级渲染控制。
- 补齐 Markdown、PDF 等导出能力。
- 在适合的场景下加入检索增强能力，提升匹配与编辑质量。

## Contributing

欢迎提交 Issue 和 Pull Request。

如果你准备参与开发，建议先从下面几步开始：

1. 在本地跑通前后端。
2. 阅读 `docs/` 下的工作流与状态设计文档。
3. 对行为变更同步补充或更新 `backend/test/` 下的测试。

## License

TODO：仓库当前还没有 `LICENSE` 文件。如果你准备以标准开源项目方式发布，建议先补齐许可证。

## Support

如果这个项目对你有帮助，欢迎给仓库点一个 Star。
