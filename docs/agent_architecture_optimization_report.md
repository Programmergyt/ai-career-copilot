# Agent 架构优化分析报告（Plan Mode + 模块化解耦）

> 目标：在现有设计基础上，将“固定链路编排”升级为“更灵活的 Plan Mode”，并将各个 Agent 模块化、可插拔、彼此解耦。

---

## 1. 背景与现状摘要

基于当前文档，系统已经具备明确的 Agent 职责边界与状态字段约束：

- 由 Planner Agent 负责意图识别、计划生成与执行调度。
- 执行链路主要由 intent→固定流程映射驱动（例如 `upload_jd` 对应从 JD Agent 到 Interview Agent 的整条链路）。
- 已定义清晰的读写契约（哪些字段可读、可写、禁写），并通过 dirty flag 控制重跑。
- 当前执行约束强调“串行、按顺序、单轮单 event”。

这些基础非常好，说明系统具备向“动态计划执行”演进的前提。

---

## 2. 当前设计的主要瓶颈

### 2.1 执行计划“半动态、半静态”

目前虽然有 `State Diff Planner` 与 `execution_plan`，但流程映射本质仍偏“intent 对应固定链路”，在以下场景灵活性不足：

- 用户复合指令：同一轮同时包含“内容改写 + 排版调整 + 导出”。
- 条件分支叠加：例如 profile 局部变化只应触发部分内容 section，而非整链重跑。
- 新增 Agent（如 ATS Scoring Agent）时，需要改 Planner 内部映射逻辑。

### 2.2 Planner 职责过重

Planner 既做分类、又做计划、又做调度，还承担 event 汇总。长期会出现：

- 规则膨胀（意图与链路规则持续增长）。
- 难测试（分类逻辑与执行策略耦合）。
- 变更风险高（改一个策略可能影响全局）。

### 2.3 Agent 与流程编排存在“隐式耦合”

虽然文档层面约束了“Agent 不直接互调”，但实际编排仍可能依赖“固定顺序假设”（例如默认 Gap 一定先于 Resume Content）。当引入新节点、并行节点或可选节点时，顺序假设会成为障碍。

### 2.4 可观测粒度偏粗

当前以单轮 `conversation_event` 为主，若后续引入动态计划，会需要更细粒度的“Plan Step 级”可观测（step 输入、输出、重试、回滚、耗时、token 成本、失败原因）。

---

## 3. 目标架构：Plan Mode + Agent 模块化

### 3.1 核心思想

将“流程”从代码中的 if/else 与固定映射，提升为**可解释、可验证、可执行的 Plan 对象**。Planner 的输出不再只是粗粒度 execution_plan，而是标准化 Step 图（DAG 或有序任务集）。

### 3.2 架构分层（建议）

1. **Intent & Task Extraction Layer**
   - 从用户输入中抽取任务集合（可多任务）。
   - 产出：`tasks[]`（如 `update_projects`, `adjust_spacing`, `export_pdf`）。

2. **Plan Builder Layer**
   - 根据任务 + 当前 state + policy 生成计划。
   - 产出：`Plan`（步骤、依赖、预条件、后置条件、可重试策略）。

3. **Plan Validator Layer**
   - 做静态检查：字段写入冲突、依赖闭环、禁写字段违规、版本策略。

4. **Plan Executor Layer**
   - 负责按 DAG / topo 顺序执行 step。
   - 支持并行（可选）、失败重试、补偿回滚、部分完成。

5. **Agent Runtime Layer（模块化 Agent）**
   - 每个 Agent 以统一接口注册到 Registry。
   - Planner/Executor 只通过接口调用，不感知内部实现。

6. **Observation & Audit Layer**
   - 记录 plan_run、step_run、state_diff、cost、latency、error taxonomy。

---

## 4. Plan Mode 数据模型建议

```yaml
plan_id: pl_xxx
session_id: s_xxx
intent_bundle:
  - content_edit
  - render_edit
created_at: ISO8601
steps:
  - step_id: st_01
    agent: resume_content
    action: update_sections
    reads: [job, candidate_profile, gaps, resume_content_json]
    writes: [resume_content_json]
    preconditions:
      - candidate_profile exists
    depends_on: []
    retry:
      max_attempts: 2
      backoff: fixed_1s
  - step_id: st_02
    agent: resume_render
    action: render_html
    reads: [resume_content_json, render_config]
    writes: [render_config, resume_html]
    depends_on: [st_01]
  - step_id: st_03
    agent: exporter
    action: export_pdf
    reads: [resume_html, render_config]
    writes: [artifacts]
    depends_on: [st_02]
policy:
  conflict: fail_fast
  partial_success: true
  timeout_ms: 45000
```

关键点：

- `reads/writes` 显式化，便于自动校验冲突。
- `depends_on` 显式化，支持未来并行执行。
- `preconditions` 显式化，避免 Agent 里埋业务分支。
- `policy` 显式化，统一失败策略与 SLA。

---

## 5. Agent 模块化与解耦方案

### 5.1 统一 Agent 接口

建议每个 Agent 遵循统一协议：

- `name()`: 唯一标识
- `capabilities()`: 声明支持 action 与可读写字段
- `validate(input, state)`: 运行前校验
- `execute(step_context) -> StepResult`: 返回 patch / artifact / metrics
- `on_error(...)`: 可选，定义可恢复错误策略

这样 Planner/Executor 只依赖抽象接口，不依赖具体 Agent 类。

### 5.2 Agent Registry（插件化）

通过注册中心管理 Agent：

- 静态注册（配置文件）+ 动态发现（入口点）二选一或并存。
- 每个 Agent 自声明 contract（读写字段、禁写字段、幂等性、超时默认值）。
- 新增 Agent 时只需：实现接口 + 注册，不改核心编排器。

### 5.3 Contract as Code

把当前文档里的契约落地为可执行规则：

- 在 Plan Validator 中自动校验 `writes ⊄ allowed_writes`。
- 检查 step 间写冲突（两个 step 写同字段且无依赖）。
- 检查 dirty flag 传播规则是否完整。

### 5.4 状态变更标准化（State Patch）

Agent 不直接“覆盖全量状态”，而返回结构化 patch：

- `set`, `merge`, `append`, `remove`
- 携带 `field_version_bump`
- 支持 patch 审计与回滚（基于 patch log）

---

## 6. 从“固定链路”到“计划驱动”的迁移路径

### Phase 1：计划结构显式化（低风险）

- 保持现有串行执行不变。
- 仅将目前的 intent→链路映射输出为标准 Plan 对象。
- 引入 Plan Validator 做禁写与依赖校验。

### Phase 2：Planner 拆分

- 将 Planner 拆为：Intent Extractor / Plan Builder / Executor。
- 每层独立测试，降低改动风险。

### Phase 3：Agent Registry + Contract Runtime

- Agent 通过注册中心加载。
- 将 docs 契约迁移为 machine-readable schema（如 YAML/JSON）。

### Phase 4：支持复合任务与有限并行

- 一轮消息支持多个 task。
- 对无冲突 step 做并行（如 interview_qa 生成可与部分非阻塞任务并行）。

### Phase 5：引入策略与优化器

- 根据 latency/cost/quality 动态选择执行策略（例如“快速模式”跳过非核心 step）。

---

## 7. 关键设计细节（避免新耦合）

### 7.1 不让 Agent 感知流程

Agent 只关心：

- 输入上下文
- 本 step action
- 可读状态
- 输出 patch

Agent 不应知道“前后是谁”，否则又回到流程耦合。

### 7.2 把业务规则放在 Plan/Policy 层

例如：

- `candidate_profile` 为空时是否允许生成简历
- `ask_question` 是否只读

这些应该是 plan 规则，不应散落在各 Agent 内。

### 7.3 可重试与幂等

- 为 step 定义幂等 key（session_id + step_id + input_hash）。
- 重试时保障“不重复写入”或“可判重写入”。

### 7.4 版本一致性

- 在 step commit 时统一处理 version bump。
- 失败回滚应基于“step 级事务边界”（至少逻辑事务）。

---

## 8. 可观测性与评估指标

建议新增两类实体：

- `plan_run`：整次计划执行记录
- `step_run`：每一步执行记录

核心指标：

- 计划成功率 / 部分成功率
- 平均 step 延迟（P50/P95）
- 每轮 token 成本
- 重试率与最终恢复率
- 回滚触发率
- 违规写入拦截次数（contract violation）

---

## 9. 风险与对策

1. **计划复杂度上升**
   - 对策：先保持串行，再渐进并行。
2. **调试难度上升**
   - 对策：强制 step 级日志与可视化 DAG。
3. **契约与实现漂移**
   - 对策：contract schema + CI 校验 + 回归测试。
4. **LLM 不稳定导致计划抖动**
   - 对策：计划模板化 + rule-based guardrail + fallback 固定计划。

---

## 10. 推荐落地清单（优先级）

### P0（立即）

- 定义统一 `Plan` / `Step` schema。
- 实现 Plan Validator（字段权限、依赖、冲突）。
- 将现有 intent→流程映射改为“先产 plan，再执行”。

### P1（短期）

- 拆分 Planner 为 3 个独立模块。
- 引入 Agent Registry 与标准 Agent 接口。
- 引入 step 级 observability。

### P2（中期）

- 支持复合意图（multi-task in one turn）。
- 支持可控并行与策略化执行。
- 将导出、检索、评分类能力以工具型 agent 插件化。

---

## 11. 预期收益

- **灵活性**：从“固定流程”升级为“按需计划”。
- **可扩展性**：新增 Agent 不再改核心编排逻辑。
- **稳定性**：契约自动校验，降低误写状态风险。
- **可维护性**：Planner 分层后，规则变更更可控。
- **可观测性**：step 级追踪提升定位与优化效率。

---

## 12. 结论

当前设计已经具备良好的契约与状态管理基础，适合演进到 Plan Mode。建议采用“**先显式化计划、再模块化执行、最后策略化优化**”的渐进式路线：

1. 不颠覆现有业务链路，先把隐式流程变成显式 Plan；
2. 用 Registry + Contract Runtime 将 Agent 真正插件化；
3. 在可观测性完备后再引入并行和动态优化。

这样可以在控制风险的前提下，实现“更灵活的 plan 模式 + agent 模块解耦”的目标。

---

## 13. 基于 `backend/` 现有实现的代码级诊断

本节基于现有代码结构做“从文档到落地”的对齐，指出当前耦合点和改造切入点。

### 13.1 当前编排形态（代码事实）

1. `workflow/graph.py` 已将节点固定注册为 `planner -> jd/profile/gap/content/render/interview -> respond`，并通过多个 `_route_after_xxx` 函数按 `execution_plan` 做条件跳转。该模式仍是“图结构固定 + 节点按名称路由”。
2. `agents/planner.py` 中 `_INTENT_PLAN` 是硬编码映射，`_build_execution_plan` 仅有少量分支（例如 `upload_jd` 且无 profile 时只跑 `jd_agent`）。
3. `workflow/state.py` 的 `execution_plan` 目前是 `list[str]`，缺少 step 级结构（reads/writes/dependencies/policy），无法承载真正 Plan Mode。
4. `api/chat.py` 调用图后一次性持久化状态，尚未沉淀 plan_run/step_run 执行轨迹。

### 13.2 当前 Agent 代码模式（可复用的优点）

现有 Agent 基本都遵循“输入 state → 返回 patch dict”的 LangGraph 节点模式，这是升级 Plan Executor 的良好基础：

- `jd_agent.py`, `profile_agent.py`, `content_agent.py`, `render_agent.py`, `gap_agent.py`, `interview_agent.py` 都是独立节点函数，已经具备模块边界。
- `agents/json_contracts.py` 已把多数 LLM 输出结构化为 Pydantic schema，可直接复用于 Agent Capability / Step I/O Schema。
- dirty flag 已存在于 `Meta.DirtyFlags`，可迁移为 Plan Policy 的一部分。

### 13.3 主要改造阻塞点

1. 路由函数数量随节点增多而膨胀（`_route_after_planner`、`_route_after_jd`...）。
2. `execution_plan: list[str]` 无法表达复合任务与并行依赖。
3. Planner 同时负责“意图识别 + 计划 +（部分）用户回复逻辑”，职责未拆分。
4. 状态写入约束仅在文档层，尚未在运行时统一拦截（例如 step 级 write-set 校验）。

---

## 14. 建议的文件夹结构调整（可渐进迁移）

> 原则：不一次性重构全部 Agent；先新增 plan_mode 目录并做兼容桥接。

### 14.1 目标目录树（建议）

```text
backend/
  agents/
    implementations/            # 迁移后的具体 Agent 实现
      jd_agent.py
      profile_agent.py
      gap_agent.py
      content_agent.py
      render_agent.py
      interview_agent.py
    registry.py                # Agent 注册中心
    contracts.py               # Agent 能力声明（reads/writes/actions）
    runtime.py                 # AgentRuntime 接口与执行封装
  workflow/
    plan_mode/
      plan_schema.py           # Plan/Step/Policy Pydantic schema
      plan_builder.py          # 任务 -> Plan
      plan_validator.py        # 合约、冲突、依赖校验
      plan_executor.py         # Step 执行、重试、状态提交
      patch.py                 # StatePatch(set/merge/append/remove)
      event_log.py             # plan_run/step_run 事件模型
    graph.py                   # 逐步瘦身为“planner + executor + respond”
    state.py                   # 增加 plan_mode 运行时字段
  api/
    chat.py                    # 保持入口不变，增加 plan_run_id 返回
  storage/
    redis_client.py            # 新增 plan_run / step_run 缓存写入
    mysql_client.py            # 新增 plan_run / step_run 持久化接口
  test/
    plan_mode/
      test_plan_builder.py
      test_plan_validator.py
      test_plan_executor.py
    agent/
      test_agent_contract_runtime.py
```

### 14.2 迁移映射（旧文件 → 新职责）

| 旧文件 | 改造建议 |
|---|---|
| `backend/agents/planner.py` | 拆分为 `workflow/plan_mode/plan_builder.py` + `agents/implementations/planner_intent.py`（仅保留意图抽取） |
| `backend/workflow/graph.py` | 从“多 route 函数”收敛为 `planner -> plan_executor -> respond` |
| `backend/workflow/state.py` | 新增 `execution_steps`, `active_plan_id`, `plan_policy`, `step_results` 等运行时字段 |
| `backend/agents/json_contracts.py` | 保留 LLM 输出 schema；新增 `agents/contracts.py` 管 Agent 能力契约 |
| `backend/storage/mysql_client.py` | 新增 `save_plan_run`, `save_step_run`；保留原业务表写入 |
| `backend/api/chat.py` | 返回中新增 `plan_id/step_summaries`（可选字段，保持向后兼容） |

---

## 15. 具体到文件的改造清单（建议先做 P0）

### P0-1：引入 Plan Schema（不改业务行为）

- 新增 `backend/workflow/plan_mode/plan_schema.py`
  - `Plan`, `PlanStep`, `StepPolicy`, `PlanPolicy`。
- 修改 `backend/workflow/state.py`
  - 将 `execution_plan: list[str]` 保留兼容。
  - 新增 `execution_steps: list[PlanStep] = []`。
  - 新增 `active_plan_id: str = ""`。

### P0-2：引入 Plan Validator（先只做静态检查）

- 新增 `backend/workflow/plan_mode/plan_validator.py`
  - 校验 step 依赖闭环。
  - 校验 writes 是否在 agent contract 允许范围内。
  - 校验并行 step 写冲突。

### P0-3：建立 Agent Registry（兼容旧节点函数）

- 新增 `backend/agents/registry.py`
  - name -> callable 映射。
  - 启动时注册现有 6 个 agent。
- 新增 `backend/agents/contracts.py`
  - 用数据结构声明每个 agent 的 `allowed_reads/allowed_writes/actions/idempotent`。

### P0-4：抽出 Plan Executor（串行版）

- 新增 `backend/workflow/plan_mode/plan_executor.py`
  - 输入 `execution_steps`。
  - 按顺序调用 registry 中 agent。
  - 统一处理 retry、错误聚合、step 日志。
- 修改 `backend/workflow/graph.py`
  - 先保留原节点图，同时新增 `executor_agent` 试运行开关（feature flag）。

### P0-5：观测与持久化骨架

- 修改 `backend/storage/mysql_client.py`
  - 新增 `save_plan_run(plan_run)`、`save_step_run(step_run)`。
- 修改 `backend/sql/init_schema.sql`
  - 新增 `plan_runs`, `step_runs` 两张表。
- 修改 `backend/api/chat.py`
  - `BackgroundTasks` 中补充 plan/step 执行记录写库。

---

## 16. SQL 与 API 字段建议（配合文件变更）

### 16.1 新增表建议

1. `plan_runs`
   - `plan_id`, `session_id`, `message_id`, `intent_bundle`, `status`, `policy_json`, `started_at`, `ended_at`。
2. `step_runs`
   - `step_run_id`, `plan_id`, `step_id`, `agent_name`, `status`, `attempt`, `latency_ms`, `error_code`, `state_patch_summary`, `created_at`。

### 16.2 API 向后兼容扩展

`POST /api/chat` 的响应建议新增可选字段（默认不影响前端旧逻辑）：

- `plan_id: str | null`
- `step_summaries: list[{step_id, agent, status, latency_ms}]`

若前端未消费，可忽略；用于后续“执行轨迹可视化”。

---

## 17. 最小可执行改造顺序（两周版本）

### Week 1

1. 完成 `plan_schema.py`、`contracts.py`、`registry.py`。
2. Planner 仍生成旧 `execution_plan`，同时镜像生成 `execution_steps`。
3. Validator 仅日志告警，不阻断主流程。

### Week 2

1. 上线串行 `plan_executor.py`（feature flag 灰度）。
2. Graph 切到 `planner -> executor -> respond`（保留旧图 fallback）。
3. 接入 `plan_runs/step_runs` 落库与 LangSmith trace 关联。

验收标准：

- 对现有 `upload_jd/upload_profile/content_edit/render_edit` 行为回归无差异。
- 新增复合指令（content_edit + render_edit）可在单轮生成两步以上 plan。
- step 级错误可观测，且失败不导致整轮状态污染。
