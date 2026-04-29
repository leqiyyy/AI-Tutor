# RAG-Anything / LightRAG 官方架构学习笔记

更新时间：2026-04-28  
用途：作为后续本项目 RAG 主链、资料入库、多模态处理、引用溯源、审核回流与知识库更新的实现校准文档。

---

## 1. 官方资料来源

本笔记基于以下官方资料和源码阅读整理：

- RAG-Anything 官方仓库：`https://github.com/HKUDS/RAG-Anything`
- RAG-Anything 技术报告：`https://arxiv.org/abs/2510.12323`
- LightRAG 官方仓库：`https://github.com/HKUDS/LightRAG`
- LightRAG 论文：`https://arxiv.org/abs/2410.05779`
- 本次源码只读克隆位置：
  - `/tmp/RAG-Anything-official`
  - `/tmp/LightRAG-official`

---

## 2. 总体分工

### RAG-Anything 的职责

RAG-Anything 是 LightRAG 上层的多模态文档处理与查询框架，主要负责：

1. 接收 PDF、Office、图片、TXT/MD 等文件。
2. 选择 parser：`mineru`、`docling`、`paddleocr`。
3. 将复杂文档解析为 `content_list`。
4. 将 `content_list` 分成纯文本和多模态元素。
5. 纯文本交给 LightRAG 的 `ainsert`。
6. 图片、表格、公式等多模态元素交给专用 processor 生成描述和实体。
7. 将多模态描述作为 chunk、entity、relation 写入 LightRAG 的存储。
8. 查询时调用 LightRAG 的 `aquery`，或先将用户提供的多模态内容转成增强查询。
9. 如果启用 VLM enhanced query，则在检索上下文中发现图片路径后，将图片转 base64 并交给 VLM 与文本上下文一起生成答案。

### LightRAG 的职责

LightRAG 是底层图增强 RAG 引擎，主要负责：

1. 文本 chunking。
2. 文档、chunk、实体、关系、图谱、向量、状态等存储。
3. 对 chunk 调用 LLM 抽取 entity/relation。
4. 合并同名实体和关系，并做 description summary。
5. 将 chunk 写入 chunks vector DB。
6. 将实体写入 graph 和 entities vector DB。
7. 将关系写入 graph 和 relationships vector DB。
8. 查询时根据 query mode 执行 local/global/hybrid/mix/naive 检索。
9. 提取 high-level / low-level keywords。
10. 构建最终 LLM context。
11. 生成答案，并返回结构化 raw data / references。

---

## 3. 官方端到端链路

### 3.1 用户上传文档

本项目中对应入口应是：

- 教师端上传资料。
- 后端保存 `Material`。
- 后端创建 `FileParseTask`。
- 调用 `RAGAnythingAdapter.index/ingest` 类能力。

官方 RAG-Anything 推荐入口：

- `process_document_complete(file_path=..., output_dir=..., parse_method=...)`
- 如果已经有外部预解析结果，可用：
  - `insert_content_list(content_list=..., file_path=..., doc_id=...)`

实现原则：

- 普通 PDF/Office/图片：优先交给 RAG-Anything parser。
- 已经由本系统预处理好的音频/视频 transcript/keyframe：走 `insert_content_list` 更稳。
- 不应在本项目里重复实现 LightRAG 的 chunk/entity/relation 主逻辑。

---

### 3.2 文档分类处理

官方 `parse_document` 根据扩展名选择处理路径：

- `.pdf`：调用 parser 的 `parse_pdf`。
- 图片：调用 parser 的 `parse_image`；如果当前 parser 不支持，回退 MinerU。
- Office/HTML：调用 parser 的 `parse_office_doc`。
- 其他格式：调用 parser 的 `parse_document`。

RAG-Anything 当前 parser：

- `mineru`：适合 PDF、图片、Office 转换后的复杂文档，OCR、表格、公式能力强。
- `docling`：偏 Office/HTML 结构保留。
- `paddleocr`：偏 OCR，适合图片/PDF OCR 结果转 content_list。

本项目建议：

- 默认 `RAGANYTHING_PARSER=mineru`。
- Office 需要 LibreOffice。
- TXT/MD/audio/video sidecar transcript 可直接构造 content_list，避免额外转 PDF。
- 视频如果启用自动预处理：ffmpeg 抽音频、抽关键帧；ASR 生成 transcript；keyframe 以 image content 加入 content_list。

---

### 3.3 原子单元与 content_list

RAG-Anything 的核心原子输入是 `content_list`。

常见元素：

```json
{
  "type": "text",
  "text": "文本内容",
  "page_idx": 0
}
```

```json
{
  "type": "image",
  "img_path": "/absolute/path/to/image.jpg",
  "image_caption": ["caption"],
  "image_footnote": ["note"],
  "page_idx": 1
}
```

```json
{
  "type": "table",
  "table_body": "markdown table",
  "table_caption": ["caption"],
  "table_footnote": ["note"],
  "page_idx": 2
}
```

```json
{
  "type": "equation",
  "text": "LaTeX 或公式文本",
  "text_format": "latex",
  "page_idx": 3
}
```

官方处理逻辑：

1. `separate_content(content_list)` 将 `type=text` 合并成纯文本。
2. 非 text 内容作为 multimodal items。
3. 纯文本走 LightRAG `ainsert`。
4. 多模态元素走 `ImageModalProcessor`、`TableModalProcessor`、`EquationModalProcessor`、`GenericModalProcessor`。

本项目要求：

- `FileParseTask.extra_data.content_items` 应尽量贴近官方 content_list。
- 必须保留 `page_idx/page/timestamp/img_path/table_body/latex/caption/source_name` 等溯源字段。
- 图片路径必须是后端可访问的安全路径，VLM enhanced query 会做路径安全检查。

---

## 4. 多模态元素如何转成可检索内容

### 4.1 图片

官方 `ImageModalProcessor` 做法：

1. 读取 `img_path`。
2. 结合 caption、footnote、上下文。
3. 将图片 base64 交给 vision model。
4. 要求 VLM 返回：
   - `detailed_description`
   - `entity_info.entity_name`
   - `entity_info.entity_type`
   - `entity_info.summary`
5. 构造 `image_chunk`。
6. 写入：
   - `text_chunks`
   - `chunks_vdb`
   - graph node
   - `entities_vdb`
7. 再对这个 chunk 做实体/关系抽取。

### 4.2 表格

官方 `TableModalProcessor` 做法：

1. 读取 `table_body`、caption、footnote、可选表格图片。
2. 结合上下文调用 LLM 分析表格。
3. 生成 detailed description 和 entity_info。
4. 构造 table chunk。
5. 与图片相同，写 chunk、entity、vector、graph，并继续抽取关系。

### 4.3 公式

官方 `EquationModalProcessor` 做法：

1. 读取公式文本和格式。
2. 结合上下文调用 LLM 分析公式含义。
3. 生成公式 description 和 entity_info。
4. 构造 equation chunk。
5. 写入 LightRAG 存储，并继续做实体关系抽取。

### 4.4 关键理解

多模态内容不是直接把图片/表格/公式原样塞进普通向量库，而是先通过专用 processor 转成：

- 可读的描述文本。
- 一个代表该多模态对象的主实体。
- 与上下文实体之间的关系。
- 可被检索的 chunk。

这也是本项目后续不能混乱的地方：**图片/表格/公式的检索基础是“模态对象描述 + 图关系 + chunk 向量”，不是只存文件路径。**

---

## 5. LightRAG 索引链路

### 5.1 文本插入

RAG-Anything 的纯文本最终调用：

- `lightrag.ainsert(input=..., file_paths=..., ids=...)`

LightRAG 的 `ainsert` 分两步：

1. `apipeline_enqueue_documents`
   - 清洗文本。
   - 生成或校验 doc id。
   - 去重。
   - 写 `full_docs`。
   - 写 `doc_status=PENDING`。
2. `apipeline_process_enqueue_documents`
   - 取 pending/failed/processing 文档。
   - 文本切 chunk。
   - 写 `text_chunks`。
   - 写 `chunks_vdb`。
   - 调用 `_process_extract_entities`。
   - 合并实体和关系。
   - 更新 `doc_status=PROCESSED/FAILED`。

### 5.2 chunking

官方默认：

- 按 token 切 chunk。
- 默认 chunk token size 约 1200。
- 默认 overlap 约 100。
- 如果设置 `split_by_character`，先按指定字符切，再按 token 限制二次切。

本项目建议：

- 课程资料默认使用官方 chunking。
- 如果是教材章节/Markdown，可用标题或段落符作为 `split_by_character`，但不能破坏 token 上限。
- 论文实验需要记录 chunk size 和 overlap。

### 5.3 实体关系抽取

LightRAG 对每个 chunk：

1. 构造 entity extraction prompt。
2. LLM 抽取 entities 和 relationships。
3. 如果启用 gleaning，会再追问补充遗漏实体关系。
4. 解析 LLM 结果为 maybe_nodes / maybe_edges。
5. 并发处理多个 chunk。
6. 调用 `merge_nodes_and_edges` 合并全局实体/关系。

实体/关系字段核心包括：

- entity name
- entity type
- description
- source_id
- file_path
- relation src/tgt
- relation keywords
- relation weight

合并时会：

- 同名实体合并 source_id。
- 多个 description 过长时使用 LLM summary。
- 关系同样合并、汇总。
- 更新 graph、entities_vdb、relationships_vdb、full_entities、full_relations、entity_chunks、relation_chunks。

---

## 6. LightRAG 存储结构

LightRAG 初始化的主要存储：

| 存储 | 作用 |
|---|---|
| `full_docs` | 原始文档全文 |
| `text_chunks` | chunk KV 存储 |
| `chunks_vdb` | chunk 向量检索 |
| `chunk_entity_relation_graph` | 实体关系图 |
| `entities_vdb` | 实体向量检索 |
| `relationships_vdb` | 关系向量检索 |
| `full_entities` | 文档级实体追踪 |
| `full_relations` | 文档级关系追踪 |
| `entity_chunks` | entity -> chunk 追踪 |
| `relation_chunks` | relation -> chunk 追踪 |
| `doc_status` | 文档处理状态 |
| `llm_response_cache` | LLM 调用缓存 |

默认实现是 JSON/NanoVectorDB/NetworkX，但可替换为：

- Qdrant / Milvus / FAISS / OpenSearch 等向量存储。
- Neo4j / Memgraph / NetworkX 等图存储。
- Redis / Mongo / PostgreSQL / JSON 等 KV 存储。

本项目当前服务器栈使用 Qdrant + Neo4j 是合理方向。

---

## 7. 用户问题处理与检索

### 7.1 Query modes

LightRAG `QueryParam.mode` 支持：

- `naive`：仅 chunk 向量检索。
- `local`：偏低层实体，适合具体概念/实体问题。
- `global`：偏高层关系，适合主题、全局性问题。
- `hybrid`：结合 local/global。
- `mix`：结合知识图谱和 chunk 向量检索。
- `bypass`：绕过检索的特殊路径。

本项目建议默认：

- 普通课程问答：`mix` 或 `hybrid`。
- 精确概念：`local`。
- 总结/比较/跨章节问题：`global` 或 `mix`。
- 对照实验必须比较多种 mode。

### 7.2 检索前准备

LightRAG 在 `kg_query` 中：

1. 从 query 提取 high-level keywords 和 low-level keywords。
2. 如果 query 很短且关键词为空，会用原 query 作为 low-level keyword。
3. 构建 query context。

关键词作用：

- low-level keywords：用于 entity/local 检索。
- high-level keywords：用于 relationship/global 检索。

### 7.3 检索过程

`_build_query_context` 是核心四阶段：

1. Search
   - local：查 entities_vdb，再找相关 relation/chunk。
   - global：查 relationships_vdb，再找相关 entity/chunk。
   - mix：额外查 chunks_vdb。
2. Truncate
   - 对实体、关系按 token budget 截断。
3. Merge chunks
   - 合并来自 entity、relation、vector 的 chunk。
   - 去重。
   - 可 rerank。
4. Build LLM context
   - 生成 entities context。
   - 生成 relations context。
   - 生成 chunks context。
   - 生成 reference list。
   - 生成 raw_data。

### 7.4 输入生成模型

LightRAG 最终将 context 填入 `PROMPTS["rag_response"]`：

- context_data：实体、关系、chunks、reference list。
- response_type：回答格式。
- user_prompt：附加用户/系统要求。
- user_query：原始问题。
- conversation_history：只传给 LLM 生成，不用于检索。

关键点：

**多轮历史不会直接参与检索，只影响最终生成。**  
如果本项目希望历史也影响检索，需要在进入 RAG 前做 query rewrite，把当前问题 + 必要历史改写成独立查询。

---

## 8. 图、表、公式查询如何处理

有两类情况：

### 8.1 文档中已有图/表/公式

入库时已经被 processor 转为：

- 描述 chunk。
- 多模态实体。
- 与文本实体的关系。
- 可检索向量。
- graph node/edge。

查询时如果检索上下文中包含图片路径，并启用 VLM enhanced query：

1. RAG-Anything 在上下文中匹配 `Image Path`。
2. 校验图片路径安全。
3. 将图片转 base64。
4. 构造 VLM messages：
   - text context
   - image_url content
   - user question
5. 交给 vision model 生成最终答案。

### 8.2 用户问题附带图/表/公式

使用：

- `aquery_with_multimodal(query, multimodal_content=[...])`

流程：

1. 对用户附带的 image/table/equation 生成描述。
2. 将描述拼接到 enhanced query。
3. 再调用普通 `aquery` 检索知识库。

这意味着用户上传的临时图片/表格不是直接进入长期知识库，而是先用于增强本轮查询。若要长期入库，必须走 `insert_content_list` 或正式资料上传链路。

---

## 9. 答案输出与引用溯源

LightRAG 现在有 `QueryResult` 和 `raw_data`：

- `content`：最终回答。
- `raw_data`：结构化检索结果。
- `reference_list`：从 raw_data 提取引用列表。
- `metadata`：query mode、keywords、processing info。

raw_data 中包含：

- entities
- relationships
- chunks
- references
- metadata

本项目要做的事情：

- 不应只接收字符串答案。
- 应优先使用 `aquery_data` 或能返回 raw_data 的路径，或者在 adapter 中兼容 `QueryResult.raw_data`。
- citations 应从 references/chunks/entities/relationships 中归一化：
  - source/file_path
  - page/page_idx
  - chunk_id
  - reference_id
  - score
  - modality
  - entity/relation id

如果只调用兼容版 `aquery` 返回字符串，本项目会丢失正式引用溯源能力。

---

## 10. 反馈、教师审核、回流的正确接入方式

官方 RAG-Anything / LightRAG 负责知识库，不负责教育业务审核。因此本项目要在业务层实现 human-in-the-loop。

### 10.1 用户反馈

学生点赞/点踩应写入本项目数据库，而不是直接写 LightRAG：

- message_id
- user_id
- class_id
- course_id
- feedback_type：like/dislike
- reason
- comment
- selected_source_id/chunk_id 可选
- created_at

点踩或低置信触发 `ReviewItem`。

### 10.2 教师审核

教师审核应展示：

- 原问题。
- AI 回答。
- 检索来源。
- confidence。
- source_count。
- grounding/evidence quality。
- 学生点踩原因。
- 学生补充说明。

教师动作：

- 采纳 AI 回答。
- 修改答案。
- 补充标准答案。
- 标记无需回流。
- 标记回流知识库。

### 10.3 回流知识库

推荐两种回流方式：

#### 方式 A：作为高可信 QA 文本写入 LightRAG

构造文本：

```text
教师审核问答
问题：...
AI 原回答：...
教师修正答案：...
适用课程：...
知识点：...
来源：teacher_review
```

然后调用 LightRAG/RAG-Anything 插入：

- `ainsert(input=qa_text, file_paths="teacher_review:<review_id>", ids=<stable_doc_id>)`
- 或 `insert_content_list([{type:"text", text: qa_text, page_idx:0}], file_path=...)`

优点：

- 最稳，完全复用 LightRAG chunk/entity/relation 抽取。
- 会进入 chunks_vdb、entities_vdb、relationships_vdb、graph。

缺点：

- 不是结构化 QA 专用检索，可能需要 prompt 让模型优先相信教师审核内容。

#### 方式 B：建立课程 QA Bank + 向量索引

本项目单独维护 `verified_qa`：

- question
- teacher_answer
- course_id
- class_id
- knowledge_point
- source_review_id
- verified_by
- embedding

查询时先查 QA Bank，再和 RAG-Anything 结果融合。

优点：

- 教育业务可控。
- 容易统计教师修正命中率。

缺点：

- 需要额外融合逻辑。

建议：

第一版采用 A，保证回流真的进入 LightRAG。  
第二版叠加 B，形成“教师高可信 QA Bank”，并在 query rewrite/context merge 前作为强证据。

---

## 11. 本项目后续实现红线

1. 不要绕开 RAG-Anything 自己手写完整 RAG 主链。
2. 不要只存 `content_items` 到本项目数据库而不写入 LightRAG。
3. 不要把图片/表格/公式只当附件路径存储，必须生成描述和实体。
4. 不要只调用返回字符串的 query 后丢掉 raw_data，否则引用溯源会变弱。
5. 用户反馈和教师审核属于业务层，不能强塞进 LightRAG 状态表。
6. 教师补答回流必须有 sync 状态和失败原因。
7. 多轮历史默认只影响生成，不影响检索；如要影响检索，必须先做 query rewrite。
8. 班级知识边界要清晰：LightRAG working_dir/workspace 或 doc_id/file_path 必须能隔离 course/class。

---

## 12. 本项目建议落地架构

### 12.1 入库

```text
教师上传资料
-> Material + FileParseTask
-> RAGAnythingAdapter.process_document_complete / insert_content_list
-> LightRAG full_docs/text_chunks/chunks_vdb/entities_vdb/relationships_vdb/graph
-> 同步本项目 KnowledgeEntity/KnowledgeRelation 投影
-> 前端展示文件状态、解析质量、图谱
```

### 12.2 查询

```text
学生/教师提问
-> chat_service 组装 class/course/session/role/history
-> query rewrite：必要时将多轮问题改写为独立问题
-> RAGAnythingAdapter.aquery / aquery_with_multimodal
-> LightRAG keyword extraction
-> local/global/mix 检索
-> entities + relations + chunks + references
-> LLM/VLM 生成
-> 保存 ChatMessage + citations + raw retrieval meta
-> 返回前端
```

### 12.3 审核回流

```text
低置信/点踩
-> ReviewItem
-> 教师修正
-> ReviewSyncRecord
-> 构造 teacher_review QA 文本
-> insert_content_list / ainsert 回流 LightRAG
-> sync=synced/failed
-> 相似问题验证命中
```

---

## 13. 后续需要优先检查的本项目代码点

- `backend/app/integrations/rag/raganything_adapter.py`
  - 是否能拿到 `QueryResult.raw_data`。
  - 是否只返回字符串导致 citation 弱化。
  - 是否正确使用 `aquery_with_multimodal`。
  - 是否正确传 `mode` / `query_mode`。
- `backend/app/services/kb_service.py`
  - audio/video transcript 是否使用 `insert_content_list`。
  - 文件状态与 RAG-Anything doc_status 是否一致。
- `backend/app/services/chat_service.py`
  - 多轮历史是否只用于生成，是否需要 query rewrite。
  - citations 是否存 raw retrieval data。
- `backend/app/services/review` / `chat_service`
  - 教师补答是否真正回流到 LightRAG，而不是只写 DB。
- `backend/app/models/knowledge.py`
  - 本地图谱应作为 LightRAG 图谱投影，不应成为另一套脱节图谱。

