import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import load_config
from .database.db import get_engine, get_session_factory
from .services.stt import STTService
from .services.llm_chain import ExpenseExtractionChain
from .services.graph import build_expense_graph
from .services.insights import InsightsEngine
from .services.split_parser import SplitParserService
from .routers import voice, expenses, analytics, splits, insights
from .routers import config as config_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    engine = get_engine(cfg.database.url, cfg.database.echo)

    app.state.cfg = cfg
    app.state.session_factory = get_session_factory(engine)
    app.state.stt = STTService(cfg.whisper)
    app.state.llm = ExpenseExtractionChain(cfg.model)
    app.state.graph = build_expense_graph(app.state.stt, app.state.llm)
    app.state.active_model_id = cfg.model.model_id
    app.state.insights_engine = InsightsEngine(app.state.llm)
    app.state.split_parser = SplitParserService(app.state.llm.llm)

    logger.info("✅ All services initialised.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Voice Expense Tracker",
    description="Personal finance ledger with splits and pattern intelligence.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(voice.router,         prefix="/api/voice",     tags=["Voice"])
app.include_router(expenses.router,      prefix="/api/expenses",  tags=["Expenses"])
app.include_router(analytics.router,     prefix="/api/analytics", tags=["Analytics"])
app.include_router(config_router.router, prefix="/api/config",    tags=["Config"])
app.include_router(splits.router,        prefix="/api/splits",    tags=["Splits"])
app.include_router(insights.router,      prefix="/api/insights",  tags=["Insights"])


@app.get("/health", tags=["System"])
def health(request: Request):
    cfg = request.app.state.cfg
    return {"status": "ok", "model": request.app.state.active_model_id,
            "whisper": cfg.whisper.model_size}
