# 记忆模块

本文档记录当前已落地的记忆模块边界。

## 边界

记忆子系统位于 workflow 内部实现之外。

- API/session 层在 LangGraph 执行前调用 `MemoryService.recall(...)`。
- API/session 层在 LangGraph 执行前调用 `MemoryContextWindowManager.manage(...)` 做 128K Token 上下文预算管理。
- API/session 层在 LangGraph 执行后调用 `MemoryService.observe_and_write(...)`。
- Workflow 和各 Agent 不导入 memory store 或 memory service。
- `CopilotState.memory_context` 与 `CopilotState.retrieved_memories` 是运行时字段，会从 Redis 持久化状态中排除。
- `CopilotState.context_window` 与 `CopilotState.llm_token_usage` 用于调试和观测，会随 `/api/chat` 响应返回。

## 目录结构

```text
backend/memory/
├── contracts.py
├── context_window.py
├── context_adapter.py
├── extractor.py
├── policy.py
├── retriever.py
├── service.py
└── stores/
    ├── chroma_memory_index.py
    ├── mysql_memory_store.py
    └── redis_memory_store.py
```

相关但不在 `backend/memory/` 下的配套模块：

```text
backend/models/token_counter.py
backend/models/llm.py
backend/storage/redis_client.py
```

## 存储

- MySQL 是记忆真值来源：`memory_records`、`memory_events`、`memory_summaries`。
- Redis 存储热 recall 缓存和近期记忆事件。
- Redis Stack/RedisJSON 用于 checkpoint 状态隔离；当 RedisJSON 不可用时，会回退为普通字符串 JSON 存储。
- ChromaDB 存储语义索引，默认落盘到项目根目录下的 `data/chroma`。

## Token 计算

LLM Token 计算由 `backend/models/token_counter.py` 提供，按 `backend/config.yaml` 中的 `llm.provider` 选择计数策略。

- `openai`、`azure_openai`、`deepseek`、`qwen`、`openai_compatible`：优先尝试 `tiktoken`，不可用时回退启发式估算。
- `anthropic`、`claude`：使用供应商覆盖参数和启发式估算。
- `ollama`、`local`：使用本地模型启发式估算。

当前配置入口：

```yaml
llm:
  context_window_tokens: 131072
  token_counter:
    method: "auto"
    chars_per_token: 3.5
    message_overhead_tokens: 4
    provider_overrides:
      anthropic:
        chars_per_token: 3.8
      ollama:
        chars_per_token: 3.6
```

每次 LLM 调用都会记录：

- `estimated_prompt_tokens`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `prompt_truncated_tokens`
- `usage_source`

真实 usage 优先从 LangChain response 的 `usage_metadata`、`response_metadata.token_usage`、`llm_output` 中提取；供应商未返回 usage 时使用估算值兜底。

## 当前归属模型

当前应用还没有用户身份体系，因此记忆记录采用：

- `session_id` 作为当前有效 owner key。
- `user_id` 作为可为空的未来扩展字段。
- 未提供 `user_id` 时，`scope=session`。

## 写入规则

第一版实现采用确定性提取：

- 候选人画像事实会写成 `profile_fact` 记忆。
- 简历 section、原始材料和面试问答会写成 `artifact` 记忆。
- 明确表达偏好的用户消息会写成 `preference` 记忆。

写入链路采用 best-effort 策略。记忆模块失败会写日志，但不会中断 `/api/chat`。

## 检索规则

Recall 使用混合检索：

1. 通过 MySQL 按 `session_id`、可选 `user_id`、kind 和 status 做结构化查询。
2. 通过 Chroma 做语义向量召回。
3. 可选地通过现有 `models.rerank` 适配器做 rerank。
4. 通过 Redis 缓存重复 recall 查询。

格式化后的结果会注入运行时 `memory_context`。

## 128K 上下文管理

`MemoryContextWindowManager` 在 Graph 调用前对完整 state 做 Token 预算估算，确保后续 LLM 调用不会超过 128K 上下文窗口。

预算计算：

```text
budget_tokens = context_window_tokens - llm.max_tokens - context_safety_margin_tokens
```

因此调试页里的“预算”不是完整 128K，而是允许进入 Graph/LLM 前的输入侧预算。当前默认值为：

```text
120,832 = 131,072 - 8,192 - 2,048
```

含义分别是：

- `131,072`：模型上下文窗口上限，即 128K Token。
- `8,192`：`llm.max_tokens`，预留给本轮模型输出。
- `2,048`：`memory.context_safety_margin_tokens`，预留给供应商协议开销、消息包装、工具/框架元数据和估算误差。
- `120,832`：Graph 调用前允许使用的最大输入预算。

默认配置：

```yaml
memory:
  context_window_tokens: 131072
  context_safety_margin_tokens: 2048
  memory_context_tokens: 24000
  dynamic_summary_tokens: 2000
  min_retrieval_tokens: 2000
```

处理顺序：

1. 估算当前 `CopilotState` 的总 Token 数。
2. 如果未超过预算，直接进入 Graph。
3. 如果超过预算，优先按分数保留检索命中的记忆片段，并截断超出 `memory_context_tokens` 的片段。
4. 如果仍超过预算，生成动态摘要，保留最多 `dynamic_summary_tokens` 的历史记忆摘要。
5. 如果仍超过预算，对 `user_message` 做滑动窗口裁剪，保留最近内容。
6. 如果仍超过预算，执行强制收敛：继续压缩 `memory_context`、压缩 `user_message`，必要时移除运行时记忆上下文。
7. 如果最终仍无法满足预算，`/api/chat` 返回 413，避免执行超窗口 LLM 调用。

输出的 `context_window` 指标包括：

- `provider`
- `model`
- `max_context_tokens`
- `budget_tokens`
- `estimated_tokens_before`
- `estimated_tokens_after`
- `memory_tokens_before`
- `memory_tokens_after`
- `retrieved_memory_count_before`
- `retrieved_memory_count_after`
- `sliding_window_tokens_removed`
- `retrieval_tokens_removed`
- `summarized_tokens`
- `summary_tokens`
- `truncated_tokens`
- `within_budget`
- `actions`

其中前端调试页重点展示：

- “预算”：`budget_tokens`，Graph 调用前可用的输入 Token 预算，不等于完整 128K，因为已经扣除了模型输出额度和安全余量。
- “Graph 前估算”：`estimated_tokens_after`，经过记忆裁剪、动态摘要和滑动窗口处理后，整个 `CopilotState` 在进入 LangGraph 前的 Token 估算。它包含用户输入、运行时记忆上下文、已持久化的简历/JD/画像状态、问题列表、渲染配置等会随 state 传入 Graph 的内容。
- “记忆长度”：`memory_tokens_after`，仅指最终注入 `CopilotState.memory_context` 的召回记忆上下文 Token 数，不包含用户本轮输入、JD、简历内容、画像、Graph 运行字段或 prompt 模板。
- “裁剪长度”：`truncated_tokens`，本轮为了满足预算从检索片段、动态摘要覆盖内容和滑动窗口中移除或压缩掉的估算 Token 总数。

## LLM 调用观测

`backend/models/llm.py` 在统一调用入口中开启 request-local trace：

- `begin_llm_trace(session_id)`
- `get_llm_trace_records()`
- `end_llm_trace(...)`

当前所有通过 `ainvoke_json_with_schema(...)`、`call_llm(...)`、`acall_llm(...)` 的调用都会被记录。记录结果写入：

- `/api/chat` 响应字段 `llm_token_usage`
- Redis session event：`event_type=llm_token_usage`
- Redis checkpoint metadata

如果单次 prompt 在进入供应商 API 前仍超过预算，LLM wrapper 会再做一次 prompt 级兜底裁剪，并记录到 `prompt_truncated_tokens`。

## Checkpoint 状态隔离

`RedisSessionStore` 新增 checkpoint 能力：

```text
session:{session_id}:checkpoint:{namespace}:{checkpoint_id}
session:{session_id}:checkpoint:{namespace}:index
```

默认 namespace 为 `live`。`/api/chat` 当前会保存：

- `{checkpoint_id}:before_graph`：Graph 调用前 state，包含上下文窗口统计。
- `{checkpoint_id}:after_graph`：Graph 调用后 state，包含 LLM 调用次数和 Token 合计。

Checkpoint 优先使用 Redis Stack 的 `JSON.SET` / `JSON.GET`。如果部署环境只有普通 Redis，代码会自动回退为 `SET` / `GET` JSON 字符串，保证功能可用。

## 前端调试视图

调试页 `frontend/src/components/tabs/DebugPanel.vue` 会展示：

- 最近触发的 Agent 链路。
- 上下文窗口预算、Graph 前估算、记忆长度、裁剪长度。
- 每次 LLM 调用的 Prompt、Completion、Total、裁剪 Token。
- LLM Token 合计。
- `resume_content_json` 与 `render_config`。

## 管理 API

```text
GET    /api/memory?session_id=...
POST   /api/memory
PATCH  /api/memory/{memory_id}
DELETE /api/memory/{memory_id}
```

删除采用 MySQL 软删除，并同步移除 Chroma 向量索引条目。
