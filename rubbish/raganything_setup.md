# RAG-Anything 启用说明

## 1. 目标

当前后端已经实现了 `RAGAnythingAdapter`，但要真正启用它，需要把：

- 后端依赖
- `raganything`
- `mineru`
- LibreOffice
- LLM / Embedding 配置

放到**同一个运行环境**里。

---

## 2. 你需要准备的环境

建议直接在你要运行后端的 Conda 环境里完成以下安装。

已知你当前准备使用的环境是：

- `E:\Profession\conda_envs\AI-Tutor-End2`

### 安装后端依赖

在项目目录执行：

```powershell
Set-Location E:\all_files\project2\AI_tutor\AI-Tutor-end5\backend
python -m pip install -r requirements.txt
```

### 安装 RAG-Anything

```powershell
python -m pip install raganything
```

### 验证 RAG-Anything

```powershell
python -c "import raganything; print(raganything.__file__)"
python -c "from raganything import RAGAnything; print(RAGAnything)"
```

### 验证 MinerU

```powershell
mineru --version
```

### 验证 LibreOffice

```powershell
& "E:\A_software\LibreOffice\program\soffice.exe" --headless --version
```

---

## 3. 必须配置的环境变量

你至少需要在 `backend/.env` 中设置这些：

```env
RAG_ENGINE=raganything

LLM_API_KEY=your_llm_key
LLM_API_BASE=your_llm_base_url
LLM_MODEL=your_chat_model
LLM_WIRE_API=responses

EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_API_BASE=your_embedding_base_url
EMBEDDING_MODEL=your_embedding_model
EMBEDDING_DIM=1536

VLM_API_KEY=your_vlm_key
VLM_API_BASE=your_vlm_base_url
VLM_MODEL=your_vlm_model
VLM_WIRE_API=chat_completions

LIBREOFFICE_PATH=E:\A_software\LibreOffice\program\soffice.exe

RAGANYTHING_WORKING_DIR=./rag_storage
RAGANYTHING_OUTPUT_DIR=./rag_output
RAGANYTHING_PARSER=mineru
RAGANYTHING_PARSE_METHOD=auto
RAGANYTHING_QUERY_MODE=mix
RAGANYTHING_MAX_CONCURRENT_FILES=1
```

如果你用的是 OpenAI-compatible 平台，也可以填：

```env
LLM_API_BASE=https://your-provider.example/v1
```

你当前提供的模型组合，可以直接按这个填：

```env
RAG_ENGINE=raganything

LLM_MODEL=gpt-5.4
LLM_API_BASE=https://beecode.cc
LLM_API_KEY=你的主模型 key
LLM_WIRE_API=responses

EXTRACT_MODEL=Qwen3-235B-A22B-Instruct
EXTRACT_API_BASE=https://apis.iflow.cn/v1
EXTRACT_API_KEY=你的抽取模型 key
EXTRACT_WIRE_API=chat_completions

EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1/
EMBEDDING_API_KEY=你的 embedding key
EMBEDDING_DIM=1024

VLM_MODEL=qwen3-vl-plus
VLM_API_BASE=https://apis.iflow.cn/v1
VLM_API_KEY=你的多模态 key
VLM_WIRE_API=chat_completions

LIBREOFFICE_PATH=E:\A_software\LibreOffice\program\soffice.exe
```

对于你现在这类平台，主模型调用会按下面方式发出：

- URL: `https://beecode.cc/responses`
- Header: `x-api-key: <你的key>`

因此：

- `LLM_API_BASE` 保持 `https://beecode.cc`
- 不要再手动写成 `https://beecode.cc/v1`

当前推荐分工：

- 最终回答模型：`gpt-5.4 @ beecode.cc`
- 实体/关系抽取模型：`Qwen3-235B-A22B-Instruct @ iflow`
- 向量模型：`BAAI/bge-m3 @ SiliconFlow`
- 多模态模型：`qwen3-vl-plus @ iflow`

---

## 4. 模型职责说明

### LLM

用于：

- 组织最终回答
- 处理查询结果
- 支持教师补答回流后的问答输出

### Embedding

用于：

- 文档向量化
- 查询向量化
- 检索相似内容

---

## 5. 启动方式

确认依赖都装在同一个环境后：

```powershell
Set-Location E:\all_files\project2\AI_tutor\AI-Tutor-end5\backend
python -m app.db.seed
uvicorn app.main:app --reload
```

---

## 6. 启用成功后的重点验证

### 1. 上传文件

上传 `txt/pdf/docx/pptx` 文件，确认：

- 文件上传成功
- `kb_status` 变为 `indexed`
- 可拿到 `parse_task_id`

### 2. 检查 KB 状态

调用：

- `GET /api/v1/courses/{course_id}/kb/status`

确认：

- `status = ready`

### 3. 发起问答

调用：

- `POST /api/v1/chat/query`

确认：

- 能返回回答
- 能返回 citation
- 问答不再只是简化 fallback

---

## 7. 当前已知风险

- 如果后端运行环境和 `raganything` 安装环境不是同一个，官方 adapter 无法真正启用
- 如果缺少 `OPENAI_API_KEY` 或 embedding 配置，RAG-Anything 初始化会失败
- 如果 LibreOffice 不在 PATH 中，`doc/docx/ppt/pptx/xls/xlsx` 转换会失败
