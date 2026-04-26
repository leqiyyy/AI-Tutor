def test_admin_overview_and_model_config(client):
    login = client.post("/api/v1/auth/login", json={
        "account": "admin@aitutor.local",
        "password": "Admin123!",
        "role": "admin",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    original_model_config = client.get("/api/v1/admin/model-config", headers=headers).json()["data"]
    original_rag_storage_config = client.get("/api/v1/admin/rag-storage-config", headers=headers).json()["data"]

    try:
        overview = client.get("/api/v1/admin/overview", headers=headers)
        model_config = client.get("/api/v1/admin/model-config", headers=headers)
        model_routing = client.get("/api/v1/admin/model-routing", headers=headers)
        rag_storage_config = client.get("/api/v1/admin/rag-storage-config", headers=headers)
        rag_system_status = client.get("/api/v1/admin/rag-system-status", headers=headers)
        model_config_put = client.put("/api/v1/admin/model-config", headers=headers, json={
            "llm_provider": "mock",
            "llm_backend": "mock",
            "embedding_backend": "mock",
            "vlm_backend": "mock",
            "reranker_provider": "mock",
            "rag_engine": "raganything",
            "storage_backend": "local",
            "email_dev_mode": True,
        })
        rag_storage_config_put = client.put("/api/v1/admin/rag-storage-config", headers=headers, json={
            "rag_storage_backend": "qdrant-neo4j",
            "vector_db_provider": "qdrant",
            "vector_db_url": "http://localhost:6333",
            "vector_db_collection": "course_chunks",
            "graph_db_provider": "neo4j",
            "graph_db_url": "bolt://localhost:7687",
            "graph_db_database": "neo4j",
            "graph_db_username": "neo4j",
        })
        experiment_results = client.get("/api/v1/admin/experiment-results", headers=headers)
        rag_ablation = client.get("/api/v1/admin/rag-ablation", headers=headers)
        personalization_metrics = client.get("/api/v1/admin/personalization-routing-metrics", headers=headers)

        assert overview.status_code == 200
        assert model_config.status_code == 200
        assert model_routing.status_code == 200
        assert rag_storage_config.status_code == 200
        assert rag_system_status.status_code == 200
        assert model_config_put.status_code == 200
        assert rag_storage_config_put.status_code == 200
        assert experiment_results.status_code == 200
        assert rag_ablation.status_code == 200
        assert personalization_metrics.status_code == 200
        assert "llm_provider" in model_config.json()["data"]
        assert "generation" in model_routing.json()["data"]
        assert "rag_storage_backend" in rag_storage_config.json()["data"]
        rag_status_payload = rag_system_status.json()["data"]
        assert "overall_status" in rag_status_payload
        assert "raganything" in rag_status_payload
        assert "dependencies" in rag_status_payload
        assert "storage" in rag_status_payload
        assert "activation_state" in rag_status_payload["storage"]
        assert "vector_db" in rag_status_payload["storage"]
        assert "graph_db" in rag_status_payload["storage"]
        assert "multimodal" in rag_status_payload
        assert "ingestion" in rag_status_payload
        assert "knowledge_graph" in rag_status_payload
        assert "readiness_checks" in rag_status_payload
        assert model_config_put.json()["data"]["llm_provider"] == "mock"
        assert model_config_put.json()["data"]["llm_backend"] == "mock"
        assert model_config_put.json()["data"]["rag_engine"] == "raganything"
        assert rag_storage_config_put.json()["data"]["rag_storage_backend"] == "qdrant-neo4j"
        assert rag_storage_config_put.json()["data"]["vector_db_provider"] == "qdrant"
        assert "summary" in experiment_results.json()["data"]
        assert "model_routing" in experiment_results.json()["data"]
        assert "groups" in rag_ablation.json()["data"]
        assert "summary" in personalization_metrics.json()["data"]
    finally:
        restore_model = client.put("/api/v1/admin/model-config", headers=headers, json=original_model_config)
        restore_storage = client.put("/api/v1/admin/rag-storage-config", headers=headers, json=original_rag_storage_config)
        assert restore_model.status_code == 200
        assert restore_storage.status_code == 200
