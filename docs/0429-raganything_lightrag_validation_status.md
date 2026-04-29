# 0429 RAG-Anything / LightRAG 验证状态

创建日期：2026-04-29

## 当前结论

系统的核心 RAG-Anything / LightRAG 链路已经不是“完全跑不通”的状态。当前运行容器中：

- `raganything==1.2.10`
- `lightrag-hku==1.4.15`
- `mineru==2.0.6`
- `transformers==4.51.3`
- `tokenizers==0.21.4`

这些版本组合已成功处理文本、教师审核回流、图片、PDF 多模态材料。

核心停滞点在业务层投影和前端兼容接口：LightRAG KV、Neo4j、Qdrant 中已经存在 PDF 表格和图片 chunk，但旧镜像的 `FileParseTask.chunks` 和 `/courses/{course_id}/search` 仍主要暴露普通文本段，导致资料搜索页无法完整展示多模态 evidence。源码中已经补了 LightRAG KV chunk 合并逻辑，但需要后续一次性重建后才会进入服务。

## 已验证的核心证据

### 1. PDF 文档状态

PDF 材料 `ai_tutor_multimodal_validation_pin4513.pdf` 的 material id：

```text
bc00969c-239c-480f-baa7-cad04ff779ba
```

LightRAG `kv_store_doc_status.json` 中状态为：

```text
status = processed
chunks_count = 3
multimodal_processed = true
```

三个 chunk 分别为：

- 正文/公式 chunk：包含 `cwnd = cwnd * 2`、`cwnd >= ssthresh` 等公式文本。
- 表格 chunk：`original_type = table`，包含 HTML table structure 和 table analysis。
- 图片 chunk：`original_type = image`，包含 Visual Analysis。

### 2. PDF 表格 chunk

表格 chunk id：

```text
chunk-bf20e11db32dd718bb0b5f639beb1ece
```

内容包含：

- 表头：阶段、触发条件、窗口变化、教学提示。
- 拥塞避免行：`cwnd 达到 ssthresh`，窗口变化为 `线性增长`。
- RAG-Anything 生成的 `Table Analysis`。

备注：MinerU/OCR 把“慢启动”识别成了“慢后动”，把 `ssthresh` 识别成了 `sthresh`。这属于解析质量问题，不是链路中断问题。后续可以通过更高质量 PDF、OCR 参数、教师纠错回流或后处理词典优化。

### 3. PDF 图片 chunk

图片 chunk id：

```text
chunk-3c035f753c445adefb67e7c58507a200
```

内容包含：

- 图题：`TCP Congestion Window Chart`
- 纵轴：`cwnd`
- 横轴：`RTT rounds`
- 蓝线先快速上升、达到峰值后急剧下降、随后缓慢恢复。
- Visual Analysis 明确解释为 TCP slow start、congestion event、recovery phase。

### 4. 图谱构建

PDF 在 `kv_store_full_entities.json` 中有 11 个实体，包括：

- `TCP Congestion Window Chart`
- `TCP Congestion Window Evolution Chart (image)`
- `cwnd`
- `RTT rounds`
- `TCP slow start phase`
- `congestion event`
- `packet loss`
- `recovery phase`

PDF 在 `kv_store_full_relations.json` 中有 18 条关系。

Neo4j 中已验证节点具备 description，例如：

- `TCP Congestion Window Evolution Chart (image)`：图片锚点，描述拥塞窗口随 RTT 的变化。
- `cwnd`：拥塞窗口大小。
- `RTT rounds`：往返时间周期。
- `TCP slow start phase`：说明每个 RTT 内 cwnd 加倍直到达到 ssthresh。

Neo4j 中已验证关系具备 description，并存在 `belongs_to` 类关系，例如：

- `TCP Congestion Window Evolution Chart (image) -> cwnd`
- `TCP Congestion Window Evolution Chart (image) -> TCP slow start phase`
- `TCP Congestion Window Chart -> congestion event`
- `TCP Congestion Window Chart -> packet loss`

### 5. 向量库状态

Qdrant 中已有三个 LightRAG 集合：

```text
lightrag_vdb_entities_baai_bge_m3_1024d        points = 31
lightrag_vdb_relationships_baai_bge_m3_1024d   points = 35
lightrag_vdb_chunks_baai_bge_m3_1024d          points = 7
```

这说明实体、关系和 chunk 都已经进入向量空间。

### 6. 中文问答验证

`/api/v1/chat/query` 使用中文问题测试：

```text
PDF 表格里拥塞避免阶段的窗口变化是什么？
```

返回答案：

```text
在TCP拥塞控制的表格中，拥塞避免阶段的窗口变化是线性增长。
```

source 命中：

```text
chunk-bf20e11db32dd718bb0b5f639beb1ece
```

也就是 PDF 表格 chunk。

图片问题：

```text
PDF 图片里的拥塞窗口曲线说明了什么？
```

source 命中：

```text
chunk-3c035f753c445adefb67e7c58507a200
```

即 PDF 图片 Visual Analysis chunk。

## 当前缺口

### 1. 业务搜索接口漏掉多模态 chunk

`/api/v1/courses/{course_id}/search` 对 PDF 表格、图片问题仍主要返回普通文本段。原因是旧镜像中的 `FileParseTask.chunks` 只有官方输出拆出的 4 个文本片段，没有合并 LightRAG KV 里的 table/image chunk。

源码层已经补充：

- 从 LightRAG `kv_store_text_chunks.json` 按 `full_doc_id` 读取 chunk。
- 合并官方输出和 LightRAG KV chunk。
- 清理 `Image Path: /app/...` 这类内部路径泄露。
- 为 table/image chunk 保留更适合前端展示的 snippet。

该补丁需要后续一次性重建后生效。

### 2. 原始图表公式单元还需更好暴露

当前 LightRAG chunk 中能看到原始图片路径、表格 HTML、Visual Analysis、Table Analysis。但前端 source 展示还没有完整结构化呈现：

- 页码。
- 原始图片或表格资源引用。
- bbox 或页面区域。
- 表格 HTML / LaTeX 公式的安全渲染。
- 多模态锚点 entity 与原始单元的关联。

这不是核心索引失败，而是产品层 source evidence 展示还需要增强。

### 3. OCR 质量需要优化

已观察到：

- “慢启动”被识别为“慢后动”。
- `ssthresh` 被识别为 `sthresh`。

后续可做：

- 教师审核纠错回流。
- 专业术语词典修正。
- 解析后规则校正。
- 更高质量 PDF 输入。
- MinerU 参数和模型版本评估。

## 依赖与部署建议

慢网络环境下不要反复 Docker rebuild。后续应采用以下策略：

1. 保留已验证核心版本：
   - `raganything==1.2.10`
   - `lightrag-hku==1.4.15`
   - `mineru==2.0.6`
   - `transformers==4.51.3`
   - `tokenizers==0.21.4`
2. 移除主镜像不需要的 `sentence-transformers`，当前系统使用外部 embedding API。
3. 使用 CPU-only PyTorch wheel，避免 PyPI 默认拉 CUDA 运行时。
4. 不在 Dockerfile 中每次升级 pip，减少网络失败点。
5. 更稳妥的生产结构是拆分镜像：
   - 主后端 API 镜像：登录、课程、问答、审核、业务数据库。
   - RAG 解析 worker 镜像：RAG-Anything + MinerU + OCR/版面模型。
   - LightRAG/Qdrant/Neo4j 持久化存储独立服务。

## 下一步任务

1. 暂停无意义重建，先保留当前健康容器继续验证核心链路。
2. 等依赖方案确认后，只做一次后端/worker 重建。
3. 重建后重新投影 PDF task，让 `FileParseTask.chunks` 合并 LightRAG KV table/image chunk。
4. 复测：
   - `/courses/{course_id}/search`
   - `/chat/query`
   - 学生端 AI 助教
   - 教师端 AI 助教
   - 审核纠错回流
   - 知识图谱接口
5. 增强前端 source 展示，使表格、图片、公式 evidence 不只以纯文本形式出现。
