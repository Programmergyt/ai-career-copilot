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

## 15. 当前已完成基线（截至当前代码）

本节仅保留已经在代码中落地、可作为下一阶段起点的部分；此前“待做但现已完成”的条目不再重复列为改造任务。

### 15.1 已完成的结构性升级

1. 编排骨架已从固定多路由图收敛为 `planner -> executor -> respond`。
2. 已引入统一的 `Plan / PlanStep / PlanPolicy / StepResult / ContractViolation` schema。
3. 已引入 `Agent Contract + Registry + Runtime` 三层运行时边界。
4. `Planner` 已输出 `active_plan_id + execution_steps + execution_plan`，不再只吐旧式字符串链路。
5. `Executor` 已按 step 串行执行，并统一处理前置条件检查、重试、step 状态更新与失败终止。
6. `State` 已补齐 plan mode 运行时字段，如 `execution_steps / plan_status / step_results / contract_violations`。
7. `/api/chat` 已向外返回 `plan_id / plan_status / execution_steps / step_results / contract_violations`，说明 plan mode 元数据已经对 API 消费方可见。
8. 已有针对 `runtime / validator / executor / graph` 的基础测试，说明当前 plan mode 骨架并非仅停留在代码结构层面。

### 15.2 已完成部分的价值总结

- Agent 已具备“单独注册、统一接入、运行时校验”的基础能力，新增实现不必再回到 graph 层硬编码。
- Plan Mode 已从“纯元数据镜像”升级为“真实执行入口”，后续可以把优化重点从“有没有 executor”转到“planner 是否足够灵活、executor 是否足够鲁棒”。
- 当前系统已经具备继续演进为“灵活计划 + 错误兜底 + replan”的合理基线，不需要再做一轮同类基础设施重建。

### 15.3 当前仍然存在的核心缺口

尽管编排骨架已经切到 Plan Mode，但当前 `planner` 的计划生成仍主要是“单 intent -> 预设 step 序列”，还不是目标中的鲁棒动态架构：

1. 仍以单意图分类为主，尚未升级为 `tasks[]` / `intent_bundle`。
2. `build_plan()` 仍由硬编码分支决定 step 序列，灵活性主要体现在执行而非规划。
3. `executor` 仍是串行 fail-fast，尚未支持部分成功、补偿、降级与 replan。
4. `plan` 的观测还主要停留在运行时内存态，尚未沉淀到数据库级 `plan_run / step_run`。
5. 多个业务 Agent 仍直接读取 `state.current_intent` 与 `state.user_message` 决定行为，尚未真正收敛为“只基于 step action / step context 执行”。
6. `resume` 相关 API 仍通过覆盖 `current_intent` 触发渲染链路，说明外部入口与旧意图模型仍然耦合。

---

## 16. 目标架构重述：鲁棒 Plan Mode

下一阶段的目标不再是“把旧流程显式化”，而是建立如下能力闭环：

**Agent 单独注册 -> Planner 每轮生成与上下文匹配的灵活 Plan -> Executor 按 Plan 执行 -> 失败时有兜底策略 -> 必要时触发 replan -> 最终沉淀完整观测。**

### 16.1 目标特征

1. **Agent 单独注册**
   - Agent 只声明能力、输入输出边界、默认重试策略。
   - 新增 Agent 时，不需要修改核心 graph，只需注册与声明 contract。

2. **Plan 按轮动态生成**
   - Planner 基于用户任务集合、当前 state、历史执行结果与 policy 动态生成 Plan。
   - Plan 不再只是固定意图模板，而是可组合、可裁剪、可重排的 step 集合。

3. **Executor 负责执行策略**
   - Executor 负责串行或有限并行执行、失败重试、降级、跳过、部分成功收敛。
   - Agent 只专注于 step 内业务，不感知整体流程。

4. **错误兜底与 replan**
   - 失败不是直接终止，而是进入分类处理：可重试、可跳过、可降级、需重规划、需用户确认。
   - replan 由 planner 基于“失败原因 + 已完成步骤 + 当前最新 state”生成剩余计划。

5. **全链路可观测**
   - 每次 plan 生成、step 执行、失败分类、replan 决策都可被记录、查询和分析。

### 16.2 与当前实现的差距

当前代码已经实现了“统一执行入口”，但还未实现以下关键能力：

- 从单 intent 升级为多任务 bundle。
- 从预设 step 模板升级为真正的 plan builder。
- 从 fail-fast 升级为 error policy + fallback + replan。
- 从内存态 step 观测升级为持久化的 plan observability。
- 从“Agent 读全局 `current_intent`”升级为“Agent 读显式 step context / action”。

---

## 17. 面向鲁棒架构的后续改造任务

### 17.0 先做的对齐事项：消除剩余旧模型耦合

目标：在继续增强 Planner/Executor 之前，先把当前仍残留的“旧意图驱动接口”边界清掉，避免后面动态计划做了一半又被旧字段拖回去。

建议改造：

1. 让 Agent 执行优先读取 `PlanStep.action`、`PlanStep.intent` 或标准化 `step_context`，逐步减少对 `state.current_intent` 的依赖。
2. 对 `content_agent`、`render_agent` 这类当前存在显式 intent 分支的实现，抽出 step-level 行为枚举，而不是继续依赖全局状态。
3. 将 `resume.py` 中通过覆写 `current_intent = "render_edit"` 触发执行的模式，逐步迁移为显式 task / plan 入口。
4. 明确 `user_message` 是原始用户输入，`step_context` 是某一步的执行参数，避免后续复合任务时多个 step 共享同一字符串导致歧义。

### 17.1 Planner：从 Intent Router 升级为 Dynamic Plan Builder

目标：让 Planner 真正基于任务和状态生成灵活计划，而不是只选择预定义模板。

建议改造：

1. 将单一 `intent` 输出升级为 `intent_bundle` / `tasks[]`。
2. 将 `build_plan()` 从 `if/elif intent` 分支，升级为：
   - task extraction
   - task normalization
   - step selection
   - dependency assembly
   - policy injection
3. 支持“同轮复合指令”，例如：
   - 内容改写 + 排版调整
   - 上传资料 + 刷新简历 + 生成面试题
   - 渲染调整 + 导出
4. 让 planner 读取上一次执行失败摘要，在 replan 时只生成剩余步骤而非整链重来。

建议新增文件职责：

- `backend/workflow/plan_mode/task_extractor.py`
- `backend/workflow/plan_mode/plan_builder.py`
- `backend/workflow/plan_mode/replan_builder.py`

### 17.2 Plan Schema：从“可执行”升级为“可恢复”

目标：让 Plan 不仅能跑，还能支撑错误分类、补偿和 replan。

建议扩展 `Plan / PlanStep / PlanPolicy`：

1. `Plan`
   - `intent_bundle`
   - `plan_reason`
   - `replan_count`
   - `parent_plan_id`
2. `PlanStep`
   - `on_error`
   - `fallback_action`
   - `skippable`
   - `timeout_ms`
   - `idempotency_key`
3. `PlanPolicy`
   - `fail_fast`
   - `partial_success`
   - `replan_on_failure`
   - `max_replans`
   - `allow_degraded_completion`

这样后续 executor 才能区分：

- 失败后重试
- 失败后跳过
- 失败后改走降级路径
- 失败后触发 replan

### 17.3 Executor：从串行执行器升级为鲁棒执行器

目标：让 executor 成为“运行时控制器”，而不只是一个 for-loop。

建议能力：

1. 执行前：
   - 校验 step 依赖、前置条件、contract、policy。
2. 执行中：
   - 支持 step 重试。
   - 支持按依赖拓扑执行。
   - 在无冲突步骤间支持有限并行。
3. 执行失败后：
   - 根据错误类型判断 retry / fallback / replan / ask_user。
   - 对失败 step 记录标准化错误码。
   - 在允许部分成功时继续推进剩余步骤。
4. 执行结束后：
   - 汇总 plan 级状态：`success / partial / failed / replanned / degraded_success`。

建议新增或重构：

- `backend/workflow/plan_mode/plan_executor.py`
- `backend/workflow/plan_mode/error_policy.py`
- `backend/workflow/plan_mode/replan_decider.py`

### 17.4 Runtime 与 Contract：从“越权拦截”升级为“运行时护栏”

目标：让 runtime 除了拦截非法写入，还能提供鲁棒执行所需的统一护栏。

建议增强：

1. 在 contract 中补充：
   - `supported_actions`
   - `required_reads`
   - `default_timeout_ms`
   - `retryable_errors`
   - `fallback_capabilities`
2. 在 runtime 中补充：
   - 输入缺失错误标准化
   - LLM 格式错误标准化
   - 超时错误标准化
   - 第三方工具失败标准化
3. 对 patch 写入增加：
   - patch 类型约束
   - version bump 约束
   - 幂等写保护
4. 引入 `step_context` 注入：
   - 由 executor 把当前 step 的 action、参数、fallback 信息传入 agent
   - agent 逐步摆脱对全局 `current_intent` 的直接依赖

这样 Planner/Executor 才能基于统一错误语义做 replan，而不是依赖字符串匹配。

### 17.5 Observation：从运行时字段升级为持久化审计

目标：让 plan mode 的调试、优化、回归验证有真实数据支撑。

建议新增持久化实体：

1. `plan_runs`
   - `plan_id`, `parent_plan_id`, `session_id`, `message_id`, `intent_bundle_json`, `status`, `replan_count`
   - `policy_json`, `error_summary`, `started_at`, `ended_at`
2. `step_runs`
   - `step_run_id`, `plan_id`, `step_id`, `agent_name`, `action`, `status`, `attempt`
   - `latency_ms`, `error_code`, `fallback_used`, `patch_summary`, `created_at`
3. `replan_events`
   - `event_id`, `old_plan_id`, `new_plan_id`, `trigger_step_id`, `reason`, `created_at`

建议 API 扩展：

- `plan_id`
- `plan_status`
- `step_summaries`
- `replanned`
- `degraded`

说明：

- 当前 `/api/chat` 实际上已经返回了比最初规划更多的 plan mode 字段，因此后续重点不是“是否要暴露 plan”，而是“如何稳定这些字段的语义，并让数据库持久化与 API 结构一致”。

---

## 18. 建议的分阶段实施路线

### Phase 1：动态规划化

目标：让 Planner 从“意图映射器”升级为“任务驱动的计划生成器”。

实施项：

1. 引入 `tasks[]` / `intent_bundle`。
2. 抽离 `task_extractor.py` 与 `plan_builder.py`。
3. 引入 `step_context`，先把 agent 从 `current_intent` 依赖迁到 step 驱动。
4. 让 planner 输出标准化 Plan，而不是固定模板的轻包装。
5. 为复合任务补测试样例。

验收标准：

- 单轮可生成多个业务 step 分支。
- 新增一个工具型 Agent 时，不需要新增新的 intent 路由分支。

### Phase 2：错误兜底化

目标：让执行失败不再简单等于整次失败。

实施项：

1. 建立标准错误分类与 `error_policy.py`。
2. 为 step 定义 retry / skip / degrade / replan 策略。
3. executor 支持 `partial_success` 与 `degraded_success`。
4. 对导出、评分类、检索类工具引入可降级路径。

验收标准：

- 同类失败可被稳定归类，而非只返回自由文本错误。
- 非核心 step 失败时，系统仍可完成核心主链路。

### Phase 3：Replan 化

目标：让系统具备“失败后重新规划剩余步骤”的能力。

实施项：

1. 引入 `replan_builder.py`。
2. 基于失败 step、已完成 step、当前 state 生成剩余计划。
3. 为每次 replan 记录 parent-child plan 关系。
4. 限制最大 replan 次数，避免无限循环。

验收标准：

- 至少一类失败场景可自动 replan 恢复。
- replan 后不会重复执行已成功且幂等安全的步骤。

### Phase 4：有限并行化

目标：在不牺牲稳定性的前提下，提升吞吐和响应速度。

实施项：

1. 在 validator 中增加同层写冲突校验。
2. executor 支持按依赖层分组执行。
3. 为并行合并引入 merge policy。
4. 先只开放低风险并行场景。

验收标准：

- 并行步骤无写冲突。
- 并行失败时可定位到具体 step，不污染其他分支结果。

### Phase 5：数据库级观测与可视化

目标：把 plan mode 变成可分析、可优化、可回归的工程系统。

实施项：

1. 新增 `plan_runs / step_runs / replan_events` 表。
2. API 返回执行摘要。
3. 后台补充 plan 级与 step 级写库。
4. 为前端或内部调试页面提供执行轨迹。

验收标准：

- 可以追踪某一轮对话的完整 plan 生命周期。
- 可以统计重试率、replan 率、降级成功率与热点失败 step。

---

## 19. 具体到文件的改造建议（新目标版）

### 19.1 Planner 与 Plan Builder

- `backend/agents/planner.py`
  - 保留入口职责，但内部聚焦为 orchestration facade。
  - 调用 `task_extractor -> plan_builder -> validator -> replan_decider`。
- `backend/agents/planner_metadata.py`
  - 逐步退化为兼容层，最终让位于真正的 `plan_builder.py`。
- `backend/workflow/plan_mode/task_extractor.py`
  - 负责从用户输入中提取任务集合。
- `backend/workflow/plan_mode/plan_builder.py`
  - 负责把任务集合、当前状态和 policy 组装成灵活 Plan。
- `backend/workflow/plan_mode/replan_builder.py`
  - 负责失败后的剩余计划生成。

### 19.2 Executor 与 Error Policy

- `backend/workflow/plan_mode/plan_executor.py`
  - 从串行执行器升级为支持 fallback 与 replan 的控制器。
- `backend/workflow/plan_mode/error_policy.py`
  - 标准化错误类型到策略的映射。
- `backend/workflow/plan_mode/replan_decider.py`
  - 判断是否应该 replan、降级还是请求用户确认。
- `backend/workflow/plan_mode/plan_validator.py`
  - 增加同层写冲突、并行安全、幂等约束校验。

### 19.3 Agent Runtime 与 Contract

- `backend/agents/contracts.py`
  - 扩展 action、timeout、retryable_errors、fallback_capabilities。
- `backend/agents/registry.py`
  - 保持单独注册中心角色，并为后续工具型 Agent 留出能力查询入口。
- `backend/agents/runtime.py`
  - 增强统一错误封装、输入校验、patch 护栏、step telemetry 和 `step_context` 注入。
- `backend/agents/implementations/content_agent.py`
  - 从 `current_intent` 分支逐步迁移到基于 step action 的执行。
- `backend/agents/implementations/render_agent.py`
  - 从“读全局 render_edit intent”迁移到“读 step action + step params”。
- `backend/agents/implementations/gap_agent.py`
  - 为后续 ask / analyze / refresh 等不同 action 做能力拆分预留入口。
- `backend/agents/implementations/interview_agent.py`
  - 为后续生成、刷新、局部重建等 action 拆分做准备。

### 19.4 State、Storage、API

- `backend/workflow/state.py`
  - 增加 replan 相关运行时字段，如 `parent_plan_id`, `replan_count`, `last_plan_error`, `step_contexts`。
- `backend/storage/mysql_client.py`
  - 新增 `save_plan_run`, `save_step_run`, `save_replan_event`。
- `backend/sql/init_schema.sql`
  - 新增 `plan_runs`, `step_runs`, `replan_events`。
- `backend/api/chat.py`
  - 对齐现有已返回字段与后续持久化字段，避免 API 和 DB 两套 plan 语义分叉。
- `backend/api/resume.py`
  - 从“覆盖 `current_intent` 触发 render”迁移为显式 plan/task 入口。

---

## 20. 推荐优先级与落地顺序

### P0：让 Planner 真正动态化

1. 先引入 `step_context`，减少 agent 对 `current_intent` 的硬依赖。
2. 引入 `tasks[]` / `intent_bundle`。
3. 新增 `task_extractor.py`、`plan_builder.py`。
4. 将 `planner_metadata.py` 中的固定链路拼装迁出。

### P1：让 Executor 真正鲁棒化

1. 建立错误分类与 `error_policy.py`。
2. 在 executor 中接入 fallback / partial_success / degraded_success。
3. 引入 `replan_decider.py` 与 `replan_builder.py`。

### P2：让系统真正可恢复

1. 增加 `parent_plan_id / replan_count / replan_events`。
2. 打通失败后剩余计划重建。
3. 建立 replan 上限与死循环保护。

### P3：让系统真正可运营

1. 落库 `plan_runs / step_runs / replan_events`。
2. API 返回执行摘要。
3. 建立 plan mode 关键指标面板。

一句话概括：

**当前阶段不再需要重复建设 plan mode 基础设施，下一阶段的重点应该从“有没有 Plan/Executor”切换为“Planner 是否能动态生成灵活计划，Executor 是否能在失败时兜底、降级并 replan”。**
