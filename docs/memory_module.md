# 记忆模块

本文档记录当前已落地的记忆模块边界。

## 边界

记忆子系统位于 workflow 内部实现之外。

- API/session 层在 LangGraph 执行前调用 `MemoryService.recall(...)`。
- API/session 层在 LangGraph 执行后调用 `MemoryService.observe_and_write(...)`。
- Workflow 和各 Agent 不导入 memory store 或 memory service。
- `CopilotState.memory_context` 与 `CopilotState.retrieved_memories` 是运行时字段，会从 Redis 持久化状态中排除。

## 目录结构

```text
backend/memory/
├── contracts.py
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

## 存储

- MySQL 是记忆真值来源：`memory_records`、`memory_events`、`memory_summaries`。
- Redis 存储热 recall 缓存和近期记忆事件。
- ChromaDB 存储语义索引，默认落盘到项目根目录下的 `data/chroma`。

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

## 管理 API

```text
GET    /api/memory?session_id=...
POST   /api/memory
PATCH  /api/memory/{memory_id}
DELETE /api/memory/{memory_id}
```

删除采用 MySQL 软删除，并同步移除 Chroma 向量索引条目。
