# 交付状态清单

## 1. 当前总体状态

当前仓库已经交付了一个：

**可运行、可联调、可测试、可文档化的 AI 助教系统后端 MVP**

并且已经完成了：

- 基础工程
- 基础业务
- 知识库与 AI 闭环
- 审核回流、学情、闪卡
- 文档与测试收尾
- 一轮面向原始规格的缺口收敛

---

## 2. 已完成的核心交付物

### 后端工程与部署

- [x] `backend/` 后端代码
- [x] FastAPI 服务入口
- [x] Alembic 迁移
- [x] Dockerfile
- [x] 根目录 `docker-compose.yml`
- [x] `.env.example`
- [x] 健康检查接口
- [x] Swagger / OpenAPI

### 文档

- [x] 前端 API 分析文档
- [x] 后端实施计划文档
- [x] 后端架构文档
- [x] API 契约文档
- [x] 后端 README

### 测试与初始化

- [x] 种子数据脚本
- [x] 管理员测试账号
- [x] 教师测试账号
- [x] 学生测试账号
- [x] pytest smoke tests

---

## 3. 已完成的业务闭环

### 认证与课程访问

- [x] 登录
- [x] 当前用户信息
- [x] 课程列表
- [x] 班级详情

### 资料上传与知识库

- [x] 课程文件上传
- [x] 解析任务创建
- [x] KB 状态查询
- [x] 图谱数据查询
- [x] 文件预览/下载/解析结果
- [x] 全文搜索

### AI 助教

- [x] 创建/复用会话
- [x] 提问
- [x] 返回回答
- [x] 返回 citation
- [x] 返回 follow-up suggestions
- [x] 保存聊天记录
- [x] 图片提问接口入口

### 审核回流

- [x] 学生点踩
- [x] 自动进入审核队列
- [x] 手动转人工审核
- [x] 教师补答
- [x] 回流同步记录

### 学习增强

- [x] 闪卡列表
- [x] 闪卡复习提交
- [x] 闪卡复习记录
- [x] 学生画像
- [x] 周报
- [x] 月报
- [x] CSV 导出
- [x] 错题本

### 管理端

- [x] 系统概览
- [x] 用户列表
- [x] 课程列表
- [x] 审核列表
- [x] 模型配置读取
- [x] 模型配置持久化

---

## 4. 已完成但属于降级实现

这些功能已经具备可运行能力，但当前不是最终最强版本：

- [x] AI / RAG 当前默认仍可使用 `SimpleRAGEngine`
- [x] 多模态图片问答当前是附件上下文降级
- [x] 存储默认是本地文件系统
- [x] 异步任务主链当前仍以同步执行为主
- [x] 管理端模型配置已持久化，但不会热重载当前运行实例

---

## 5. RAG-Anything 接入状态

### 已完成

- [x] 后端已新增 `RAGAnythingAdapter` 代码路径
- [x] 后端已支持通过 `RAG_ENGINE=raganything` 切换到官方框架路径
- [x] 后端已增加 RAG-Anything 所需配置项：
  - `OPENAI_API_KEY`
  - `OPENAI_API_BASE`
  - `LLM_MODEL`
  - `EMBEDDING_MODEL`
  - `EMBEDDING_DIM`
  - `LIBREOFFICE_PATH`
  - `RAGANYTHING_*`
- [x] README 已补充启用说明

### 仍需你本地环境配合

要真正启用 `RAGAnythingAdapter`，还需要满足：

- [ ] 在**同一个 Python 环境**中安装后端依赖 `requirements.txt`
- [ ] 在**同一个 Python 环境**中安装 `raganything`
- [ ] 在**同一个 Python 环境**中能调用 `mineru`
- [ ] 系统中可调用 LibreOffice 的 `soffice`
- [ ] 提供真实可用的 LLM / Embedding API 配置

### 当前阻塞点

你提供的 `AI-Tutor-End2` 环境中已经有：

- `raganything`
- `mineru`
- LibreOffice

但我们验证后发现：

- 该环境下还缺后端依赖，例如 `sqlalchemy`

因此当前状态是：

**RAG-Anything adapter 代码已接入，但尚未在完整后端运行环境中完成最终启用验证。**

---

## 6. 仍属增强项的后续工作

下面这些不再属于 MVP 阻塞项，而是后续增强项：

- [ ] 独立 `roles / user_roles / permissions`
- [ ] 完整 RBAC 权限系统
- [ ] 真实 OpenAI / OpenAI-compatible LLM provider 生产级接入
- [ ] 真实 embedding / reranker / ASR / VLM provider
- [ ] LightRAG / RAG-Anything 的生产级调优
- [ ] SSE / 流式输出
- [ ] repository 层系统化拆分
- [ ] 更细粒度互动空间模型
- [ ] 更强的内容审核、审计日志与监控

---

## 7. 当前验证结果

- [x] `backend/app` 编译通过
- [x] `pytest` smoke tests 通过
- [x] Alembic migrations 可识别
- [x] 健康检查正常
- [x] 种子数据可重复初始化

当前本地 smoke test 结果：

- `7 passed`

Alembic 当前 head：

- `20260402_0005`
