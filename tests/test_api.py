from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "RAG Safety Checker API"
    assert data["status"] == "running"
    assert "llm_provider" in data

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "message" in data
    assert "supabase_configured" in data
    assert "llm_configured" in data
    assert "llm_provider" in data
    assert "llm_model" in data
    assert data["llm_provider"] == "groq"
