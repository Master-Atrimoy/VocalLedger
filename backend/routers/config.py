import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import httpx

from ..services.llm_chain import ExpenseExtractionChain
from ..services.graph import build_expense_graph
from ..services.split_parser import SplitParserService

router = APIRouter()
logger = logging.getLogger(__name__)


class ModelSwitchRequest(BaseModel):
    model_id: str


@router.get("/")
def get_config(request: Request):
    cfg = request.app.state.cfg
    return {
        "active_model": request.app.state.active_model_id,
        "whisper_model": cfg.whisper.model_size,
        "ollama_base_url": cfg.model.base_url,
    }


@router.get("/ollama-models")
async def list_ollama_models(request: Request):
    cfg = request.app.state.cfg
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{cfg.model.base_url}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
        return {"online": True, "models": models, "active": request.app.state.active_model_id}
    except httpx.ConnectError:
        return {"online": False, "models": [], "active": request.app.state.active_model_id,
                "error": "Ollama is not running. Start with: ollama serve"}
    except Exception as e:
        return {"online": False, "models": [], "active": request.app.state.active_model_id, "error": str(e)}


@router.post("/model")
def switch_model(body: ModelSwitchRequest, request: Request):
    new_id = body.model_id.strip()
    current = request.app.state.active_model_id
    if new_id == current:
        return {"switched": False, "active_model": current}
    try:
        from omegaconf import OmegaConf
        new_cfg = OmegaConf.merge(request.app.state.cfg.model, OmegaConf.create({"model_id": new_id}))
        new_chain = ExpenseExtractionChain(new_cfg)
        new_graph = build_expense_graph(request.app.state.stt, new_chain)
        new_split_parser = SplitParserService(new_chain.llm)
        request.app.state.llm = new_chain
        request.app.state.graph = new_graph
        request.app.state.split_parser = new_split_parser 
        request.app.state.active_model_id = new_id
        logger.info(f"Model switched: {current} → {new_id}")
        return {"switched": True, "active_model": new_id}
    except Exception as e:
        raise HTTPException(500, f"Switch failed: {e}")
