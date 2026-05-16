.PHONY: install pull-model setup backend frontend eval eval-stt test clean

install:
	pip install -r requirements.txt

pull-model:
	ollama pull mistral:7b

setup: install pull-model
	@echo "✅ Setup complete. Run 'make backend' and 'make frontend' in separate terminals."

backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	streamlit run frontend/app.py --server.port 8501

eval:
	python -m evaluation.eval_extraction

eval-stt:
	python -m evaluation.eval_stt

test:
	pytest tests/ -v --tb=short

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f expenses.db
