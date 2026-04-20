# 第四章 AI助教平台关键模块设计与实现（二稿）

> 适用论文题目：基于大语言模型和检索增强生成的助教平台设计  
> 写作定位：本章面向系统实现，不写成泛泛的功能介绍，而是围绕项目代码中的真实处理链路、模型配置、数据落库、RAG-Anything 集成、知识图谱原型、问答闭环和实验观测机制展开。  
> 主要对应代码：`backend/app/services/`、`backend/app/integrations/`、`backend/app/models/`、`frontend/src/pages/`。

## 4.1 平台关键模块总体实现思路

本系统面向高校课程教学场景，目标是构建一个能够支持课程资料管理、知识库动态更新、基于课程证据的智能问答、教师审核回流以及学习分析的 AI 助教平台。系统整体采用前后端分离架构：前端使用 React、Vite、TypeScript 和 Tailwind CSS 构建学生端、教师端和管理端界面；后端使用 FastAPI 提供统一 REST API；数据库访问使用 SQLAlchemy ORM；数据存储支持本地文件系统和 MinIO 对象存储；异步索引任务通过 Celery 预留队列能力；RAG 知识引擎层采用 RAG-Anything 增强主链与 SimpleRAGEngine 本地回退链并存的方式实现。

从模块协同角度看，系统可划分为五个核心层次：第一，用户与课程业务层，负责认证、课程、班级、任务、资料、消息等基础教学业务；第二，知识库构建层，负责文件上传、解析、分块、content items 归一化、知识空间状态维护和索引任务管理；第三，AI 问答层，负责问题接收、历史上下文组装、RAG 检索、重排序、生成回答、引用落库与置信度输出；第四，教师审核与知识回流层，负责低置信回答、学生点踩反馈、教师修正和人工问答补丁回灌；第五，学习分析与实验评估层，负责学习行为记录、问答事件统计、RAG 性能指标、模型路由切片和离线 benchmark 报告导出。

本章重点说明后三个层次的实现细节。需要特别指出的是，本文系统并不将大语言模型直接作为唯一知识来源，而是将 LLM、Embedding、VLM、Parser、Reranker、数据库和对象存储共同组织为一条可追溯的课程知识处理链。系统通过配置项和管理端模型配置表支持模型 API、本地 OpenAI-compatible 服务以及 mock 回退三类模式。默认配置中，生成模型字段为 `LLM_MODEL=claude-opus-4-6`，嵌入模型为 `text-embedding-3-small`，嵌入维度为 `1536`，RAG-Anything 解析器为 `mineru`，查询模式为 `mix`。在真实部署中，可将这些模型指向中转 API、本地部署模型服务或兼容 OpenAI 协议的模型网关；在无 API Key 的开发环境中，系统会回退到 mock 或规则化摘要，保证原型主流程可运行。

## 4.2 课程资源管理与知识库构建模块设计与实现

### 4.2.1 模块功能概述

课程资源管理与知识库构建模块是整个 AI 助教平台的知识入口。教师上传讲义、PPT、实验指导书、图片或其他课程资料后，系统需要完成文件保存、资料元数据记录、重复文件检测、解析任务创建、同步或异步索引执行、知识库状态更新以及解析失败处理。该模块主要对应后端接口 `POST /api/v1/courses/{course_id}/files/upload`，核心业务逻辑位于 `backend/app/services/kb_service.py`，资料、知识空间和解析任务分别由 `Material`、`KBSpace` 和 `FileParseTask` 等数据表承载。

系统在设计上将“文件上传成功”和“知识库索引成功”区分开。文件上传只说明课程资料已经进入平台，索引成功才说明该资料已经被解析、分块并能够进入问答链路。因此，资料表 `Material` 中设置 `kb_status` 字段，支持 `pending`、`processing`、`indexed` 和 `failed` 等状态；解析任务表 `FileParseTask` 中设置 `status` 字段，支持 `pending`、`processing`、`completed` 和 `failed` 等状态。通过这种状态拆分，教师和管理员能够判断资料是否只是保存成功，还是已经完成知识库构建。

### 4.2.2 课程资料上传与任务创建流程

资料上传流程首先进行课程与班级权限校验。教师请求上传文件时，系统根据 `course_id` 和可选 `class_id` 调用 `resolve_class_for_course` 确定资料归属班级。如果教师未显式指定班级，系统会选择该课程下教师可访问的班级。随后系统读取上传文件内容，计算 SHA-256 哈希值，并在同一班级内检查是否存在相同文件。若检测到重复资料且原解析任务仍处于 `pending`、`processing` 或 `completed` 状态，系统直接复用已有 `Material` 和 `FileParseTask`，返回 `deduplicated=true` 与 `action=reuse_existing`。该设计避免教师重复上传同一课件时造成重复解析、重复嵌入和重复图谱更新。

若文件不是重复资料，系统通过存储适配层保存文件。当前实现支持两类存储后端：当 `STORAGE_BACKEND=local` 时，系统调用 `LocalStorageBackend` 将文件复制到本地 `uploads/{class_id}` 目录，并生成随机存储文件名；当 `STORAGE_BACKEND=minio` 时，系统调用 `MinioStorageBackend` 将文件保存到 MinIO 对象存储桶。MinIO 配置包括 `MINIO_ENDPOINT`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`、`MINIO_BUCKET` 和 `MINIO_SECURE`。这种适配层设计使系统在毕设开发阶段可使用本地文件系统，在生产或实验服务器中可切换到对象存储。

文件保存后，系统创建 `Material` 记录，保存班级、上传者、标题、文件名、文件路径、文件大小、MIME 类型、文件类型和描述等元数据。文件类型根据扩展名映射为 `pdf`、`docx`、`ppt`、`md`、`txt`、`image` 或 `other`。完成资料元数据保存后，系统进入索引阶段。索引方式分为同步和异步两种：当 `async_index=false` 时，接口内直接调用 `ingest_material_with_retry` 执行解析与索引；当 `async_index=true` 时，系统先调用 `prepare_parse_task_for_enqueue` 创建或更新解析任务，再通过 `enqueue_parse_task` 将任务提交给 Celery worker，返回 `parse_task_id` 与 `queue_task_id`，由后台任务继续执行索引。

### 4.2.3 RAG-Anything 主链入库流程

当管理端或环境变量选择 `RAG_ENGINE=raganything` 且依赖可用时，系统通过 `RAGAnythingAdapter` 执行增强入库。适配器会按班级维护独立的 RAG-Anything 工作目录，路径分别为 `RAGANYTHING_WORKING_DIR/{class_id}` 与 `RAGANYTHING_OUTPUT_DIR/{class_id}`。这种按班级隔离目录的方式可以避免不同课程或班级的索引文件混淆，也便于后续按课程重建知识库。

RAG-Anything 实例初始化时，系统构造 `RAGAnythingConfig`，主要配置包括 `parser`、`parse_method`、`max_concurrent_files`、`working_dir` 和 `parser_output_dir`。本项目默认 `RAGANYTHING_PARSER=mineru`，`RAGANYTHING_PARSE_METHOD=auto`，`RAGANYTHING_MAX_CONCURRENT_FILES=1`。其中 MinerU 用于多模态文档解析，`auto` 模式用于根据文件类型自动选择解析策略。若系统配置了 `LIBREOFFICE_PATH`，适配器会将 LibreOffice 路径写入环境变量，用于支持 Office 文档转换。

在模型函数注入方面，`RAGAnythingAdapter` 向 RAG-Anything 注入三类函数：生成模型函数、嵌入函数和视觉模型函数。生成模型函数通过 OpenAI-compatible Chat Completions 或 Responses API 调用大语言模型，用于文本生成与知识抽取；嵌入函数使用 LightRAG 的 `openai_embed` 适配器，并结合 `EMBEDDING_MODEL` 与 `EMBEDDING_DIM` 完成向量化；视觉模型函数通过 OpenAI-compatible VLM 接口处理图片附件或视觉内容。若模型路由判定生成或嵌入后端为 `mock`，适配器会拒绝初始化 RAG-Anything 主链，因为 RAG-Anything 原生索引需要真实生成模型和嵌入模型支持。

资料入库时，系统调用 RAG-Anything 的 `process_document_complete`，传入原始文件路径、输出目录、解析方式、文档 ID 和文件名。处理完成后，系统读取 `get_document_processing_status` 返回的状态，并依据 `text_processed`、`multimodal_processed` 和 `fully_processed` 生成质量标签。质量等级包括 `complete`、`partial`、`text_only`、`multimodal_only` 和 `failed`。当文本处理成功但多模态处理未完全成功时，系统仍允许资料进入可检索状态，同时在 `Material.kb_error` 中记录“文本索引成功但多模态处理未完全完成”的提示。这种设计使系统能够在多模态依赖不稳定时最大限度利用已成功处理的文本知识，同时保留处理质量信息，便于后续实验切片分析。

### 4.2.4 解析结果结构化落库设计

解析完成后的核心数据落点是 `FileParseTask`。该表保存解析器名称、任务状态、摘要、提取文本、分块结果、扩展元数据和错误信息。对于文本分块，系统将结果保存为 `chunks`，每个分块包含 `chunk_id`、`text`、`page`、`source_name` 和 `source_type` 等字段。该结构直接服务于后续检索召回和引用展示。

除文本分块外，系统还设计了统一多模态内容项 `content_items`。在本地回退解析器中，`SimpleParserProvider` 会识别文本、Markdown 表格、CSV 表格、公式模式和图片文件，并生成 `text`、`table`、`equation`、`figure` 等内容项。RAG-Anything 主链也可能返回不同格式的多模态元素。为了让下游模块稳定读取，系统在索引成功后调用 `_normalize_task_content_items` 将不同来源的内容项归一化为 `content_items_schema=v1`。

归一化后的内容项字段包括 `item_id`、`modality`、`raw_type`、`text`、`source_name`、`source_type`、`page`、`score`、`bbox`、`layout_type`、`doc_id`、`chunk_id`、`table_html`、`table_markdown`、`formula_latex`、`image_path`、`ocr_text`、`timestamp_start`、`timestamp_end` 和 `meta`。其中 `modality` 支持 `text`、`table`、`formula`、`image`、`audio`、`video` 和 `code` 等类型，并通过别名映射将 `equation`、`math`、`latex` 归一为 `formula`，将 `figure`、`diagram`、`chart`、`photo`、`screenshot` 归一为 `image`，将 `dataframe`、`csv`、`spreadsheet` 归一为 `table`。这种 schema 设计为后续多模态检索、图谱构建和前端文件分析提供了统一接口。

### 4.2.5 知识库状态管理、重试与告警机制

系统使用 `KBSpace` 表示课程或班级知识空间。该表保存 `course_id`、`class_id`、`status`、`document_count`、`chunk_count` 和 `last_built_at` 等字段。每次资料解析完成后，系统统计已完成解析任务数量和总分块数量，并更新知识空间状态。当至少有资料完成索引时，知识空间状态可更新为 `ready`；当解析失败时，则记录为 `failed`。

为了提高知识库构建稳定性，系统在 `kb_service.ingest_material_with_retry` 中实现重试机制。最大重试次数由 `KB_PARSE_MAX_RETRIES` 控制，默认值为 2。每次尝试开始和结束都会写入 `FileParseTask.extra_data.ingest.history`，同时记录 `attempt_count`、`max_attempts`、`retry_available`、`last_error_category`、`queue_task_id`、`queue_status`、`auto_retry_round` 和 `next_retry_after` 等字段。失败类别按照错误信息粗分为 `timeout`、`upstream`、`parser`、`permission` 和 `unknown`。这些字段不仅用于接口返回，也用于管理端队列监控和实验分析。

系统还提供索引任务管理接口，包括课程级任务列表、单文件重试、管理员全局任务列表、队列状态查询、失败任务批量重试和队列指标聚合。当失败任务达到最大尝试次数或自动重试轮次耗尽时，系统会通过 `Notification` 向管理员发送告警，告警 payload 中包含任务 ID、课程 ID、班级 ID、资料 ID、失败原因、尝试次数、队列状态和触发时间等信息。由此，资料入库从“后台黑盒过程”转变为可查询、可重试、可告警的任务化流程。

## 4.3 多模态资料解析与 RAG-Anything 双图机制适配

### 4.3.1 RAG-Anything 框架中的双图思想

RAG-Anything 是香港大学等团队提出的 All-in-One 多模态 RAG 框架，其核心思想是将现代文档中的文本、图片、表格、公式等异构元素视为相互关联的知识单元，而不是先全部压缩为纯文本再做检索。根据其论文与官方开源项目说明，RAG-Anything 在 LightRAG 的基础上扩展了多模态文档处理能力，通过文档解析、模态感知内容处理、知识图谱构建和跨模态混合检索来完成复杂文档问答。

在论文表述中，可以将 RAG-Anything 的“两类图”概括为文本知识图与多模态跨模态图。文本知识图继承 LightRAG 的图增强 RAG 思路，主要围绕文本实体、文本关系和语义块构建结构化索引，用于支持局部概念检索和全局主题检索。多模态跨模态图则面向图像、表格、公式、版面元素等非纯文本对象，记录不同模态内容之间的上下文位置、语义关联和来源关系，使系统能够在回答问题时同时利用文本语义相似度和跨模态结构导航。二者结合后，RAG-Anything 不只是做普通向量检索，而是把语义相似、文档结构、模态关系和知识图连接起来进行混合检索。

本系统并未直接复现 RAG-Anything 论文中的所有底层算法，而是通过 `RAGAnythingAdapter` 将其作为增强型主链接入后端业务系统，并在本地数据库中维护课程资料、解析状态、content items、课程知识图谱原型和引用信息。这样既能利用 RAG-Anything 对多模态复杂文档的处理能力，又能保证毕设系统的业务闭环、权限控制、任务观测和论文实验可控。

### 4.3.2 多模态内容分流与统一表示

在 RAG-Anything 的思想下，文档解析后的内容不应只保存为一段长文本，而应按模态和结构分解为原子内容项。例如，课件中的正文段落、公式、图片说明、表格行列、流程图说明都可能成为独立证据单元。本文系统用 `content_items v1` 作为这一思想在后端落库中的实现。文本、表格、公式和图片都可以用统一 schema 表达，同时保留各自特有字段，例如表格保留 `table_markdown`，公式保留 `formula_latex`，图片保留 `image_path` 和 `ocr_text`，音视频预留时间片字段。

在当前可运行实现中，本地解析器主要对文本类文件、Markdown 表格、CSV 表格、公式表达式和图片文件进行基础识别；RAG-Anything 主链则可在依赖完整时通过 MinerU 等解析器处理 PDF、Office 文档、图片及其版面结构。系统通过 `raganything_quality` 记录每份资料的处理质量，因此即便多模态处理部分失败，仍可明确区分“文本可用但多模态未完全可用”的状态。这种质量标注对论文实验很重要，因为后续可按 `complete`、`partial`、`text_only` 等类别分析问答效果差异。

### 4.3.3 音视频资料处理能力边界

课程资源中常见的音视频资料通常需要 ASR 转写、关键帧抽取、OCR、VLM 图像描述和时间片索引等步骤。结合当前项目代码，系统已经在配置层支持 VLM 路由，在 content items schema 中预留 `audio`、`video`、`timestamp_start` 和 `timestamp_end` 字段，也在 API 契约中规划了 transcript、keyframe 和 OCR 等扩展接口。但当前已稳定实现的核心仍是文档型资料、图片附件和表格/公式基础识别，音视频深度解析属于后续增强方向。

因此，论文中应将本系统表述为“具备多模态资料处理的架构基础和文档型多模态原型能力”，而不宜写成“已经完成成熟复杂音视频理解”。这种表述既符合代码事实，也能体现系统预留的扩展方向。

## 4.4 课程知识图谱原型构建与动态更新

### 4.4.1 知识实体与关系数据模型

课程知识图谱用于组织课程知识点之间的关联，并辅助资料可视化与检索增强。系统在数据库中使用 `KnowledgeEntity` 表表示实体，使用 `KnowledgeRelation` 表表示实体关系。实体字段包括 `name`、`entity_type`、`description`、`source_material_id`、`confidence`、`source_span`、`provenance`、`status`、`reviewed_by` 和 `reviewed_at`。关系字段包括 `source_id`、`target_id`、`relation_type`、`weight`、`confidence`、`source_span` 和 `provenance`。

其中，`confidence` 表示实体或关系的可信程度；`source_span` 保存来源页码、分块编号、来源文件名和模态类型等证据锚点；`provenance` 保存来源资料 ID 列表、首次出现时间、最近出现时间和出现次数。这些字段使知识图谱不只是概念网络，也具备可追溯性。前端或接口返回图谱时，节点和边都会带出置信度与 provenance，便于教师查看某个知识点来自哪些资料。

### 4.4.2 知识抽取与图谱构建流程

当前系统采用启发式关键词方式构建课程知识图谱原型。资料解析完成后，解析器基于文件名和正文内容抽取关键词；系统对关键词去重、归一化并选择前若干个高频项作为知识实体。随后系统将相邻关键词之间建立 `co_occurs_with` 关系，用于表示这些知识点在同一资料中共现。

当新资料入库时，系统不会简单覆盖旧实体，而是执行增量合并。如果实体首次出现，则创建新 `KnowledgeEntity`，写入来源资料、置信度、source span 和 provenance；如果实体已存在，则更新 `source_material_id`，合并来源页码、分块编号、来源名称和模态类型，并更新 `provenance.source_material_ids`、`last_seen_at` 和 `occurrence_count`。关系更新也采用类似策略：重复出现的关系会提高 `weight`，并融合新的来源信息。

这种图谱构建方式的优势是可解释、可运行、便于和课程资料绑定；不足是语义关系类型仍较粗，主要体现为关键词共现而非复杂语义抽取。因此论文中应使用“课程知识图谱原型”或“课程知识关联结构”表述，而不应夸大为成熟高质量自动知识图谱。

### 4.4.3 图谱辅助检索策略

系统在本地回退检索路径中实现了图谱辅助检索策略。检索策略由 `RAG_RETRIEVAL_STRATEGY` 控制，支持 `lexical`、`hybrid` 和 `graph` 三种模式。`lexical` 模式主要依据问题词项与分块文本的重合度；`graph` 模式优先利用命中的知识实体扩展相关词项；`hybrid` 模式同时考虑词项重合、图谱扩展和查询变体覆盖度，是当前默认策略。

具体流程为：系统先对用户问题提取词项，再在 `KnowledgeEntity` 中查找实体名称是否与问题词项重合；若命中实体，则将该实体词项作为图谱增强词。候选分块打分时，系统计算 `lexical_score`、`graph_boost`、`query_coverage` 和 `query_coverage_boost`，再合成为 `retrieval_score`。若开启查询改写，系统还会生成多个查询变体，分别检索并合并命中的分块，记录 `matched_query_count` 和 `query_hits`。该策略使课程知识图谱能够参与 RAG 证据召回，而不只是前端展示图。

### 4.4.4 动态知识更新机制

系统的动态知识更新主要来自两类事件：课程资料更新和教师审核回流。教师上传或重建课程资料时，系统重新执行解析、分块、content items 归一化、知识实体同步和知识空间统计更新。由于图谱实体与关系采用 provenance 合并策略，新资料会增量补充现有知识结构。

教师审核回流发生在低置信回答或学生点踩之后。教师提交修正答案后，系统创建 `ReviewSyncRecord` 并调用当前 RAG 引擎的 `add_qa_pair`。在 RAG-Anything 路径中，人工问答会通过 `insert_content_list` 插入主链索引；同时本地回退链也会把人工问答保存到 `KBSpace.extra_data.manual_qa`。后续类似问题进入本地回退路径时，系统会从已同步的审核记录中检索相似问答，并将教师修正答案作为优先上下文。由此，用户反馈不是只停留在界面状态，而是能够进入知识服务链路。

## 4.5 检索增强问答模块设计与实现

### 4.5.1 问答模块总体处理流程

问答模块的后端入口为 `POST /api/v1/chat/query` 和 `POST /api/v1/chat/query-with-image`，核心处理逻辑位于 `chat_service.send_message`。系统首先根据 `course_id` 或 `class_id` 确定班级上下文，然后创建或获取 `ChatSession`，保存用户消息，并将提问行为记录到学习分析表。接着系统读取最近 10 条历史消息组成对话上下文，并从管理端持久化配置中读取当前模型和 RAG 引擎设置。

问答主流程可概括为：接收问题与附件，保存用户消息，组装历史上下文，选择 RAG 引擎，构建模型路由快照，执行 RAG 查询，记录 RAGQueryEvent，保存 AI 消息与 citation，根据置信度判断是否触发教师审核，最后返回回答、来源、建议追问、置信度和审核标记。该流程将“生成回答”和“业务闭环”连接起来，使一次提问既产生回答，也产生可观测数据、引用数据和可能的审核数据。

### 4.5.2 模型路由与生成模型选择

系统通过 `model_routing_service.py` 统一管理生成模型、嵌入模型、视觉模型和重排序模型的运行后端。生成模型支持 `LLM_BACKEND=auto|api|local|mock`，嵌入模型支持 `EMBEDDING_BACKEND=auto|api|local|mock`，视觉模型支持 `VLM_BACKEND=auto|api|local|mock`，重排序器支持 `RERANKER_PROVIDER=mock|none|api|local`。管理端 `GET /admin/model-routing` 可返回每种能力的 `requested_backend`、`effective_backend`、`provider`、`model`、`api_base`、`api_key_configured` 和 `fallback_reason`。

这种设计允许系统在不同环境下切换模型来源。若部署环境有外部模型 API，可将 LLM、Embedding 和 VLM 路由到 API；若有本地模型服务，可将后端设为 `local` 并填写本地 OpenAI-compatible 地址；若缺少模型服务，系统可退回 `mock`，保持功能演示与测试可运行。RAG-Anything 主链要求生成和嵌入模型不能为 mock，因此在模型配置不足时系统会自动回退到 SimpleRAGEngine。

### 4.5.3 RAG-Anything 主链查询

在 RAG-Anything 可用时，系统优先调用其原生查询能力。若用户上传了图像附件，适配器优先尝试视觉描述并调用 `aquery_with_multimodal`；普通文本问题优先调用 `aquery`；若当前版本只提供同步方法，则兼容调用 `query`。查询模式由 `RAGANYTHING_QUERY_MODE` 控制，默认值为 `mix`，可根据依赖版本兼容传入 `mode` 或 `query_mode` 参数。

由于不同 RAG-Anything 版本可能返回字符串、字典、列表或对象，适配器实现了统一归一化逻辑，将原始结果转换为 `answer`、`sources` 和 `confidence`。来源字段统一为 `name`、`page`、`type`、`score`、`chunk_id` 等，使主链和回退链在 API 层保持一致。若主链初始化失败、查询异常或返回空答案，系统会记录 fallback 原因并进入本地回退路径。

### 4.5.4 查询改写、多路召回与候选合并

为提高检索召回率，系统实现了查询改写与多查询合并能力。配置项 `RAG_QUERY_REWRITE_ENABLED` 控制是否启用，`RAG_QUERY_REWRITE_MODE` 支持 `none`、`simple`、`compact` 和 `keywords`，`RAG_QUERY_REWRITE_MAX_VARIANTS` 控制最大变体数量。查询改写工具会根据原问题生成一个或多个查询变体，例如保留原问题、提取关键词或生成更紧凑的问题表达。

在本地回退链中，系统对每个查询变体分别检索课程分块，再按 `chunk_id`、来源名、页码和片段内容进行去重合并。合并后的候选记录会保存命中的查询变体数量和覆盖情况。候选打分时，命中多个查询变体的分块会获得一定覆盖度加分。该机制适合处理学生问题表述不规范、术语与资料表达不一致的场景。

### 4.5.5 重排序与证据组织

候选分块进入答案生成前需要重排序。系统将重排序器抽象为统一 provider，支持 `mock`、`none`、`api` 和 `local`。`none` 表示不改变原始顺序；`mock` 使用确定性启发式分数；`api` 可调用外部 rerank 服务，并兼容 `scores`、`results`、`data` 等多种返回格式；`local` 优先尝试加载 `sentence_transformers.CrossEncoder`，若依赖或模型不可用，则退回本地启发式评分。

重排后系统选择 `RAG_ANSWER_TOP_K` 个证据片段，默认值为 3。证据组织时保留来源文件名、页码、资料类型、分块编号、检索分数和重排分数。若存在教师审核回流答案，系统会将教师修正内容作为高优先级上下文；若存在图片附件理解结果，则将图片上下文加入证据拼接。最终，系统在提示中要求生成模型优先依据课程证据回答，若证据不足则说明不确定性。

### 4.5.6 答案生成、引用落库与置信度输出

答案生成阶段根据模型路由决定执行方式。当生成后端为 `api` 或 `local` 时，系统通过 OpenAI-compatible 接口或 Responses API 调用大语言模型，并传入课程证据、教师修正答案、图片上下文、历史消息和角色化提示。学生端提示强调耐心解释、定义和示例；教师端提示强调结构化、简洁和教学可用性。当生成后端为 `mock` 时，系统返回基于已检索证据的规则化摘要，保证没有外部 API 时也能完成演示。

系统将 AI 回答保存为 `ChatMessage`，将来源保存为 `ChatCitation`。每条 citation 包括 `source_name`、`source_type`、`page`、`score`、`chunk_id` 和原始 source 数据。接口响应中返回 `sources`、`suggestions`、`confidence` 和 `needs_review`，前端可展示引用溯源并允许学生点赞或点踩。

置信度主要依据主链返回值或重排后 top 证据分数估计。系统设置 `CONFIDENCE_THRESHOLD=0.7`，当回答置信度低于阈值时自动生成审核项。需要说明的是，该置信度是工程层面的可信度估计，不等同于严格概率校准结果。论文可将其表述为“用于触发人工审核的回答质量启发式指标”。

### 4.5.7 问答可观测与实验指标记录

系统每次问答都会写入 `RAGQueryEvent`。记录字段包括 RAG 引擎、查询模式、查询方法、是否使用多模态、是否使用 fallback、fallback 原因、是否成功、时延、置信度、来源数量和扩展数据。扩展数据中记录检索策略、reranker provider、候选数量、选中数量、图谱词数量、查询改写模式、查询变体数量以及 LLM、Embedding、VLM、Reranker 的路由后端。

管理端基于这些事件提供 RAG 性能接口、查询改写消融接口、个性化路由指标接口和实验结果快照接口。离线 benchmark 脚本还支持按 benchmark spec 计算 Recall@k、nDCG@k 和 MRR，并支持与历史报告进行 baseline 对比。这些功能为第五章系统测试与结果分析提供可复现的数据来源。

## 4.6 教师审核与知识回流模块设计与实现

### 4.6.1 审核触发机制

教师审核模块用于解决 AI 回答可能存在的不确定性和错误问题。系统支持两类审核触发方式：第一，低置信自动触发，即当 AI 回答 `confidence < 0.7` 时，系统创建 `ReviewItem`，触发原因为 `low_confidence`；第二，用户反馈触发，即学生对回答点踩并提交原因时，系统将消息标记为 `needs_review=True`，并创建触发原因为 `dislike` 的审核项。

`ReviewItem` 记录学生 ID、班级 ID、原问题、AI 回答、触发原因、教师答案、处理状态、审核教师和审核时间。教师端可以查看待处理审核项，判断 AI 回答是否需要修正、补充或驳回。

### 4.6.2 教师修正答案提交与状态流转

教师提交修正答案后，系统更新审核项状态为 `resolved`，写入 `teacher_answer`、`reviewed_by` 和 `reviewed_at`。同时，系统创建 `ReviewSyncRecord`，记录问题、最终答案、同步状态和同步说明。同步状态包括 `pending`、`synced` 和 `failed`，用于追踪教师修正是否成功进入知识库。

如果教师选择不加入知识库，则同步记录保持 pending，并说明同步被教师跳过；如果教师选择加入知识库，系统调用当前 RAG 引擎的 `add_qa_pair`。调用成功后，`ReviewSyncRecord.sync_status` 更新为 `synced`，并记录同步时间；调用失败则记录为 `failed` 并保存错误信息。

### 4.6.3 知识回流对后续问答的影响

知识回流的目标不是修改大模型参数，而是把教师确认后的问答内容加入可检索知识源。对于 RAG-Anything 主链，系统将人工问答作为文本内容插入 RAG-Anything 索引；对于本地回退链，系统将人工问答加入 `KBSpace.extra_data.manual_qa`，并在后续本地查询中检索已同步的 `ReviewSyncRecord`。当学生再次提出相似问题时，教师修正答案会作为优先上下文进入回答生成。

这种机制实现了用户反馈驱动的迭代优化，但其优化对象是知识库内容和检索上下文，而不是 LLM 参数。因此，论文中应表述为“基于反馈与教师审核的知识回流优化机制”，不应写成“模型自动在线训练”。后续若需要进一步提升模型性能，可将审核数据导出为微调数据或偏好优化数据，作为未来工作。

## 4.7 学习分析与个性化支持模块设计与实现

### 4.7.1 学习行为记录与学生画像

学习分析模块以学习行为记录为基础。系统通过 `LearningRecord` 保存学生查看资料、提交任务、提问、点踩等行为，通过 `StudentProfile` 保存学生偏好课程、强项主题、薄弱主题、提问总数、点踩次数、任务完成率、活跃度和最近活跃时间等画像字段。问答时，系统会记录 `ask_question` 行为；学生点踩时，会记录 `message_dislike` 行为。这些数据用于构建学生学习状态和后续推荐依据。

### 4.7.2 错题本与闪卡复习

系统通过 `StudyMistake` 支持错题本功能，保存题目、章节、学生答案、正确答案、解析、错误次数、掌握状态和最近练习时间。闪卡功能通过 `Flashcard` 和 `FlashcardRecord` 实现，保存问题、答案、来源资料、标签、难度系数、复习间隔、下次复习时间、复习次数和每次复习评分。闪卡复习机制采用间隔复习思想，根据学生反馈调整后续复习计划。

这些功能把 AI 助教从即时问答扩展到持续学习支持。学生不仅能得到当前问题的答案，还能将薄弱知识沉淀为错题和闪卡，通过持续复习巩固知识点。

### 4.7.3 个性化推荐与学习报告

当前系统的个性化推荐采用规则驱动方式，主要依据学生近期提问、薄弱知识点、错题内容、资料标题、文件名、解析关键词和课程图谱实体进行匹配。该方式相比复杂推荐模型更易解释，适合当前原型阶段。学生端可展示个性化推荐资料、学习周报、月报和学习建议；教师端可查看班级学情、预警学生、高频错题和教学建议。

系统还将模型路由信息加入学习报告上下文，使实验阶段能够按照 LLM、Embedding、VLM 和 Reranker 的后端组合分析不同模型配置对推荐与问答效果的影响。管理端 `personalization-routing-metrics` 接口可统计不同路由切片下的查询数、用户数、成功率、fallback 率、平均置信度、来源数量、平均时延、活跃度和学习事件数等指标。

## 4.8 前后端交互与可视化实现

### 4.8.1 学生端课程页与 AI 助教组件

学生端主要位于 `frontend/src/pages/student-course`。课程页包含课程资料、AI 助教、任务中心、错题本、闪卡、互动空间和学习报告等模块。学生版 AI 助教组件支持多轮对话、附件上传、图片预览、文件类型识别、快捷提问、回答引用展示、点赞点踩和个性化推荐。引用展示区域会列出来源文件名、页码和资料类型，使学生能够追溯回答依据。

### 4.8.2 教师端课程管理与教师 AI 助教

教师端主要位于 `frontend/src/pages/teacher-course`。教师可上传课程资料、查看资料解析状态、管理任务、查看学生问题、处理 AI 低置信回答、查看课程知识图谱和使用教师版 AI 助教。教师版 AI 助教侧重生成教案、试卷、学情分析和教学建议，并展示学生反馈列表。当前前端部分页面仍包含原型化示例数据，但后端已经提供资料上传、问答、审核、RAG 性能、模型配置和实验结果等真实接口，可逐步替换模拟数据。

### 4.8.3 管理端监控与模型配置

管理端后端接口包括用户管理、课程管理、审核管理、模型配置、模型路由、索引任务监控、队列指标、RAG 性能、查询改写消融、个性化路由指标和实验结果导出。模型配置接口允许管理员更新 `llm_provider`、`llm_model`、`llm_backend`、`embedding_model`、`embedding_backend`、`vlm_model`、`vlm_backend`、`reranker_provider`、`reranker_model` 和 `rag_engine` 等字段。系统在运行时读取这些持久化配置，使实验切换不必改动代码。

## 4.9 本章小结

本章围绕 AI 助教平台关键模块的设计与实现进行了说明。系统以 FastAPI、React、SQLAlchemy、Celery、Redis、本地/MinIO 存储和 RAG-Anything 为基础，形成了课程资料上传、解析索引、content items 归一化、课程知识图谱原型、RAG 问答、引用展示、低置信审核、教师知识回流、学习分析和实验评估的完整闭环。

在知识库构建方面，系统通过 `Material`、`FileParseTask` 和 `KBSpace` 管理资料生命周期，并结合 RAG-Anything 的 MinerU 解析、多模态状态标签和本地回退解析保证资料可入库、可查询、可重试。在问答方面，系统支持 RAG-Anything 主链、本地 fallback、查询改写、多路召回、图谱辅助检索、重排序、模型路由和引用落库。在持续优化方面，系统通过低置信审核、点踩反馈和教师修正答案回流实现知识库层面的迭代改进，并通过 RAGQueryEvent、管理端指标和离线 benchmark 为系统评估提供数据基础。

需要强调的是，当前系统定位为毕设阶段的可运行原型。课程知识图谱属于基于关键词共现和来源锚点的原型实现，多模态能力以文档型资料和基础图片/表格/公式处理为主，个性化推荐以规则驱动为主，反馈优化主要体现为知识回流而非模型参数在线训练。这样的边界表述能够保证论文内容与代码实现一致，同时为后续系统扩展留下明确方向。

