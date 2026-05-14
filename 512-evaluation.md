# 512 Evaluation Summary

> 本文档仅依据当前仓库与服务器中的实际运行产物整理，未读取 `paper.md`、`paper2.md`、`paper3.md`、`paper4.md`、`paper5.md`、`paper6.md` 等论文草稿文件。主要来源包括 `cybersecurity_rag_dataset*.json`、`backend/runtime_tmp/experiment_reports/`、`backend/runtime_tmp/429_core_chain_reports/`、`backend/runtime_tmp/final_*.csv`、`backend/tests/` 以及最近在 Docker 容器内执行过的测试结果。

## 1. 已使用的数据集与评估对象

| 编号 | 数据集/评估对象 | 文件或产物路径 | 规模 | 覆盖内容 | 当前用途 | 结果状态 |
|---|---|---:|---:|---|---|---|
| D1 | Cybersecurity RAG Dataset v1 | `cybersecurity_rag_dataset.json` | 85 题 | 文本、混合、多模态、不可回答、开放问答、噪声鲁棒等 | LightRAG/RAG-Anything 多模式 HTTP benchmark | 已完成多模式结果汇总 |
| D2 | Cybersecurity Benchmark Spec v1 | `backend/runtime_tmp/cybersecurity_benchmark_spec.json` | 85 题 | 为 D1 补充 expected source/doc/chunk，用于 Recall/MRR/nDCG | 检索指标评分 | 已用于 v1 多模式评分 |
| D3 | Cybersecurity RAG Dataset v2 | `cybersecurity_rag_dataset_v2.json` | 140 题 | 增加图谱关系、图片问题、跨文件综合、表格/公式问题等 | 扩展版检索与切片分析 | 已用于 naive v2 与 BM25 基线 |
| D4 | Cybersecurity Benchmark Spec v2 | `backend/runtime_tmp/cybersecurity_benchmark_spec_v2.json` | 140 题 | 为 D3 补充 expected source/doc/chunk | 扩展版检索指标评分 | 已用于 v2 scoring |
| D5 | 429 核心链路测试资料 | `backend/runtime_tmp/429_core_chain_reports/*.json` | 2 次完整链路运行 | Markdown 表格/公式 + 图片上传、解析、检索、图谱、AI 答疑、教师审核回流 | 端到端功能验证 | 2/2 次 passed |
| D6 | 实际知识库导出产物 | `backend/runtime_tmp/final_chunks.csv` 等 | 1932 chunks、708 entities、1616 relations | 多模态描述、实体、关系、source span/provenance | 展示知识库构建与图谱投影结果 | 已有可展示表 |
| D7 | 后端功能回归测试 | `backend/tests/` | 多个 API/服务测试文件 | 登录注册、课程、KB、RAG、推荐、通知、指标等 | 功能正确性回归 | 认证子集当前 4 passed；完整套件本次未纳入结果 |

## 2. 数据集结构

| 数据集 | 题量 | 题型分布 | 模态分布 | 难度分布 | 可回答性 |
|---|---:|---|---|---|---|
| D1: `cybersecurity_rag_dataset.json` | 85 | fact_extraction 36；comparison 12；multi_modal 9；multi_hop_reasoning 8；unanswerable 8；open_ended 7；noise_resistant 5 | text 73；mixed 8；image 4 | medium 40；hard 24；easy 21 | answerable 77；unanswerable 8 |
| D2: `cybersecurity_benchmark_spec.json` | 85 | fact_extraction 36；comparison 12；multi_modal 9；multi_hop_reasoning 8；unanswerable 8；open_ended 7；noise_resistant 5 | 通过 expected source/doc/chunk 评分 | 同 D1 | 77 个可评分检索题，8 个不可回答题 |
| D3: `cybersecurity_rag_dataset_v2.json` | 140 | fact_extraction 53；comparison 18；unanswerable 12；multi_modal 10；graph_relation 10；multi_hop_reasoning 9；image_question 9；open_ended 7；noise_resistant 5；cross_file_synthesis 4；concept/table/formula 各 1 | text 115；image 12；mixed 11；table 1；formula 1 | medium 68；hard 40；easy 32 | answerable 128；unanswerable 12 |
| D4: `cybersecurity_benchmark_spec_v2.json` | 140 | 同 D3 | 通过 expected source/doc/chunk 评分 | 同 D3 | 128 个可评分检索题，12 个不可回答题 |

## 3. RAG 检索与回答 Benchmark 结果

说明：以下结果来自 `backend/runtime_tmp/experiment_reports/cybersecurity_*_http/*corrected_summary.json` 与 `slice_analysis_v2_dataset.json`。`success_count` 表示 HTTP/API 调用成功，不等同于答案完全正确；`citation_valid_rate` 表示返回引用在当前评估脚本下可被识别为有效。`mix` 与 `naive` 的 success_rate 字段在 corrected summary 中未显式写出，但 `success_count/query_count = 85/85`。

| 模式 | 数据集 | 问题数 | 可评分题数 | API 成功 | Recall@5 | MRR | nDCG@5 | 引用有效率 | 平均时延(s) | P95 时延(s) | 平均来源数 | 平均置信度 | 待审核数 | zero-hit 数 | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| naive | D1 | 85 | 77 | 85/85 | 0.7662 | 0.8424 | 0.7100 | 1.0000 | 9.73 | 27.26 | 4.09 | 0.7374 | 25 | 1 | v1 中检索指标最高且速度较快，但置信度偏低、待审核较多 |
| mix | D1 | 85 | 77 | 85/85 | 0.6840 | 0.8251 | 0.6562 | 1.0000 | 100.48 | 152.28 | 4.11 | 0.7565 | 20 | 3 | 召回明显优于 local/hybrid/global，但延迟最高 |
| local | D1 | 85 | 77 | 85/85 | 0.4372 | 0.4608 | 0.3955 | 1.0000 | 11.68 | 67.83 | 4.42 | 0.8642 | 6 | 33 | 置信度高、待审核少，但检索召回低于 naive/mix |
| hybrid | D1 | 85 | 77 | 85/85 | 0.4113 | 0.4177 | 0.3702 | 1.0000 | 13.59 | 56.85 | 4.62 | 0.8673 | 9 | 38 | 召回略低于 local，高于 global |
| global | D1 | 85 | 77 | 85/85 | 0.3442 | 0.3550 | 0.3086 | 1.0000 | 13.50 | 82.70 | 4.58 | 0.8669 | 12 | 43 | v1 中检索表现最弱，zero-hit 较多 |
| naive v2 | D3 | 140 | 128 | 140/140 | 0.6094 | 0.6151 | 0.5499 | 未单独汇总 | 17.45 | 未单独汇总 | 2.79 | 未单独汇总 | 未单独汇总 | 未单独汇总 | 扩展集上指标下降，说明 v2 更难，尤其包含图谱/跨文件/多模态问题 |

## 4. Raw Text BM25 基线

来源：`backend/runtime_tmp/experiment_reports/raw_text_bm25_v2.json`。该实验是检索基线，不经过完整生成链路；因此延迟与完整 HTTP RAG benchmark 不可直接等价比较。

| 基线 | 数据集 | 构建文件数 | 构建 chunks | 平均 chunk tokens | 问题数 | 可评分题数 | Recall@K | MRR | nDCG@K | 平均检索时延(ms) | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| raw_text_bm25 | D3 | 22 | 114 | 560.68 | 140 | 128 | 0.6198 | 0.5952 | 0.5552 | 4.99 | 文本检索基线在 v2 上与 naive v2 接近，但对图片/公式/表格模态支持弱 |

| BM25 切片 | 问题数 | 可评分题数 | Recall@K | MRR | nDCG@K | 平均时延(ms) | 观察 |
|---|---:|---:|---:|---:|---:|---:|---|
| text | 115 | 103 | 0.7314 | 未完整展开 | 未完整展开 | 约 5ms | 文本问题表现最好 |
| image | 12 | 12 | 0.0833 | 0.0278 | 0.0417 | 5.16 | 纯文本 BM25 基线几乎不能处理图片证据 |
| mixed | 11 | 11 | 0.2727 | 0.3212 | 0.2434 | 5.49 | 混合证据召回不足 |
| formula | 1 | 1 | 0.0000 | 0.0000 | 0.0000 | 5.09 | 公式问题未命中 |
| table | 1 | 1 | 0.0000 | 0.0000 | 0.0000 | 4.89 | 表格问题未命中 |

## 5. 题型/模态切片结果摘要

来源：`slice_analysis_v2_dataset.json`。这里只展示可直接进入论文/报告的典型切片，完整切片可继续从 JSON 展开。

| 模式 | 切片 | 问题数 | Recall@5 | MRR | nDCG@5 | 平均时延(s) | 观察 |
|---|---|---:|---:|---:|---:|---:|---|
| naive | image | 4 | 0.7500 | 0.5833 | 0.6250 | 16.99 | v1 图片题命中较好 |
| mix | image | 4 | 0.7500 | 0.4167 | 0.5000 | 89.93 | mix 能命中图片题，但延迟高 |
| local | mixed | 8 | 0.6667 | 0.4521 | 0.4908 | 4.42 | local 在 v1 mixed 切片优于 hybrid/global |
| hybrid | image | 4 | 0.7500 | 0.4583 | 0.5327 | 3.80 | hybrid 图片切片比 global 明显好 |
| global | image | 4 | 0.0000 | 0.0000 | 0.0000 | 2.51 | global 对图片证据召回失败 |
| naive v2 | image | 12 | 0.8333 | 0.6139 | 0.6681 | 34.83 | v2 图片切片在 naive 下仍能召回，但速度较慢 |
| naive v2 | formula | 1 | 0.0000 | 0.0000 | 0.0000 | 9.65 | 公式链路仍需补强 |
| naive v2 | unanswerable | 12 | N/A | N/A | N/A | 8.44 | refusal_accuracy 仅 0.1667，拒答能力需要改进 |

## 6. 429 核心链路端到端验证

来源：`backend/runtime_tmp/429_core_chain_reports/verify_429_core_chain_0134999d.json`、`verify_429_core_chain_61063b80.json`。

| 运行标识 | 时间 | 总状态 | 覆盖资料 | 资料解析结果 | 覆盖链路 | 结论 |
|---|---|---|---|---|---|---|
| 61063b80 | 2026-04-29T10:04:37Z | passed | Markdown 表格/公式 + PNG 图片 | Markdown: table/formula/text，3 chunks；Image: image/text，2 chunks | 教师登录、学生登录、教师建班、学生入班、资料上传、资料分析、KB 状态、学生检索、图谱构建、学生/教师 AI 引用答疑、学生反馈、教师审核、审核同步、学生追问 | 核心教学闭环通过 |
| 0134999d | 2026-04-29T13:27:16Z | passed | Markdown 表格/公式 + PNG 图片 | Markdown: table/formula/text，3 chunks；Image: image/text，1 chunk | 同上 | 第二次核心链路复验通过 |

可展示的链路检查表：

| 检查项 | 两次运行结果 |
|---|---|
| teacher/student login | passed |
| teacher create class + student join class | passed |
| Markdown upload + analysis | passed |
| Image upload + analysis | passed |
| KB status available | passed |
| student search retrieves uploaded chunks | passed |
| graph constructed with provenance and summaries | passed |
| student/teacher AI chat with citations | passed |
| feedback creates review signal | passed |
| teacher review resolved and synced | passed |
| student follow-up after review | passed |

## 7. 知识库构建与图谱导出产物

来源：`backend/runtime_tmp/final_chunks.csv`、`final_entities.csv`、`final_relations.csv`。

| 导出文件 | 数据行数 | 字段 | 可展示结果 | 观察 |
|---|---:|---|---|---|
| `final_chunks.csv` | 1932 | file_name, chunk_index, chunk_id, text | chunk 样例表、按文件 chunk 统计表 | 图片 chunk 中已经出现 VLM 英文结构描述，如包过滤模型、状态包检查流程、VPN 图等 |
| `final_entities.csv` | 708 | file_name, name, entity_type, description, confidence | 实体类型与置信度表 | 已包含中文概念实体，也存在 table/artifact 类英文节点，需要在前端展示时继续筛选 |
| `final_relations.csv` | 1616 | source_file, source, relation_type, target, weight, confidence, source_span | 关系三元组与 provenance 表 | source_span 中包含 material_id、pages、file_path、source_id、keywords、evidence，可用于溯源 |

## 8. 功能回归测试情况

| 测试集合 | 执行方式/来源 | 范围 | 最近结果 | 说明 |
|---|---|---|---|---|
| 认证与课程子集 | Docker 容器内隔离 SQLite 执行：`pytest tests/test_auth_security.py tests/test_auth_and_courses.py -q` | 注册验证码、登录、忘记密码、已登录改密、登录失败锁定、课程基本流 | 4 passed | 这是最近一次明确完成的当前代码验证 |
| 完整后端测试套件 | Docker 容器内尝试执行：`pytest tests -q` | backend/tests 全量 | 本次未纳入最终结果 | 执行到一批用例后进入慢速 RAG/多模态部分，耗时较长，已停止，避免影响本次汇总 |
| 历史后端单元/集成测试 | `backend/tests/` 与 `__pycache__`、历史执行记录 | admin、auth、course、KB、chat、RAG、reranker、metrics、recommendation 等 | 存在大量已执行痕迹 | 可作为“测试覆盖范围”说明，但本文不把未重新拿到完整日志的历史 pass 数当作最新结果 |
| 前端构建测试 | `cd frontend && npm run build` | Vite 生产构建、路由懒加载、类型编译链路 | build passed | 最近已成功构建并重建 Docker 前端镜像 |
| 服务健康检查 | Docker 容器与 `/health` | frontend、backend-api、celery、db、redis、qdrant、neo4j、minio | backend-api healthy；`/health` 200 | 当前服务处于可访问状态 |

## 9. 目前可以放入论文/报告的结果表

| 表名建议 | 数据来源 | 推荐展示字段 | 是否已具备 |
|---|---|---|---|
| 数据集统计表 | D1-D4 | 题量、题型、模态、难度、可回答性 | 已具备 |
| RAG 模式总体效果对比表 | corrected summary | 模式、Recall@5、MRR、nDCG@5、时延、来源数、置信度、zero-hit | 已具备 |
| RAG 模式效率对比表 | corrected summary | 平均时延、P95、最大时延、平均来源数 | 已具备 |
| 模态切片效果表 | slice analysis | text/image/mixed/table/formula 的 Recall/MRR/nDCG | 已具备，公式/表格样本较少需注明 |
| 不可回答问题拒答能力表 | slice analysis | unanswerable 数量、refusal_accuracy | 已具备，结果偏弱 |
| BM25 基线对比表 | raw_text_bm25_v2 | Recall@K、MRR、nDCG@K、平均检索时延 | 已具备 |
| 端到端核心链路测试表 | 429 reports | 登录、建班、入班、上传、解析、检索、图谱、答疑、审核回流 | 已具备 |
| 知识库产物规模表 | final CSV | chunks/entities/relations 数量与字段 | 已具备 |
| 图谱溯源样例表 | final_relations.csv | source、relation、target、source_span | 已具备 |
| 多模态 chunk 描述样例表 | final_chunks.csv | 图片名、chunk_id、VLM description 摘要 | 已具备 |

## 10. 结果解读与待补强点

| 维度 | 当前结论 | 证据 | 后续建议 |
|---|---|---|---|
| 新增资料是否可入库 | 可以，429 核心链路两次 passed，Markdown/图片均 indexed | `429_core_chain_reports` | 后续可补 PDF/Office 的同类端到端报告 |
| 引用有效性 | v1 多模式 corrected summary 中 citation_valid_rate 为 1.0 | corrected summary | 需要继续区分“引用存在”与“引用是否语义最优” |
| 检索效果 | naive/mix 在 v1 上明显优于 local/hybrid/global；v2 上 naive 指标下降 | benchmark summaries | 应继续扩大 v2 下 mix/hybrid/local/global 的完整对比 |
| 多模态能力 | 图片切片在 naive/mix/local/hybrid 下可命中，但 raw BM25 对图片几乎无效 | slice analysis + BM25 baseline | 说明 VLM 描述/多模态入库有价值；公式/表格样本量需增加 |
| 拒答能力 | unanswerable refusal_accuracy 仅 0.125 或 0.1667 | slice analysis | 需要加强证据不足时的拒答策略 |
| 延迟 | mix 召回较好但平均 100.48s，显著慢于 naive/local/hybrid/global | corrected summary | 需要优化 mix 模式或按意图路由选择模式 |
| 图谱展示质量 | 关系和实体已可导出，但存在 table/artifact 类节点 | final_entities/final_relations | 前端展示应继续过滤材料/表格结构类 artifact 节点 |

