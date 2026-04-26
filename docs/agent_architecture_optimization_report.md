# Agent 架构优化分析报告（Plan Mode + 模块化解耦）

> 目标：在现有设计基础上，将“固定链路编排”升级为“更灵活的 Plan Mode”，每次运行时先由LLM生成静态的计划，包含要执行的Agent列表以及相关的安排，然后按照计划一一执行，执行出错要进行replan；将各个 Agent 模块化、可插拔、彼此解耦。
> 目前运行环境：` (D:\Anaconda\shell\condabin\conda-hook.ps1) ; (conda activate rag_workflow)`

---

## 1. 现状分析（基于当前后端代码）

### 1.1 编排层现状

当前主流程已经是 Plan Mode 的基础形态，不再是多节点固定链路：

- `workflow/graph.py` 当前图结构为：`planner -> executor -> respond`。
- `planner` 节点由 `agents.runtime.make_runtime_node("planner")` 包装，进入统一运行时约束。
- `executor` 节点为 `workflow.plan_mode.plan_executor.plan_executor_node_async`，按 `execution_steps` 串行执行。

结论：编排主干已完成“Planner + Executor”收敛，具备继续演进为完整 Plan Mode 的条件。

### 1.2 Planner 现状

`agents/planner.py` 的职责为：

1. 用 LLM 做意图识别（`IntentClassificationOutput`）。
2. 用本地规则生成任务包（`task_extractor.extract_task_bundle`）。
3. 用本地规则模板生成计划（`plan_builder.build_plan_from_tasks`）。
4. 用 `plan_validator.validate_plan` 做静态校验。

关键事实：

- 当前 **LLM 仅用于 intent classification**。
- 当前 `PlanStep` 仍由代码内 `_StepSpec` 规则拼装，不是 LLM 原生产出的静态计划。

结论：与“每轮先由 LLM 生成静态计划”的目标相比，还差 Planner 生成机制升级。

### 1.3 Plan Schema 与执行策略现状

`workflow/plan_mode/plan_schema.py` 已包含：

- `Plan/PlanStep/PlanPolicy/StepResult/ContractViolation`
- `depends_on`、`preconditions`、`retry`、`on_error`、`skippable`、`fallback_action`

`workflow/plan_mode/plan_executor.py` 已支持：

- 串行执行
- 重试（retry）
- 降级（degrade）
- 跳过（skip）
- 合约违规记录

`workflow/plan_mode/replan_decider.py` 当前是桩实现：

- `should_replan_after_step_failure(...)` 固定返回 `False`。

结论：执行器具备失败分类与恢复策略基础，但 **自动 replan 闭环尚未落地**。

### 1.4 Agent 模块化与解耦现状

已完成的解耦能力：

- `agents/contracts.py` 明确每个 Agent 的读写边界与支持动作。
- `agents/registry.py` 通过注册中心统一发现执行器。
- `agents/runtime.py` 统一执行入口，做合约过滤、违规记录、step result 注入。

仍存在的耦合点：

- 默认注册表 `build_default_registry()` 写死内置 Agent 列表。
- `plan_builder.py` 对业务链路与 Agent 选择采用硬编码规则。
- 新增 Agent 需同时改动 contracts、registry、plan_builder、测试，扩展成本仍偏高。

结论：目前属于“可插拔雏形”，距离“高度可插拔（声明式接入）”还有一段差距。

### 1.5 状态与持久化现状

- `workflow/state.py` 已有完整运行时字段：`execution_steps`、`step_results`、`contract_violations`、`replan_candidate` 等。
- `api/chat.py`、`api/resume.py` 持久化到 Redis 时会排除运行时字段（仅保留业务状态）。

优点：状态清晰，运行时数据不会污染长期会话存储。

注意点：Plan 运行轨迹目前仅体现在单次 API 返回中，没有单独的 plan_run/step_run 落库与可追溯视图。

### 1.6 测试覆盖现状

已有测试：

- `test_plan_validator.py`：计划合法性、依赖环、前置条件、合约边界。
- `test_plan_executor.py`：串行执行、失败中断、重试、降级、合约违规。
- `test_agent_runtime.py`：运行时合约过滤与异常记录。

缺口：

- 缺少“replan 触发与回路”测试（因为功能尚未启用）。
- 缺少“LLM 生成 Plan”相关结构化输出测试。
- 缺少“插件化注册（动态 Agent 清单）”测试。

---

## 2. 目标差距总结

对照本报告开头目标，当前差距可归纳为 4 点：

1. 计划来源差距：目前是“LLM 意图 + 规则拼装计划”，目标是“LLM 直接生成静态计划”。
2. 故障恢复差距：目前仅设置 `replan_candidate`，未真正触发 replan 并继续执行。
3. 插拔能力差距：目前 Agent 注册与编排模板有硬编码，新增 Agent 仍需改多处。
4. 可观测性差距：缺少面向 Plan 运行历史的独立存储与分析入口。

---

## 3. 改造原则

为避免大改带来回归风险，建议采用“分阶段可回退”策略：

1. 先替换 Planner 计划生成方式，再接入 replan。
2. 保留 `plan_validator` 作为 LLM 计划的强约束闸门。
3. Executor 保持串行不变，先做正确性，再考虑并行能力。
4. 每阶段都以测试先行，确保可灰度。

---

## 4. 分阶段改动计划（写入本次优化目标）

### 阶段 A：LLM 静态计划生成落地（核心）

目标：让 Planner 输出的 `Plan` 来自 LLM，而不是本地 `_StepSpec` 规则模板。

主要改动：

1. 新增计划输出 JSON 合约。
2. 新增 Planner 专用提示词（约束可用 Agent、action、读写字段、前置条件）。
3. `planner_node_async` 中引入“LLM 生成 Plan -> 结构化校验 -> validate_plan”链路。
4. 保留原 `build_plan_from_tasks` 作为降级兜底（feature flag 控制）。

建议涉及文件：

- 新增：`backend/agents/plan_contracts.py`
- 新增：`backend/prompts/plan_generation.py`
- 修改：`backend/agents/planner.py`
- 可选修改：`backend/config_loader.py`、`backend/config.yaml`（增加 `ENABLE_LLM_PLAN`）

验收标准：

1. 同一输入可返回结构化 `Plan(steps[])`。
2. 无效计划会被 `validate_plan` 拦截并给出可解释错误。
3. 当 LLM 计划失败时，系统可回退到规则计划，接口可用性不下降。

### 阶段 B：replan 闭环执行

目标：步骤失败后自动重规划并继续执行，而不是直接失败退出。

主要改动：

1. 将 `replan_decider.py` 从桩实现升级为策略模块：
	- 根据 `error_code`、step 是否关键、重试次数决定是否 replan。
2. Executor 增加 replan loop：
	- 失败 -> 生成 replan 输入（携带已完成步骤、失败原因、当前状态）
	- Planner 生成新计划（可截断未执行步骤）
	- 继续执行，限制最大 replan 次数（如 1~2 次）
3. 在 `CopilotState` 增加 replan 计数字段（如 `replan_count`、`max_replans`）。

建议涉及文件：

- 修改：`backend/workflow/plan_mode/replan_decider.py`
- 修改：`backend/workflow/plan_mode/plan_executor.py`
- 修改：`backend/workflow/state.py`
- 修改：`backend/agents/planner.py`（支持 replan 场景输入）

验收标准：

1. 可重试类失败触发 replan 并继续执行。
2. 不可恢复失败快速终止并返回明确错误。
3. replan 次数受控，避免死循环。

### 阶段 C：Agent 插件化增强（降低接入成本）

目标：新增 Agent 时尽量不改核心编排代码。

主要改动：

1. 把 Agent 元数据从硬编码迁移到声明式描述：
	- 名称、支持 intent/action、默认读写、能力标签。
2. `build_default_registry()` 支持“自动发现 + 配置注册”。
3. Planner 生成计划时使用 Agent 能力目录（capability catalog），减少写死映射。

建议涉及文件：

- 修改：`backend/agents/registry.py`
- 修改：`backend/agents/contracts.py`
- 新增：`backend/agents/capability_catalog.py`（或 YAML 配置）
- 修改：`backend/agents/planner.py`

验收标准：

1. 新增一个 Agent 仅需新增实现 + 合约声明，最少改动主链路。
2. 未注册 Agent 不会被 Planner 选中。
3. Agent 能力变更可通过配置生效并通过校验。

### 阶段 D：Plan 可观测性与回放能力

目标：支持问题定位、效果评估、线上回放。

主要改动：

1. 增加 `plan_run` / `step_run` 持久化（MySQL）。
2. 记录计划版本、replan 链路、每步耗时、失败原因、降级路径。
3. 增加查询接口或内部调试接口（按 session_id 查看计划执行历史）。

建议涉及文件：

- 修改：`backend/storage/mysql_client.py`
- 新增/修改：`backend/sql/init_schema.sql`
- 修改：`backend/api/chat.py`（异步落库扩展）
- 可选新增：`backend/api/plan_debug.py`

验收标准：

1. 单次会话可追溯完整计划执行轨迹。
2. 可区分首次计划与 replan。
3. 可统计失败率、replan 命中率、平均步耗时。

---

## 5. 推荐实施顺序与里程碑

建议按以下顺序推进，保证每一步都可独立上线：

1. M1（1~2 天）：阶段 A 骨架（LLM 计划 + 校验 + 兜底）。
2. M2（1~2 天）：阶段 B（replan loop + 上限控制 + 测试）。
3. M3（2~3 天）：阶段 C（声明式 Agent 能力目录 + 自动注册）。
4. M4（1~2 天）：阶段 D（plan_run/step_run 落库 + 查询）。

---

## 6. 风险与缓解

1. LLM 计划不稳定：
	- 缓解：严格 JSON schema + `validate_plan` + 规则计划兜底。
2. replan 导致链路变长：
	- 缓解：限制 replan 次数，区分可恢复/不可恢复错误。
3. 插件化后配置错误增多：
	- 缓解：启动期进行 capability 自检并阻止不合法 Agent 注册。
4. 观测落库增加写放大：
	- 缓解：异步批量写入，设置抽样或日志级别。

---

## 7. 完成定义（Definition of Done）

满足以下条件视为本次“Plan Mode + 模块化解耦”目标达成：

1. 每轮请求由 LLM 生成结构化静态计划并通过校验后执行。
2. 执行失败可按策略自动 replan，且具备次数与边界控制。
3. Agent 接入从“多文件硬编码改造”下降到“声明式注册 + 最小代码变更”。
4. 可查询单轮会话的计划执行轨迹，并可定位失败步骤与原因。

