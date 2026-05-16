@echo off
:: Voice Expense Tracker v1 — Windows helper
:: Usage: run.bat [command]

SET CMD=%1

IF "%CMD%"=="install" (
    pip install -r requirements.txt
    GOTO end
)
IF "%CMD%"=="pull-model" (
    ollama pull mistral:7b
    GOTO end
)
IF "%CMD%"=="setup" (
    pip install -r requirements.txt
    ollama pull mistral:7b
    echo.
    echo Setup complete.
    echo Run "run.bat backend" and "run.bat frontend" in separate terminals.
    GOTO end
)
IF "%CMD%"=="backend" (
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
    GOTO end
)
IF "%CMD%"=="frontend" (
    streamlit run frontend/app.py --server.port 8501
    GOTO end
)
IF "%CMD%"=="eval" (
    python -m evaluation.eval_extraction
    GOTO end
)
IF "%CMD%"=="eval-stt" (
    python -m evaluation.eval_stt
    GOTO end
)
IF "%CMD%"=="test" (
    pytest tests/ -v --tb=short
    GOTO end
)
IF "%CMD%"=="clean" (
    for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
    if exist expenses.db del expenses.db
    echo Cleaned.
    GOTO end
)

echo.
echo  Voice Expense Tracker v1 — Commands:
echo.
echo    run.bat setup       Install deps + pull Mistral model
echo    run.bat backend     Start FastAPI on :8000
echo    run.bat frontend    Start Streamlit on :8501
echo    run.bat eval        Run LLM extraction evaluation
echo    run.bat eval-stt    Run STT WER evaluation
echo    run.bat test        Run test suite
echo    run.bat clean       Remove cache + DB
echo.

:end
