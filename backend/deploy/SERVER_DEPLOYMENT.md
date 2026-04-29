# AI Tutor 服务器部署与远程调试指南

本文档用于把当前项目从本地运行迁移到服务器运行。推荐方式是：业务后端、前端、PostgreSQL、Redis、Qdrant、Neo4j、MinIO 全部使用 Docker Compose 管理；LLM、VLM、Embedding、Reranker、ASR 优先走 API，避免在服务器上直接部署大模型导致资源压力过大。

## 1. 服务器推荐配置

API 优先部署，也就是不在服务器本地跑大模型：

- 最低配置：`8 vCPU / 16 GB RAM / 100 GB SSD`
- 推荐配置：`8-16 vCPU / 32 GB RAM / 200 GB SSD`
- 系统：`Ubuntu 22.04 LTS` 或 `Ubuntu 24.04 LTS`

如果要本地部署 VLM、Embedding、ASR 或生成模型，需要单独准备 GPU 服务器。毕业设计联调阶段建议先不要这样做，优先使用硅基流动、OpenAI-compatible API 或学校服务器上的模型服务。

## 2. 服务器安装基础工具

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

执行 `usermod` 后需要退出 SSH 并重新登录。

验证：

```bash
docker --version
docker compose version
```

## 3. 上传或拉取项目

推荐使用 Git：

```bash
git clone <你的仓库地址> AI-Tutor-end5
cd AI-Tutor-end5
```

如果还没有远程仓库，也可以把项目压缩后上传到服务器：

```bash
scp AI-Tutor-end5.zip user@server:/data/
ssh user@server
cd /data
unzip AI-Tutor-end5.zip
cd AI-Tutor-end5
```

## 4. 配置服务器环境变量

复制模板：

```bash
cp backend/.env.server.example backend/.env.server
```

编辑：

```bash
nano backend/.env.server
```

至少需要修改：

- `SECRET_KEY`：换成随机长字符串。
- `POSTGRES_PASSWORD`：生产环境不要用默认值。
- `GRAPH_DB_PASSWORD`：Neo4j 密码，同时会被 compose 用于初始化 Neo4j。
- `LLM_MODEL`、`LLM_API_BASE`、`LLM_API_KEY`：生成模型配置。
- `EXTRACT_MODEL`、`EXTRACT_API_BASE`、`EXTRACT_API_KEY`：LightRAG/RAG-Anything 抽取模型配置。
- `EMBEDDING_MODEL`、`EMBEDDING_API_BASE`、`EMBEDDING_API_KEY`、`EMBEDDING_DIM`：嵌入模型配置。
- `VLM_MODEL`、`VLM_API_BASE`、`VLM_API_KEY`：如果要处理图片、截图、视频关键帧，需要配置。
- `RERANKER_API_KEY`：如果 reranker 使用硅基流动 API，需要配置。

建议初期保持：

```env
RAG_ENGINE=raganything
RAGANYTHING_STRICT_MODE=true
EMBEDDING_BACKEND=api
RERANKER_PROVIDER=api
MULTIMODAL_AUTO_PREPROCESS_ENABLED=false
ASR_PROVIDER=none
```

这样可以先验证文档、图片、知识库、RAG 问答主链路，再逐步开启音视频自动预处理。

## 5. 一键启动服务器栈

从项目根目录执行：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml up -d --build
```

启动后包含：

- `frontend`：Nginx 静态前端和 `/api` 反向代理，外部访问端口 `80`
- `backend-api`：FastAPI 后端，本机调试端口 `127.0.0.1:8000`
- `celery-worker`：异步解析、入库、索引任务
- `db`：PostgreSQL
- `redis`：缓存与 Celery broker
- `qdrant`：向量数据库
- `neo4j`：图数据库
- `minio`：对象存储，可按需启用

查看状态：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml ps
```

## 6. 初始化数据库

当前 `docker-compose.server.yml` 会先运行 `backend-migrate`，自动执行 Alembic 迁移，并在 `SEED_DEMO_DATA=true` 时写入演示账号和基础课程。正常情况下不需要手动初始化。

如果需要手动修复或重新执行迁移：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml exec backend-api alembic upgrade head
```

如果需要生成演示账号和基础课程：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml exec backend-api python -m app.db.seed
```

访问：

```text
http://服务器IP/
```

如果你配置了域名和 HTTPS，则访问你的域名即可。

## 7. 健康检查

后端健康检查：

```bash
curl http://127.0.0.1:8000/health
```

容器日志：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml logs -f backend-api
docker compose --env-file backend/.env.server -f docker-compose.server.yml logs -f celery-worker
```

RAG-Anything 运行时检查：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml exec backend-api python scripts/check_raganything_runtime.py
```

## 8. 服务器上继续修改和调试

### 8.1 推荐方式：VS Code Remote SSH

在本机 VS Code 安装 `Remote - SSH`，连接服务器后打开项目目录：

```text
/data/AI-Tutor-end5
```

修改代码后，在服务器终端执行：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml up -d --build backend-api celery-worker frontend
```

这种方式最接近生产部署，适合最终测试。

### 8.2 热重载开发方式

如果你想像本地一样边改边看效果，启动开发 override：

```bash
docker compose --env-file backend/.env.server \
  -f docker-compose.server.yml \
  -f docker-compose.server.dev.yml \
  up -d --build backend-api celery-worker frontend-dev
```

此时：

- 前端开发地址：`http://服务器IP:3000/`
- 后端调试地址：`http://127.0.0.1:8000/health`
- 后端代码通过 bind mount 挂载，`uvicorn --reload` 会自动重启。
- 前端代码通过 bind mount 挂载，Vite 会热更新。

查看开发日志：

```bash
docker compose --env-file backend/.env.server \
  -f docker-compose.server.yml \
  -f docker-compose.server.dev.yml \
  logs -f backend-api frontend-dev celery-worker
```

停止开发栈：

```bash
docker compose --env-file backend/.env.server \
  -f docker-compose.server.yml \
  -f docker-compose.server.dev.yml \
  down
```

## 9. 推荐测试顺序

第一轮只测基础链路：

1. 打开 `http://服务器IP/`
2. 注册或登录教师账号。
3. 创建课程和班级。
4. 学生用邀请码加入课程。
5. 教师上传一个很小的 `.txt` 或 `.md` 资料。
6. 等 Celery 完成解析入库。
7. 学生端/教师端分别向 AI 提问。
8. 检查回答、引用、置信度、教师审核标记。

第二轮再测复杂资料：

1. PDF
2. DOCX
3. PPTX
4. 图片
5. 带 sidecar transcript 的音频/视频

第三轮再开启自动音视频预处理：

```env
MULTIMODAL_AUTO_PREPROCESS_ENABLED=true
ASR_PROVIDER=api
ASR_API_BASE=...
ASR_API_KEY=...
```

不要一开始就把长视频、大 PDF、大 PPT 全部上传，否则服务器会被解析任务打满。

## 10. 数据和持久化

服务器 compose 使用 Docker volumes 保存数据：

- `postgres_data`：业务数据库
- `redis_data`：Redis 数据
- `qdrant_data`：向量库
- `neo4j_data`：图数据库
- `backend_uploads`：原始上传文件
- `backend_rag_storage`：RAG-Anything/LightRAG 工作目录
- `backend_rag_output`：解析输出
- `backend_runtime_tmp`：临时处理产物

停止服务但保留数据：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml down
```

危险操作，删除全部容器和数据卷：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml down -v
```

## 11. 为什么服务器版会比本地顺畅

本地卡顿的主要原因是多个重任务同时抢资源：

- 前端 Vite 编译
- FastAPI
- Celery
- Redis
- Qdrant
- Neo4j
- MinerU / LibreOffice / ffmpeg
- RAG-Anything 图构建和 embedding

服务器 Docker 化后，这些组件被拆成独立容器，资源占用更可控；同时生产前端由 Nginx 提供静态文件，不再运行 Vite 开发服务。模型调用优先走 API，也避免本机或服务器加载大模型。

## 12. 常见问题

### 12.1 后端健康检查失败

查看日志：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml logs --tail=200 backend-api
```

重点检查：

- `.env.server` 是否缺少 API key
- PostgreSQL 是否健康
- Neo4j 密码是否和 `GRAPH_DB_PASSWORD` 一致
- Qdrant 是否启动

### 12.2 上传资料后一直 processing

查看 Celery：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml logs -f celery-worker
```

如果是大文件，先用小文件验证链路；如果是模型 API 超时，增大相关 timeout 或换更稳定的 API。

### 12.3 服务器内存不足

建议：

- 不要同时上传多个大文件。
- `RAGANYTHING_MAX_CONCURRENT_FILES=1`
- `MULTIMODAL_AUTO_PREPROCESS_ENABLED=false`
- 优先使用 API embedding、API reranker、API VLM。
- 长视频先人工生成字幕或转写文本，再作为 `.md/.txt` 上传。
