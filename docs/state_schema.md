# State Schema

全局状态 JSON Schema 定义。所有 Agent 共享该状态结构，通过 LangGraph State 管理。

---

## 顶层结构

```json
{
  "session_id": "string (required)",
  "job": "Job",
  "candidate_profile": "CandidateProfile",
  "resume_content_json": "ResumeContent",
  "render_config": "RenderConfig",
  "resume_html": "ResumeHtml",
  "gaps": "Gap[]",
  "questions_to_ask": "Question[]",
  "interview_qa": "InterviewQA[]",
  "conversation_events": "ConversationEvent[]",
  "meta": "Meta",
  "pending_actions": "PendingAction[]"
}
```

---

## `session_id`

| 属性 | 值 |
|------|-----|
| 类型 | string |
| 必填 | 是 |
| 说明 | 会话唯一标识，贯穿前后端、Redis、事件流、导出 |

---

## `Job`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | JD 唯一标识 |
| source | string | 是 | 原始 JD 文本或文件引用 |
| parsed_at | string (ISO 8601) | 是 | 解析时间 |
| version | int | 是 | 结构版本号 |
| industry | string | 否 | 行业 |
| title | string | 是 | 岗位名称 |
| tech_stack | string[] | 是 | 技术栈 |
| keywords | string[] | 是 | 核心关键词 |
| hard_skills | string[] | 是 | 硬技能 |
| soft_skills | string[] | 否 | 软技能 |
| responsibilities | string[] | 是 | 职责 |
| education_requirement | string | 否 | 学历要求 |
| experience_requirement | string | 否 | 经验要求 |
| implicit_preferences | string[] | 否 | 隐含偏好 |
| bonus_items | string[] | 否 | 加分项 |

写入者：JD Agent

---

## `CandidateProfile`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| profile_basic | ProfileBasic | 是 | 基本信息 |
| materials | Material[] | 是 | 原始材料仓库 |
| facts | Fact[] | 是 | 结构化事实 |

### `ProfileBasic`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 姓名 |
| email | string | 否 | 邮箱 |
| phone | string | 否 | 电话 |
| city | string | 否 | 城市 |
| school | string | 否 | 学校 |

### `Material`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| material_id | string | 是 | 材料唯一标识 |
| type | string | 是 | pdf / docx / text / message |
| content | string | 是 | 原始内容 |
| uploaded_at | string (ISO 8601) | 是 | 上传时间 |

### `Fact`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 事实唯一标识 |
| type | string | 是 | skill / project / internship / award / paper |
| content | string | 是 | 结构化内容 |
| source_refs | string[] | 是 | 来源材料/消息 ID |
| updated_at | string (ISO 8601) | 是 | 更新时间 |

写入者：Profile Agent

---

## `ResumeContent`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| profile | ResumeProfile | 是 | 个人信息 |
| summary | string | 是 | 个人总结 |
| skills | SectionItem[] | 是 | 技能列表 |
| internships | SectionItem[] | 是 | 实习经历 |
| projects | SectionItem[] | 是 | 项目经历 |
| awards | SectionItem[] | 是 | 获奖 |
| papers | SectionItem[] | 是 | 论文 |
| meta | ResumeContentMeta | 是 | 内容元信息 |

### `ResumeProfile`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 姓名 |
| email | string | 否 | 邮箱 |
| phone | string | 否 | 电话 |
| city | string | 否 | 城市 |
| github | string | 否 | GitHub 地址 |
| education | Education[] | 是 | 教育经历 |

### `Education`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识 |
| school | string | 是 | 学校 |
| major | string | 是 | 专业 |
| degree | string | 是 | 学位 |
| start_date | string | 是 | 开始日期 |
| end_date | string | 是 | 结束日期 |

### `SectionItem`（通用）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 稳定唯一标识 |
| title | string | 是 | 标题 |
| content | string | 是 | 内容描述 |
| source_refs | string[] | 是 | 来源材料/消息 ID |
| updated_at | string (ISO 8601) | 是 | 更新时间 |

### `ResumeContentMeta`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| target_role | string | 是 | 目标岗位 |
| version | int | 是 | 内容版本号 |
| last_updated_at | string (ISO 8601) | 是 | 最后更新时间 |
| content_hash | string | 是 | 内容哈希（用于脏检测）|

写入者：Resume Content Agent

---

## `RenderConfig`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| template_id | string | 是 | "default" | 模板 ID |
| theme | string | 是 | "light" | 主题 |
| font_family | string | 是 | "Source Han Sans" | 字体 |
| font_size | int | 是 | 14 | 字号 |
| line_height | float | 是 | 1.5 | 行高 |
| page_margin | PageMargin | 是 | 见下 | 页边距 |
| section_order | string[] | 是 | 见下 | Section 排序 |
| dense_mode | bool | 是 | false | 紧凑模式 |
| accent_style | string | 是 | "minimal" | 强调风格 |
| visibility_map | object | 是 | {} | Section 显示控制 |
| layout_mode | string | 是 | "single-column" | single-column / double-column |
| spacing_scale | string | 是 | "standard" | compact / standard / relaxed |
| version | int | 是 | 1 | 渲染配置版本号 |
| last_render_reason | string | 否 | "" | 最近一次渲染原因 |

### `PageMargin`

| 字段 | 类型 | 默认值 |
|------|------|--------|
| top | int | 24 |
| right | int | 24 |
| bottom | int | 24 |
| left | int | 24 |

默认 `section_order`：`["profile", "skills", "projects", "internships", "awards"]`

写入者：Resume Render Agent

---

## `ResumeHtml`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| html | string | 是 | HTML 字符串 |
| version | int | 是 | HTML 版本号 |
| derived_from_content_version | int | 是 | 对应的内容版本 |
| derived_from_render_version | int | 是 | 对应的渲染配置版本 |
| updated_at | string (ISO 8601) | 是 | 更新时间 |
| checksum | string | 是 | HTML 校验和 |

写入者：Resume Render Agent

---

## `Gap`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识 |
| type | string | 是 | missing_skill / missing_experience / no_quantification / low_relevance |
| severity | string | 是 | high / medium / low |
| description | string | 是 | 缺口描述 |
| related_section_ids | string[] | 否 | 关联的 section item id |
| resolved | bool | 是 | 是否已解决 |
| resolution_source | string | 否 | 解决来源 |

写入者：Gap Analysis Agent

---

## `Question`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识 |
| question | string | 是 | 问题内容 |
| reason | string | 是 | 追问原因 |
| target_field | string | 是 | 目标状态字段 |
| priority | string | 是 | high / medium / low |
| status | string | 是 | pending / answered / dismissed |
| answer_ref | string | 否 | 回答对应的消息 ID |

写入者：Gap Analysis Agent

---

## `InterviewQA`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识 |
| category | string | 是 | technical / project_deep_dive / behavioral |
| question | string | 是 | 问题 |
| answer | string | 是 | 参考答案 |
| source_refs | string[] | 是 | 内容来源引用 |
| version | int | 是 | 版本号 |

写入者：Interview Agent

---

## `ConversationEvent`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| event_id | string | 是 | 唯一标识 |
| message_id | string | 是 | 用户消息 ID |
| intent | string | 是 | 识别到的意图 |
| triggered_agents | string[] | 是 | 触发的 Agent 列表 |
| state_diff_summary | object | 是 | 状态变化摘要 |
| created_at | string (ISO 8601) | 是 | 创建时间 |
| status | string | 是 | success / failed / partial |

写入者：Planner Agent

---

## `Meta`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| active_resume_content_version | int | 是 | 当前内容版本 |
| active_render_version | int | 是 | 当前渲染配置版本 |
| active_html_version | int | 是 | 当前 HTML 版本 |
| last_user_message_id | string | 是 | 最近用户消息 ID |
| last_successful_pipeline | string | 否 | 最近成功的 pipeline 名 |
| dirty_flags | DirtyFlags | 是 | 脏标记 |

### `DirtyFlags`

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| content_dirty | bool | false | 内容是否已修改 |
| render_dirty | bool | false | 渲染配置是否已修改 |
| interview_dirty | bool | false | 面试问答是否过期 |
| export_dirty | bool | false | 导出是否过期 |

写入者：Planner Agent

---

## `PendingAction`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 唯一标识 |
| type | string | 是 | wait_answer / export / render_confirm / async_generate |
| status | string | 是 | pending / completed / cancelled |
| owner_agent | string | 是 | 负责的 Agent |
| depends_on | string[] | 否 | 依赖的 action id |
| created_at | string (ISO 8601) | 是 | 创建时间 |

写入者：Planner Agent

---

## 状态不变量

1. `resume_content_json` 是简历事实的唯一真值来源
2. `resume_html` 只能由 `resume_content_json + render_config` 派生，禁止回写事实层
3. 所有 section item 必须有稳定 `id`
4. `conversation_events` 可回放最近一次状态变化路径
5. `content_dirty=true` 时，`resume_html` 和 `interview_qa` 视为过期
6. `render_dirty=true` 时，只重新生成 `resume_html`，不重跑内容链路
