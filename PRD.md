好，这里我帮你整理成一份可以直接用于开发、能写进简历、也能拿去面试讲的完整 PRD。

这版 PRD 的核心改动是：

- 简历内容存储为结构化 JSON，由内容类 Agent 负责维护
- 简历最终预览存储为 HTML，由独立的 Render Agent 负责维护
- 用户修改“内容”和修改“渲染样式”走两条不同链路，避免实现时职责混乱

---

# 产品需求文档（PRD）

# 一、产品概述

## 1.1 产品名称

AI Job Copilot（对话式求职助手 Agent）

## 1.2 产品定位

基于多轮对话、结构化状态管理与记忆机制的 AI Agent 系统，帮助用户完成从岗位理解、候选人画像构建、简历内容生成、简历渲染调整到面试准备的全流程。

## 1.3 核心目标

- 自动解析岗位需求（JD）
- 动态构建候选人画像
- 生成并持续优化简历内容 JSON
- 根据用户自然语言指令实时调整简历 HTML 渲染效果
- 自动生成面试问答集
- 通过多轮对话补全信息缺口

## 1.4 核心价值

- 提升简历与 JD 匹配度，减少无效投递
- 降低求职准备成本
- 提供分析、简历内容、简历渲染、面试准备的闭环能力
- 将内容生成与展示渲染解耦，降低局部修改成本
- 模拟真实求职辅导过程，提升 Agent 项目的工程含金量

---

# 二、目标用户与使用场景

## 2.1 目标用户

- 在校学生 / 应届生
- AI / 后端 / 测试开发方向求职者
- 转行求职用户

## 2.2 核心使用流程

1. 用户输入 JD，可为文本或文件。
2. 用户上传或分多轮补充个人材料，例如项目经历、实习经历、技能说明、获奖信息。
3. 系统解析材料并生成：
   - 岗位分析结果
   - 候选人画像
   - 简历内容 JSON
   - 简历 HTML 预览
   - 缺失信息追问
4. 用户继续补充事实信息，系统只更新受影响的内容区块。
5. 用户可以单独提出渲染指令，例如：
   - “把行距调大一点”
   - “页边距缩小，尽量压缩到一页”
   - “改成更偏互联网风格的模板”
6. 系统仅更新渲染配置和 HTML，不改动简历内容 JSON。
7. 用户导出岗位分析、简历和面试问答结果。

## 2.3 典型用户指令分类

### 内容类指令

- “我的名字是xxx，教育经历是xxx”
- “把这个项目写得更突出后端能力”
- “补充一段实习经历”
- “这段项目强调性能优化”
- “删除这段不相关经历”

### 渲染类指令

- “把行距改成更大一点”
- “标题更明显一些”
- “整体更紧凑，尽量控制一页”
- “改成更适合算法岗的极简风格”

---

# 三、产品形态设计

## 3.1 界面结构

### 左侧：对话区

- 支持输入 JD / 上传附件 / 增量补充个人材料
- 支持内容修改指令与渲染修改指令
- 系统主动追问缺失信息
- 对每一轮输入给出执行反馈，例如：
  - “已更新项目经历内容”
  - “已调整简历行距和页边距”

### 右侧：实时结果面板

顶部用 Tabs 展示多个模块，切换后状态保留。

#### 1. 岗位分析

- 技术要求
- 能力要求
- 匹配度评分
- Gap 分析

#### 2. 简历预览

- 实时展示最终 HTML 渲染结果
- 支持局部刷新
- 支持切换模板或主题后即时预览

#### 3. 缺失信息提示

- 系统主动生成补充问题
- 支持用户逐条回答后实时并入状态

#### 4. 面试问答集

- 技术问题
- 项目深挖问题
- 行为面试问题
- 参考答案

#### 5. 调试视图（建议开发期保留）

- 当前 `resume_content_json`
- 当前 `render_config`
- 最近一次触发的 Agent 链路

---

# 四、核心状态设计

## 4.1 状态总览

系统维护以下核心状态：

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
  "conversation_events": [],
   "meta": {},
   "pending_actions": []
}
```

这里必须强调三条状态设计原则：

- 所有可被局部修改的对象都必须有稳定 `id`
- 所有由 Agent 生成的关键结果都必须带 `version`
- 所有内容类字段都应尽量保留 `source_refs`，便于追溯来源与后续增量更新

## 4.2 状态字段说明

### 0. `session_id`

- 当前会话唯一标识
- 前后端、Redis、事件流、导出链路都使用该字段串联
- 不允许前端仅靠内存对象管理整份状态

### 1. `job`

岗位信息，由 JD Agent 维护。

建议字段：

- 行业
- 岗位名称
- 技术栈
- 核心关键词
- hard skills
- soft skills
- 职责
- 学历要求
- 经验要求
- 隐含偏好
- 加分项

建议补充的必须字段：

- `id`: JD 对象版本 ID
- `source`: 原始 JD 文本或文件引用
- `parsed_at`: 最近一次解析时间
- `version`: 当前 JD 结构版本
- `confidence`: 解析置信度或完整度

### 2. `candidate_profile`

候选人画像，由 Profile Agent 维护。

建议字段：

- 基本信息
- 教育经历
- 技能清单
- 项目经历原始材料
- 实习经历原始材料
- 论文 / 奖项 / 竞赛经历
- 事实级标签，例如“是否有量化结果”“是否有团队协作经历”

为保证后续局部更新，`candidate_profile` 不能只是一团文本，建议至少分成以下层次：

- `profile_basic`: 姓名、邮箱、电话、城市、学校等基础信息
- `materials`: 原始材料仓库，每份材料有独立 `material_id`
- `facts`: 从材料中抽取出的结构化事实
- `normalized_entities`: 去重后的技能、项目、公司、技术名词

每条项目、实习、技能事实建议至少包含：

- `id`
- `type`
- `content`
- `source_refs`
- `confidence`
- `updated_at`

### 3. `resume_content_json`

简历内容的唯一事实来源，由 Resume Content Agent 维护。

要求：

- 必须为结构化 JSON
- 不允许把 HTML 作为简历事实源数据
- 所有下游展示、导出、面试问答都应优先消费该 JSON

建议结构：

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
      "last_content_agent": "resume_content_agent",
      "last_updated_at": "",
      "content_hash": ""
  }
}
```

这里还需要补充两个强制约束：

- `skills / internships / projects / awards / papers` 中每个元素必须有稳定 `id`
- 每个 section item 必须尽量保留 `source_refs`，用于说明该内容来自哪些原始材料或追问回答

建议每个 section item 至少包含：

```json
{
   "id": "project_001",
   "title": "",
   "content": "",
   "source_refs": ["material_12", "message_08"],
   "editable": true,
   "updated_at": ""
}
```

这样才能支持：

- 局部重写单个项目
- 删除指定经历而不影响其他 section
- 前端精准高亮“本次更新了哪一条内容”

### 4. `render_config`

渲染配置，由 Resume Render Agent 维护。

要求：

- 只描述展示，不描述事实内容
- 任何渲染修改都优先写入该配置
- Render Agent 根据 `resume_content_json + render_config` 生成 HTML

建议结构：

```json
{
  "template_id": "default",
  "theme": "light",
  "font_family": "Source Han Sans",
  "font_size": 14,
  "line_height": 1.5,
  "page_margin": {
    "top": 24,
    "right": 24,
    "bottom": 24,
    "left": 24
  },
  "section_order": ["profile", "skills", "projects", "internships", "awards"],
  "dense_mode": false,
   "accent_style": "minimal",
   "version": 1,
   "last_render_reason": "user_render_edit"
}
```

为了支撑稳定渲染，建议再明确以下字段：

- `visibility_map`: 控制 section 是否显示
- `layout_mode`: single-column / double-column
- `spacing_scale`: 紧凑、标准、宽松
- `custom_css_tokens`: 前端模板变量，而不是任意自由 HTML

原则：

- Render Agent 修改的是“渲染配置”，不是直接改 HTML 字符串
- 前端可在不调用 LLM 的情况下消费一部分明确配置项

### 5. `resume_html`

最终预览产物，由 Resume Render Agent 维护。

要求：

- 是渲染结果，不是事实源
- 必须可以由 `resume_content_json + render_config` 再生成
- 允许用于预览、导出 PDF、前端展示

为了支持缓存、回滚与导出，`resume_html` 不建议只存一个字符串，建议改为对象：

```json
{
   "html": "<html>...</html>",
   "version": 3,
   "derived_from_content_version": 5,
   "derived_from_render_version": 2,
   "updated_at": "",
   "checksum": ""
}
```

这样可以明确判断：

- 当前 HTML 是否过期
- 当前导出对应的是哪一版内容与哪一版样式
- 是否需要重新渲染

### 6. `gaps`

能力缺口列表，由 Gap Analysis Agent 维护。

示例：

- 缺失技能
- 缺失经历
- 缺少量化结果
- 相关性不足的 section

每条 gap 建议至少包含：

- `id`
- `type`
- `severity`
- `description`
- `related_section_ids`
- `resolved`
- `resolution_source`

### 7. `questions_to_ask`

待追问问题列表，由 Gap Analysis Agent 或 Planner 维护。

每条 question 建议至少包含：

- `id`
- `question`
- `reason`
- `target_field`
- `priority`
- `status`: pending / answered / dismissed
- `answer_ref`

### 8. `conversation_events`

事件流，用于记录：

- 用户输入
- 识别到的 intent
- 受影响状态
- 触发的 Agent 链路
- 执行结果

这是调试和可追踪性的关键，建议每条 event 至少包含：

- `event_id`
- `message_id`
- `intent`
- `triggered_agents`
- `state_diff_summary`
- `created_at`
- `status`

---

### 9. `meta`

`meta` 不应是模糊兜底字段，建议只放全局运行元信息：

- `active_resume_content_version`
- `active_render_version`
- `active_html_version`
- `last_user_message_id`
- `last_successful_pipeline`
- `dirty_flags`

其中 `dirty_flags` 很关键，建议至少有：

```json
{
   "content_dirty": false,
   "render_dirty": false,
   "interview_dirty": false,
   "export_dirty": false
}
```

用途：

- 判断是否需要重跑 Resume Content Agent
- 判断是否只需要重跑 Render Agent
- 判断当前面试问答是否过期

### 10. `pending_actions`

这个字段是当前 PRD 里缺失但实现上非常必要的，用于承接异步或待确认动作。

建议内容包括：

- 等待用户回答的问题
- 尚未完成的导出任务
- 等待确认的渲染调整建议
- 后台异步生成中的面试问答任务

每条 action 建议至少包含：

- `id`
- `type`
- `status`
- `owner_agent`
- `depends_on`
- `created_at`

---

## 4.3 状态不变量（必须写死）

为避免开发过程出现状态错乱，建议把以下规则写成不变量：

1. `resume_content_json` 是简历事实的唯一真值来源。
2. `resume_html` 只能由 `resume_content_json + render_config` 派生，不可直接人工修改后回写事实层。
3. 任何 section 级内容都必须有稳定 `id`，否则无法支持局部更新。
4. `conversation_events` 必须可回放最近一次状态变化路径。
5. 当 `content_dirty=true` 时，`resume_html` 和 `interview` 结果默认视为可能过期。
6. 当 `render_dirty=true` 时，只要求重新生成 `resume_html`，不要求重跑内容链路。

## 4.4 为什么这些字段是必须的

如果缺少上面的 `id / version / source_refs / dirty_flags / pending_actions`，后续会直接出现四类问题：

- 无法精准更新某一条项目或某一段实习
- 无法判断当前 HTML 是否是最新渲染结果
- 无法解释“为什么这次触发了某个 Agent”
- 无法在异步生成、追问、导出场景下稳定管理状态

---

# 五、核心功能模块

## 5.1 对话式输入系统

### 功能

- 支持多轮输入 JD、简历、项目经历、实习经历、论文、自由补充文本
- 支持覆盖、删除、改写和追加信息
- 支持通过自然语言控制简历展示样式

### 关键要求

- 每轮输入都必须先做意图分类
- 系统必须识别该轮输入是“内容更新”还是“渲染更新”
- 不允许把渲染修改误路由到内容链路

## 5.2 JD 解析模块（JD Agent）

### 功能

- 提取岗位技术关键词
- 提取能力要求
- 提取岗位职责与隐含要求

### 输出

- 结构化 `job` JSON

## 5.3 用户材料解析模块（Profile Agent）

### 功能

- 解析 PDF / DOCX / Markdown / 文本
- 抽取技能、项目、成果、角色、量化结果
- 将原始材料映射到结构化 `candidate_profile`

### 约束

- 不直接写最终简历 HTML
- 不直接决定最终 section 的文案风格

## 5.4 Gap 分析模块（Gap Analysis Agent）

### 功能

- 对比 `job` 与 `candidate_profile`
- 输出匹配度评分、缺失能力、优化建议、待追问问题

### 输出

- `gaps`
- `questions_to_ask`

## 5.5 简历内容生成模块（Resume Content Agent）

### 功能

- 自动改写项目描述为 STAR 风格
- 优化技能排序
- 根据 JD 进行关键词对齐
- 将候选人画像映射为标准化 `resume_content_json`

### 输入

- `job`
- `candidate_profile`
- `gaps`
- 用户追加内容类指令

### 输出

- `resume_content_json`
- 可选 `content_diff`，用于前端提示本轮更新了哪些区块

### 局部更新原则

- 修改项目，只更新 `projects`
- 修改技能，只更新 `skills`
- 删除经历，只更新对应 section
- 用户只修改渲染，不触发该 Agent

### 强约束

- 不得捏造用户没有提供的事实
- 不直接输出 HTML
- 不修改 `render_config`

## 5.6 简历渲染模块（Resume Render Agent）

### 功能

- 将 `resume_content_json` 渲染为最终 HTML
- 将用户的渲染指令转成结构化 `render_config`
- 支持主题、行距、字号、页边距、section 排序等布局调整

### 输入

- `resume_content_json`
- `render_config`
- 用户追加渲染类指令

### 输出

- 更新后的 `render_config`
- `resume_html`
- 可选 `render_metadata`，例如页数估计、溢出警告、模板版本号

### 支持的渲染指令示例

- “把行距调大一点”
- “整体更紧凑一些”
- “页边距改小，尽量压缩到一页”
- “标题更明显一些”
- “项目区放在实习前面”
- “改成极简黑白风格”

### 强约束

- 不得修改 `resume_content_json` 的事实内容
- 不得补充或删除项目、技能、经历事实
- 渲染失败时允许回退默认模板，但不得丢失内容 JSON

## 5.7 面试问答生成模块（Interview Agent）

### 功能

- 生成技术问题
- 生成项目深挖问题
- 生成行为面试问题
- 生成参考答案

### 依赖

- 依赖 `job`
- 依赖 `candidate_profile`
- 依赖 `resume_content_json`
- 不依赖 `resume_html`

## 5.8 主动追问机制

系统自动生成问题，例如：

- “你的项目是否有量化成果？”
- “你在团队中的职责是什么？”
- “该岗位要求 C#，你是否有相关经验？”
- “这段实习里你主要负责系统设计、开发还是测试？”

这是 Agent 产品感和工程价值的重要体现。

## 5.9 实时更新策略

### 更新路由规则

1. 用户修改 JD：
   - 触发 `JD Agent → Gap Analysis Agent → Resume Content Agent → Resume Render Agent → Interview Agent`
2. 用户补充项目 / 实习 / 技能：
   - 触发 `Profile Agent → Resume Content Agent → Resume Render Agent → Interview Agent`
3. 用户只修改样式：
   - 只触发 `Render Config Parser / Resume Render Agent`
4. 用户要求“更突出后端能力”：
   - 触发 `Resume Content Agent`，随后触发 `Resume Render Agent`
5. 用户只问“为什么匹配度低”：
   - 优先触发 `Gap Analysis Agent`，不重新生成简历

### 局部更新原则

- 内容未变时，只重渲染 HTML
- 样式未变时，只更新受影响内容 section 和相关 HTML 片段
- 面试问答默认依赖内容 JSON，不依赖 HTML

## 5.10 导出功能

支持导出：

- 岗位分析报告（PDF / Markdown）
- 简历内容 JSON（调试 / 存档）
- 简历 HTML（预览 / 前端展示）
- 简历 PDF / DOCX（由 HTML 或模板转换生成）
- 面试问答集（Markdown / PDF）

---

# 六、Agent 架构设计

## 6.1 总体架构

```text
用户输入
   ↓
Planner Agent
   ↓
├── JD Agent
├── Profile Agent
├── Gap Analysis Agent
├── Resume Content Agent
├── Resume Render Agent
└── Interview Agent
   ↓
状态更新（JSON）
   ↓
HTML 渲染 / 结果展示 / 导出
```

## 6.2 Planner Agent 职责

- 识别用户输入的 intent
- 决定执行流程
- 判断是否需要追问
- 判断是否需要只更新 `render_config`
- 控制是否重新生成内容
- 控制是否只重渲染 HTML

### 推荐拆分的子职责

#### 1. Intent Classifier

分类结果建议至少包含：

- `upload_jd`
- `upload_profile`
- `content_edit`
- `render_edit`
- `export`
- `ask_question`

#### 2. State Diff Planner

- 判断本轮输入影响哪些状态字段
- 输出最小执行计划，避免全链路重跑

#### 3. Execution Orchestrator

- 顺序调度各 Agent
- 记录事件流
- 管理失败回退路径

## 6.3 Agent 边界约束

为避免开发时职责混乱，以下边界必须固定：

- JD Agent 只能写 `job`
- Profile Agent 只能写 `candidate_profile`
- Gap Analysis Agent 只能写 `gaps` 和 `questions_to_ask`
- Resume Content Agent 只能写 `resume_content_json`
- Resume Render Agent 只能写 `render_config` 和 `resume_html`
- Interview Agent 只能读取 `job + candidate_profile + resume_content_json`

## 6.4 推荐执行流

### 场景 A：首次输入 JD + 材料

`JD Agent → Profile Agent → Gap Analysis Agent → Resume Content Agent → Resume Render Agent → Interview Agent`

### 场景 B：补充项目经历

`Profile Agent → Resume Content Agent → Resume Render Agent → Interview Agent`

### 场景 C：只修改行距 / 页边距 / 模板

`Render Config Parser → Resume Render Agent`

### 场景 D：只问匹配度问题

`Gap Analysis Agent` 直接回复，不重跑全链路

---

# 七、记忆系统设计

## 7.1 会话内记忆

记录：

- 用户输入内容
- 当前状态快照
- 当前 `resume_content_json`
- 当前 `render_config`
- 当前 `resume_html` 版本号
- 最近一次输入 intent

作用：

- 保持上下文一致性
- 支持局部更新与回滚
- 支持调试“为什么这次只重渲染了 HTML”

## 7.2 跨会话记忆（可选）

记录：

- 常用技能
- 历史项目
- 偏好岗位
- 常用渲染偏好，例如一页简历、紧凑排版、极简模板

作用：

- 个性化生成内容
- 下次自动恢复简历渲染偏好

---

# 八、系统架构设计

## 8.1 总体系统架构

```text
Frontend (Vue3)
   ↓
Backend (FastAPI)
   ↓
Conversation API / Session API
   ↓
Agent Orchestrator (LangGraph、LangChain)
   ↓
├── Content Pipeline
│    ├── JD Agent
│    ├── Profile Agent
│    ├── Gap Analysis Agent
│    └── Resume Content Agent
│
├── Render Pipeline
│    ├── Render Config Parser
│    └── Resume Render Agent
│
└── Interview Pipeline
     └── Interview Agent
   ↓
LLM / Embedding / Rerank Models
   ↓
Storage
  - Redis（会话态 / 缓存 / 中间任务态）
  - DB（结构化 JSON 持久化，MySQL）
  - Object Storage（上传文件 / HTML 快照 / 导出文件，后续按需接入）
```

## 8.2 核心组件

### 1. 文件解析层

- PDF -> Markdown
- DOCX -> Markdown
- Markdown / TXT -> 标准文本
- 解析结果归入 `candidate_profile` 原始材料区

### 2. 并发控制

- 使用 semaphore 限制 LLM 并发调用
- Resume Render Agent 必须支持幂等执行，避免并发覆盖旧 HTML

### 3. 状态存储

建议至少拆分三类对象：

- `resume_content_json`
- `render_config_json`
- `resume_html`

### 4. 导出链路

- HTML 作为统一预览层
- PDF / DOCX 由 HTML 或模板转换得到
- 导出必须基于当前 `resume_content_json + render_config`

## 8.3 前后端接口建议

### `POST /chat`

输入：

- `session_id`
- `message`
- `attachments`

输出：

- `job`
- `gaps`
- `questions_to_ask`
- `resume_content_json`
- `render_config`
- `resume_html`
- `triggered_agents`

### `POST /resume/render`

输入：

- `session_id`
- `render_instruction`

输出：

- `render_config`
- `resume_html`

### `GET /resume/content`

- 返回当前 `resume_content_json`

### `GET /resume/html`

- 返回当前 `resume_html`

### `POST /export`

- 支持 html / pdf / markdown / json 导出

---

# 九、关键设计难点

## 9.1 状态一致性

- 用户会修改历史输入
- 需要明确区分内容状态与渲染状态
- 需要支持最小影响范围更新

## 9.2 局部更新

- 避免全量重生成
- 必须根据 intent 路由最小执行链

## 9.3 信息抽取

- 非结构化材料到结构化画像的稳定映射
- 结构化结果必须可直接映射到 `resume_content_json`

## 9.4 记忆污染

- 区分有效事实与历史噪声
- 区分历史渲染偏好与当前 session 临时需求

## 9.5 内容层与视图层解耦

- 防止 HTML 反向污染业务事实数据
- 防止“改样式”误触发“改内容”

## 9.6 导出一致性

- HTML、PDF、页面预览必须来自同一份 `resume_content_json + render_config`

---

# 十、MVP 版本规划

## 第一阶段（核心）

- JD 解析
- 结构化简历内容 JSON 生成
- HTML 简历渲染
- 对话输入
- 实时预览
- 内容指令 / 渲染指令路由

## 第二阶段

- Gap 分析
- 面试问答生成
- 主动追问
- 局部更新 diff 展示

## 第三阶段（加分）

- 记忆系统
- 多模板
- 更细粒度的 section 级渲染控制
- HTML 到 PDF 的精细导出
- 渲染风格偏好记忆

---

# 十一、项目亮点（用于简历）

可以写成：

- 基于 LangGraph 构建对话式多 Agent 求职系统
- 实现候选人画像动态建模与信息补全
- 将简历内容生成与 HTML 渲染解耦，构建 JSON + HTML 双层架构
- 支持实时简历生成、样式调整与局部更新
- 引入主动追问机制提升信息完整性
- 构建岗位分析、简历优化、简历渲染与面试准备闭环

---

# 十二、开发约束与验收标准（防歧义）

## 12.1 不允许的实现方式

- 不允许把 HTML 作为唯一简历存储格式
- 不允许 Resume Content Agent 直接输出最终页面结构
- 不允许 Resume Render Agent 直接编造项目、技能、经历内容
- 不允许用户一句“加大行距”导致全链路重新跑 JD、Gap、Interview
- 不允许 Interview Agent 依赖 HTML 抽取事实

## 12.2 最小可用验收标准

### A. 内容链路

- 输入 JD 和两份项目材料后，可以生成稳定的 `resume_content_json`
- 用户补充一段项目经历后，只更新对应 section，不重写全部简历

### B. 渲染链路

- 用户输入“行距从 1.3 改成 1.6”后，只更新 `render_config` 和 `resume_html`
- HTML 预览刷新时间应明显低于一次完整内容重生成

### C. 一致性

- `resume_html` 必须可以由 `resume_content_json + render_config` 重新生成
- 导出的 PDF 与页面预览保持一致

### D. 可追踪性

- 每次用户输入都能在事件流中看到：`intent -> affected_state -> triggered_agents`
