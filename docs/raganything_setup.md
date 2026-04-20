# RAG-Anything 配置说明（兼容入口）

更新时间：2026-04-17

> 本文档保留为兼容入口，详细实施内容请优先参考：  
> `docs/rag_integration.md`

---

## 1. 快速启动

1. 安装后端依赖与 RAG-Anything 依赖。  
2. 配置 `.env` 中的 RAG/LLM/Embedding/VLM 参数。  
3. 设置 `RAG_ENGINE=raganything`。  
4. 启动后端并执行上传-索引-问答验证。

---

## 2. 关键配置

```env
RAG_ENGINE=raganything
RAGANYTHING_QUERY_MODE=mix
RAGANYTHING_PARSER=mineru
RAGANYTHING_PARSE_METHOD=auto
RAGANYTHING_MAX_CONCURRENT_FILES=1

LLM_MODEL=...
LLM_API_BASE=...
LLM_API_KEY=...

EMBEDDING_MODEL=...
EMBEDDING_API_BASE=...
EMBEDDING_API_KEY=...
EMBEDDING_DIM=...

VLM_MODEL=...
VLM_API_BASE=...
VLM_API_KEY=...
```

---

## 3. 验证建议

1. 上传文件后检查 `kb/status` 与 `tasks/{id}`。  
2. 执行 `chat/query`，确认返回 citation。  
3. 切换 `RAGANYTHING_QUERY_MODE`，确认日志与结果变化。  
4. 触发审核回流，确认回流记录可追踪。  

