# 实验评估报告模板（AI助教后端）

更新时间：2026-04-17  
用途：记录后端 RAG/推荐/反馈优化实验结果，用于毕设与迭代决策。

---

## 1. 实验基本信息

- 实验编号：
- 实验日期：
- 执行人：
- 分支/版本：
- 关联任务：

---

## 2. 实验目标

本次实验要验证的问题：

1.  
2.  
3.  

成功判定标准：

1.  
2.  

---

## 3. 实验环境

### 3.1 系统环境

- OS：
- Python：
- 数据库：
- Redis/Celery：
- 模型部署方式（API/本地）：

### 3.2 数据范围

- 课程数量：
- 文件数量：
- 文件类型分布（PDF/PPT/图片/音视频）：
- 问答测试集规模：

---

## 4. 实验配置

### 4.1 检索配置

- RAG 引擎：
- Query mode：
- TopK：
- Reranker：

### 4.2 模型配置

- LLM：
- Embedding：
- VLM：
- ASR（如有）：

### 4.3 反馈与推荐配置

- 反馈阈值：
- 推荐策略版本：

---

## 5. 指标结果

### 5.1 检索指标

| 指标 | 基线 | 本次 | 变化 |
|---|---:|---:|---:|
| Recall@5 |  |  |  |
| nDCG@10 |  |  |  |
| MRR |  |  |  |

### 5.2 生成与溯源指标

| 指标 | 基线 | 本次 | 变化 |
|---|---:|---:|---:|
| 引用可追溯率 |  |  |  |
| 幻觉率 |  |  |  |
| 平均响应时间(ms) |  |  |  |

### 5.3 反馈与推荐指标

| 指标 | 基线 | 本次 | 变化 |
|---|---:|---:|---:|
| 点踩率 |  |  |  |
| 转人工率 |  |  |  |
| 推荐点击率(CTR) |  |  |  |
| 推荐满意度 |  |  |  |

---

## 6. 结果分析

### 6.1 有效改进点

1.  
2.  

### 6.2 退化点/异常点

1.  
2.  

### 6.3 根因分析

1.  
2.  

---

## 7. 结论与下一步

### 7.1 实验结论

- 是否达到目标：是 / 否
- 是否建议上线：是 / 否

### 7.2 下一步动作

1.  
2.  
3.  

---

## 8. 附录

- 关键日志路径：
- 关键测试脚本：
- 对比图/表：
- 相关 PR/提交：


## 9. Offline Benchmark Runner (S6 Stage 1)

Script:
- `backend/scripts/run_research_benchmark.py`

Purpose:
- Execute a deterministic offline benchmark against backend APIs.
- Export experiment artifacts as JSON + Markdown for research tracking.

Default behavior:
- Seeds baseline data.
- Runs a small fixed query set.
- Collects snapshots from admin metrics APIs:
  - `/admin/rag-performance`
  - `/admin/rag-ablation`
  - `/admin/personalization-routing-metrics`
  - `/admin/experiment-results`
- Writes reports to `backend/runtime_tmp/experiment_reports/`.

Optional multimodal regression check:
- Use `--include-fixtures` to run upload/analysis checks based on:
  - `backend/tests/fixtures/multimodal/fixture_manifest.json`

Examples:
- `Set-Location backend; python scripts/run_research_benchmark.py --days 7`
- `Set-Location backend; python scripts/run_research_benchmark.py --days 14 --include-fixtures`

## 10. Offline Benchmark Stage 2 (Scoring + Baseline Comparison)

New script options:
- `--benchmark-spec <path>`: load benchmark questions and expected source/chunk/doc ids.
- `--retrieval-k <int>`: control k for Recall@k and nDCG@k computation.
- `--baseline-report <path>`: compare current report against a previous benchmark JSON report.

Scoring outputs:
- `retrieval_eval.status`
  - `scored`
  - `not_scored_no_ground_truth`
- `retrieval_eval.recall_at_k`
- `retrieval_eval.ndcg_at_k`
- `retrieval_eval.mrr`
- `retrieval_eval.details[]` per-question breakdown

Baseline comparison outputs:
- `baseline_comparison.status`
- `baseline_comparison.summary` (improved/regressed/unchanged counts)
- `baseline_comparison.metrics[]` (baseline/current/delta/trend)
- Extra exported files (when baseline is provided):
  - `benchmark_compare_<run_id>.json`
  - `benchmark_compare_<run_id>.md`

Template file:
- `backend/tests/fixtures/benchmark/benchmark_spec_template.json`

Example weekly workflow:
1. Run baseline week:
   - `Set-Location backend; python scripts/run_research_benchmark.py --days 7 --benchmark-spec tests/fixtures/benchmark/benchmark_spec_template.json`
2. Run current week and compare to baseline:
   - `Set-Location backend; python scripts/run_research_benchmark.py --days 7 --benchmark-spec tests/fixtures/benchmark/benchmark_spec_template.json --baseline-report <baseline_json_path>`
