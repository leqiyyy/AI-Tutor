# 评测数据集构建操作教程

本文档说明如何为 AI 助教系统构建毕业论文实验评测数据，包括资料准备、问题生成、人工标注、JSON 文件编写、LLM 辅助构建和后续评估运行。

## 1. 你最终要构建什么

最终需要得到两类东西：

1. 一批已经上传到系统知识库的课程资料。
2. 一个评测问题 JSON 文件，用于自动运行 benchmark。

评测问题 JSON 文件示例：

```json
{
  "questions": [
    {
      "id": "fact_001",
      "type": "事实查询",
      "text": "TCP 慢启动的主要作用是什么？",
      "expected_source_names": ["network_notes.pdf"],
      "expected_chunk_ids": [],
      "expected_doc_ids": []
    }
  ]
}
```

其中最重要的是：

- `text`：要问系统的问题。
- `expected_source_names`：这个问题的标准来源文件名。

自动评估脚本会用 `expected_source_names` 和系统回答返回的 `sources` 对比，从而计算 Recall@K、nDCG@K 和 MRR。

## 2. 第一步：选择评测资料

建议先做一个小而完整的数据集，不要一开始就做太大。

推荐规模：

| 资料类型 | 建议数量 | 目的 |
|---|---:|---|
| PDF 讲义或教材 | 2-3 个 | 测试基础文本 RAG |
| PPT 课件 | 2-5 个 | 测试课件解析 |
| 含表格的资料 | 1-2 个 | 测试表格理解 |
| 含图片/流程图的资料 | 1-2 个 | 测试多模态能力 |

资料来源可以是：

1. OpenStax 开放教材。
2. MIT OpenCourseWare 公开课资料。
3. 学校课程资料。
4. 自己整理的 Markdown、Word 或 PDF 讲义。

建议你把资料文件名改得清楚，例如：

```text
network_notes.pdf
subnetting_handbook.pdf
experiment_results.pdf
data_pipeline_slides.pdf
```

文件名要稳定，因为后续 JSON 里的 `expected_source_names` 要和系统返回的来源文件名对应。

## 3. 第二步：上传资料并确认索引完成

可以通过前端上传，也可以通过后端 API 上传。对于刚开始构建数据集，建议先用前端上传，方便确认资料是否成功进入课程知识库。

上传后需要确认：

1. 文件出现在课程资料列表中。
2. 解析任务完成。
3. 知识库状态正常。
4. 针对资料中的简单问题，系统能返回 citation 或 sources。

只有资料已经完成解析和索引，后续自动评估才有意义。

## 4. 第三步：设计问题类型

建议至少覆盖以下问题类型：

| 类型 | 建议数量 | 示例 |
|---|---:|---|
| 事实查询 | 10-20 | TCP 慢启动的主要作用是什么？ |
| 概念解释 | 10-20 | 什么是 CIDR？ |
| 对比分析 | 5-10 | Go-Back-N 和 Selective Repeat 有什么区别？ |
| 推理应用 | 5-10 | 如果子网前缀是 /24，可用主机数是多少？ |
| 跨章节综合 | 5-10 | TCP 可靠传输涉及哪些机制？ |
| 表格理解 | 5-10 | 表格中准确率最高的方法是哪一个？ |
| 多模态问题 | 5-10 | 流程图中数据预处理之后的步骤是什么？ |

本科论文建议最终做到 50-100 个问题。时间紧的话，先做 30-50 个也可以。

## 5. 第四步：人工构建问题

最稳妥的方式是人工阅读资料，每看到一个明确知识点，就写一个问题，并记录它来自哪个文件。

建议使用这样的工作表：

| id | type | question | source_file | page_or_section | note |
|---|---|---|---|---|---|
| fact_001 | 事实查询 | TCP 慢启动的作用是什么？ | network_notes.pdf | p12 | 定义题 |
| table_001 | 表格理解 | 哪种算法准确率最高？ | experiment_results.pdf | p5 | 表格题 |

其中 `page_or_section` 和 `note` 不一定写入 benchmark JSON，但人工评分和论文分析时会很有用。

## 6. 第五步：结合 LLM 生成候选问题

LLM 很适合帮助你批量生成候选问题，但不能完全替代人工标注。推荐流程是：

1. 你复制某一节课程资料内容给 LLM。
2. 让 LLM 生成问题、问题类型、参考答案和来源文件名。
3. 你人工检查问题是否真的能从资料中回答。
4. 删除太泛、太难、无法定位来源的问题。
5. 把保留下来的问题写入 JSON。

### 6.1 LLM 生成问题提示词

可以直接使用下面的提示词：

```text
你现在是毕业论文实验评测数据集构建助手。

我会给你一段课程资料内容和资料文件名。请你基于资料内容生成适合 RAG 系统评测的问题。

要求：
1. 问题必须能从给定资料中回答，不能依赖外部知识。
2. 每个问题都要标注问题类型。
3. 问题类型从以下类别选择：事实查询、概念解释、对比分析、推理应用、跨章节综合、表格理解、多模态资料。
4. 每个问题都要给出 expected_source_names，值必须是我提供的资料文件名。
5. 每个问题给出简短参考答案，方便我人工审核。
6. 输出 JSON 数组，不要输出多余解释。

资料文件名：
network_notes.pdf

资料内容：
【在这里粘贴课程资料片段】

请生成 10 个评测问题。
```

期望输出：

```json
[
  {
    "id": "fact_001",
    "type": "事实查询",
    "text": "TCP 慢启动的主要作用是什么？",
    "expected_source_names": ["network_notes.pdf"],
    "reference_answer": "TCP 慢启动用于在连接开始时逐步增加拥塞窗口，避免一开始发送过多数据造成网络拥塞。"
  }
]
```

### 6.2 LLM 生成表格题提示词

如果资料里有表格，可以使用：

```text
下面是一段从课程资料中提取的表格内容。请基于表格生成 8 个用于测试 RAG 表格理解能力的问题。

要求：
1. 问题必须依赖表格中的行列关系、数值比较或字段对应关系。
2. 不要生成只靠常识就能回答的问题。
3. 每个问题给出 expected_source_names。
4. 每个问题给出参考答案和需要用到的表格字段。
5. 输出 JSON 数组。

资料文件名：
experiment_results.pdf

表格内容：
【在这里粘贴表格】
```

### 6.3 LLM 生成多模态问题提示词

如果你有课件截图、流程图、图片说明，可以先把图片内容人工简述或用 VLM 描述，再让 LLM 生成问题：

```text
下面是某张课程课件截图的内容描述。请生成 5 个用于测试多模态资料问答能力的问题。

要求：
1. 问题必须依赖截图中的流程、图示、公式或文字。
2. 问题不能只依赖普通文本常识。
3. 每个问题给出 expected_source_names。
4. 每个问题给出参考答案。
5. 输出 JSON 数组。

资料文件名：
data_pipeline_slides.pdf

截图内容描述：
【例如：图中展示了数据处理流程，依次为数据采集、数据清洗、特征提取、模型训练、结果评估】
```

## 7. 第六步：人工审核 LLM 生成的问题

LLM 生成后必须人工检查。重点检查：

| 检查项 | 说明 |
|---|---|
| 是否能从资料中回答 | 不能依赖外部知识 |
| 来源文件是否正确 | `expected_source_names` 要写对 |
| 问题是否清楚 | 避免过于宽泛 |
| 是否有唯一或较明确答案 | 便于评分 |
| 类型是否覆盖全面 | 不要全是定义题 |

对于不能明确定位来源的问题，建议删除，不要勉强保留。

## 8. 第七步：整理成 benchmark JSON

最终 benchmark 文件建议放在：

```text
backend/tests/fixtures/benchmark/thesis_benchmark_spec.json
```

可以参考示例文件：

```text
backend/tests/fixtures/benchmark/thesis_benchmark_spec.example.json
```

注意：实际运行时可以复制 example 文件为正式文件：

```bash
cp backend/tests/fixtures/benchmark/thesis_benchmark_spec.example.json \
   backend/tests/fixtures/benchmark/thesis_benchmark_spec.json
```

然后把里面的问题和文件名改成你的真实资料。

## 9. 第八步：运行自动评估

在后端目录运行：

```bash
cd backend
python scripts/run_research_benchmark.py \
  --days 30 \
  --benchmark-spec tests/fixtures/benchmark/thesis_benchmark_spec.json \
  --retrieval-k 5
```

输出目录：

```text
backend/runtime_tmp/experiment_reports/
```

输出包括：

1. JSON 报告。
2. Markdown 报告。
3. Recall@K。
4. nDCG@K。
5. MRR。
6. 查询成功率。
7. RAG 主链成功率。
8. fallback 率。
9. 平均置信度和延迟。

## 10. 第九步：人工评分生成质量

自动脚本主要评估检索质量。生成质量建议人工评分。

评分表：

| 问题编号 | 方法 | 正确性 | 完整性 | 相关性 | 可读性 | 溯源性 | 是否幻觉 |
|---|---|---:|---:|---:|---:|---:|---|
| fact_001 | Full System | 5 | 4 | 5 | 5 | 5 | 否 |

评分建议：

| 指标 | 说明 |
|---|---|
| 正确性 | 是否符合资料内容 |
| 完整性 | 是否覆盖关键点 |
| 相关性 | 是否紧扣问题 |
| 可读性 | 是否适合学生理解 |
| 溯源性 | 是否能对应引用资料 |
| 是否幻觉 | 是否出现资料中没有的错误信息 |

## 11. 第十步：构建 baseline 数据

建议至少构建三组：

| 组别 | 说明 |
|---|---|
| LLM Only | 不使用课程资料，直接生成 |
| Text-only RAG | 普通文本 RAG，只抽文本 |
| Full System | 当前完整系统 |

如果时间充足，再加：

| 组别 | 说明 |
|---|---|
| Vector RAG | 只用向量检索 |
| Vector RAG + Reranker | 加重排序 |
| Full System + 多模态 | 完整系统处理复杂资料 |

每组都使用同一份 `thesis_benchmark_spec.json`，这样结果才可比。

## 12. 最推荐的最小流程

如果你现在要马上开始，按这个顺序做：

1. 选 3 个资料文件：一个普通 PDF、一个含表格 PDF、一个 PPT 或截图资料。
2. 上传到系统并等待索引完成。
3. 每个资料先人工写 10 个问题，共 30 个。
4. 用 LLM 再辅助扩展到 50 个问题。
5. 人工审核问题和来源文件。
6. 保存为 `backend/tests/fixtures/benchmark/thesis_benchmark_spec.json`。
7. 运行 `run_research_benchmark.py`。
8. 导出自动指标。
9. 人工评分生成质量。
10. 对比 LLM Only、Text-only RAG 和 Full System。

这样就能得到一套比较完整、能写进毕业论文的实验数据。
