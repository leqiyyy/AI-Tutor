# AI Tutor Server Quickstart

详细部署说明见 [backend/deploy/SERVER_DEPLOYMENT.md](backend/deploy/SERVER_DEPLOYMENT.md)。

## 1. 第一次部署

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

重新登录 SSH 后：

```bash
git clone <your-repo-url> AI-Tutor-end5
cd AI-Tutor-end5
cp backend/.env.server.example backend/.env.server
nano backend/.env.server
```

至少填写：

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `GRAPH_DB_PASSWORD`
- `LLM_MODEL` / `LLM_API_BASE` / `LLM_API_KEY`
- `EXTRACT_MODEL` / `EXTRACT_API_BASE` / `EXTRACT_API_KEY`
- `EMBEDDING_MODEL` / `EMBEDDING_API_BASE` / `EMBEDDING_API_KEY` / `EMBEDDING_DIM`
- `RERANKER_API_KEY`

启动：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml up -d --build
docker compose --env-file backend/.env.server -f docker-compose.server.yml exec backend-api alembic upgrade head
docker compose --env-file backend/.env.server -f docker-compose.server.yml exec backend-api python -m app.db.seed
```

访问：

```text
http://<server-ip>/
```

## 2. 日常更新

```bash
git pull
docker compose --env-file backend/.env.server -f docker-compose.server.yml up -d --build
docker compose --env-file backend/.env.server -f docker-compose.server.yml exec backend-api alembic upgrade head
```

## 3. 查看日志

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml logs -f backend-api
docker compose --env-file backend/.env.server -f docker-compose.server.yml logs -f celery-worker
```

## 4. 服务器热重载开发

```bash
docker compose --env-file backend/.env.server \
  -f docker-compose.server.yml \
  -f docker-compose.server.dev.yml \
  up -d --build backend-api celery-worker frontend-dev
```

访问开发前端：

```text
http://<server-ip>:3000/
```

后端会以 `uvicorn --reload` 启动，前端会以 Vite dev server 启动。推荐配合 VS Code Remote SSH 修改服务器上的代码。

## 5. 停止

保留数据：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml down
```

删除全部容器和数据卷，谨慎使用：

```bash
docker compose --env-file backend/.env.server -f docker-compose.server.yml down -v
```
