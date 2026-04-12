# Workflow Plan

系统 Workflow 定义：阶段、流转条件、跳过逻辑。

---

## 1. 主流程

```
用户输入
  ↓
Planner Agent: Intent Classifier
  ↓
Planner Agent: State Diff Planner → 生成 execution_plan
  ↓
Planner Agent: Execution Orchestrator → 按 plan 顺序调度 Agent
  ↓
状态更新 + 记录 conversation_event
  ↓
返回结果给前端
```

---

## 2. Intent 到执行链路映射

| Intent | 执行链路 | 说明 |
|--------|----------|------|
| upload_jd | JD Agent → Gap Analysis Agent → Resume Content Agent → Resume Render Agent → Interview Agent | 全链路 |
| upload_profile | Profile Agent → Resume Content Agent → Resume Render Agent → Interview Agent | 跳过 JD Agent |
| content_edit | Resume Content Agent → Resume Render Agent | 跳过 Profile/Gap/Interview（除非内容变化触发 dirty） |
| render_edit | Resume Render Agent | 只跑渲染 |
| export | 导出服务（非 Agent）| 读取当前状态直接导出 |
| ask_question | Gap Analysis Agent | 只读查询，不修改内容 |

---

## 3. 条件分支规则

### 3.1 首次 vs 增量

| 条件 | 行为 |
|------|------|
| `job` 为空 且 intent = upload_jd | 执行全链路 |
| `job` 非空 且 intent = upload_jd | JD Agent 覆盖更新 → 后续链路全部重跑 |
| `candidate_profile` 为空 且 intent = upload_profile | Profile Agent 创建 → 后续链路 |
| `candidate_profile` 非空 且 intent = upload_profile | Profile Agent 增量合并 → 仅受影响 section 重跑 |

### 3.2 内容编辑细分

| 条件 | 行为 |
|------|------|
| 用户修改特定 section（如 projects）| Resume Content Agent 只更新 projects → Resume Render Agent |
| 用户要求"更突出某能力" | Resume Content Agent 调整相关 section → Resume Render Agent |
| 用户删除某条经历 | Resume Content Agent 删除对应 item → Resume Render Agent |

### 3.3 渲染编辑

| 条件 | 行为 |
|------|------|
| 用户修改行距/字号/边距等 | Resume Render Agent 更新 render_config → 重新生成 resume_html |
| 用户切换模板/主题 | Resume Render Agent 更新 template_id/theme → 重新生成 resume_html |
| 用户调整 section 顺序 | Resume Render Agent 更新 section_order → 重新生成 resume_html |

---

## 4. 跳过逻辑

| 条件 | 跳过的 Agent | 原因 |
|------|-------------|------|
| intent = render_edit | JD, Profile, Gap, Resume Content, Interview | 渲染不涉及内容变更 |
| intent = ask_question | 除 Gap Analysis 外所有 | 只读查询 |
| intent = export | 所有 Agent | 直接读取当前状态导出 |
| `job` 为空 且 intent = upload_profile | Gap Analysis Agent | 没有 JD 无法做 Gap 分析 |
| `candidate_profile` 为空 且 intent = upload_jd | Resume Content Agent, Resume Render Agent, Interview Agent | 没有候选人数据无法生成简历 |
| content_dirty = false 且 intent 非内容相关 | Resume Content Agent | 内容未变无需重跑 |
| render_dirty = false 且 content_dirty = false | Resume Render Agent | 无需重渲染 |

---

## 5. Dirty Flag 驱动规则

| 事件 | dirty_flags 变化 |
|------|-----------------|
| Resume Content Agent 写入 | content_dirty=false, render_dirty=true, interview_dirty=true, export_dirty=true |
| Resume Render Agent 写入 | render_dirty=false, export_dirty=true |
| Interview Agent 写入 | interview_dirty=false |
| 导出完成 | export_dirty=false |
| JD Agent 写入 | content_dirty=true, render_dirty=true, interview_dirty=true |
| Profile Agent 写入 | content_dirty=true, render_dirty=true, interview_dirty=true |

---

## 6. 失败回退

| 失败点 | 回退策略 |
|--------|----------|
| JD Agent 解析失败 | 返回错误信息，不修改状态，记录 event(status=failed) |
| Profile Agent 解析失败 | 返回错误信息，保留已有 candidate_profile |
| Resume Content Agent 失败 | 保留上一版 resume_content_json |
| Resume Render Agent 失败 | 回退默认模板重试一次，仍失败则保留上一版 resume_html |
| Interview Agent 失败 | 保留上一版 interview_qa，标记 interview_dirty=true |
| 任何 Agent 超时 | 记录 event(status=failed)，返回超时提示 |

---

## 7. 执行约束

1. Agent 按链路顺序串行执行，不并行
2. 每个 Agent 执行完毕后立即写入状态并更新 dirty_flags
3. 每轮用户输入只生成一条 conversation_event
4. Planner Agent 记录完整执行链路到 event.triggered_agents
5. 渲染指令不触发内容链路
6. 内容指令执行后自动触发渲染链路
