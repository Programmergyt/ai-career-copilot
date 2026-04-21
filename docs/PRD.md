# 产品需求文档（PRD）

# 一、产品概述

## 1.1 产品名称

AI Job Copilot

## 1.2 产品定位

基于多轮对话、结构化状态管理与记忆机制的多 Agent 系统，覆盖岗位理解、候选人画像构建、简历内容生成、简历渲染、面试准备全流程。

## 1.3 核心目标

- 解析岗位需求（JD）
- 构建候选人结构化画像
- 生成简历内容 JSON
- 根据用户指令调整简历 HTML 渲染
- 生成面试问答集
- 通过多轮对话补全信息缺口

---

# 二、目标用户与使用场景

## 2.1 目标用户

- 在校学生 / 应届生
- AI / 后端 / 测试开发方向求职者
- 转行求职用户

## 2.2 核心使用流程

1. 用户输入 JD（文本或文件）
2. 用户上传或分多轮补充个人材料（项目经历、实习经历、技能说明、获奖信息）
3. 系统生成：岗位分析、候选人画像、简历内容 JSON、简历 HTML 预览、缺失信息追问
4. 用户补充事实信息，系统只更新受影响的内容区块
5. 用户提出渲染指令，系统仅更新渲染配置和 HTML，不改动内容 JSON
6. 用户导出结果

## 2.3 用户指令分类

### 内容类指令

- "我的名字是xxx，教育经历是xxx"
- "把这个项目写得更突出后端能力"
- "补充一段实习经历"
- "删除这段不相关经历"

### 渲染类指令

- "把行距改成更大一点"
- "标题更明显一些"
- "整体更紧凑，尽量控制一页"
- "改成极简风格"

---

# 三、产品形态

## 3.1 界面结构

### 左侧：对话区

- 输入 JD / 上传附件 / 补充个人材料
- 内容修改指令与渲染修改指令
- 系统主动追问缺失信息
- 每轮给出执行反馈（如"已更新项目经历内容"、"已调整简历行距"）

### 右侧：实时结果面板（Tabs）

| Tab | 内容 |
|-----|------|
| 岗位分析 | 技术要求、能力要求、匹配度评分、Gap 分析 |
| 简历预览 | HTML 渲染结果，支持局部刷新、主题切换 |
| 缺失信息 | 系统生成的补充问题，用户逐条回答后并入状态 |
| 面试问答 | 技术问题、项目深挖、行为面试、参考答案 |
| 调试视图 | `resume_content_json`、`render_config`、最近触发的 Agent 链路（开发期） |

---

# 四、核心状态设计

## 4.1 状态总览

```json
{
  "session_id": "",
  "job": {},
  "candidate_profile": {},
  "resume_content_json": {},
  "render_config": {},
  "resume_html": {},
  "gaps": [],
  "questions_to_ask": [],
  "interview_qa": [],
  "conversation_events": [],
  "meta": {},
  "pending_actions": []
}
```

## 4.2 状态设计原则

1. 所有可被局部修改的对象必须有稳定 `id`
2. 所有由 Agent 生成的关键结果必须带 `version`
3. 所有内容类字段保留 `source_refs`，用于追溯来源与增量更新

## 4.3 状态字段定义

### `session_id`

当前会话唯一标识。前后端、Redis、事件流、导出链路统一使用该字段串联。

### `job`

岗位信息。由 JD Agent 写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | JD 唯一标识 |
| source | string | 原始 JD 文本或文件引用 |
| parsed_at | string | 解析时间 |
| version | int | 结构版本号 |
| industry | string | 行业 |
| title | string | 岗位名称 |
| tech_stack | string[] | 技术栈 |
| keywords | string[] | 核心关键词 |
| hard_skills | string[] | 硬技能 |
| soft_skills | string[] | 软技能 |
| responsibilities | string[] | 职责 |
| education_requirement | string | 学历要求 |
| experience_requirement | string | 经验要求 |
| implicit_preferences | string[] | 隐含偏好 |
| bonus_items | string[] | 加分项 |

### `candidate_profile`

候选人画像。由 Profile Agent 写入。

分层结构：

| 子字段 | 类型 | 说明 |
|--------|------|------|
| profile_basic | object | 姓名、邮箱、电话、城市、学校 |
| materials | Material[] | 原始材料仓库，每份材料有独立 `material_id` |
| facts | Fact[] | 从材料中抽取的结构化事实 |

**Material 结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| material_id | string | 材料唯一标识 |
| type | string | pdf / docx / text / message |
| content | string | 原始内容 |
| uploaded_at | string | 上传时间 |

**Fact 结构：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 事实唯一标识 |
| type | string | skill / project / internship / award / paper |
| content | string | 结构化内容 |
| source_refs | string[] | 来源材料/消息 ID |
| updated_at | string | 更新时间 |

### `resume_content_json`

简历内容唯一事实来源。由 Resume Content Agent 写入。

```json
{
  "profile": {
    "name": "",
    "email": "",
    "phone": "",
    "city": "",
    "github": "",
    "education": []
  },
  "summary": "",
  "skills": [],
  "internships": [],
  "projects": [],
  "awards": [],
  "papers": [],
  "meta": {
    "target_role": "",
    "version": 1,
    "last_updated_at": "",
    "content_hash": ""
  }
}
```

**Section Item 通用结构（skills / internships / projects / awards / papers 中每个元素）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 稳定唯一标识 |
| title | string | 标题 |
| content | string | 内容 |
| source_refs | string[] | 来源材料/消息 ID |
| updated_at | string | 更新时间 |

约束：
- 必须为结构化 JSON，不允许 HTML 作为事实源
- 所有下游展示、导出、面试问答消费该 JSON
- 不得捏造用户未提供的事实

### `render_config`

渲染配置。由 Resume Render Agent 写入。

```json
{
  "template_id": "default",
  "theme": "light",
  "font_family": "Source Han Sans",
  "font_size": 14,
  "line_height": 1.5,
  "page_margin": { "top": 24, "right": 24, "bottom": 24, "left": 24 },
  "section_order": ["profile", "skills", "projects", "internships", "awards"],
  "dense_mode": false,
  "accent_style": "minimal",
  "visibility_map": {},
  "layout_mode": "single-column",
  "spacing_scale": "standard",
  "version": 1,
  "last_render_reason": ""
}
```

约束：
- 只描述展示，不描述事实内容
- Render Agent 修改渲染配置，不直接改 HTML 字符串

### `resume_html`

渲染产物。由 Resume Render Agent 写入。

```json
{
  "html": "",
  "version": 1,
  "derived_from_content_version": 1,
  "derived_from_render_version": 1,
  "updated_at": "",
  "checksum": ""
}
```

约束：
- 是派生结果，不是事实源
- 必须可由 `resume_content_json + render_config` 再生成

### `gaps`

能力缺口列表。由 Gap Analysis Agent 写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| type | string | missing_skill / missing_experience / no_quantification / low_relevance |
| severity | string | high / medium / low |
| description | string | 缺口描述 |
| related_section_ids | string[] | 关联的 section item id |
| resolved | bool | 是否已解决 |
| resolution_source | string | 解决来源 |

### `questions_to_ask`

待追问问题列表。由 Gap Analysis Agent 写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| question | string | 问题内容 |
| reason | string | 追问原因 |
| target_field | string | 目标状态字段 |
| priority | string | high / medium / low |
| status | string | pending / answered / dismissed |
| answer_ref | string | 回答对应的消息 ID |

### `interview_qa`

面试问答集。由 Interview Agent 写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| category | string | technical / project_deep_dive / behavioral |
| question | string | 问题 |
| answer | string | 参考答案 |
| source_refs | string[] | 内容来源引用 |
| version | int | 版本号 |

### `conversation_events`

事件流。由 Planner Agent 写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | string | 唯一标识 |
| message_id | string | 用户消息 ID |
| intent | string | 识别到的意图 |
| triggered_agents | string[] | 触发的 Agent 列表 |
| state_diff_summary | object | 状态变化摘要 |
| created_at | string | 创建时间 |
| status | string | success / failed / partial |

### `meta`

全局运行元信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| active_resume_content_version | int | 当前内容版本 |
| active_render_version | int | 当前渲染配置版本 |
| active_html_version | int | 当前 HTML 版本 |
| last_user_message_id | string | 最近用户消息 ID |
| last_successful_pipeline | string | 最近成功的 pipeline 名 |
| dirty_flags | object | 脏标记 |

**dirty_flags：**

```json
{
  "content_dirty": false,
  "render_dirty": false,
  "interview_dirty": false,
  "export_dirty": false
}
```

### `pending_actions`

异步或待确认动作队列。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| type | string | wait_answer / export / render_confirm / async_generate |
| status | string | pending / completed / cancelled |
| owner_agent | string | 负责的 Agent |
| depends_on | string[] | 依赖的 action id |
| created_at | string | 创建时间 |

## 4.4 状态不变量

1. `resume_content_json` 是简历事实的唯一真值来源
2. `resume_html` 只能由 `resume_content_json + render_config` 派生，不可回写事实层
3. 任何 section 级内容必须有稳定 `id`
4. `conversation_events` 必须可回放最近一次状态变化路径
5. `content_dirty=true` 时，`resume_html` 和 `interview_qa` 视为过期
6. `render_dirty=true` 时，只重新生成 `resume_html`，不重跑内容链路

---

# 五、Agent 定义

## 5.1 Agent 列表

| Agent | 职责 |
|-------|------|
| Planner Agent | 意图分类、执行计划生成、执行元数据生成 |
| JD Agent | 解析 JD，输出结构化 `job` |
| Profile Agent | 解析用户材料，输出结构化 `candidate_profile` |
| Gap Analysis Agent | 对比 job 与 profile，输出 `gaps` 和 `questions_to_ask` |
| Resume Content Agent | 生成/更新 `resume_content_json` |
| Resume Render Agent | 生成/更新 `render_config` 和 `resume_html` |
| Interview Agent | 生成 `interview_qa` |

## 5.2 Planner Agent

子模块：

**Intent Classifier** — 将用户输入分类为：

| Intent | 说明 |
|--------|------|
| upload_jd | 上传/输入 JD |
| upload_profile | 上传/补充个人材料 |
| content_edit | 修改简历内容 |
| render_edit | 修改渲染样式 |
| export | 导出请求 |
| ask_question | 提问/查询 |

**State Diff Planner** — 判断本轮输入影响哪些状态字段，输出最小执行计划。

**Execution Metadata Builder** — 基于最小执行计划补充结构化 step 元数据，用于后续 executor 化和 step 级观测。

## 5.3 JD Agent

- 提取技术关键词、能力要求、岗位职责、隐含要求
- 输出结构化 `job`

## 5.4 Profile Agent

- 解析 PDF / DOCX / Markdown / 文本
- 抽取技能、项目、成果、角色、量化结果
- 输出结构化 `candidate_profile`
- 不写简历 HTML，不决定文案风格

## 5.5 Gap Analysis Agent

- 对比 `job` 与 `candidate_profile`
- 输出匹配度评分、缺失能力、待追问问题
- 写入 `gaps` 和 `questions_to_ask`

## 5.6 Resume Content Agent

- 改写项目描述为 STAR 风格
- 优化技能排序，根据 JD 进行关键词对齐
- 写入 `resume_content_json`
- 局部更新：修改项目只更新 `projects`，修改技能只更新 `skills`

约束：
- 不得捏造用户未提供的事实
- 不输出 HTML
- 不修改 `render_config`

## 5.7 Resume Render Agent

- 将 `resume_content_json` 渲染为 HTML
- 将渲染指令转为结构化 `render_config`
- 写入 `render_config` 和 `resume_html`

约束：
- 不修改 `resume_content_json`
- 不补充或删除项目、技能、经历
- 渲染失败时回退默认模板，不丢失内容 JSON

## 5.8 Interview Agent

- 生成技术问题、项目深挖问题、行为面试问题、参考答案
- 读取 `job`、`candidate_profile`、`resume_content_json`
- 写入 `interview_qa`
- 不依赖 `resume_html`

## 5.9 Agent 边界约束

| Agent | 可写字段 | 禁止写入 |
|-------|----------|----------|
| JD Agent | job | 其他所有字段 |
| Profile Agent | candidate_profile | 其他所有字段 |
| Gap Analysis Agent | gaps, questions_to_ask | 其他所有字段 |
| Resume Content Agent | resume_content_json | render_config, resume_html, job, candidate_profile |
| Resume Render Agent | render_config, resume_html | resume_content_json, job, candidate_profile |
| Interview Agent | interview_qa | 其他所有字段（只读 job, candidate_profile, resume_content_json）|
| Planner Agent | conversation_events, meta, pending_actions | 业务数据字段 |

---

# 六、Workflow 定义

## 6.1 更新路由规则

| 触发条件 | 执行链路 |
|----------|----------|
| 用户输入/修改 JD | JD Agent → Gap Analysis Agent → Resume Content Agent → Resume Render Agent → Interview Agent |
| 用户补充项目/实习/技能 | Profile Agent → Resume Content Agent → Resume Render Agent → Interview Agent |
| 用户只修改样式 | Resume Render Agent |
| 用户要求"更突出某能力" | Resume Content Agent → Resume Render Agent |
| 用户查询匹配度 | Gap Analysis Agent（不重跑全链路）|

说明：

- 当前阶段仍使用固定 LangGraph 节点图执行这些链路。
- 不在这一阶段引入统一 `plan_executor`。
- 先完成 Agent 模块解耦，再进入编排器重构。

## 6.2 局部更新原则

- 内容未变时，只重渲染 HTML
- 样式未变时，只更新受影响内容 section 和相关 HTML
- 面试问答依赖内容 JSON，不依赖 HTML

---

# 七、记忆系统

## 7.1 会话内记忆

存储：Redis。生命周期：单次会话。

记录内容：
- 用户输入历史
- 当前状态快照
- 当前 `resume_content_json`、`render_config`
- 当前 `resume_html` 版本号
- 最近 intent

## 7.2 跨会话记忆（MVP 第三阶段）

存储：MySQL。

记录内容：
- 常用技能、历史项目、偏好岗位、渲染偏好

---

# 八、系统架构

## 8.1 架构总览

```
Frontend (Vue3)
  ↓
Backend (FastAPI)
  ↓
Conversation API / Session API
  ↓
Agent Orchestrator (LangGraph 固定图)
  ↓
├── Planner: intent + execution_plan + execution_steps
├── Agent Runtime: contract 校验 + registry 查找 + 执行包装
├── Content Pipeline: JD Agent → Profile Agent → Gap Analysis Agent → Resume Content Agent
├── Render Pipeline: Resume Render Agent
└── Interview Pipeline: Interview Agent
  ↓
LLM / Embedding / Rerank (models/)
  ↓
Storage: Redis + MySQL + 本地临时文件
```

## 8.2 文件解析层

| 输入格式 | 输出格式 |
|----------|----------|
| PDF | Markdown |
| DOCX | Markdown |
| Markdown / TXT | 标准文本 |

解析结果归入 `candidate_profile.materials`。

## 8.3 存储设计

| 存储 | 用途 |
|------|------|
| Redis | 会话状态、缓存、中间任务态 |
| MySQL | 结构化 JSON 持久化（job、resume_content_json、render_config、resume_html、interview_qa） |
| 本地文件 | 运行时临时文件（上传解析中间产物），不持久化 |

## 8.4 API 定义

### `POST /api/chat`

请求：`session_id`, `message`, `attachments`

响应：`job`, `gaps`, `questions_to_ask`, `resume_content_json`, `render_config`, `resume_html`, `triggered_agents`

### `POST /api/resume/render`

请求：`session_id`, `render_instruction`

响应：`render_config`, `resume_html`

### `GET /api/resume/content`

响应：当前 `resume_content_json`

### `GET /api/resume/html`

响应：当前 `resume_html`

### `POST /api/export`

请求：`session_id`, `format`（html / pdf / markdown / json）

响应：导出文件

## 8.5 并发控制

- 使用 semaphore 限制 LLM 并发调用
- Resume Render Agent 幂等执行，避免并发覆盖

---

# 九、导出功能

| 导出内容 | 格式 |
|----------|------|
| 岗位分析报告 | PDF / Markdown |
| 简历内容 JSON | JSON |
| 简历 HTML | HTML |
| 简历 | PDF（由 HTML 转换）|
| 面试问答集 | Markdown / PDF |

导出基于当前 `resume_content_json + render_config`。

---

# 十、MVP 版本规划

### 第一阶段（核心）

- JD 解析
- 简历内容 JSON 生成
- HTML 简历渲染
- 对话输入
- 实时预览
- 内容指令 / 渲染指令路由

### 第二阶段

- Gap 分析
- 面试问答生成
- 主动追问
- 局部更新 diff 展示

### 第三阶段

- 跨会话记忆
- 多模板
- Section 级渲染控制
- HTML 到 PDF 精细导出

---

# 十一、开发约束

## 11.1 禁止的实现方式

- 不允许 HTML 作为唯一简历存储格式
- 不允许 Resume Content Agent 输出页面结构
- 不允许 Resume Render Agent 编造内容
- 不允许渲染指令触发全链路重跑
- 不允许 Interview Agent 依赖 HTML

## 11.2 验收标准

### 内容链路

- 输入 JD 和两份项目材料后，生成稳定的 `resume_content_json`
- 补充一段项目经历后，只更新对应 section

### 渲染链路

- 输入渲染指令后，只更新 `render_config` 和 `resume_html`
- HTML 刷新时间低于完整内容重生成

### 一致性

- `resume_html` 可由 `resume_content_json + render_config` 重新生成
- 导出 PDF 与页面预览一致

### 可追踪性

- 每次输入在事件流中记录：`intent → affected_state → triggered_agents`

### 架构演进约束

- 当前阶段完成后，新增或替换某个 Agent 实现时，不需要改 workflow 路由，只需要修改 contract 与 registry
- `execution_steps` 可以稳定产出，但不会在这一阶段直接驱动执行
