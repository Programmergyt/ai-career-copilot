# Agents Contract

所有 Agent 的输入/输出/禁写字段契约。

当前阶段的设计目标不是立即把 workflow 改造成统一 Plan Executor，而是先完成 Agent 模块解耦：

1. 用 `contracts.py` 将读写边界显式化。
2. 用 `registry.py` 统一 Agent 注册和查找。
3. 用 `runtime.py` 统一做运行前校验、运行后 patch 校验、日志与异常包装。
4. 保留现有 `workflow/graph.py` 和 `execution_plan` 路由方式不变。

因此，本文件的契约既是设计约束，也是 `backend/agents/contracts.py` 的直接来源。

---

## 契约总表

| Agent | 读取字段 | 写入字段 | 禁止写入 |
|-------|----------|----------|----------|
| Planner Agent | 业务状态只读 + 运行时输入 | `active_plan_id`, `current_intent`, `execution_plan`, `execution_steps`, `triggered_agents`, `reply_message`, `meta` | `job`, `candidate_profile`, `resume_content_json`, `render_config`, `resume_html`, `gaps`, `questions_to_ask`, `interview_qa` |
| JD Agent | `user_message`, `user_attachments`, `job`, `meta` | `job`, `meta`, `reply_message` | `candidate_profile`, `resume_content_json`, `render_config`, `resume_html`, `gaps`, `questions_to_ask`, `interview_qa` |
| Profile Agent | `user_message`, `user_attachments`, `candidate_profile`, `meta` | `candidate_profile`, `meta`, `reply_message` | `job`, `resume_content_json`, `render_config`, `resume_html`, `gaps`, `questions_to_ask`, `interview_qa` |
| Gap Analysis Agent | `job`, `candidate_profile`, `resume_content_json`, `questions_to_ask`, `meta` | `gaps`, `questions_to_ask`, `meta`, `reply_message` | `job`, `candidate_profile`, `resume_content_json`, `render_config`, `resume_html`, `interview_qa` |
| Resume Content Agent | `job`, `candidate_profile`, `gaps`, `resume_content_json`, `current_intent`, `user_message`, `meta` | `resume_content_json`, `meta`, `reply_message` | `render_config`, `resume_html`, `job`, `candidate_profile`, `gaps`, `questions_to_ask`, `interview_qa` |
| Resume Render Agent | `resume_content_json`, `render_config`, `current_intent`, `user_message`, `resume_html`, `meta` | `render_config`, `resume_html`, `meta`, `reply_message` | `resume_content_json`, `job`, `candidate_profile`, `gaps`, `questions_to_ask`, `interview_qa` |
| Interview Agent | `job`, `candidate_profile`, `resume_content_json`, `interview_qa`, `meta` | `interview_qa`, `meta`, `reply_message` | `render_config`, `resume_html`, `job`, `candidate_profile`, `gaps`, `questions_to_ask`, `resume_content_json` |

说明：

- `reply_message` 和 `meta` 作为节点级运行结果，允许由业务 Agent 更新。
- `execution_steps` 在当前阶段只是 Planner 输出的结构化镜像，不参与实际调度。
- `conversation_events`、`pending_actions` 暂不纳入运行时强校验范围，避免与当前实现脱节。

---

## 逐 Agent 详细契约

### 1. Planner Agent

```
读取: session_id, job, candidate_profile, resume_content_json, render_config, gaps, questions_to_ask, interview_qa, meta, 用户输入
写入: active_plan_id, current_intent, execution_plan, execution_steps, triggered_agents, reply_message, meta
禁写: job, candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**子模块职责：**

| 子模块 | 输入 | 输出 |
|--------|------|------|
| Intent Classifier | 用户消息文本 | intent (upload_jd / upload_profile / content_edit / render_edit / export / ask_question) |
| State Diff Planner | intent, 当前 state | affected_fields[], execution_plan |
| Execution Metadata Builder | execution_plan, contract | execution_steps |

---

### 2. JD Agent

```
读取: user_message, user_attachments, job, meta
写入: job, meta, reply_message
禁写: candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**输出格式：** 完整 `Job` 对象（见 state_schema.md）

**触发条件：** intent = upload_jd

---

### 3. Profile Agent

```
读取: user_message, user_attachments, candidate_profile, meta
写入: candidate_profile, meta, reply_message
禁写: job, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**输出格式：** 完整 `CandidateProfile` 对象（增量合并到已有数据）

**触发条件：** intent = upload_profile

**约束：**
- 不写简历 HTML
- 不决定文案风格
- 增量合并材料和事实，不覆盖已有数据

---

### 4. Gap Analysis Agent

```
读取: job, candidate_profile, resume_content_json, questions_to_ask, meta
写入: gaps, questions_to_ask, meta, reply_message
禁写: resume_content_json, render_config, resume_html, interview_qa, job, candidate_profile
```

**输出格式：**
- `Gap[]`：能力缺口列表
- `Question[]`：待追问问题列表

**触发条件：** intent = upload_jd（JD 更新后）、intent = ask_question（匹配度查询）

---

### 5. Resume Content Agent

```
读取: job, candidate_profile, gaps, resume_content_json, current_intent, user_message, meta
写入: resume_content_json, meta, reply_message
禁写: render_config, resume_html, job, candidate_profile, gaps, questions_to_ask, interview_qa
```

**输出格式：** 完整 `ResumeContent` 对象（局部更新时只修改受影响的 section）

**触发条件：** intent = upload_jd / upload_profile / content_edit

**约束：**
- 不得捏造用户未提供的事实
- 不输出 HTML
- 不修改 render_config
- 局部更新：修改项目只更新 `projects`，修改技能只更新 `skills`

---

### 6. Resume Render Agent

```
读取: resume_content_json, render_config, current_intent, user_message, resume_html, meta
写入: render_config, resume_html, meta, reply_message
禁写: resume_content_json, job, candidate_profile, gaps, questions_to_ask, interview_qa
```

**输出格式：**
- 更新后的 `RenderConfig` 对象
- 新的 `ResumeHtml` 对象

**触发条件：** intent = render_edit、内容更新后自动触发

**约束：**
- 不修改 resume_content_json 的事实内容
- 不补充或删除项目、技能、经历
- 渲染失败时回退默认模板，不丢失内容 JSON
- 幂等执行，相同输入产出相同 HTML

---

### 7. Interview Agent

```
读取: job, candidate_profile, resume_content_json, interview_qa, meta
写入: interview_qa, meta, reply_message
禁写: render_config, resume_html, job, candidate_profile, gaps, questions_to_ask, resume_content_json
```

**输出格式：** `InterviewQA[]` 列表

**触发条件：** 内容链路执行完成后自动触发

**约束：**
- 不依赖 resume_html
- 不修改任何其他状态字段

---

## 边界约束总结

1. 每个 Agent 只能写入其指定字段，违反即为运行时 contract violation
2. 所有 Agent 通过 LangGraph State 读写，不直接访问数据库
3. Agent 间不直接调用；当前阶段仍由固定 workflow 图调度
4. 写入时必须维护对应的 `version` 或派生版本关系
5. 写入 `meta.dirty_flags` 的责任可以由业务 Agent 自己完成，runtime 只做边界校验，不替业务补丁
6. 当前阶段的目标是“统一接入与校验”，不是“统一执行器”；因此 contract 先服务于解耦和测试，再服务于下一阶段 executor 化
