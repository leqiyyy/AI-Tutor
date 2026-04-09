# 后端实施计划与当前状态

## 1. 项目定位

本项目后端定位为：

**模块化单体（Modular Monolith）的 AI 助教系统后端**

核心主线：

1. 教师上传课程资料
2. 系统构建班级/课程知识库
3. 学生或教师向 AI 助教提问
4. 返回带 citation 的回答
5. 低置信度或点踩回答进入审核队列
6. 教师补答并回流知识库
7. 学情分析、闪卡、学习画像持续优化

---

## 2. 分阶段计划

### Phase 0：分析阶段

目标：

- 扫描项目结构
- 分析前端 API 依赖
- 输出分析文档与实施计划

当前状态：

- 已完成

交付：

- [frontend_api_analysis.md](e:/all_files/project2/AI_tutor/AI-Tutor-end5/docs/frontend_api_analysis.md)
- 当前文档

### Phase 1：基础工程

目标：

- FastAPI 主工程
- 核心配置管理
- 数据库/Redis/Celery/存储适配层
- 健康检查
- 统一响应与异常处理

当前状态：

- 已完成

### Phase 2：基础业务

目标：

- 认证
- 用户、课程、班级
- 任务与通知
- Alembic 基线
- 种子数据

当前状态：

- 已完成

### Phase 3：知识库与 AI 闭环

目标：

- 文件上传
- 解析任务
- KB 状态/图谱
- 聊天问答
- citation
- 自动审核触发

当前状态：

- 已完成（使用简化 RAG 降级实现）

### Phase 4：审核回流 + 学情 + 闪卡

目标：

- 审核回流记录
- 学情统计
- 学生画像
- 闪卡复习闭环

当前状态：

- 已完成

### Phase 5：收尾与联调准备

目标：

- README
- `.env.example`
- Swagger/OpenAPI
- pytest smoke tests
- 后端架构文档
- API 契约文档

当前状态：

- 已完成

### Phase 6：规格对齐收尾

目标：

- 对照原始总目标查漏补缺
- 补前端剩余高价值占位接口
- 形成最终交付状态清单

当前状态：

- 已完成一轮关键缺口收敛

---

## 3. 当前已实现模块

### 接入层

- FastAPI 入口
- 路由聚合
- 统一异常处理
- 统一响应结构
- 统一鉴权依赖
- CORS
- 请求日志
- 健康检查

### 平台业务层

- auth
- users
- courses
- classes
- class_members
- notifications
- tasks
- submissions
- chat_sessions
- reviews
- flashcards
- analytics
- student_profiles
- study_mistakes
- admin_settings

### AI / KB 层

- 简化解析器
- 简化 RAG 引擎
- 资料上传与索引
- citation 落库
- 低置信度审核触发
- 教师回流同步记录

### 基础设施层

- SQLite / PostgreSQL 配置兼容
- Redis 适配层
- Celery 适配层
- 本地文件存储
- MinIO 适配占位
- Alembic 迁移
- pytest smoke tests

---

## 4. 当前已实现的核心闭环

### 闭环 1：认证与课程访问

- 登录
- 当前用户
- 课程列表
- 班级详情

状态：

- 已完成

### 闭环 2：教师上传资料到课程知识库

- 上传文件
- 元数据入库
- 创建解析任务
- 查询任务状态
- 查询知识库状态

状态：

- 已完成

### 闭环 3：学生/教师使用 AI 助教问答

- 创建或复用会话
- 提问
- 返回回答
- 返回 citation
- 返回 follow-up suggestions
- 保存聊天记录

状态：

- 已完成

### 闭环 4：学生点踩 + 教师审核 + 回流知识库

- 学生点踩
- 自动进入审核队列
- 教师提交修正答案
- 回流同步状态记录

状态：

- 已完成

### 闭环 5：学习闪卡

- 获取闪卡列表
- 提交复习结果
- 落库复习记录
- 更新下次复习时间

状态：

- 已完成

### 闭环 6：基础学情统计

- 提问次数
- 高频关键词
- 点踩问题数
- 活跃度
- 任务完成率
- 热点主题

状态：

- 已完成

---

## 5. 已实现的主要 API

### 认证

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/send-verify-code`
- `GET /api/v1/auth/me`

### 课程 / 班级

- `GET /api/v1/courses`
- `GET /api/v1/courses/{course_id}`
- `GET /api/v1/courses/{course_id}/analytics`
- `POST /api/v1/courses`
- `GET /api/v1/classes`
- `GET /api/v1/classes/{class_id}`
- `POST /api/v1/classes`
- `POST /api/v1/classes/join`
- `POST /api/v1/classes/{class_id}/invite`

### 文件 / 知识库

- `POST /api/v1/courses/{course_id}/files/upload`
- `GET /api/v1/courses/{course_id}/files`
- `GET /api/v1/courses/{course_id}/files/{file_id}/preview`
- `GET /api/v1/courses/{course_id}/files/{file_id}/download`
- `GET /api/v1/courses/{course_id}/files/{file_id}/analysis`
- `GET /api/v1/courses/{course_id}/kb/status`
- `POST /api/v1/courses/{course_id}/kb/rebuild`
- `GET /api/v1/courses/{course_id}/graph`
- `GET /api/v1/courses/{course_id}/search`

### AI 聊天 / 审核

- `POST /api/v1/chat/query`
- `POST /api/v1/chat/query-with-image`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/sessions/{session_id}/messages`
- `POST /api/v1/chat/messages/{message_id}/feedback`
- `GET /api/v1/reviews/pending`
- `POST /api/v1/reviews/{review_id}/submit`
- `POST /api/v1/reviews/escalate`

### 任务 / 通知

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks`
- `POST /api/v1/tasks/{task_id}/submit`
- `GET /api/v1/tasks/{task_id}/submissions`
- `GET /api/v1/notifications`
- `POST /api/v1/notifications`
- `POST /api/v1/notifications/mark-read`

### 学习增强

- `GET /api/v1/flashcards`
- `POST /api/v1/flashcards/{flashcard_id}/review`
- `GET /api/v1/students/me/profile`
- `GET /api/v1/students/me/reports/weekly`
- `GET /api/v1/students/me/reports/monthly`
- `GET /api/v1/students/me/export`
- `GET /api/v1/students/me/mistakes`
- `POST /api/v1/students/me/mistakes`
- `PUT /api/v1/students/me/mistakes/{mistake_id}/mastered`
- `POST /api/v1/students/me/mistakes/{mistake_id}/practice`

### 管理端

- `GET /api/v1/admin/overview`
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/classes`
- `GET /api/v1/admin/courses`
- `GET /api/v1/admin/reviews`
- `GET /api/v1/admin/settings`
- `GET /api/v1/admin/model-config`
- `PUT /api/v1/admin/model-config`

---

## 6. 当前降级实现说明

以下能力当前采用“可运行优先”的降级策略：

### AI / RAG

- 当前不是 LightRAG / RAG-Anything 真接入
- 当前使用 `SimpleParserProvider + SimpleRAGEngine`
- 检索基于解析文本块和关键词匹配

### 多模态

- `query-with-image` 已有接口
- 目前仍走简化附件上下文路径
- 没有真实 VLM 推理

### 存储

- 默认本地文件系统
- MinIO 适配层已预留，但不是默认主路径

### 异步任务

- Celery 适配层已存在
- 当前主链仍以同步执行为主，方便本地 MVP 运行

### 配置管理

- 管理端 `model-config` 已持久化
- 但不直接热更新运行中的 provider 实例

---

## 7. 当前仍未完全覆盖的增强项

以下内容不是主链阻塞项，但相较于你最初完整目标仍属于后续增强空间：

- `roles` / `user_roles` 真正独立的 RBAC 数据模型
- `course_chapters` 独立表
- 更细粒度的 `course_files` / `task_submissions` 命名对齐
- `roles_permissions` 模块化拆分
- `VLM / ASR / reranker / embedding` 的完整抽象族与真实实现
- `RAG-Anything` / `LightRAG` 真实接入
- SSE / 流式输出
- repository 层系统化拆分
- 更完整的互动空间问答模型区分（discussion / question / reply）
- 图数据库或更真实的知识图谱推理
- 更细粒度内容审核 / 敏感内容策略引擎

---

## 8. 当前交付判断

从“前端可联调 + MVP 主链闭环 + 可运行后端 + 文档测试交付”这个标准来看，当前项目已经达到：

**可交付的 MVP 后端状态**

并且具备：

- 可启动
- 可种子初始化
- 可查看 Swagger
- 可跑 smoke tests
- 可继续向真实 RAG/模型能力平滑演进

---

## 9. 建议的下一步

如果继续迭代，建议优先顺序是：

1. 真实 provider / RAG 接入
2. repository 层与 service 子模块再整理
3. 更完整的 RBAC 与管理员审计能力
4. 更细粒度多模态与流式输出
