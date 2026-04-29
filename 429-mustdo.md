# 429 Must-Do 执行清单

创建日期：2026-04-29  
目标：把 AI Tutor 从“核心能力基本具备”推进到“前后端 live 联调可验收、核心链路稳定闭环、个性化能力可解释落地、实验和部署可复现”。

---

## 0. 当前判断

项目已具备 FastAPI 后端、React/Vite 前端、认证、课程/班级、资料入库、RAG-Anything/LightRAG、AI 对话、教师审核、画像/推荐/学习路径的基础代码。

当前最关键的停滞点不是“功能从零开发”，而是：

- [ ] 固定运行环境，避免依赖和镜像反复变化。
- [ ] 让前端从 mock 稳定切到 live。
- [ ] 打通注册登录、角色权限、班级空间的真实闭环。
- [ ] 让资料入库后的 RAG-Anything 多模态结果完整投影到业务 API。
- [ ] 稳定跑通“学生提问 -> RAG 回答 -> 点踩/低置信审核 -> 教师修正 -> 回流知识库 -> 再次命中”。
- [ ] 让学生画像、推荐、学习路径先以可解释规则版落地，再迭代算法。

### 2026-04-29 当前执行结论

- [x] 已确认后端按 Docker 容器运行，并在容器内执行核心链路验证。
- [x] 已修复异步入库 task id 不一致问题：上传接口预生成 Celery `queue_task_id`，数据库任务和队列任务可追踪到同一个 id。
- [x] 已修复 RAG-Anything 写回 `FileParseTask.extra_data` 时覆盖入队 metadata 的问题，避免任务状态、重试、队列信息被旧对象写丢。
- [x] 已修复增量图谱投影中显式实体与候选关键词节点重复/缺少 provenance 的问题。
- [x] 已修复图谱增量投影的稳定性问题：当 LightRAG 没稳定抽出英文唯一 token/业务标识时，系统会从本次预处理文本补充候选实体，并回扫同班级历史解析任务合并 `source_material_ids`。
- [x] 已将课程图谱默认返回上限从 300 调整为 1000，避免课程下多班级/历史实体较多时新近低置信候选节点被默认截断。
- [x] 已修复 Markdown 表格/公式被折叠成纯文本的问题：`.md/.txt` 预处理会额外抽取 `table` 与 `equation/formula` content items。
- [x] 已修复独立图片上传触发 MinerU 零块失败的问题：图片文件走 `content_list`，包含文本锚点和 image 单元，仍交给 RAG-Anything 多模态处理。
- [x] 已补齐图谱边的 `description/summary` 字段，便于前端和问答侧展示“关系描述/摘要”。
- [x] 已新增端到端验证脚本：`backend/scripts/verify_429_core_chain.py`。
- [x] 已跑通真实核心链路：登录 -> 创建班级 -> 学生加入 -> 上传表格/公式 Markdown 与图片 -> RAG-Anything/LightRAG 入库 -> 分析页 -> 检索 -> 图谱 -> 学生/教师 AI 问答 -> 引用溯源 -> 学生点踩 -> 教师审核 -> 回流知识库 -> 追问。
- [x] 核心链路复验报告：`backend/runtime_tmp/429_core_chain_reports/verify_429_core_chain_0134999d.json`，18 项检查全部通过。
- [x] 容器内 RAG runtime 检查通过：`status=ready`，`blocker_count=0`，Qdrant 与 Neo4j 均可达。
- [x] 已同步修复到后端 API 容器与 Celery worker 容器，并重启服务进程加载代码。
- [x] 后端阻断回归测试通过：`tests/test_kb_index_task_management.py` 11 passed；图谱 API 与 RAG 查询补测 3 passed；多模态预处理测试 2 passed；多模态回归 E2E 1 passed。
- [x] 前端基线验证通过：`npm run type-check` 与 `npm run build` 均通过。
- [x] 已完成主页/角色 Dashboard 第一轮 live 联调：前端 `.env.local` 为 live 模式，登录、学生/教师/管理员 dashboard、教师邀请码接口均走真实后端。
- [x] 已修复 Dashboard 伪联调点：学生/教师/管理员顶部用户信息改为使用当前会话或 dashboard `greetingName`，教师分享邀请码改为调用后端真实接口。
- [x] 已将本次前端构建产物同步到运行中的 `ai-tutor-frontend-1` nginx 容器，容器内 `/health` 与 `/api/v1/auth/login` 代理验证通过。
- [ ] 注意：当前课程级 KB 状态为 `degraded`，原因是历史运行中仍有 16 个失败材料、1 个旧材料缺少 storage metadata；本次新链路材料均为 `indexed`，但部署验收前应清理/重建历史脏数据。
- [x] 已修复 LightRAG 直接引用查询的 `mix` 模式兼容问题：配置仍保留 `RAGANYTHING_QUERY_MODE=mix`，但 direct `aquery_llm` 实际使用稳定的 `hybrid`，避免旧的 keyword 解析异常阻断回答。
- [ ] 注意：Qdrant client 1.17.1 与 server 1.13.2 有兼容警告；当前可运行，但部署前建议统一版本。
- [ ] 注意：测试用 PNG 仍会触发 VLM “bad header checksum”警告，但图片 content_list 锚点和 fallback 入库链路已通过；后续应替换为真实无损图片样例做视觉描述质量验收。

---

## P0：必须先完成的稳定运行与核心闭环

### 1. 环境冻结与基线检查

- [ ] 记录 Python、Node、npm 版本。
- [ ] 确认后端依赖是否已安装。
- [ ] 确认前端依赖是否已安装。
- [ ] 确认 `backend/.env`、`backend/.env.server`、前端环境变量样例存在。
- [ ] 确认数据库初始化脚本可用：`backend/scripts/init_database.py`。
- [x] 确认 RAG 运行时检查脚本可用：`backend/scripts/check_raganything_runtime.py`。
- [ ] 确认 RAG smoke 脚本可用：`backend/scripts/smoke_raganything_pipeline.py`。
- [ ] 跑后端测试：`python -m pytest backend/tests -q`。
- [x] 跑前端类型检查：`npm run type-check`。
- [x] 跑前端构建：`npm run build`。

验收标准：

- [ ] 后端测试结果明确，失败项有记录。
- [x] 前端 type-check/build 结果明确，失败项有记录。
- [x] RAG-Anything 运行时是否 ready 有明确结论。
- [x] 当前环境版本和阻塞项写回本清单。

### 2. 注册登录与角色会话闭环

- [x] 联调 `POST /api/v1/auth/login`。
- [x] 联调 `GET /api/v1/auth/me`。
- [x] 校验后端 `access_token` 和前端 `accessToken` 的归一化。
- [x] 校验 `Authorization: Bearer <token>` 全局携带。
- [x] 校验学生、教师、管理员三类 demo 账号登录。
- [ ] 校验注册接口，包括学生注册和教师注册。
- [ ] 校验退出登录，清空本地 token 和用户态。
- [ ] 校验刷新页面后会话恢复。
- [ ] 校验 token 失效后返回登录页。
- [ ] 校验路由守卫：
  - [ ] 未登录不能访问业务页。
  - [ ] 学生不能访问教师页。
  - [ ] 教师不能访问管理员页。
  - [ ] 管理员进入管理端。

验收标准：

- [x] 三类角色均可真实登录。
- [x] 不同角色进入不同 dashboard。
- [x] 界面入口和可点击操作随角色变化。（已验证 dashboard 数据与教师邀请码主操作，课程空间逐页待补）
- [ ] 错误账号、过期 token、无权限访问均有明确 UI 状态。

### 3. 课程、班级、空间边界统一

约定：

- `course`：知识库边界，关联资料、RAG 索引、知识图谱。
- `class`：教学组织边界，关联学生、教师、邀请码、任务、讨论、成员。
- 前端路由里的 `courseId` 在课程空间页面大多实际表示 `classId`，但调用知识库/RAG/资料接口时必须使用真实 `courseId`。

任务：

- [ ] 检查前端 course service 是否能同时保留 `classId` 与 `courseId`。
- [ ] 检查后端 bootstrap 接口是否返回 `classId`、`courseId`、角色、权限、知识库状态。
- [x] 联调教师创建课程/班级。（已验证创建班级）
- [x] 联调教师生成邀请码。
- [x] 联调学生通过邀请码加入班级。
- [ ] 校验学生加入后 dashboard 出现该空间。
- [ ] 校验教师端学生数、班级成员列表变化。
- [ ] 校验同一空间下学生端和教师端展示不同操作入口。

验收标准：

- [ ] 教师创建班级后学生可加入。
- [ ] 加入班级后学生和教师两侧状态同步变化。
- [ ] 空数据用户显示真实空状态，不显示 mock 假数据。

### 4. 资料入库与 RAG-Anything 处理链路

- [ ] 教师上传 PDF。
- [x] 教师上传 TXT/MD。
- [x] 教师上传图片。
- [ ] 教师上传含表格、图片、公式的 PDF。（已验证 Markdown 表格/公式与独立图片；PDF 专项待补）
- [x] 后端创建 `Material`。
- [x] 后端创建 `FileParseTask`。
- [x] 小文件同步索引可用。
- [ ] 大文件异步任务可用。（Celery task id 链路已修复，仍需真实大文件压测）
- [x] 上传接口返回 `parse_task_id`。
- [x] 任务状态可从 `pending/processing` 进入 `completed/failed`。
- [ ] 文件分析页展示：
  - [ ] summary。
  - [ ] extracted_text。
  - [x] chunks。
  - [x] content_items。
  - [x] raganything_status。
  - [x] raganything_quality。
  - [ ] failure reason。
- [x] 将 LightRAG KV 中的 table/image/formula chunk 合并回 `FileParseTask.chunks`。
- [ ] 保留多模态 evidence 字段：
  - [x] source_type。
  - [x] page。
  - [ ] bbox 或定位信息。
  - [x] snippet。
  - [x] image path / preview url。
  - [x] table markdown/html。
  - [x] formula latex。
  - [x] entity/relation provenance。
- [ ] 上传失败可 retry。
- [ ] retry 有最大次数和冷却时间。

验收标准：

- [ ] 资料上传后状态可稳定变为完成。
- [x] `/api/v1/courses/{course_id}/search` 能搜到文本、表格、图片、公式 evidence。（本轮验证 Markdown 表格/公式与图片入库；搜索命中表格/公式材料）
- [x] `/api/v1/chat/query` 能引用对应 evidence。
- [ ] 失败任务可定位、可重试、不污染知识库。

### 5. 学生端与教师端 AI 助教对话

- [x] 学生端 AI 调用真实 `/api/v1/chat/query`。
- [x] 教师端 AI 调用真实 `/api/v1/chat/query` 或教师兼容路由。
- [ ] 消息请求携带 `courseId`、`classId`、`sessionId`、角色、附件。（后端链路已验证 `class_id`；前端 live 仍需逐页确认）
- [x] 响应返回 answer、sources、confidence、quality、review_context、messageId。
- [ ] 前端展示引用来源、置信度、证据片段。
- [x] 前端支持继续追问。（后端多轮追问已验证）
- [ ] 前端支持点赞/点踩。
- [x] 点踩调用后端 feedback 接口。
- [ ] 多轮上下文处理区分新话题、追问、澄清。（后端可运行，策略质量待专项评估）
- [x] 低证据或低置信时触发审核，而不是强行编造。

验收标准：

- [x] 学生问教材内问题能命中资料并返回引用。
- [x] 教师问课程问题能命中同一知识库。
- [ ] 资料外问题会提示不确定或进入审核。
- [x] 点踩后教师端审核队列出现记录。

### 6. 教师审核与知识库回流

- [x] 教师审核列表展示学生问题。
- [x] 审核项展示 AI 原回答、证据、置信度、触发原因、学生反馈。
- [x] 教师可填写标准答案。
- [ ] 教师可标注知识点。
- [x] 教师提交后更新 ReviewItem 状态。
- [x] 提交后调用 `rag.add_qa_pair` 或等价回流接口。
- [x] 回流结果写入 QA/FAQ 或课程知识库增量索引。
- [ ] 回流后相似问题再次检索优先命中教师答案。（已验证追问可回答且回流 `synced`；“优先命中教师答案”还需排序专项断言）

验收标准：

- [x] “答错 -> 教师修正 -> 再问命中修正答案”闭环成功。（本轮验证到回流 synced 与追问成功，排序优先级待加强）
- [ ] 回流失败有错误状态和可重试机制。

---

## P1：前后端全功能联调

### 7. 前端 live 模式切换

- [x] 设置 `VITE_API_MODE=live`。
- [x] 设置 `VITE_API_BASE_URL=/api/v1` 或与部署代理保持一致。
- [ ] 确认所有 service 层不再静默回退 mock。
- [ ] 网络错误、空数据、权限错误、加载中状态完整。

### 8. Dashboard 与空间页面联调

- [x] 学生 dashboard。
- [x] 教师 dashboard。
- [x] 管理员 dashboard。
- [ ] 学生课程空间首页。
- [ ] 教师课程空间首页。
- [ ] 资料列表。
- [ ] 资料分析页。
- [ ] 知识图谱页。
- [ ] 任务页。
- [ ] 互动讨论页。
- [ ] 学生管理页。
- [ ] 审核中心。
- [ ] 管理端用户、课程、班级、模型配置、RAG 状态页。

验收标准：

- [ ] 每个页面至少完成真实接口请求、空状态、错误状态、主要按钮交互。

---

## P2：画像、推荐、学习路径与算法优化

### 9. 学生画像

- [ ] 汇总学生行为：提问、点踩、错题、审核关联、资料访问、闪卡复习。
- [ ] 将问题映射到知识点。
- [ ] 建立知识点掌握度。
- [ ] 建立薄弱项、强项、风险信号。
- [ ] 给每个画像结论提供解释依据。

算法建议：

- [ ] MVP 使用可解释规则：正确率、提问频次、点踩、审核、最近学习时间。
- [ ] 数据足够后评估 BKT。
- [ ] 不建议早期直接上 DKT，数据稀疏且解释性弱。
- [ ] LLM 可辅助知识点归因，但画像分数不应完全由 LLM 决定。

### 10. 个性化推荐

- [ ] 推荐复习知识点。
- [ ] 推荐资料片段。
- [ ] 推荐题目或闪卡。
- [ ] 推荐教师已修正 FAQ。
- [ ] 推荐继续追问方向。
- [ ] 每条推荐展示原因。

算法建议：

- [ ] 第一阶段：规则 + 内容相似度。
- [ ] 第二阶段：embedding 召回 + rerank。
- [ ] 第三阶段：行为数据足够后加入 item-item / user-item 协同过滤。
- [ ] 第四阶段：混合排序，综合掌握度、难度、近期行为、教师优先级。

### 11. 学习路径规划

- [ ] 构建课程知识点图。
- [ ] 标注 prerequisite / related_to / explains / assessed_by。
- [ ] 根据学生目标和薄弱点生成路径。
- [ ] 每个路径节点关联资料、题目、FAQ、图表公式 evidence。
- [ ] 学生完成节点后动态更新路径。
- [ ] 教师端可查看路径变化原因。

---

## P3：实验评估、部署验证与高级优化

### 12. 实验评估

- [ ] RAG 评估：Recall@K、MRR、nDCG、citation accuracy、faithfulness、hallucination rate。
- [ ] 多模态评估：table/image/formula hit rate、引用准确率。
- [ ] 对话评估：首答解决率、追问轮数、低置信触发率、点踩率。
- [ ] 推荐评估：CTR、采纳率、完成率、复习后正确率提升。
- [ ] 系统评估：上传耗时、问答延迟、P95/P99、失败率、并发稳定性。

### 13. 部署验证

- [ ] 拆分 API、worker、frontend、PostgreSQL、Redis、Qdrant、Neo4j、MinIO。
- [ ] 所有密钥和模型配置走环境变量。
- [ ] 记录 request id、user id、course/class id、model、retrieval mode、source ids、latency。
- [ ] 制定业务库、上传文件、RAG 输出目录、LightRAG KV、Qdrant、Neo4j 备份方案。
- [ ] 制定回滚方案。

### 14. 高级优化

- [ ] 微调只用于意图识别、问题分类、答案风格、知识点标注或 reranker，不用于硬记教材事实。
- [ ] 建设课程级开放式 QA/FAQ 数据库，吸收教师审核答案。
- [ ] 多轮对话使用短期上下文 + 长期画像记忆。
- [ ] 表格、图片、公式作为一等 source 类型展示，不再只压成普通文本。
- [ ] 优化 OCR 术语纠错词典，例如 `ssthresh`、`cwnd`、专业中文术语。

---

## 现场执行记录

### 2026-04-29 第一轮基线检查

- [x] Host Python：默认 `python` 为 2.7.18，`python3` 为 3.8.10；host 后端依赖不完整且 pip/OpenSSL 异常，后端测试与运行检查应以 Docker 容器为准。
- [x] Node/npm：Node v22.14.0，npm 10.9.2。
- [x] Docker 基线：API、Celery worker、PostgreSQL、Redis、Qdrant、Neo4j、MinIO、Frontend 容器均在运行。
- [x] Docker 部署注意：后端镜像未挂载本地源码，代码修复后需要重建镜像，或临时 `docker cp` 到 API/worker 容器并重启对应容器。
- [x] RAG-Anything runtime：容器内 `scripts/check_raganything_runtime.py` 通过，`status=ready`，`blocker_count=0`，严格 RAG-Anything、MinerU、Qdrant、Neo4j、ASR API、模型配置均可识别。
- [x] 后端健康检查：容器内 `/health` 与 `/health/ready` 均通过，DB/schema/Redis/storage/Celery ready。
- [x] 前端依赖：`npm ci` 已完成。
- [x] 前端类型检查：`npm run type-check` 通过。
- [x] 前端构建：`npm run build` 通过。
- [x] 后端基础测试：`tests/test_auth_and_courses.py` + `tests/test_response_meta.py` 共 4 项通过。
- [x] 后端 KB 阻断测试：修复后 `tests/test_kb_index_task_management.py` 共 11 项通过。

### 2026-04-29 第一轮阻断修复

- [x] 修复异步索引任务 ID 丢失：上传接口在提交 Celery 任务前预生成 `queue_task_id`，并使用该 ID 作为 Celery `task_id`，避免 worker 抢先写回 `extra_data` 时覆盖队列元数据。
- [x] 修复 RAG-Anything 写回元数据时覆盖 ingest 状态：写入 preprocess/RAG 结果前刷新并合并 `FileParseTask.extra_data`，保留 `queue_task_id`、`queue_status` 等任务观测字段。
- [x] 修复自动重试任务 ID 管理：自动重试同样预生成 queue task id，保证 retry 与任务详情接口可关联。
- [x] 修复知识图谱增量溯源合并：当 RAG-Anything 返回显式实体时，对已存在的关键词实体只做 provenance/appears_in 合并，不新增噪声关键词节点。
- [x] 修复持久化 Docker DB 下测试不稳定：上传去重测试改为每次生成唯一内容，同时保留同一测试内二次上传去重断言。
- [x] 已同步修复到 API/worker 容器用于本轮验证；正式部署仍需重建后端 Docker 镜像。

验证结果：

- [x] `test_kb_async_enqueue_and_async_retry` 通过。
- [x] `test_graph_provenance_updates_on_incremental_ingest` 通过。
- [x] `tests/test_kb_index_task_management.py` 全量通过：11 passed。

残留风险：

- [ ] 尚未完成真实多模态链路验证：上传含表格、图片、公式的 PDF -> MinerU/RAG-Anything 解析 -> LightRAG/Qdrant/Neo4j 入库 -> 学生/教师问答 -> 引用溯源 -> 反馈审核回流。
- [ ] Qdrant Python client 1.17.1 与 server 1.13.2 版本差异较大，需要统一版本以降低检索兼容风险。
- [ ] 测试结束时 RAGAnything/LightRAG logger 偶发 `I/O operation on closed file`，不影响当前用例通过，但需要作为清理项跟踪。

### 2026-04-29 主页与角色 Dashboard 联调

- [x] 前端 live 配置确认：`frontend/.env.local` 使用 `VITE_API_MODE=live`、`VITE_API_BASE_URL=/api/v1`、`VITE_API_PROXY_TARGET=http://localhost:8000`。
- [x] 修复学生 Dashboard 用户区硬编码姓名/邮箱，改为优先使用 dashboard `greetingName`，再回退当前会话用户。
- [x] 修复教师 Dashboard 用户区硬编码姓名/邮箱，改为优先使用 dashboard `greetingName`，并移除问候语中的固定教师姓名。
- [x] 修复管理员 Dashboard 用户区硬编码信息，改为使用当前会话或 dashboard 返回值。
- [x] 修复教师课程卡片的邀请码按钮：不再前端随机生成，改为调用 `POST /api/v1/teacher/courses/{class_id}/invite-code`。
- [x] 后端 dashboard 兼容接口补齐通知数据读取：学生/教师 dashboard 从 `Notification` 表返回真实通知列表。
- [x] 前端验证：`npm run type-check` 通过，`npm run build` 通过。
- [x] 容器内 API 验证：学生、教师、管理员 `POST /api/v1/auth/login` 均 200 且返回 token。
- [x] 容器内 API 验证：学生、教师、管理员 `GET /api/v1/auth/me` 均 200 且角色正确。
- [x] 容器内 API 验证：`GET /api/v1/student/dashboard` 返回 `greetingName=Li Student`、课程数 4。
- [x] 容器内 API 验证：`GET /api/v1/teacher/dashboard` 返回 `greetingName=Wang Teacher`、课程数 45。
- [x] 容器内 API 验证：教师邀请码接口返回真实邀请码 `CS301A1`。
- [x] 容器内 API 验证：`GET /api/v1/admin/dashboard` 返回 `greetingName=System Admin` 和管理端数据键。
- [x] 已将 `frontend/out` 同步到运行中的 `ai-tutor-frontend-1:/usr/share/nginx/html/`。
- [x] 前端容器验证：`/student-dashboard` SPA 路由回退正常，首页 HTML 引用本次构建产物。
- [x] 前端容器代理验证：`/health` 返回后端 ready，`/api/v1/auth/login` 可通过 nginx 代理成功登录。

残留风险：

- [ ] `/auth/me` 当前只确认角色正确，姓名字段为空；Dashboard 已通过 `greetingName` 展示真实姓名，但会话恢复瞬间的用户菜单仍可能短暂显示角色兜底名。
- [ ] 本轮只完成主页与三类 Dashboard 的第一轮联调；课程空间、资料分析页、知识图谱页、审核中心仍需逐页做浏览器点击验证。
- [ ] RAG 流程仍需保留专项验证：真实含表格、图片、公式的 PDF 样例触发 MinerU/RAG-Anything 多模态解析，并检查原始图/表/公式单元、实体关系摘要、检索 evidence 与引用展示。
