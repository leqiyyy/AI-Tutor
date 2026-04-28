# 前后端联调规划

## 1. 当前结论

前端已经具备较完整的服务层封装，并支持 `mock` 与 `live` 两种运行模式。后端已经具备认证、课程/班级、课程知识库、RAG 问答、通知、学习分析、教师审核、管理员配置等核心能力，但前后端接口命名、资源边界和字段结构尚未完全一致。

本次联调的核心目标不是重新设计业务，而是建立一层稳定的接口契约，使前端从 `mock` 平滑切换到真实后端，同时尽量复用后端已经完成的 RAG-Anything 主链路、知识库管理、音视频预处理、Qdrant/Neo4j 配置、reranker 和审核回流能力。

## 2. 前端运行模式与基础配置

前端位于 `frontend/`，使用 Vite + React + TypeScript。前端通过环境变量控制请求模式：

```env
VITE_API_MODE=live
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY_TARGET=http://localhost:8000
```

说明如下：

- `VITE_API_MODE=live`：关闭前端 mock，所有服务调用真实后端。
- `VITE_API_BASE_URL=/api/v1`：与后端 FastAPI 的版本前缀保持一致。
- `VITE_API_PROXY_TARGET=http://localhost:8000`：开发环境下由 Vite 将 `/api` 请求代理到后端。

如果后端实际端口不是 `8000`，只需要调整 `VITE_API_PROXY_TARGET`。

## 3. 资源边界需要先统一

当前后端同时存在 `course` 和 `class` 两个概念：

- `course` 表示课程知识库和课程资料的知识边界。
- `class` 表示教学班级、邀请码、学生加入、任务、讨论、成员等教学组织边界。

前端文档中大量使用 `courseId` 作为页面参数，但从后端业务来看，学生进入的“课程空间”更接近 `class_id`。因此联调时建议采用如下规则：

- 前端路由中的 `courseId` 暂时按 `classId` 使用，用于课程空间首页、学生任务、讨论、成员、班级资料列表等功能。
- 后端返回课程空间 bootstrap 数据时，同时返回 `classId` 和 `courseId`。
- 当调用知识库、RAG-Anything、文件上传、知识图谱、资料分析等接口时，使用真实 `courseId`。
- 前端服务层保留字段名 `courseId`，但内部适配时根据接口选择 `classId` 或 `courseId`，避免大面积改页面代码。

这是联调的关键前置约定，否则会出现“学生加入的是班级，但知识库接口需要课程 ID”的混乱。

## 4. 接口适配策略

建议采用“后端补聚合接口 + 前端服务层轻量适配”的混合方式。

- 对已经存在且语义清晰的后端接口，优先在前端服务层改调用路径或做字段转换。
- 对前端页面需要一次性渲染复杂页面的数据，例如学生首页、教师首页、管理员首页、课程空间 bootstrap，优先在后端新增聚合接口。
- 对认证返回、聊天消息、课程卡片、资料卡片等高频数据结构，统一输出 camelCase 兼容字段，减少前端页面层判断。
- 不建议让前端直接拼接太多后端底层接口，否则页面会变成临时装配层，后续维护成本高。

## 5. 第一阶段：认证与基础会话联调

目标：完成登录、注册、获取当前用户、退出登录的真实链路。

前端期望接口：

- `POST /auth/login`
- `POST /auth/send-verify-code`
- `POST /auth/register`
- `GET /auth/me`

后端已有对应路由，但字段需要重点确认：

- 前端期望登录返回 `accessToken`、`refreshToken`、`expiresAt`、`user`、`isDemo`。
- 后端当前更偏向返回 `access_token`、`token_type`、`role`、`user_id`、`real_name`。

联调任务：

- 在前端 `auth` 服务中增加登录响应归一化，兼容后端 snake_case 返回。
- 或在后端登录接口中额外返回 camelCase 字段，同时保留旧字段。
- 确认 `Authorization: Bearer <token>` 能被后端正常识别。
- 验证学生、教师、管理员三类账号登录后可正确进入对应页面。

验收标准：

- `VITE_API_MODE=live` 下三类用户均可登录。
- 刷新页面后 `GET /auth/me` 能恢复会话。
- token 失效时前端能清理会话并返回登录页。

## 6. 第二阶段：首页 Dashboard 联调

目标：让学生、教师、管理员三个首页从真实后端拿数据。

前端期望接口：

- `GET /student/dashboard`
- `GET /teacher/dashboard`
- `GET /admin/dashboard`

后端现状：

- 管理员已有 `GET /admin/overview`，但前端期望字段不同。
- 学生和教师首页聚合接口尚不完整，需要补后端聚合或前端组合调用。

建议实现：

- 后端新增或适配 `GET /student/dashboard`，聚合学生课程、待办、推荐、通知、最近活动。
- 后端新增或适配 `GET /teacher/dashboard`，聚合教师课程、学生数、待审核、通知、学生预警。
- 后端新增 `GET /admin/dashboard`，可复用 `/admin/overview`、`/admin/users`、`/admin/courses` 等数据。

验收标准：

- 前端首页不再依赖 mock。
- 新注册用户首页为空状态合理，不展示 demo 数据。
- demo 账号可展示演示课程与统计数据。

## 7. 第三阶段：课程空间与资料管理联调

目标：打通学生加入课程、课程空间首页、资料列表、教师上传资料和知识库状态。

前端涉及接口：

- `POST /student/courses/join`
- `GET /student/courses/:courseId`
- `GET /student/courses/:courseId/materials`
- `GET /teacher/courses/:courseId`
- `GET /teacher/courses/:courseId/materials`
- `POST /teacher/courses/:courseId/files`
- `GET /teacher/courses/:courseId/materials/:fileId/analysis`
- `GET /teacher/courses/:courseId/materials/:fileId/preview`
- `GET /teacher/courses/:courseId/materials/:fileId/download`

后端可复用接口：

- `POST /classes/join`
- `GET /classes/{class_id}`
- `GET /classes/{class_id}/materials`
- `POST /courses/{course_id}/files/upload`
- `GET /courses/{course_id}/files`
- `GET /courses/{course_id}/files/{file_id}/analysis`
- `GET /courses/{course_id}/files/{file_id}/preview`
- `GET /courses/{course_id}/files/{file_id}/download`
- `GET /courses/{course_id}/kb/status`

联调任务：

- 前端加入课程接口映射到 `POST /classes/join`。
- 课程 bootstrap 返回 `classId`、`courseId`、课程名称、教师名称、邀请码、知识库状态。
- 教师资料上传走后端 RAG-Anything 入库接口，不走前端 mock 上传。
- 上传后前端轮询资料解析状态、索引状态、chunk 数、图节点数、失败原因。

验收标准：

- 学生可通过邀请码加入班级。
- 教师可上传 PDF、DOCX、PPTX、图片、音频、视频等资料。
- 上传资料后后端创建解析任务，并进入 RAG-Anything/预处理链路。
- 前端可看到资料状态从处理中变为已完成或失败。

## 8. 第四阶段：RAG-Anything 问答联调

目标：让学生和教师 AI 助教页面真实调用后端 RAG-Anything 主链路。

前端涉及接口：

- `GET /student/ai/conversations`
- `POST /student/ai/messages`
- `POST /teacher/ai/messages`
- `POST /ai/attachments`
- `POST /ai/messages/:id/like`
- `POST /ai/messages/:id/dislike`

后端可复用接口：

- `GET /chat/sessions`
- `GET /chat/sessions/{session_id}/messages`
- `POST /chat/send`
- `POST /chat/query`
- `POST /chat/query-with-image`
- `POST /chat/attachments/upload`
- `POST /chat/messages/{message_id}/feedback`

联调任务：

- 前端 AI 服务改为调用 `/chat/*` 真实接口，或后端新增 `/student/ai/*`、`/teacher/ai/*` 兼容路由。
- 图片/文档临时附件上传改为 multipart，而不是 JSON。
- 消息发送时传入 `courseId`、`classId`、`sessionId`、`attachmentIds`、用户角色。
- 后端回答返回 `answer`、`citations`、`evidences`、`confidence`、`needReview`、`messageId`。
- 点赞/点踩映射到后端 feedback 接口。

验收标准：

- 用户提问能触发 RAG-Anything 检索，而不是 simple fallback。
- 回答中能展示引用来源、置信度、证据片段。
- 上传临时图片或文档后，附件解析结果能参与本轮问答。
- 低置信或点踩回答能进入教师审核队列。

## 9. 第五阶段：知识图谱、审核回流与推荐联调

目标：验证系统闭环，而不是只验证问答。

知识图谱：

- 前端期望 `GET /student|teacher/courses/:courseId/knowledge-graph`。
- 后端已有 `GET /courses/{course_id}/graph`。
- 需要适配节点、边、来源、页码、时间戳、置信度字段。

教师审核：

- 前端期望教师端审核列表、审核提交、回流知识库。
- 后端已有 chat review 和 reviews 路由。
- 需要统一审核项字段：问题、AI 回答、证据、置信度、触发原因、学生反馈、教师修正。

个性化推荐：

- 前端期望课程内推荐、学习概览、错题、闪卡。
- 后端已有 recommendations、students、flashcards 部分能力。
- 优先联调推荐资料列表和推荐理由，再联调完整学习画像。

验收标准：

- 教师能看到由低置信问答产生的审核任务。
- 教师修正后可选择回流知识库。
- 回流内容能触发增量索引或至少进入后续检索候选。
- 学生端能看到基于课程资料和学习行为生成的推荐。

## 10. 第六阶段：管理员与系统配置联调

目标：让管理员端可以查看系统状态与核心配置。

优先联调内容：

- 用户列表与状态管理。
- 课程列表。
- 模型配置。
- RAG 存储配置。
- RAG 系统状态。
- 索引任务状态。

后端已有相关接口：

- `GET /admin/users`
- `PUT /admin/users/{user_id}/status`
- `GET /admin/courses`
- `GET /admin/model-config`
- `PUT /admin/model-config`
- `GET /admin/rag-storage-config`
- `PUT /admin/rag-storage-config`
- `GET /admin/rag-system-status`

验收标准：

- 管理员端能查看当前 LLM、VLM、embedding、reranker 配置。
- 能查看 Qdrant、Neo4j、Redis、Celery、RAG-Anything 状态。
- 能查看索引任务失败原因和最近运行记录。

## 11. 联调优先级

P0 必须先完成：

- 认证登录与 token。
- 学生/教师/管理员 dashboard。
- 学生加入课程。
- 课程空间 bootstrap。
- 教师上传资料到 RAG-Anything。
- 学生基于课程资料提问并获得 RAG 回答。

P1 完成核心闭环：

- 临时附件问答。
- 引用与置信度展示。
- 教师审核与回流。
- 知识图谱可视化。
- 通知。

P2 完善体验：

- 错题本。
- 闪卡。
- 学习画像。
- 个性化推荐细化。
- 管理员内容审核与系统配置页面。

## 12. 建议的实际执行顺序

1. 配置前端 `.env.local`，切换到 `live` 模式。
2. 启动后端，确认 `/api/v1/docs` 和 `/api/v1/auth/login` 可访问。
3. 先联调认证，不碰复杂页面。
4. 补齐 dashboard 聚合接口或前端适配。
5. 统一 `classId` 与 `courseId` 的传递规则。
6. 联调学生加入课程和课程空间 bootstrap。
7. 联调教师资料上传、知识库文件列表、解析状态。
8. 联调 RAG 问答和引用证据。
9. 联调临时附件上传与参与问答。
10. 联调教师审核、知识回流、图谱展示。
11. 联调推荐、学习分析、通知和管理员配置。

## 13. 当前最需要改动的地方

后端侧优先：

- 新增 dashboard 聚合接口。
- 新增课程空间 bootstrap 聚合接口，统一返回 `classId` 与 `courseId`。
- 给聊天问答接口补齐前端需要的引用、置信度、证据字段。
- 给文件上传和解析状态接口补齐前端展示字段。

前端侧优先：

- 将 `.env.local` 切换到 `live`。
- 认证服务兼容后端 snake_case 登录返回。
- 课程服务增加 `classId`/`courseId` 适配。
- AI 服务从当前 `/student/ai/*`、`/teacher/ai/*` 适配到后端 `/chat/*`，或等待后端兼容路由。
- 附件上传改为 multipart 表单。

## 14. 风险点

- 如果不先统一 `courseId` 和 `classId`，后续课程空间、资料上传、RAG 问答会反复错位。
- 如果 dashboard 完全由前端组合多个底层接口，页面会加载慢且错误处理复杂。
- 如果临时附件仍按 JSON 上传，将无法对接后端真实文件解析链路。
- 如果前端直接绕过 RAG-Anything 状态，只展示上传成功，会误以为资料可问答，但实际还未完成索引。
- 如果回答接口不返回引用、证据和置信度，论文中的可信问答链路无法在前端体现。

