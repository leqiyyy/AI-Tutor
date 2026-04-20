from pathlib import Path

from scripts.run_research_benchmark import run_offline_benchmark


def test_run_offline_benchmark_exports_reports():
    fixture_manifest = Path(__file__).resolve().parent / "fixtures" / "multimodal" / "fixture_manifest.json"
    output_dir = Path(__file__).resolve().parents[1] / "runtime_tmp" / "test_benchmark_reports"
    result = run_offline_benchmark(
        days=7,
        class_id=None,
        output_dir=output_dir,
        include_fixtures=False,
        fixture_manifest=fixture_manifest,
        questions=["Explain TCP slow start briefly."],
    )

    json_path = Path(result["report_json_path"])
    md_path = Path(result["report_md_path"])
    assert json_path.exists()
    assert md_path.exists()
    assert result["summary"]["query_count"] == 1
    assert "query_success_rate" in result["summary"]
    assert "rates" in result["rag_performance"]
    assert "summary" in result["personalization_routing"]
    assert "retrieval_eval" in result
    assert result["retrieval_eval"]["status"] == "not_scored_no_ground_truth"
    assert result["baseline_comparison"] is None


def test_run_offline_benchmark_supports_qrels_and_baseline_comparison():
    fixture_manifest = Path(__file__).resolve().parent / "fixtures" / "multimodal" / "fixture_manifest.json"
    output_dir = Path(__file__).resolve().parents[1] / "runtime_tmp" / "test_benchmark_reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    benchmark_spec = output_dir / "benchmark_spec_test.json"
    benchmark_spec.write_text(
        """{
  "questions": [
    {
      "id": "q1",
      "text": "Explain TCP slow start with one short example.",
      "expected_source_names": ["network_notes.pdf"]
    }
  ]
}""",
        encoding="utf-8",
    )

    baseline = run_offline_benchmark(
        days=7,
        class_id=None,
        output_dir=output_dir,
        include_fixtures=False,
        fixture_manifest=fixture_manifest,
        questions=["ignored when benchmark_spec_path is provided"],
        benchmark_spec_path=benchmark_spec,
        retrieval_k=5,
        baseline_report_path=None,
    )
    assert baseline["retrieval_eval"]["status"] == "scored"
    assert baseline["retrieval_eval"]["scored_queries"] == 1

    current = run_offline_benchmark(
        days=7,
        class_id=None,
        output_dir=output_dir,
        include_fixtures=False,
        fixture_manifest=fixture_manifest,
        questions=["ignored when benchmark_spec_path is provided"],
        benchmark_spec_path=benchmark_spec,
        retrieval_k=5,
        baseline_report_path=Path(baseline["report_json_path"]),
    )
    comparison = current["baseline_comparison"]
    assert comparison is not None
    assert comparison["status"] == "compared"
    assert comparison["summary"]["compared_metrics"] >= 1
    assert Path(current["comparison_json_path"]).exists()
    assert Path(current["comparison_md_path"]).exists()
