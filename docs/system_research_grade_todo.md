# AI助教系统后端完整待办清单（后端先行版）

更新时间：2026-04-17  
适用范围：仅后端研发阶段（前后端联调后置）

---

## 1. 对齐性检查结论

先给结论：你之前的 TODO 方向正确，但还不够完整。

已对齐的点：

- 后端优先、联调后置。
- 聚焦 RAG-Anything 主链、多模态、知识图谱、模型路由。
- 关注评测与可复现。

仍需补齐的点（你给的技术文档里是硬性要求）：

1. 必须补齐的模块清单未完全展开（`roles_permissions`、`feedback_analysis`、`recommendations`、`multimodal` 等）。  
2. 必须实现 API 列表未逐项落地到任务（尤其反馈分析、推荐、多模态、管理端性能接口）。  
3. 数据库实体要求未逐表映射到改造任务。  
4. 交付文档清单（`frontend_api_analysis.md`、`backend_implementation_plan.md`、`backend_architecture.md`、`api_contract.md`、`rag_integration.md`、`experiment_report.md`）未纳入强约束任务。  
5. 每项“怎么做、实现什么效果”不够细，执行时容易走偏。  

下面是对齐你技术文档后的完整执行清单。

---

## 2. 执行原则（必须遵守）

1. 当前阶段只做后端，不改前端业务页面。  
2. 所有模块围绕主闭环：知识库构建 → AI问答溯源 → 审核回流 → 学情优化。  
3. 先做可运行能力，再做增强；遇阻塞必须有 fallback。  
4. 每阶段结束必须有最小验证（接口可调、测试可跑、日志可追踪）。  
5. 所有变更同步记录到 `docs/backend_execution_progress_log.md`。  

---

## 3. 完整待办清单（做什么 / 怎么做 / 实现效果）

状态说明：`未开始` / `进行中` / `已完成`

### Phase 0：基线校正与文档恢复

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 恢复并更新必需文档到 `docs/` | 将 `rubbish/` 中历史文档迁回 `docs/`，并按现代码更新内容 | 达到交付清单要求，后续研发有统一规范入口 |
| 未开始 | 固化后端实施计划 | 更新 `docs/backend_implementation_plan.md`，对齐 Phase0-6 | 阶段目标可执行、可验收 |
| 未开始 | 固化 API 契约文档 | 更新 `docs/api_contract.md`，逐接口补 request/response/error | 后续联调可直接按契约开发 |
| 未开始 | 新建 RAG 集成文档 | 新建 `docs/rag_integration.md`，写清配置、流程、降级策略 | RAG-Anything 上线路径清晰可复现 |
| 未开始 | 新建实验评估文档 | 新建 `docs/experiment_report.md` 模板，定义指标和对比方案 | 科研实验有统一记录模板 |

### Phase 1：数据模型与迁移补齐

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 权限模型补齐 | 增加 `roles`、`user_roles`，兼容现有 `users.role`（迁移期双轨） | 教师/学生/管理端权限边界可扩展 |
| 未开始 | 课程结构补齐 | 增加 `course_chapters`，关联资料与知识点 | 学情分析、知识盲区定位更细粒度 |
| 未开始 | 反馈模型补齐 | 增加 `message_feedback`、`feedback_reasons`、`feedback_statistics` | 点踩原因可结构化统计与分析 |
| 未开始 | 推荐模型补齐 | 增加 `recommendations`、`recommendation_feedback`、`user_interactions` | 推荐效果可落库、可迭代 |
| 未开始 | 多模态结果表补齐 | 增加 `file_parse_results`、`video_transcripts`、`image_ocr_results` | 多模态解析结果可检索、可追溯 |
| 未开始 | Alembic 迁移整理 | 追加迁移脚本并做历史迁移回放测试 | 数据库升级可控，无破坏性变更 |
| 未开始 | 种子数据增强 | 增加管理员/教师/学生 + 推荐/反馈/多模态样例数据 | 本地一键可验证全链路 |

### Phase 2：路由与服务边界补齐（按导航树映射）

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 路由分组标准化 | 按 `auth/users/courses/classes/kb/chat/reviews/...` 统一整理 | 接口职责清晰，便于后续联调 |
| 未开始 | 互动空间接口补齐 | 增补 `interactions` 服务与 API（帖子、回复、点赞、置顶） | 教师端/学生端互动能力后端完整 |
| 未开始 | 反馈分析接口补齐 | 增加 `/api/v1/analytics/feedback/*` 全套接口 | 可直接支撑反馈看板与盲区分析 |
| 未开始 | 推荐接口补齐 | 增加 `/api/v1/recommendations/materials`、`/learning-path`、`/feedback` | 推荐与学习路径后端闭环形成 |
| 未开始 | 多模态预览接口补齐 | 增加 `/api/v1/files/{id}/transcript`、`/keyframes`、`/ocr` | 文件预览与多模态结果可查询 |
| 未开始 | 管理端性能接口补齐 | 增加 `/api/v1/admin/rag-performance`、`/experiment-results` | 管理端可查看RAG与实验状态 |

### Phase 3：AI编排层落地（不是仅 chat service）

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 构建 AI Orchestrator | 新建 `ai_orchestrator` 服务：问题分类、上下文注入、工具路由 | 问答不再是单函数拼装，具可扩展编排能力 |
| 未开始 | 角色上下文注入 | 按教师/学生注入不同 system prompt 与策略 | 回答风格与内容更符合角色场景 |
| 未开始 | 课程上下文注入 | 强制带 `course_id/class_id/session` 上下文 | 回答可控，减少跨课程幻觉 |
| 未开始 | 置信度评估标准化 | 定义置信度计算与阈值策略，持久化评分来源 | 审核触发可解释、可调优 |
| 未开始 | 追问建议生成升级 | 基于检索结果和用户历史生成 follow-up | 追问建议更贴合课程知识路径 |
| 未开始 | 资料推送策略接入 | 在回答后返回相关推荐资料 | 支撑“答疑+资料推送”闭环 |

### Phase 4：RAG-Anything 主链彻底落实

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 查询主链替换 | `RAGAnythingAdapter.query` 优先走 `aquery/aquery_with_multimodal` | 真正使用 RAG-Anything 检索而非仅词匹配 |
| 未开始 | 查询模式生效 | 接入 `RAGANYTHING_QUERY_MODE` 并在日志中输出 | 可按场景切换 local/global/hybrid/mix |
| 未开始 | 证据统一结构 | 统一 citation 输出字段（source/page/chunk/score/doc_id） | 溯源结果标准化，易于前端展示 |
| 未开始 | 审核回流写入主检索 | 教师补答同步写回 RAG 可检索路径 + DB 追踪表 | 反馈真正驱动知识库迭代 |
| 未开始 | fallback 策略降级化 | 仅在主链异常时启用 simple engine，记录触发原因 | 系统稳定且主链效果可监控 |

### Phase 5：多模态解析与知识图谱增强

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 统一内容表示层 | 建立 `ContentItem(type, content, metadata, embedding)` | 文本/图像/表格/转录统一入检索 |
| 未开始 | PDF 多模态解析增强 | 接入 OCR、表格、版面块提取并结构化落库 | 图文混排资料可被正确检索 |
| 未开始 | 视频解析链路 | 关键帧提取 + ASR 转录 + 时间戳落库 | 支持视频资料问答溯源 |
| 未开始 | 音频解析链路 | ASR 转写 + 说话段落标记 | 支持音频资料问答 |
| 未开始 | PPT 解析链路 | 幻灯片拆分、标题正文结构化 | 课件内容可按页溯源 |
| 未开始 | 实体关系抽取质量化 | 增加 `confidence/source_span/provenance` 字段 | 知识图谱可审计、可验证 |
| 未开始 | 图谱审核流 | 增加实体审核接口与状态流转 | 图谱质量可人工把关 |

### Phase 6：反馈分析、推荐系统、个性化学习

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 点踩原因统计 | 对 `feedback_reasons` 按课程/章节聚合 | 明确模型薄弱点 |
| 未开始 | 知识盲区识别 | 用点踩+低置信+高频问题生成 `knowledge_gaps` | 可指导资料补充与教案优化 |
| 未开始 | 优化建议生成 | 输出“资料补充建议 + 模型优化建议”接口 | 管理端可直接查看改进方向 |
| 未开始 | 推荐引擎实现 | 候选召回（资料/任务/闪卡）+ 排序（行为+画像+掌握度） | 推荐不再静态，形成个性化 |
| 未开始 | 学习路径推荐 | 生成周计划、章节优先级、下一步建议 | 支撑学生端学习空间闭环 |
| 未开始 | 推荐反馈回流 | 记录“不感兴趣/点击/完成”并更新策略 | 推荐可持续优化 |

### Phase 7：模型能力层与双轨部署

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | Provider 抽象补齐 | 完成 `LLM/VLM/Embedding/Reranker/ASR/Parser/BaseRAGEngine` 基类 | 模型替换不改业务主逻辑 |
| 未开始 | Mock/Fallback 完整化 | 为各 provider 提供可运行 mock | 无 key 环境也可调试与测试 |
| 未开始 | API/本地双轨路由 | 配置支持 `api` 和 `local(vLLM等)` 两类后端 | 研究与部署可灵活切换 |
| 未开始 | 模型调用可观测 | 记录延迟、token、错误率、成本 | 可做性能/成本实验评估 |

### Phase 8：测试、验证与交付收尾

| 状态 | 做什么 | 怎么做 | 实现效果 |
|---|---|---|---|
| 未开始 | 单测扩展 | 覆盖权限边界、异常链路、并发、降级路径 | 避免回归破坏核心闭环 |
| 未开始 | 集成测试扩展 | 覆盖 8 个核心闭环（认证→知识库→问答→审核→推荐） | 后端全链路可持续验证 |
| 未开始 | RAG 评测脚本 | 输出 Recall@n、nDCG、引用可追溯率、响应耗时 | 实验结果可量化 |
| 未开始 | 管理端监控数据接口验证 | 验证 rag-performance/experiment-results 指标正确性 | 管理端可用作实验面板 |
| 未开始 | 交付清单核对 | 对照你文档第16节逐项打勾 | 满足毕设后端构建规范 |

---

## 4. 核心里程碑（后端先行）

### M1：后端主链稳定可运行

- 完成 Phase 0-3  
- 效果：核心 API 契约稳定，AI编排层形成，基础闭环稳态运行。

### M2：RAG 与多模态能力成型

- 完成 Phase 4-5  
- 效果：RAG-Anything 主链生效，多模态资料可解析可检索可溯源，图谱质量可控。

### M3：反馈优化与个性化能力成型

- 完成 Phase 6-7  
- 效果：反馈分析、推荐、学习路径、模型双轨均可运行并可观测。

### M4：科研评测与交付完备

- 完成 Phase 8  
- 效果：测试、评测、文档、交付物齐全，进入联调阶段风险低、返工少。

---

## 5. 当前最先要做的三件事（执行起点）

1. 先补文档基线：恢复并更新 `docs/api_contract.md`、`docs/backend_implementation_plan.md`、`docs/backend_architecture.md`、`docs/rag_integration.md`、`docs/experiment_report.md`。  
2. 立刻启动 RAG 主链替换：把 `RAGAnythingAdapter.query` 切到原生查询并接入 query mode。  
3. 同步推进数据模型补齐：优先补 `feedback/recommendation/multimodal` 相关表与迁移。  

---

## 6. 与你后端构建要求的一致性说明

本清单已对齐你文档中的关键硬性要求：

- 只做后端，联调后置。  
- 以“AI助教 + 知识溯源 + 审核回流 + 学情闭环”为核心主线。  
- 保留并强化 RAG-Anything + 多模态 + 知识图谱路线。  
- 保证“可运行 + 可验证 + 可扩展 + 可复现”的分阶段落地方式。  

