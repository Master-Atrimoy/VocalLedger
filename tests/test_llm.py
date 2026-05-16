"""Unit tests for LLM extraction chain — mocked, no Ollama needed."""
import pytest
from unittest.mock import MagicMock, patch
from omegaconf import OmegaConf
from backend.services.llm_chain import ExpenseExtractionChain


@pytest.fixture
def mock_cfg():
    return OmegaConf.create({
        "model_id": "mistral:7b", "temperature": 0.0,
        "base_url": "http://localhost:11434", "request_timeout": 60,
    })


@pytest.fixture
def chain(mock_cfg):
    with patch("backend.services.llm_chain.ChatOllama"):
        return ExpenseExtractionChain(mock_cfg)


def _mock(chain, response):
    chain.chain = MagicMock()
    chain.chain.invoke = MagicMock(return_value=response)


class TestHappyPath:
    def test_food_expense(self, chain):
        _mock(chain, '{"amount":200,"currency":"INR","category":"Food","description":"groceries","date":"today","payment_method":"unknown","transaction_type":"expense"}')
        r = chain.extract("spent 200 on groceries")
        assert r.success and r.expense.amount == 200.0 and r.expense.category.value == "Food"

    def test_income(self, chain):
        _mock(chain, '{"amount":1200,"currency":"INR","category":"Income","description":"tuition fees","date":"today","payment_method":"unknown","transaction_type":"income"}')
        r = chain.extract("got 1200 from students for tuition fees")
        assert r.success and r.expense.transaction_type.value == "income"

    def test_transport_cash_yesterday(self, chain):
        _mock(chain, '{"amount":85,"currency":"INR","category":"Transport","description":"auto fare","date":"yesterday","payment_method":"cash","transaction_type":"expense"}')
        r = chain.extract("auto fare 85 yesterday cash")
        assert r.success and r.expense.payment_method.value == "cash" and r.expense.date == "yesterday"

    def test_k_suffix(self, chain):
        _mock(chain, '{"amount":2000,"currency":"INR","category":"Shopping","description":"Zara shopping","date":"today","payment_method":"card","transaction_type":"expense"}')
        r = chain.extract("2k at Zara card")
        assert r.success and r.expense.amount == 2000.0

    def test_strips_markdown(self, chain):
        _mock(chain, '```json\n{"amount":500,"currency":"INR","category":"Health","description":"doctor fee","date":"today","payment_method":"unknown","transaction_type":"expense"}\n```')
        r = chain.extract("doctor 500")
        assert r.success and r.expense.amount == 500.0

    def test_list_returns_first(self, chain):
        _mock(chain, '[{"amount":200,"currency":"INR","category":"Food","description":"food","date":"today","payment_method":"unknown","transaction_type":"expense"}]')
        r = chain.extract("spent 200 on food")
        assert r.success and r.expense.amount == 200.0


class TestEdgeCases:
    def test_no_expense(self, chain):
        _mock(chain, '{"error": "no transaction found"}')
        r = chain.extract("hello how are you")
        assert not r.success and r.error == "no transaction found"

    def test_malformed_json(self, chain):
        _mock(chain, "I cannot extract anything from this.")
        r = chain.extract("some text")
        assert not r.success

    def test_llm_exception(self, chain):
        chain.chain = MagicMock()
        chain.chain.invoke = MagicMock(side_effect=Exception("Connection refused"))
        r = chain.extract("spent 100")
        assert not r.success and "LLM error" in r.error

    def test_invalid_category(self, chain):
        _mock(chain, '{"amount":100,"currency":"INR","category":"InvalidCat","description":"test","date":"today","payment_method":"unknown","transaction_type":"expense"}')
        r = chain.extract("spent 100")
        assert not r.success
