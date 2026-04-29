# 0428 后续研发与联调 TODO

更新时间：2026-04-28  
目标：保证系统顺利运行，前后端 live 联调成功，注册登录、班级空间、资料入库、AI 助教、审核回流、学生画像、个性化推荐、实验评估与部署验证形成完整闭环。

---

## 0. 当前定位

项目当前不应再按早期 `Phase 0` 理解。后端已经完成大量 RAG-Anything、索引任务、查询观测、模型路由、benchmark 等能力；前端也已完成服务层与 mock/live 双模式整理。

当前真实停滞点：

- 依赖环境未完全恢复，测试和构建尚未重新跑通。
- 前端默认仍是 `mock` 模式，live 模式未完成全链路验收。
- 真实 RAG-Anything 运行环境、模型配置、向量库/图谱库/异步任务栈需要验证。
- 核心闭环需要连续跑通：注册登录 -> 班级空间 -> 资料入库 -> RAG 问答 -> 点踩/低置信审核 -> 教师补答 -> 回流知识库 -> 再次检索命中。
- 学生画像、推荐、学习路径需要从可解释规则版落地，再逐步优化算法。

---

## 1. 阶段 0：环境恢复与基线验证

### 任务

- [ ] 安装后端依赖：`backend/requirements.txt`。
- [ ] 如需正式 RAG，安装：`backend/requirements-raganything.txt`。
- [ ] 确认 `pytest`、`uvicorn`、`alembic` 可用。
- [ ] 安装前端依赖：在 `frontend/` 执行 `npm install`。
- [ ] 跑后端测试：`python -m pytest backend/tests -q`。
- [ ] 跑前端类型检查：`npm run type-check`。
- [ ] 跑前端构建：`npm run build`。
- [ ] 初始化数据库，确认 Alembic migration 可执行。
- [ ] 执行 seed，确认管理员、教师、学生 demo 账号可用。
- [ ] 启动后端并检查 `/health`、`/health/ready`、`/docs`。

### 验收标准

- [ ] 后端测试通过。
- [ ] 前端类型检查和构建通过。
- [ ] Swagger 可访问。
- [ ] 三类 demo 账号存在并可登录。
- [ ] 记录当前环境、配置和测试结果。

---

## 2. 阶段 1：注册登录与角色会话闭环

### 任务

- [ ] 联调 `POST /api/v1/auth/login`。
- [ ] 兼容后端 `access_token` 与前端 `accessToken`。
- [ ] 登录后保存 token，并自动携带 `Authorization: Bearer <token>`。
- [ ] 联调 `GET /api/v1/auth/me`，刷新页面后恢复会话。
- [ ] 学生、教师、管理员登录后跳转不同 dashboard。
- [ ] 联调学生注册。
- [ ] 联调教师注册。
- [ ] 验证码接口可先保持 dev mock，但响应结构必须稳定。
- [ ] 如教师注册需要审核，管理员端应能看到待审核记录。
- [ ] 统一退出登录逻辑，清理本地 session。
- [ ] 完善路由守卫和角色权限：
  - [ ] 未登录不能访问业务页。
  - [ ] 学生不能访问教师页。
  - [ ] 教师不能访问管理员页。
  - [ ] 管理员进入管理端。

### 验收标准

- [ ] 三类角色均可登录。
- [ ] 刷新页面不丢会话。
- [ ] 退出登录正常。
- [ ] 错误账号密码有明确提示。
- [ ] 不同身份进入不同首页。
- [ ] 前端界面随身份变化展示不同功能入口。

---

## 3. 阶段 2：班级空间与课程空间闭环

### 关键约定

- `course`：知识库边界，关联资料、知识图谱、RAG 索引。
- `class`：教学组织边界，关联学生、邀请码、任务、讨论、成员。
- 前端页面中的 `courseId` 在多数课程空间场景中按 `classId` 使用。
- 后端 bootstrap 必须同时返回 `classId` 和 `courseId`。

### 任务

- [ ] 学生通过邀请码加入班级。
- [ ] 加入成功后学生 dashboard 课程列表刷新。
- [ ] 教师创建课程/班级。
- [ ] 教师生成邀请码。
- [ ] 学生加入后教师 dashboard 学生数变化。
- [ ] 学生课程空间联调：
  - [ ] 首页。
  - [ ] 资料列表。
  - [ ] 任务列表。
  - [ ] 互动区。
  - [ ] AI 助教。
  - [ ] 闪卡/学习空间。
- [ ] 教师课程空间联调：
  - [ ] 首页统计。
  - [ ] 资料管理。
  - [ ] 知识图谱。
  - [ ] 任务管理。
  - [ ] 学生管理。
  - [ ] 问答审核。
  - [ ] 教师 AI 助教。
- [ ] 管理员空间联调：
  - [ ] 用户列表。
  - [ ] 课程列表。
  - [ ] 班级列表。
  - [ ] 注册审核。
  - [ ] 模型配置。
  - [ ] RAG 状态。

### 验收标准

- [ ] 教师创建班级后，学生能通过邀请码加入。
- [ ] 学生加入后，学生 dashboard 出现该课程空间。
- [ ] 教师端学生数发生变化。
- [ ] 不同身份进入同一课程空间能看到不同操作入口。
- [ ] 空数据账号显示空状态，不显示 demo 假数据。

---

## 4. 阶段 3：前后端 live 模式全站联调

### 任务

- [ ] 开启前端 live 模式：
  - [ ] `VITE_API_MODE=live`
  - [ ] `VITE_API_BASE_URL=/api/v1`
  - [ ] Vite proxy 指向后端服务。
- [ ] 联调 dashboard：
  - [ ] `/student/dashboard`
  - [ ] `/teacher/dashboard`
  - [ ] `/admin/dashboard`
- [ ] 联调课程空间：
  - [ ] student course bootstrap。
  - [ ] teacher course bootstrap。
  - [ ] materials。
  - [ ] tasks。
  - [ ] discussions。
  - [ ] questions。
  - [ ] knowledge graph。
  - [ ] students。
- [ ] 联调 AI 服务：
  - [ ] 会话列表。
  - [ ] 消息列表。
  - [ ] 发送消息。
  - [ ] 点赞/点踩。
  - [ ] 反馈提交。
  - [ ] 教师审核列表。
  - [ ] 教师采纳/补答。
- [ ] 补齐或修正 `frontend_compat.py` 字段适配。
- [ ] 对缺失接口返回合理空结构，避免 500。
- [ ] 统一前端 loading、empty、error、success 状态。

### 验收标准

- [ ] 前端 live 模式可完整访问。
- [ ] 三个 dashboard 可用。
- [ ] 学生/教师课程页主要 tab 都能显示真实接口数据。
- [ ] 常用按钮点击后至少有真实接口响应或明确错误提示。
- [ ] 网络错误、空数据、权限错误都有前端状态变化。

---

## 5. 阶段 4：核心链路一：资料入库 + 后端处理 + 知识库状态

### 任务

- [ ] 教师端上传 PDF。
- [ ] 教师端上传 TXT/MD。
- [ ] 教师端上传 PPT。
- [ ] 教师端上传图片。
- [ ] 音频/视频先支持 transcript sidecar。
- [ ] 后端保存 `Material`。
- [ ] 后端创建 `FileParseTask`。
- [ ] 小文件支持同步索引。
- [ ] 大文件支持 Celery 异步索引。
- [ ] 上传接口返回 `parse_task_id`。
- [ ] 异步任务返回 `queue_task_id`。
- [ ] 资料列表展示状态：
  - [ ] pending。
  - [ ] processing。
  - [ ] completed。
  - [ ] failed。
- [ ] 文件分析页展示：
  - [ ] summary。
  - [ ] chunk count。
  - [ ] content_items。
  - [ ] content_items_schema。
  - [ ] raganything_status。
  - [ ] raganything_quality。
  - [ ] error reason。
- [ ] 单文件 retry。
- [ ] 管理端 batch retry。
- [ ] retry cooldown。
- [ ] max attempts。
- [ ] failure alert。
- [ ] 入库后生成知识图谱 entity/relation。
- [ ] 图谱节点/边展示 confidence/provenance/source_span。

### 验收标准

- [ ] 教师上传资料后状态能从处理中变为完成。
- [ ] 文件分析页可看到摘要、chunk、content items。
- [ ] 知识图谱有节点和边。
- [ ] 上传失败时有错误原因。
- [ ] 失败任务可以重试。
- [ ] 管理端能看到索引任务状态。

---

## 6. 阶段 5：核心链路二：学生端/教师端 AI 助教对话

### 任务

- [ ] 跑 `backend/scripts/check_raganything_runtime.py`。
- [ ] 配置真实 LLM。
- [ ] 配置真实 Embedding。
- [ ] 配置 VLM。
- [ ] 配置 Reranker。
- [ ] 确认 generation/embedding effective backend 不是 `mock`。
- [ ] 确认 RAG-Anything 可初始化。
- [ ] 学生端创建 AI 会话。
- [ ] 学生端发送课程相关问题。
- [ ] 请求带上 `class_id/course_id/session_id`。
- [ ] 后端基于课程知识库检索。
- [ ] 返回 answer、sources、confidence、suggestions。
- [ ] 前端展示引用来源。
- [ ] 教师端 AI 助教可提问。
- [ ] 教师端工具型功能可用：
  - [ ] 生成教案。
  - [ ] 生成试题。
  - [ ] 学情分析。
  - [ ] 生成闪卡。
- [ ] 图片附件上传。
- [ ] 文档临时附件上传。
- [ ] 本轮 query 携带附件。
- [ ] 多模态附件优先走 `aquery_with_multimodal`。
- [ ] 多轮上下文策略：
  - [ ] 最近 6-10 轮保留原文。
  - [ ] 更早内容做 summary。
  - [ ] 历史对话与本轮 RAG 证据分开注入。

### 验收标准

- [ ] 学生基于刚上传资料提问能答出相关内容。
- [ ] 回答带来源。
- [ ] 低相关问题能提示证据不足。
- [ ] 教师端 AI 助教可用。
- [ ] 多轮追问能理解上下文。
- [ ] 管理端能看到 RAG query event。

---

## 7. 阶段 6：核心链路三：反馈、审核、回流机制

### 任务

- [ ] 低置信自动进入审核队列。
- [ ] source_count 太少时进入审核队列。
- [ ] grounding level 低时进入审核队列。
- [ ] 学生点踩回答。
- [ ] 学生选择点踩原因。
- [ ] 学生填写补充说明。
- [ ] 教师端出现审核任务。
- [ ] 教师审核页展示：
  - [ ] 学生问题。
  - [ ] AI 回答。
  - [ ] 引用来源。
  - [ ] 置信度。
  - [ ] 点踩原因。
  - [ ] 学生补充说明。
- [ ] 教师可采纳 AI 回答。
- [ ] 教师可修改答案。
- [ ] 教师可补充标准答案。
- [ ] 教师可标记已处理。
- [ ] 教师补答写入数据库。
- [ ] 教师补答同步写入 RAG-Anything 可检索路径。
- [ ] 记录回流状态：
  - [ ] pending。
  - [ ] synced。
  - [ ] failed。
- [ ] 相似问题后续能检索到教师修正内容。
- [ ] 统计审核前后相似问题命中率。
- [ ] 统计点踩率变化。
- [ ] 统计人工修正被引用次数。

### 验收标准

- [ ] 点踩后教师端出现审核任务。
- [ ] 教师补答后回流状态可见。
- [ ] 回流失败有错误原因。
- [ ] 回流成功后相似问题能命中教师补答。
- [ ] 管理端能查看审核数量和回流状态。
- [ ] 实验报告能引用审核回流指标。

---

## 8. 阶段 7：学生画像、个性化推荐、学习路径规划

### 8.1 学生画像

#### 任务

- [ ] 记录基础学习行为：
  - [ ] 登录次数。
  - [ ] 学习时长。
  - [ ] 资料浏览。
  - [ ] 任务完成率。
  - [ ] 闪卡复习次数。
  - [ ] AI 提问次数。
- [ ] 计算知识掌握度：
  - [ ] 任务得分。
  - [ ] 错题数量。
  - [ ] 闪卡正确率。
  - [ ] AI 提问频率。
  - [ ] 低置信问答主题。
- [ ] 建立问题画像：
  - [ ] 高频提问关键词。
  - [ ] 点踩主题。
  - [ ] 追问深度。
  - [ ] 常见误区。
- [ ] 建立学习风险：
  - [ ] 长时间未学习。
  - [ ] 任务逾期。
  - [ ] 连续错题。
  - [ ] 某知识点掌握度低。
  - [ ] 频繁请求教师帮助。
- [ ] 建立偏好画像：
  - [ ] 偏好资料类型。
  - [ ] 推荐点击行为。
  - [ ] 不感兴趣反馈。
  - [ ] 学习时间段。

### 8.2 个性化推荐第一版：规则 + 内容匹配

#### 推荐候选

- [ ] 课程资料。
- [ ] 知识点解释。
- [ ] 错题练习。
- [ ] 闪卡。
- [ ] 任务。
- [ ] 教师补充资料。
- [ ] 学习路径节点。

#### 推荐打分

建议第一版使用可解释加权公式：

```text
score =
  0.35 * knowledge_gap_score
+ 0.20 * content_relevance
+ 0.15 * urgency
+ 0.10 * difficulty_match
+ 0.10 * user_preference
+ 0.10 * freshness
```

#### 任务

- [ ] 实现 `knowledge_gap_score`。
- [ ] 实现 `content_relevance`。
- [ ] 实现 `urgency`。
- [ ] 实现 `difficulty_match`。
- [ ] 实现 `user_preference`。
- [ ] 实现 `freshness`。
- [ ] 返回推荐理由。
- [ ] 记录推荐曝光。
- [ ] 记录推荐点击。
- [ ] 记录推荐完成。
- [ ] 记录不感兴趣反馈。

### 8.3 学习路径规划

#### 任务

- [ ] 将知识点、资料、练习、闪卡、任务抽象为路径节点。
- [ ] 建立先修关系、章节顺序、知识依赖。
- [ ] 为节点计算重要程度、难度、掌握度缺口。
- [ ] 找出低掌握知识点。
- [ ] 按先修关系排序。
- [ ] 为每个知识点匹配资料 + 练习 + 闪卡。
- [ ] 根据学生可用时间生成周计划。
- [ ] 学生完成学习后更新 mastery score。
- [ ] 路径动态重排。

### 验收标准

- [ ] 学生端能看到推荐资料和推荐理由。
- [ ] 学生端能看到本周学习路径。
- [ ] 教师端能看到学生知识薄弱点。
- [ ] 推荐点击/完成/不感兴趣能回流。
- [ ] 推荐结果基于行为和课程数据生成，不是固定 mock。

---

## 9. 阶段 8：实验评估与部署验证

### 9.1 实验评估

#### RAG 检索指标

- [ ] Recall@k。
- [ ] nDCG@k。
- [ ] MRR。
- [ ] 引用可追溯率。

#### 生成质量指标

- [ ] 回答正确率。
- [ ] 幻觉率。
- [ ] 平均响应时间。
- [ ] P95 latency。
- [ ] 低置信触发率。

#### 审核回流指标

- [ ] 点踩率。
- [ ] 转人工率。
- [ ] 审核处理率。
- [ ] 回流后相似问题命中率。

#### 推荐指标

- [ ] CTR。
- [ ] 完成率。
- [ ] 不感兴趣率。
- [ ] 推荐后掌握度提升。

#### 系统指标

- [ ] 上传成功率。
- [ ] 索引成功率。
- [ ] 平均索引耗时。
- [ ] 查询成功率。
- [ ] fallback rate。
- [ ] 模型调用错误率。

### 9.2 部署验证

- [ ] 验证 `docker-compose.server.yml`。
- [ ] 启动 frontend。
- [ ] 启动 backend-api。
- [ ] 启动 PostgreSQL。
- [ ] 启动 Redis。
- [ ] 启动 Celery worker。
- [ ] 启动 Qdrant。
- [ ] 启动 Neo4j。
- [ ] 启动 MinIO。
- [ ] 检查 `.env.server`。
- [ ] 检查 API keys。
- [ ] 检查 CORS。
- [ ] 检查 `SECRET_KEY`。
- [ ] 检查数据库密码。
- [ ] 检查 Neo4j 密码。
- [ ] 检查 MinIO 密码。
- [ ] 跑 RAG runtime check。
- [ ] 跑 RAG pipeline smoke。
- [ ] 跑 multimodal suite。
- [ ] 跑 research benchmark。

### 9.3 演示脚本

- [ ] 管理员配置模型。
- [ ] 教师创建班级。
- [ ] 学生加入班级。
- [ ] 教师上传资料。
- [ ] 学生基于资料提问。
- [ ] 学生点踩。
- [ ] 教师审核。
- [ ] 教师补答回流。
- [ ] 学生再次提问并命中修正内容。
- [ ] 查看推荐和学习路径。
- [ ] 管理员查看实验指标。

### 验收标准

- [ ] 一键部署后系统可访问。
- [ ] 前端 live 模式正常。
- [ ] 核心链路连续跑通三次。
- [ ] benchmark 生成 JSON/Markdown 报告。
- [ ] 论文/答辩可直接引用截图、指标和流程。

---

## 10. 额外优化建议

### 10.1 特定模型微调

- [ ] 不优先微调整个大模型。
- [ ] 优先优化 query rewrite。
- [ ] 优先优化 reranker。
- [ ] 优先优化 embedding domain adaptation。
- [ ] 优先优化教育问答 prompt 模板。
- [ ] 累积教师审核数据后构造 SFT 数据：
  - [ ] question。
  - [ ] retrieved evidence。
  - [ ] bad answer。
  - [ ] teacher revised answer。
  - [ ] citation labels。

### 10.2 开放式问答数据库

- [ ] 建立课程 QA Bank。
- [ ] QA 来源包括：
  - [ ] 学生高频问题。
  - [ ] 教师补答。
  - [ ] 低置信审核。
  - [ ] 任务错题。
- [ ] 每条 QA 记录字段：
  - [ ] course_id。
  - [ ] class_id。
  - [ ] knowledge_point。
  - [ ] difficulty。
  - [ ] source。
  - [ ] verified_by_teacher。
  - [ ] embedding。
  - [ ] citation。

### 10.3 多轮对话上下文优化

- [ ] 最近 6-10 轮保留原文。
- [ ] 长期历史压缩为 conversation summary。
- [ ] 本轮 RAG evidence 单独注入。
- [ ] 上下文优先级固定为：
  - [ ] 课程资料证据。
  - [ ] 教师审核答案。
  - [ ] 历史对话。
  - [ ] 模型常识。

### 10.4 协同过滤推荐算法

- [ ] 初期先记录用户行为。
- [ ] 数据足够后实现 User-Based CF。
- [ ] 数据足够后实现 Item-Based CF。
- [ ] 后续考虑矩阵分解或 implicit feedback 模型。
- [ ] 推荐融合：
  - [ ] 内容推荐解决冷启动。
  - [ ] 协同过滤提升个性化。
  - [ ] 教师推荐作为强干预信号。

### 10.5 知识图谱增强

- [ ] 实体增加 confidence。
- [ ] 实体增加 provenance。
- [ ] 实体增加 source_span。
- [ ] 实体增加 occurrence_count。
- [ ] 关系增加 confidence。
- [ ] 关系增加 provenance。
- [ ] 图谱用于先修路径。
- [ ] 图谱用于知识盲区定位。
- [ ] 图谱用于推荐路径排序。

### 10.6 RAG 质量优化

- [ ] 对比 `local/global/hybrid/mix`。
- [ ] 做 query rewrite ablation。
- [ ] 对比 reranker on/off。
- [ ] 对比不同 embedding 模型。
- [ ] 记录 fallback reason。
- [ ] 建立固定 benchmark set。

### 10.7 安全与权限

- [ ] 学生只能访问自己班级。
- [ ] 教师只能访问自己班级。
- [ ] 管理员可全局访问。
- [ ] 文件下载权限校验。
- [ ] 资料预览权限校验。
- [ ] AI 消息权限校验。
- [ ] 审核任务权限校验。

### 10.8 稳定性优化

- [ ] 大文件上传限制。
- [ ] 索引任务幂等。
- [ ] 失败任务重试。
- [ ] 模型调用超时。
- [ ] RAG 查询降级提示。
- [ ] 前端长任务 loading。
- [ ] 前端轮询索引状态。
- [ ] 后端记录关键链路耗时。

---

## 11. 推荐执行顺序

1. [ ] 恢复依赖和测试环境。
2. [ ] 跑通登录注册和三角色 dashboard。
3. [ ] 跑通教师创建班级、学生加入班级。
4. [ ] 开启前端 live 模式，修前后端字段差异。
5. [ ] 跑通资料上传、解析、索引、状态查询。
6. [ ] 配置真实 RAG-Anything runtime。
7. [ ] 跑通学生 AI 助教问答。
8. [ ] 跑通点踩、教师审核、补答回流。
9. [ ] 跑通教师 AI 助教衍生工具。
10. [ ] 实现画像、推荐、学习路径第一版。
11. [ ] 跑 benchmark 和部署 smoke。
12. [ ] 整理最终文档、实验报告、演示流程。

---

## 12. 实施细则：每类任务怎么做、是否实用、技术含量与算法参考

本节用于把上面的 TODO 变成可执行方案。执行时优先按“先闭环、再优化、最后做算法增强”的顺序推进。

---

## 12.1 环境恢复与基线验证

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 后端依赖恢复 | 在 `backend/` 建虚拟环境，安装 `requirements.txt`；正式 RAG 环境再安装 `requirements-raganything.txt`。优先固定 Python 3.11。 | 必须做，否则无法判断代码真实健康度。 | 依赖可能包含 RAG-Anything、MinerU、模型相关包，安装失败要分清是基础 API 失败还是 RAG 扩展失败。 |
| 前端依赖恢复 | 在 `frontend/` 执行 `npm install`，然后跑 `npm run type-check` 和 `npm run build`。 | 必须做，前端 live 联调前必须保证类型和构建通过。 | Vite/React 版本较新，依赖锁文件已有 `package-lock.json`，不要随意升级大版本。 |
| 数据库初始化 | 本地先用 SQLite 快速验证；正式联调改 PostgreSQL，执行 Alembic migration，再执行 seed。 | 必须做，注册登录、班级、聊天都依赖数据。 | 注意 SQLite 与 PostgreSQL 的字段/事务差异，最终验收必须在 PostgreSQL 跑一次。 |
| 自动化测试 | 后端跑 `python -m pytest backend/tests -q`；前端跑 type-check/build。 | 必须做，是后续修改的回归基线。 | 如果测试依赖 RAG 包缺失，应区分 smoke 测试与纯业务测试，不要因为真实模型未配置而阻塞基础业务测试。 |
| 健康检查 | 启动 API 后访问 `/health`、`/health/ready`、`/docs`。 | 必须做，部署与联调都依赖健康状态。 | `/ready` 应能暴露数据库、Redis、RAG 等依赖状态，便于定位部署问题。 |

---

## 12.2 注册登录与角色会话闭环

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 登录响应兼容 | 在前端 `authService` 中归一化后端字段：`access_token -> accessToken`、`token_type -> tokenType`、`real_name -> realName`。或后端额外返回 camelCase 字段。 | 必须做，避免前端 live 模式大量字段判断。 | 推荐前端服务层做一次归一化，后端保持兼容字段，页面层不要写转换逻辑。 |
| 当前用户恢复 | 前端启动时调用 `GET /auth/me`，失败则清 session；成功则根据 `role` 恢复路由。 | 必须做，刷新页面不丢登录态。 | 注意 token 过期时统一处理 401，避免各页面重复处理。 |
| 注册链路 | 学生注册直接创建 student；教师注册可以创建 pending teacher，再由管理员审核激活。验证码本地开发可用 dev mock。 | 实用，能体现完整用户入口。 | 教师审核有业务含义，适合作为管理员端交互变化的演示点。 |
| 角色路由守卫 | 前端 route guard 根据 `user.role` 限制页面；后端接口也必须用 `get_current_student/teacher/admin` 保护。 | 必须做，安全与演示都需要。 | 不能只靠前端隐藏按钮，后端必须做权限校验。 |
| 退出登录 | 前端清理 auth storage，跳转 login；后端可暂不维护 token blacklist。 | 必须做。 | 如果后续有 refresh token，再补服务端 revoke。当前毕设阶段可先客户端退出。 |

算法/技术参考：

- 认证：JWT Bearer Token。
- 权限：RBAC，当前可用 `role` 简化实现；后续可扩展 `roles/user_roles/permissions`。
- 会话恢复：SPA bootstrap auth check。

---

## 12.3 班级空间与课程空间

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 明确 `course/class` 边界 | 后端 bootstrap 同时返回 `classId` 和 `courseId`。前端路由参数可继续叫 `courseId`，服务层内部按接口选择 class/course。 | 必须做，否则后续资料、任务、成员、RAG 会混乱。 | 课程资料/RAG 使用 `course_id` 或 class 绑定的 course；班级成员/任务/讨论使用 `class_id`。 |
| 教师创建班级 | 前端调用 `/teacher/courses` compat 或后端 classes/courses 组合接口。创建 Course + Class，返回 inviteCode。 | 必须做，演示闭环入口。 | 如果一个课程可有多个班级，后端要支持一个 course 多 class；如果毕设简化，可先一 course 对一 class。 |
| 学生加入班级 | 前端输入邀请码，后端查 Class.invite_code，创建 ClassMember。 | 必须做。 | 加入后需要 dashboard 和课程空间列表立即变化。防重复加入，返回已有 membership。 |
| 学生课程空间 | 使用 compat 聚合接口返回首页、资料、任务、讨论、AI 入口、学习概览。 | 必须做。 | 首页应允许空数据，不要展示 mock 课程。 |
| 教师课程空间 | 返回资料管理、学生列表、任务统计、问答审核、知识图谱。 | 必须做。 | 教师端更强调管理动作和状态变化，比如上传后状态、学生数、待审核数。 |
| 管理员空间 | 聚合用户、课程、班级、模型配置、RAG 状态。 | 高实用，便于答辩演示系统完整性。 | 管理端适合展示系统可观测，不必所有写操作都复杂实现。 |

算法/技术参考：

- 数据建模：Course 作为知识边界，Class 作为组织边界，ClassMember 作为成员关系。
- 权限判断：基于 class membership 的 ACL。
- 聚合接口：Backend-for-Frontend/BFF 思路，用 `frontend_compat.py` 减少前端拼装成本。

---

## 12.4 前后端 live 联调

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 开启 live 模式 | 设置 `VITE_API_MODE=live`、`VITE_API_BASE_URL=/api/v1`，Vite proxy 指到 FastAPI。 | 必须做。 | 默认 mock 只能说明页面可看，不能说明系统可用。 |
| 字段归一化 | 在 `services/*` 统一把后端 snake_case 转为前端 camelCase。复杂页面优先后端 compat 返回前端结构。 | 必须做。 | 页面组件不应感知 mock/live 差异。 |
| 空状态 | 所有列表接口返回空数组和统计 0，前端显示空状态。 | 必须做，真实新账号常为空。 | 空状态不是错误；避免前端因为 `undefined` 崩溃。 |
| 错误态 | `http.ts` 已统一封装错误，页面需要 catch 并展示错误提示。 | 必须做。 | 401、403、404、500 要分开处理，权限错误不要伪装成空数据。 |
| 写操作反馈 | 创建、加入、上传、点踩、审核等动作要有 loading/success/error，并刷新相关数据。 | 必须做。 | 交互变化是演示验收重点。 |

技术参考：

- BFF/compat layer：后端适配前端视图模型。
- API envelope：统一 `code/message/data/meta/error`。
- 前端状态机：`idle/loading/success/error/empty`。

---

## 12.5 资料入库与知识库处理

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 文件上传 | 教师端 multipart 上传到后端；后端保存文件到 local/MinIO，创建 `Material`。 | 必须做，是 RAG 的入口。 | 限制文件大小和类型，返回 `file_id/material_id`。 |
| 创建解析任务 | 上传后创建 `FileParseTask`，状态为 pending/processing/completed/failed。 | 必须做。 | 任务状态要幂等，同一文件重复提交要有策略。 |
| 同步/异步处理 | 小文件同步，正式环境用 Celery 异步。上传返回 `parse_task_id`、`queue_task_id`。 | 必须做。 | 前端通过轮询查看状态，避免长请求超时。 |
| 多模态预处理 | 文本转 content_list；PDF/PPT/图片交给 RAG-Anything；音视频优先 transcript sidecar，后续接 ASR/ffmpeg。 | 高实用，体现多模态技术含量。 | 音视频自动处理成本高，第一版用 sidecar 更稳定。 |
| RAG-Anything 入库 | `RAGAnythingAdapter` 调用正式入库入口，将文本/图片/content_list 写入 LightRAG 存储。 | 必须做。 | 真实环境必须配置非 mock LLM 和 embedding。 |
| 知识图谱生成 | 从 RAG-Anything/解析结果提取实体和关系，写入 `KnowledgeEntity/KnowledgeRelation`。 | 高实用，便于教师端可视化。 | 需要 provenance、confidence，避免图谱只是装饰。 |
| 失败重试 | 单文件 retry + 管理端 batch retry，记录 attempt_count、last_error、cooldown。 | 必须做，真实文件解析必然会失败。 | 避免无限重试；失败达到阈值通知管理员。 |

算法/技术参考：

- 文档处理：MinerU、OCR、layout parser、table/formula extraction。
- 多模态统一表示：`ContentItem(type, text, image_path, metadata, page, timestamp, bbox)`。
- 异步任务：Celery + Redis。
- 图谱抽取：实体识别 + 关系抽取 + provenance merge。
- 质量标签：`complete/partial/text_only/multimodal_only/failed`。

---

## 12.6 学生端与教师端 AI 助教

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| RAG runtime 检查 | 执行 `check_raganything_runtime.py`，确认 RAG-Anything、LLM、Embedding、存储依赖 ready。 | 必须做。 | generation 和 embedding 不能是 mock，否则正式 RAG 查询无意义。 |
| 学生提问 | 前端调用 `/chat/query`，传 `course_id/class_id/session_id/message/attachments`。 | 必须做。 | 课程上下文必须显式传入，避免跨课程幻觉。 |
| RAG 检索 | `RAGAnythingAdapter.query` 优先走 `aquery/aquery_with_multimodal`，query mode 用 `mix/hybrid`。 | 必须做。 | 要记录 query_method、source_count、confidence、fallback_reason。 |
| 回答生成 | LLM 基于检索证据生成答案，并返回 citations、confidence、suggestions。 | 必须做。 | Prompt 应强调“不确定时说明证据不足”，避免编造。 |
| 引用展示 | 前端展示来源文件、页码、chunk、score。 | 必须做，体现可溯源。 | citation 字段要稳定，前端不要猜字段。 |
| 教师 AI 工具 | 教案、试题、学情分析、闪卡生成先实现为 RAG + Prompt 模板，后续可异步任务化。 | 实用，答辩展示价值高。 | 第一版不用复杂 agent，稳定模板更可控。 |
| 附件问答 | 上传临时附件，当前轮对话携带附件；图片走 VLM，多文档走临时 content。 | 中高实用。 | 临时附件要有 TTL，避免污染课程知识库。 |
| 多轮上下文 | 最近 6-10 轮原文 + 早期 summary + 本轮 RAG evidence。 | 必须做，聊天体验需要。 | RAG evidence 优先级高于历史对话，防止历史错误扩大。 |

算法/技术参考：

- RAG：RAG-Anything + LightRAG。
- Query Rewrite：多查询改写、关键词提取、compact query。
- Reranking：BGE reranker、API reranker、本地 reranker。
- Prompt Engineering：角色 prompt、课程上下文 prompt、引用约束 prompt。
- Conversation Memory：sliding window + summary memory。

---

## 12.7 反馈、审核与回流

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 低置信触发审核 | 根据 confidence、source_count、grounding_level 生成 ReviewItem。 | 必须做，是教师介入闭环。 | 阈值可配置，避免太多误报。 |
| 点踩触发审核 | 学生点踩后写 feedback，带 reason/comment，关联 AI message。 | 必须做。 | 点踩原因用于后续反馈分析和推荐。 |
| 教师审核界面 | 展示问题、AI 回答、证据、置信度、学生反馈，允许补答/采纳/驳回。 | 必须做。 | 教师端必须能看到待处理数量变化。 |
| 回流知识库 | 教师补答写入 DB，并调用 RAG-Anything `add_qa_pair` 或等价入口。 | 高技术含量，核心创新闭环。 | 记录 sync 状态和错误原因；不要只写 DB。 |
| 回流验证 | 教师补答后，用相似问题再次查询，验证是否命中补答内容。 | 必须做，证明闭环有效。 | 可写 smoke 脚本自动验证。 |
| 指标统计 | 统计点踩率、审核处理率、回流成功率、回流后命中率。 | 高实用，支撑实验报告。 | 要按 course/class/time window 聚合。 |

算法/技术参考：

- Active Learning：低置信样本进入人工标注。
- Human-in-the-loop RAG：教师补答作为高可信 QA。
- Feedback Loop：用户反馈 -> 人工审核 -> 知识库更新 -> 后续质量提升。

---

## 12.8 学生画像

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 行为采集 | 在资料浏览、AI 提问、任务提交、闪卡复习、推荐点击等事件处写 learning event。 | 必须做，没有行为就没有画像。 | 统一事件结构：user_id/class_id/event_type/ref_id/metadata/timestamp。 |
| 知识点映射 | 将问题、错题、资料 chunk、任务题目映射到 knowledge_point。 | 高实用。 | 可先用关键词/图谱实体匹配，后续用 embedding 相似度。 |
| 掌握度计算 | 每个学生每个知识点维护 mastery score。 | 必须做，推荐和路径都依赖。 | 第一版用规则加权，后续可引入 BKT/IRT。 |
| 学习风险识别 | 根据未学习天数、逾期任务、连续错题、低掌握度识别 risk。 | 实用，教师端可展示预警。 | 风险阈值要可解释，便于答辩说明。 |
| 偏好画像 | 统计学生点击/完成/忽略的资料类型和难度。 | 中高实用。 | 用于推荐排序，解决“推荐看起来随机”的问题。 |

画像第一版掌握度公式建议：

```text
mastery =
  0.35 * task_score_norm
+ 0.25 * flashcard_accuracy
+ 0.15 * material_completion
+ 0.15 * ai_question_inverse_difficulty
+ 0.10 * recent_activity
- 0.20 * mistake_penalty
- 0.15 * dislike_or_low_confidence_penalty
```

算法参考：

- Knowledge Tracing 第一版：规则画像。
- 后续增强：BKT（Bayesian Knowledge Tracing）、DKT（Deep Knowledge Tracing）、IRT（Item Response Theory）。
- 文本归因：关键词匹配 + embedding similarity + graph entity linking。

---

## 12.9 个性化推荐

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 候选召回 | 从课程资料、错题、闪卡、任务、教师推荐、QA Bank 召回候选。 | 必须做。 | 冷启动时优先教师推荐和课程重点资料。 |
| 规则排序 | 使用可解释打分公式排序，返回推荐理由。 | 必须做，第一版稳定。 | 推荐理由比复杂算法更适合毕设演示。 |
| 用户反馈 | 记录曝光、点击、完成、不感兴趣。 | 必须做，后续优化依赖。 | 没有曝光日志就无法算 CTR。 |
| 内容相似推荐 | 用 embedding 或关键词计算候选与错题/提问/知识点的相似度。 | 高实用。 | 可复用 RAG embedding 或轻量 TF-IDF。 |
| 协同过滤增强 | 行为数据足够后做 User-Based CF / Item-Based CF。 | 中长期优化。 | 数据少时 CF 效果差，不应作为第一版核心。 |

第一版推荐打分：

```text
score =
  0.35 * knowledge_gap_score
+ 0.20 * content_relevance
+ 0.15 * urgency
+ 0.10 * difficulty_match
+ 0.10 * user_preference
+ 0.10 * freshness
```

算法参考：

- 内容推荐：TF-IDF/BM25/Embedding Similarity。
- 协同过滤：UserCF、ItemCF、implicit feedback matrix。
- 排序融合：weighted ranking、learning-to-rank 后续可选。
- 冷启动：教师推荐、课程章节顺序、知识缺口优先。

---

## 12.10 学习路径规划

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 构建知识 DAG | 节点为知识点/资料/练习/闪卡；边为先修关系、章节顺序、依赖关系。 | 高实用，路径规划核心。 | 初期可从课程章节和图谱关系生成。 |
| 找薄弱点 | 使用 mastery score 找低掌握知识点。 | 必须做。 | 低掌握点需要结合近期任务和错题，不只看 AI 提问。 |
| 路径排序 | 按先修关系拓扑排序，再按重要度和截止时间加权。 | 高技术含量。 | 图里有环时要降级为章节顺序。 |
| 匹配学习资源 | 每个知识点匹配资料、练习、闪卡、问答。 | 必须做。 | 匹配失败时可推荐教师补充资料或通用复习建议。 |
| 周计划生成 | 根据学生可用时间和节点预计耗时生成 3-7 天计划。 | 实用，学生端可见。 | 不要生成过满计划，需考虑任务截止。 |
| 动态重排 | 学生完成/失败/忽略后更新 mastery，再重排路径。 | 高实用。 | 每次重排要保留已完成项，避免路径跳变过大。 |

算法参考：

- DAG Topological Sort。
- Shortest Path / Personalized Path Ranking。
- Prerequisite-aware Recommendation。
- Multi-objective ranking：掌握度缺口、任务紧急度、难度匹配、学习时间。

---

## 12.11 实验评估

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| 构建 benchmark set | 每门课准备固定问题、标准答案、期望来源 doc/chunk/page。 | 必须做。 | 没有 ground truth 就只能做 smoke，不能算 Recall/nDCG。 |
| 检索指标 | 用返回 sources 与期望 sources 比较，计算 Recall@k、nDCG@k、MRR。 | 高技术含量。 | 需要统一 source id/chunk id。 |
| 生成指标 | 人工或规则评估正确率、幻觉率、引用可追溯率。 | 必须做，论文需要。 | 幻觉率可先人工标注小样本。 |
| 性能指标 | 记录平均延迟、P95、查询成功率、fallback rate。 | 必须做。 | 已有 RAG query event，可直接聚合。 |
| 审核回流指标 | 统计回流前后相似问题命中变化。 | 高价值。 | 这是系统闭环最有说服力的实验。 |
| 推荐指标 | 统计 CTR、完成率、不感兴趣率、推荐后掌握度提升。 | 中高价值。 | 初期用户少，可以用模拟用户或小样本实验。 |

算法/指标参考：

- IR 指标：Recall@k、Precision@k、nDCG@k、MRR。
- RAG 指标：Groundedness、Citation Accuracy、Faithfulness。
- 推荐指标：CTR、CVR、Coverage、Diversity、Novelty。
- A/B 思路：query rewrite on/off、reranker on/off、不同 query mode 对比。

---

## 12.12 部署验证

| 任务 | 具体实现方式 | 实用性 | 技术含量/注意点 |
|---|---|---|---|
| server compose | 使用 `docker-compose.server.yml` 启动 frontend/backend/db/redis/celery/qdrant/neo4j/minio。 | 必须做，证明可部署。 | 需要检查端口、volume、healthcheck。 |
| `.env.server` | 配置真实数据库、模型 API key、向量库、图谱库、MinIO、CORS、SECRET_KEY。 | 必须做。 | 不要把真实 key 提交到仓库。 |
| RAG smoke | 跑 runtime check、pipeline smoke、multimodal suite。 | 必须做。 | smoke 失败要定位是模型、解析器、存储还是权限问题。 |
| 前端生产验证 | 构建 frontend 镜像，确认 nginx 代理 `/api/v1` 到后端。 | 必须做。 | SPA 刷新路由需 nginx fallback 到 index.html。 |
| 演示脚本 | 按管理员配置、教师建班、学生入班、资料入库、AI 问答、审核回流、推荐路径完整演示。 | 必须做。 | 演示脚本要固定材料和问题，避免现场随机失败。 |

---

## 12.13 高级优化与论文加分方向

| 方向 | 具体实现方式 | 实用性 | 技术含量/算法参考 |
|---|---|---|---|
| 特定模型微调 | 不优先微调整个 LLM；优先微调 reranker、embedding 或 query rewrite。教师审核数据积累后再做 SFT。 | 中长期有价值。 | SFT 数据格式：question + evidence + bad answer + teacher revised answer。 |
| 开放式 QA Bank | 将学生高频问题、教师补答、审核样本、错题解析沉淀为课程 QA 数据库。 | 高实用，直接提升回流价值。 | 可向量化 QA，作为高可信检索源。 |
| 多轮上下文优化 | recent turns + summary memory + RAG evidence 三层上下文。 | 必须优化，影响对话体验。 | Sliding Window、Conversation Summary、Context Compression。 |
| 协同过滤 | 行为数据足够后做 UserCF/ItemCF，和内容推荐融合。 | 数据足够后有价值。 | Implicit Feedback、Cosine Similarity、Matrix Factorization。 |
| 图谱增强 | 用图谱先修关系做路径规划和推荐排序。 | 高价值，适合论文展示。 | Entity Linking、Relation Extraction、Graph Ranking。 |
| RAG 质量优化 | 对比 query mode、query rewrite、reranker、embedding 模型。 | 高价值，适合实验章节。 | Ablation Study、Retrieval Evaluation。 |
| 安全权限 | 全接口后端校验 class membership 和 role。 | 必须做。 | RBAC + resource ownership check。 |
| 稳定性 | 大文件限制、任务幂等、超时、重试、降级提示、轮询状态。 | 必须做。 | Resilience Engineering、Retry with Cooldown、Circuit Breaker 可选。 |
