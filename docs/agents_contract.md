# Agents Contract

所有 Agent 的输入/输出/禁写字段契约。

---

## 契约总表

| Agent | 读取字段 | 写入字段 | 禁止写入 |
|-------|----------|----------|----------|
| Planner Agent | 全部（只读业务数据）| meta, pending_actions, section_rationales | job, candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa |
| JD Agent | 用户输入（JD 文本/文件）| job, section_rationales | candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa |
| Profile Agent | 用户输入（材料）| candidate_profile, section_rationales | job, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa |
| Gap Analysis Agent | job, candidate_profile | gaps, questions_to_ask, section_rationales | resume_content_json, render_config, resume_html, interview_qa, job, candidate_profile |
| Resume Content Agent | job, candidate_profile, gaps, 用户内容指令 | resume_content_json, section_rationales | render_config, resume_html, job, candidate_profile, gaps, questions_to_ask, interview_qa |
| Resume Render Agent | resume_content_json, render_config, 用户渲染指令 | render_config, resume_html, section_rationales | resume_content_json, job, candidate_profile, gaps, questions_to_ask, interview_qa |
| Interview Agent | job, candidate_profile, resume_content_json | interview_qa, section_rationales | render_config, resume_html, job, candidate_profile, gaps, questions_to_ask, resume_content_json |
| Question Agent | 当前 graph state, 用户问题 | agent_reply_message, section_rationales | 所有业务状态字段 |

---

## 逐 Agent 详细契约

### 1. Planner Agent

```
读取: session_id, conversation_events, meta, 用户输入
写入: meta, pending_actions, section_rationales
禁写: job, candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**子模块职责：**

| 子模块 | 输入 | 输出 |
|--------|------|------|
| Intent Classifier | 用户消息文本 | intent (upload_jd / upload_profile / content_edit / render_edit / export / ask_question) |
| State Diff Planner | intent, 当前 state | affected_fields[], execution_plan |
| Execution Orchestrator | execution_plan | triggered_agents, section_rationales, 调度结果 |

---

### 2. JD Agent

```
读取: 用户输入（JD 文本或文件内容）
写入: job, section_rationales
禁写: candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**输出格式：** 完整 `Job` 对象（见 state_schema.md）

**解释输出：** `section_rationales[]`，说明为什么提取这些岗位要求，以及它们如何影响后续简历匹配和面试准备。

**触发条件：** intent = upload_jd

---

### 3. Profile Agent

```
读取: 用户输入（材料文本、附件解析结果）, candidate_profile（已有数据，用于增量合并）
写入: candidate_profile, section_rationales
禁写: job, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**输出格式：** 完整 `CandidateProfile` 对象（增量合并到已有数据）

**解释输出：** `section_rationales[]`，说明为什么将材料整理为这些基本信息和事实记录。

**触发条件：** intent = upload_profile

**约束：**
- 不写简历 HTML
- 不决定文案风格
- 增量合并材料和事实，不覆盖已有数据

---

### 4. Gap Analysis Agent

```
读取: job, candidate_profile
写入: gaps, questions_to_ask, section_rationales
禁写: resume_content_json, render_config, resume_html, interview_qa, job, candidate_profile
```

**输出格式：**
- `Gap[]`：能力缺口列表
- `Question[]`：待追问问题列表

**解释输出：** `section_rationales[]`，说明为什么这些缺口和追问会影响岗位匹配度。

**触发条件：** intent = upload_jd（JD 更新后）、intent = gap_analysis

---

### 5. Resume Content Agent

```
读取: job, candidate_profile, gaps, 用户内容指令
写入: resume_content_json, section_rationales
禁写: render_config, resume_html, job, candidate_profile, gaps, questions_to_ask, interview_qa
```

**输出格式：** 完整 `ResumeContent` 对象（局部更新时只修改受影响的 section）

**解释输出：** `section_rationales[]`，说明为什么这样排序、改写或呈现技能、项目、实习和总结。

**触发条件：** intent = upload_jd / upload_profile / content_edit

**约束：**
- 不得捏造用户未提供的事实
- 不输出 HTML
- 不修改 render_config
- 局部更新：修改项目只更新 `projects`，修改技能只更新 `skills`

---

### 6. Resume Render Agent

```
读取: resume_content_json, render_config, 用户渲染指令
写入: render_config, resume_html, section_rationales
禁写: resume_content_json, job, candidate_profile, gaps, questions_to_ask, interview_qa
```

**输出格式：**
- 更新后的 `RenderConfig` 对象
- 新的 `ResumeHtml` 对象

**解释输出：** `section_rationales[]`，说明为什么这样调整版式、字号、间距、模板或 section 可见性。

**触发条件：** intent = render_edit、内容更新后自动触发

**约束：**
- 不修改 resume_content_json 的事实内容
- 不补充或删除项目、技能、经历
- 渲染失败时回退默认模板，不丢失内容 JSON
- 幂等执行，相同输入产出相同 HTML

---

### 7. Interview Agent

```
读取: job, candidate_profile, resume_content_json
写入: interview_qa, section_rationales
禁写: render_config, resume_html, job, candidate_profile, gaps, questions_to_ask, resume_content_json
```

**输出格式：** `InterviewQA[]` 列表

**解释输出：** `section_rationales[]`，说明为什么选择这些技术、项目深挖或行为面试问题。

**触发条件：** 内容链路执行完成后自动触发

**约束：**
- 不依赖 resume_html
- 不修改任何其他状态字段

---

### 8. Question Agent

```
读取: 当前 graph state, 用户问题
写入: agent_reply_message, section_rationales
禁写: job, candidate_profile, resume_content_json, render_config, resume_html, gaps, questions_to_ask, interview_qa
```

**输出格式：**
- `agent_reply_message`：给用户的直接回答
- `section_rationales[]`：说明本次回答依据了哪些 graph state 字段

**触发条件：** intent = ask_question

**约束：**
- 基于当前 graph state 回答问题，不持久化额外状态
- 信息不足时说明缺少的状态数据
- 最终用户可见的 `reply_message` 仍由 Respond 节点统一拼装

---

### 9. Respond 节点

```
读取: user_message, current_intent, execution_plan, agent_reply_message, section_rationales
写入: reply_message
禁写: 所有业务状态字段
```

Respond 节点使用稳定 Markdown 模板拼装所有 intent 的最终回复，包含用户输入、意图识别、各 Agent 的用户可见决策依据和最终结果；不调用 LLM 润色。

---

## 边界约束总结

1. 每个 Agent 只能写入其指定字段，违反即为 Bug
2. 所有 Agent 通过 LangGraph State 读写，不直接访问数据库
3. Agent 间不直接调用，由 Planner Agent 的 Execution Orchestrator 调度
4. 写入时必须递增对应的 `version` 字段
5. 写入后必须通知 Planner Agent 更新 `meta.dirty_flags`
6. 各 Agent 不直接生成最终 `reply_message`，只追加 `section_rationales`
7. `section_rationales` 为运行时字段，暂不持久化
8. `section_rationales` 只写面向用户的简要决策依据，不输出模型内部逐步推理
