# 模型调用 Skill

## 目的
大模型可以假定所有环境变量（包括所有API KEY）已经配置完毕。告诉大模型在当前 Python 环境下，如何调用以下三类模型能力：

- LLM
- Embedding
- Rerank

---

## 1. LLM 调用

### 模型
- `deepseek-chat`

### SDK
- `openai.OpenAI`

### 环境变量
```python
LLM_MODEL=deepseek-chat
LLM_API_BASE=https://api.deepseek.com
DEEPSEEK_API_KEY=your_api_key
```

### 初始化
```python
import os
from openai import OpenAI

MODEL_NAME = os.getenv("LLM_MODEL", "deepseek-chat")
API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

llm_client = OpenAI(
    api_key=API_KEY,
    base_url=API_BASE,
)
```

### 调用方式
```python
resp = llm_client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": "你是一个助手。"},
        {"role": "user", "content": "请解释轴承温度升高的常见原因。"},
    ],
    temperature=0.3,
    max_tokens=1024,
)

answer = resp.choices[0].message.content
```

---

## 2. Embedding 调用

### 模型
- `text-embedding-v4`

### SDK
- `langchain_community.embeddings.DashScopeEmbeddings`

### 环境变量
```python
DASHSCOPE_API_KEY=your_dashscope_api_key
```

### 初始化
```python
from langchain_community.embeddings import DashScopeEmbeddings

embeddings = DashScopeEmbeddings(
    model="text-embedding-v4"
)
```

### 单条查询向量化
```python
query = "轴承温度异常升高"
query_vector = embeddings.embed_query(query)
```

### 批量文本向量化
```python
docs = [
    "轴承温度升高可能与润滑不足有关。",
    "冷却异常也会导致轴承温升。"
]

doc_vectors = embeddings.embed_documents(docs)
```

---

## 3. Rerank 调用

### 模型
- `gte-rerank-v2`

### SDK
- `langchain_community.document_compressors.dashscope_rerank.DashScopeRerank`

### 环境变量
```python
DASHSCOPE_API_KEY=your_dashscope_api_key
```

### 初始化
```python
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank

reranker = DashScopeRerank(
    model="gte-rerank-v2"
)
```

### 调用方式
```python
query = "轴承温度异常升高的原因"
documents = [
    "轴承温度升高通常与润滑不足、磨损、冷却不良有关。",
    "空气预热器堵塞会影响换热效率。",
    "振动增大时应检查轴承损伤和对中情况。"
]

results = reranker.rerank(
    documents=documents,
    query=query,
    top_n=2
)
```

### 返回结果使用方式
```python
ranked_docs = [
    {
        "text": documents[item["index"]],
        "score": item["relevance_score"]
    }
    for item in results
]
```

---

## 4. 三种模型的统一初始化示例

```python
import os
from openai import OpenAI
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank


def init_models():
    model_name = os.getenv("LLM_MODEL", "deepseek-chat")
    api_base = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

    llm_client = OpenAI(
        api_key=deepseek_api_key,
        base_url=api_base,
    )

    embeddings = DashScopeEmbeddings(
        model="text-embedding-v4"
    )

    reranker = DashScopeRerank(
        model="gte-rerank-v2"
    )

    return {
        "model_name": model_name,
        "llm_client": llm_client,
        "embeddings": embeddings,
        "reranker": reranker,
    }
```

---

## 5. 最小调用示例

```python
import os
from openai import OpenAI
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank

MODEL_NAME = os.getenv("LLM_MODEL", "deepseek-chat")
API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

llm_client = OpenAI(api_key=API_KEY, base_url=API_BASE)
embeddings = DashScopeEmbeddings(model="text-embedding-v4")
reranker = DashScopeRerank(model="gte-rerank-v2")

query = "轴承温度异常升高的原因"

query_vector = embeddings.embed_query(query)

documents = [
    "轴承温升常见原因包括润滑不足、磨损、冷却不良。",
    "若伴随振动增大，还应检查对中偏差。",
    "空气预热器堵塞通常不直接导致轴承温升。"
]

rerank_results = reranker.rerank(
    documents=documents,
    query=query,
    top_n=2
)

top_docs = [documents[item["index"]] for item in rerank_results]

resp = llm_client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": "你是一个专业助手。"},
        {"role": "user", "content": "参考资料：\n" + "\n".join(top_docs) + "\n\n请回答：" + query},
    ],
    temperature=0.3,
    max_tokens=512,
)

print(resp.choices[0].message.content)
```