def test_admin_overview_and_model_config(client):
    login = client.post("/api/v1/auth/login", json={
        "account": "admin@aitutor.local",
        "password": "Admin123!",
        "role": "admin",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    overview = client.get("/api/v1/admin/overview", headers=headers)
    model_config = client.get("/api/v1/admin/model-config", headers=headers)
    model_routing = client.get("/api/v1/admin/model-routing", headers=headers)
    model_config_put = client.put("/api/v1/admin/model-config", headers=headers, json={
        "llm_provider": "mock",
        "llm_backend": "mock",
        "embedding_backend": "mock",
        "vlm_backend": "mock",
        "reranker_provider": "mock",
        "rag_engine": "mock",
        "storage_backend": "local",
        "email_dev_mode": True,
    })
    experiment_results = client.get("/api/v1/admin/experiment-results", headers=headers)
    rag_ablation = client.get("/api/v1/admin/rag-ablation", headers=headers)
    personalization_metrics = client.get("/api/v1/admin/personalization-routing-metrics", headers=headers)

    assert overview.status_code == 200
    assert model_config.status_code == 200
    assert model_routing.status_code == 200
    assert model_config_put.status_code == 200
    assert experiment_results.status_code == 200
    assert rag_ablation.status_code == 200
    assert personalization_metrics.status_code == 200
    assert "llm_provider" in model_config.json()["data"]
    assert "generation" in model_routing.json()["data"]
    assert model_config_put.json()["data"]["llm_provider"] == "mock"
    assert model_config_put.json()["data"]["llm_backend"] == "mock"
    assert "summary" in experiment_results.json()["data"]
    assert "model_routing" in experiment_results.json()["data"]
    assert "groups" in rag_ablation.json()["data"]
    assert "summary" in personalization_metrics.json()["data"]
