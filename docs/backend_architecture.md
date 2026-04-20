# AI助教系统后端架构说明（当前实现 + 目标演进）

更新时间：2026-04-17

---

## 1. 架构模式

采用 **模块化单体（Modular Monolith）**：

- 单仓库、单服务主进程，降低复杂度
- 模块边界清晰，便于后续拆分
- 先保证毕设阶段可运行、可验证

---

## 2. 分层架构

### 2.1 接入层

- FastAPI 入口：`backend/app/main.py`
- 路由聚合：`backend/app/api/v1/api.py`
- 统一鉴权依赖：`backend/app/core/deps.py`
- 统一响应：`backend/app/core/response.py`、`responses.py`
- 健康检查：`backend/app/core/health.py`
- 全局异常：`backend/app/core/exceptions.py`

### 2.2 业务服务层

核心服务位于 `backend/app/services/`：

- `auth_service.py`
- `course_service.py`
- `kb_service.py`
- `chat_service.py`
- `task_service.py`
- `flashcard_service.py`
- `analytics_service.py`
- `mistake_service.py`
- `admin_service.py`

### 2.3 AI 编排与知识引擎层

- RAG 引擎入口：`backend/app/integrations/rag/__init__.py`
- 简化引擎：`simple_engine.py`
- RAG-Anything 适配：`raganything_adapter.py`
- 解析器：`backend/app/integrations/parser/simple.py`

目标演进：

- 增加 AI Orchestrator（问题分类、工具路由、上下文注入）
- 增加多模态统一 content item 表示
- 增加反馈分析与推荐策略引擎

### 2.4 数据与基础设施层

- ORM 模型：`backend/app/models/*.py`
- 迁移：`backend/alembic/versions/`
- 数据库：PostgreSQL（开发可 SQLite）
- 缓存：Redis（可关闭）
- 异步：Celery（可降级）
- 存储：Local/MinIO 适配

---

## 3. 关键业务链路

### 3.1 资料入库链路

教师上传文件  
→ 保存文件元数据  
→ 触发解析与索引  
→ 更新 `file_parse_tasks` 与 `kb_spaces`  
→ 课程知识库状态可查询

### 3.2 AI问答链路

接收问题  
→ 注入课程/角色上下文  
→ RAG 检索与证据生成  
→ LLM 生成回答  
→ 落库消息与 citation  
→ 返回建议追问与置信度

### 3.3 审核回流链路

低置信度或点踩  
→ 进入审核队列  
→ 教师补答  
→ 同步回知识库（可追踪）

---

## 4. 当前差距与演进重点

1. 查询主链需切到 RAG-Anything 原生查询。  
2. 多模态解析需从简化文本提取升级为结构化解析。  
3. 图谱实体关系需加置信度和溯源信息。  
4. 推荐与反馈分析模块需独立服务化。  
5. 模型路由层需支持 API/本地双轨。  

---

## 5. 目录规范（目标态）

建议保留并强化以下边界：

- `api/`：仅处理入参和响应
- `services/`：业务编排
- `repositories/`：数据访问（建议逐步补齐）
- `integrations/`：外部能力适配（RAG/模型/解析/存储）
- `workers/`：异步任务

---

## 6. 可观测与可维护要求

1. 每个请求可追踪 request_id。  
2. 关键链路记录耗时与失败原因。  
3. 模型调用记录 latency、错误率、token、成本。  
4. 关键闭环具备测试覆盖和回归脚本。  

