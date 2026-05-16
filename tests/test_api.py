"""Integration tests — mocked services, no Ollama or Whisper needed.
Run: pytest tests/test_api.py -v
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.models import Base
from backend.schemas.expense import ExpenseCreate, ExpenseCategory, PaymentMethod, TransactionType


def _fake_result(success=True, amount=200.0, category="Food", tx_type="expense"):
    expense = ExpenseCreate(
        amount=amount, currency="INR", category=ExpenseCategory(category),
        description="test", date=date.today(),
        payment_method=PaymentMethod.UNKNOWN,
        transaction_type=TransactionType(tx_type),
        raw_text="test",
    ) if success else None
    return {
        "success": success, "transcript": "test input",
        "stt_metadata": {"language": "en", "language_probability": 0.99},
        "raw_extraction": {"amount": amount, "category": category} if success else None,
        "expense": expense, "error": None if success else "no transaction found",
        "retry_count": 0,
    }


@pytest.fixture(scope="module")
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)

    app.state.session_factory = factory
    app.state.graph = MagicMock()
    app.state.llm = MagicMock()
    app.state.stt = MagicMock()
    app.state.split_parser = MagicMock()
    app.state.insights_engine = MagicMock()
    app.state.active_model_id = "mistral:7b"
    app.state.cfg = MagicMock()
    app.state.cfg.model.model_id = "mistral:7b"
    app.state.cfg.whisper.model_size = "small"

    return TestClient(app)


class TestHealth:
    def test_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestVoiceText:
    def test_success(self, client):
        client.app.state.graph.invoke = MagicMock(return_value=_fake_result(True, 200))
        r = client.post("/api/voice/text", data={"text": "spent 200 on groceries"})
        assert r.status_code == 200
        assert r.json()["expense"]["amount"] == 200.0

    def test_extraction_failure(self, client):
        client.app.state.graph.invoke = MagicMock(return_value=_fake_result(False))
        r = client.post("/api/voice/text", data={"text": "hello"})
        assert r.status_code == 422


class TestExpenses:
    def _create(self, client, amount=500.0, category="Food"):
        client.app.state.graph.invoke = MagicMock(return_value=_fake_result(True, amount, category))
        r = client.post("/api/voice/text", data={"text": f"spent {amount}"})
        assert r.status_code == 200
        return r.json()["expense"]

    def test_list_empty(self, client):
        r = client.get("/api/expenses/")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_create_list(self, client):
        self._create(client, 200.0)
        r = client.get("/api/expenses/")
        assert len(r.json()) >= 1

    def test_get_by_id(self, client):
        exp = self._create(client, 300.0)
        r = client.get(f"/api/expenses/{exp['id']}")
        assert r.status_code == 200 and r.json()["amount"] == 300.0

    def test_not_found(self, client):
        r = client.get("/api/expenses/99999")
        assert r.status_code == 404

    def test_delete(self, client):
        exp = self._create(client)
        r = client.delete(f"/api/expenses/{exp['id']}")
        assert r.status_code == 200
        assert client.get(f"/api/expenses/{exp['id']}").status_code == 404


class TestAnalytics:
    def test_summary(self, client):
        r = client.get("/api/analytics/summary")
        assert r.status_code == 200
        body = r.json()
        assert "total_expense" in body and "total_income" in body and "net" in body

    def test_categories(self, client):
        r = client.get("/api/analytics/categories")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_export_csv(self, client):
        r = client.get("/api/analytics/export")
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
