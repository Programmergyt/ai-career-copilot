本质上是 RAG-based LLM workflow。在远望工业智能有限公司，2025/11/25-2026/3 做软件开发时完成。

# 关键词数据库构建
1. 核对所有机组名、设备名、测点名，并将其存入关键词数据库。
2. 导出 25 年 3-9 月的数据进行分析，构建相关关键词数据库。

# 向量数据库构建
1. 用 Docling 扫描 PDF 和 Word，提取文本、表格并统一转为 Markdown。
2. 清洗文本关键词，统一机组、设备和测点命名。
3. 按语义段落切分 big chunk，再拆成 small chunk。
4. 对 small chunk 做 embedding 并写入向量数据库。

# Query 与检索流程
1. Query 清洗与关键词映射。
2. 规则引擎整合。
3. Query Expansion 与 Multi Query。
4. 混合检索、RRF 融合、Rerank 重排。