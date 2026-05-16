from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
import logging

from ..schemas.expense import VoiceExpenseResponse, ExpenseCreate
from ..database.models import Expense
from ..services.graph import make_initial_state
from ..dependencies import get_db, get_graph

router = APIRouter()
logger = logging.getLogger(__name__)


def _save(expense_data: ExpenseCreate, db: Session) -> Expense:
    db_expense = Expense(**expense_data.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


def _confidence(result: dict) -> float:
    return round(max(0.5, 1.0 - result.get("retry_count", 0) * 0.2), 2)


@router.post("/audio", response_model=VoiceExpenseResponse)
async def process_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    graph=Depends(get_graph),
):
    audio_bytes = await file.read()
    result = graph.invoke(make_initial_state(audio_bytes=audio_bytes))
    if not result["success"]:
        raise HTTPException(422, result.get("error", "Extraction failed"))
    db_expense = _save(result["expense"], db)
    stt = result.get("stt_metadata") or {}
    return VoiceExpenseResponse(
        transcript=result["transcript"],
        language_detected=stt.get("language"),
        expense=db_expense,
        extraction_confidence=_confidence(result),
    )


@router.post("/text", response_model=VoiceExpenseResponse)
async def process_text(
    text: str = Form(...),
    db: Session = Depends(get_db),
    graph=Depends(get_graph),
):
    result = graph.invoke(make_initial_state(text_input=text))
    if not result["success"]:
        raise HTTPException(422, result.get("error", "Extraction failed"))
    db_expense = _save(result["expense"], db)
    return VoiceExpenseResponse(
        transcript=result["transcript"],
        expense=db_expense,
        extraction_confidence=_confidence(result),
    )
