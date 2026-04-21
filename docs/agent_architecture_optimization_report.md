# Agent 架构优化分析报告（Plan Mode + 模块化解耦）

> 目标：在现有设计基础上，将“固定链路编排”升级为“更灵活的 Plan Mode”，并将各个 Agent 模块化、可插拔、彼此解耦。
> 目前运行环境：` (D:\Anaconda\shell\condabin\conda-hook.ps1) ; (conda activate rag_workflow)`

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

## 17. 最小可执行改造顺序

### 可行性判断

如果本轮目标明确限定为“**先完成 Agent 模块解耦，必要时小幅调整 state，但暂不改当前 workflow 图结构**”，则可行性较高，原因如下：

1. `backend/agents/*.py` 已基本满足“节点函数输入 state、输出 patch”的统一形态，天然适合包一层 runtime/contract。
2. 当前 `workflow/graph.py` 虽然路由固定，但它依赖的其实只是节点名与 `execution_plan`，并不阻止先把 Agent 实现从“直接 import 调用”升级为“注册 + 能力声明 + 统一执行包装”。
3. `workflow/state.py` 当前运行时字段较少，但只需增加少量元数据字段，就能支撑 contract 校验、step 观测和后续平滑切换，而不必现在就引入完整 DAG executor。

需要注意的边界：

- 这一阶段不要同时推进 `graph.py` 大改，否则会把“Agent 解耦”和“编排重构”两个变量绑在一起，回归风险明显上升。
- `state` 可以改，但应以“补充运行时元信息”为主，不要先把 `execution_plan` 全量替换成复杂 Step DAG。

### 建议按模块拆分的最小顺序

### Module 1：先固化 Agent Contract

1. 新增 `backend/agents/contracts.py`。
2. 为现有 `jd/profile/gap/content/render/interview` 六个 Agent 声明：
   - `agent_name`
   - `supported_intents` 或 `supported_actions`
   - `allowed_reads`
   - `allowed_writes`
   - `default_retryable`
   - `idempotent`（先可选）
3. 第一阶段只做“声明落地”，不改业务逻辑。

这一模块完成后的收益是：先把“文档里的职责边界”变成代码里的显式契约，为后面的 runtime 校验打底。

### Module 2：引入 Registry，但不改 Graph 形态

1. 新增 `backend/agents/registry.py`。
2. 将当前各节点函数注册为：
   - `jd_agent -> jd_node_async`
   - `profile_agent -> profile_node_async`
   - `gap_agent -> gap_node_async`
   - `content_agent -> content_node_async`
   - `render_agent -> render_node_async`
   - `interview_agent -> interview_node_async`
3. `graph.py` 先保持现有节点拓扑不变，只把内部调用入口改成“从 registry 取 agent 运行”或为后续切换预留兼容层。

这一层的目标不是动态编排，而是先去掉“编排层直接绑定具体实现文件”的硬耦合。

### Module 3：补一层 Agent Runtime Adapter

1. 新增 `backend/agents/runtime.py`。
2. 对每个 Agent 执行统一做三件事：
   - 运行前按 contract 校验最小必需输入是否存在
   - 执行后检查返回 patch 的写入字段是否越权
   - 统一包装日志、异常、耗时和失败返回
3. 当前 `graph.py` 仍按原节点顺序走，但节点内部不再“裸调 agent 函数”，而是走 runtime。

这一层是本轮最关键的解耦点。做完之后，后续无论是保留固定图，还是改成 executor，Agent 接入方式都已经统一了。

### Module 4：对 State 做最小增量改造

建议只加运行时字段，不动现有持久化主结构：

1. 在 `backend/workflow/state.py` 增加：
   - `execution_steps: list[dict[str, Any]] = []`
   - `active_plan_id: str = ""`
   - `step_results: list[dict[str, Any]] = []`
   - `contract_violations: list[dict[str, Any]] = []`
2. 保留现有 `execution_plan: list[str]` 作为 graph 路由唯一依据。
3. `execution_steps` 在这一阶段只做“镜像元数据”，例如：
   - `step_id`
   - `agent`
   - `status`
   - `reads`
   - `writes`

这样可以做到：workflow 不变，但 plan/step 级数据已经开始沉淀，为下一阶段 executor 化做兼容准备。

### Module 5：轻量拆分 Planner，但先不引入新 Executor

1. 保留 `backend/agents/planner.py` 对外节点入口不变。
2. 先把内部逻辑拆成两个私有层次：
   - intent classify
   - plan metadata build
3. 当前仍输出 `execution_plan` 给 graph 路由。
4. 同时补充生成 `execution_steps`，但仅作为镜像，不参与实际调度。

这一步的重点不是“计划驱动执行”，而是先把 Planner 从“只吐字符串数组”升级为“同时吐一份结构化计划草案”。

### Module 6：补齐观测与回归测试

1. 优先新增测试，而不是先改数据库：
   - contract 校验测试
   - registry 注册测试
   - runtime patch 越权拦截测试
   - planner 输出 `execution_plan + execution_steps` 的兼容测试
2. 观测先落日志和内存态：
   - step 开始/结束
   - latency
   - contract violation
3. `plan_runs/step_runs` 落库可以放到下一小阶段，不必和 Agent 解耦绑定上线。

这样能把本轮范围收紧在“运行时边界清晰化”，而不是过早进入存储和编排联动改造。

### 本轮完成后的验收标准

1. `workflow/graph.py` 拓扑与现有行为保持一致，`upload_jd / upload_profile / content_edit / render_edit / ask_question` 回归无差异。
2. 所有业务 Agent 都能通过统一 `contract + registry + runtime` 接入。
3. Agent 返回 patch 时，运行时可以识别越权写入并记录告警或阻断。
4. Planner 除了输出旧 `execution_plan` 外，还能稳定输出结构化 `execution_steps` 元数据。
5. 新增或替换某个 Agent 实现时，不需要再去改 graph 路由逻辑，只需改注册与 contract。

### 下一阶段再做的事

等上述 6 个模块稳定后，再进入下一轮：

1. 将 `execution_steps` 从“镜像元数据”升级为真正执行输入。
2. 引入串行 `plan_executor.py`。
3. 再把 `graph.py` 从“多 route 函数”收敛为 `planner -> executor -> respond`。

这样改造路径会更稳：先解耦 Agent，再替换编排器，而不是两者同时动。

---

## 18. Module 5-6 完成情况（截至当前代码基线）

本节记录当前代码已经完成的范围，作为后续真正进入 Plan Mode 改造的起点。

### 18.1 Module 5 已完成内容

当前 `backend/agents/planner.py` 已完成从“只输出 `execution_plan`”到“输出 `execution_plan + execution_steps + active_plan_id`”的升级，但仍保持旧 workflow 的兼容行为不变：

1. 继续使用旧的 intent 分类逻辑。
2. 继续输出 `execution_plan: list[str]`，供 `workflow/graph.py` 现有路由使用。
3. 新增输出：
   - `active_plan_id`
   - `execution_steps`
4. `execution_steps` 当前仅作为镜像元数据，包含：
   - `step_id`
   - `agent`
   - `status`
   - `reads`
   - `writes`

这意味着当前系统已经具备了“计划元数据显式化”的第一步，但尚未进入“计划驱动执行”。

### 18.2 Module 6 已完成内容

当前代码已具备一套不依赖数据库的最小观测与回归测试骨架：

1. `backend/agents/runtime.py` 已统一记录：
   - step 执行成功
   - step 执行失败
   - contract violation
2. `backend/workflow/state.py` 已增加：
   - `step_results`
   - `contract_violations`
3. 已新增或补充测试覆盖：
   - contract 声明与 registry 注册
   - runtime 越权写入拦截
   - runtime 异常封装
   - state 新运行时字段序列化
   - planner 输出 `execution_plan + execution_steps` 的兼容测试

### 18.3 当前阶段明确未做的事

为控制范围，以下事项仍然刻意留在下一阶段：

1. 不新增 `plan_runs / step_runs` 数据库表。
2. 不修改 `backend/sql/init_schema.sql`。
3. 不把 `execution_steps` 作为真实执行输入。
4. 不引入 `plan_executor.py`。
5. 不重写 `workflow/graph.py` 的固定路由结构。

这个边界是合理的，因为当前新增的 `execution_steps / step_results / contract_violations / active_plan_id` 都属于运行时元数据，并未进入现有持久化主链路。

---

## 19. 基于当前基线，真正切换到 Plan Mode 的推荐流程

在当前基础上，后续应采用“**先让 execution_steps 可验证，再让 execution_steps 可执行，最后再收敛 workflow 图**”的顺序，而不是一步到位重写。

### Phase A：把 `execution_steps` 从镜像元数据升级为可校验对象

目标：先让 Planner 产出的 step 元数据具备足够语义，但暂时仍不负责执行。

建议动作：

1. 新增 `backend/workflow/plan_mode/plan_schema.py`
   - 定义 `Plan`
   - 定义 `PlanStep`
   - 定义 `PlanPolicy`
2. 将当前 `ExecutionStep` 逐步对齐到 `PlanStep`，补充字段：
   - `depends_on`
   - `preconditions`
   - `retry`
   - `intent`
   - `action`
3. 新增 `backend/workflow/plan_mode/plan_validator.py`
   - 校验 step 写入字段是否超出 contract
   - 校验依赖闭环
   - 校验同层写冲突

这一步完成后，Planner 产出的就不只是“能看”的镜像，而是“能被静态检查”的执行草案。

### Phase B：引入串行 `plan_executor.py`，但先不替换 graph

目标：先在代码中建立真正的 plan 执行器，再决定是否切图。

建议动作：

1. 新增 `backend/workflow/plan_mode/plan_executor.py`
2. 第一版 executor 只做串行执行：
   - 按 `execution_steps` 顺序取 step
   - 通过 registry + runtime 调 agent
   - 聚合 step 结果
3. executor 输出继续回写现有 state：
   - `step_results`
   - `contract_violations`
   - 业务字段 patch

关键原则：

- 这一阶段 executor 的行为必须和现有 graph 固定链路等价。
- 先做 feature flag 或 shadow mode，避免一上来替换主链路。

### Phase C：把 graph 从“节点路由图”收敛为“planner -> executor -> respond”

目标：在 executor 行为稳定后，才真正替换编排骨架。

建议动作：

1. `planner` 输出完整 `Plan`
2. `graph.py` 缩减为：
   - `planner`
   - `executor`
   - `respond`
3. 原 `_route_after_xxx` 系列函数逐步下线

这样做的收益：

- 新增 Agent 不再需要增加新的 route 函数
- 编排复杂度从图路由转移到 Plan/Executor，更便于测试

### Phase D：支持复合任务与有限并行

目标：真正体现 Plan Mode 的价值，而不是仅仅换一种串行写法。

建议动作：

1. Intent 层从单 intent 升级为 task bundle
2. Planner 支持单轮输出多个 step 分支
3. 对无写冲突步骤引入有限并行
4. 为并行步骤补充：
   - merge 策略
   - 冲突策略
   - retry 策略

到这一步，系统才算真正进入 Plan Mode，而不是“带 step 元数据的旧流程”。

### Phase E：最后再接入数据库级 plan observability

数据库改造应当放在 executor 稳定之后，而不是现在提前做。

建议动作：

1. 在 `backend/sql/init_schema.sql` 中新增：
   - `plan_runs`
   - `step_runs`
2. 在 `backend/storage/mysql_client.py` 中新增：
   - `save_plan_run`
   - `save_step_run`
3. 在 `backend/api/chat.py` 中补充后台写库

理由：

- 如果现在就建表，字段设计会很容易随着 executor 设计变化而反复修改。
- 等 `PlanStep`、executor、错误分类稳定后再落库，数据模型会更稳。

---

## 20. 推荐的后续实施顺序（Plan Mode 真正落地版）

基于当前已完成的 Module 1-6，建议后续严格按下面顺序推进：

1. 定义 `plan_schema.py`，统一 `Plan / PlanStep / PlanPolicy`。
2. 实现 `plan_validator.py`，让 `execution_steps` 先可校验。
3. 让 Planner 输出从“镜像 step”升级为“标准 PlanStep 草案”。
4. 实现串行 `plan_executor.py`，通过 feature flag 或 shadow mode 验证与旧 graph 等价。
5. 等 executor 稳定后，再把 `graph.py` 收敛为 `planner -> executor -> respond`。
6. 最后补 `plan_runs / step_runs` 持久化、API 返回摘要和可视化。

一句话概括就是：

**当前代码已经完成了“Plan Mode 的前置解耦层”，下一阶段不要急着上数据库，应该先把 Plan 的 schema、validator 和 executor 真正建立起来。**
