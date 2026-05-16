from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from datetime import date, timedelta
import dateparser, logging

from ..schemas.expense import ExpenseCreate, ExpenseCategory, PaymentMethod, TransactionType
from .stt import STTService
from .llm_chain import ExpenseExtractionChain

logger = logging.getLogger(__name__)


class ExpenseState(TypedDict):
    audio_bytes: Optional[bytes]
    text_input: Optional[str]
    transcript: Optional[str]
    stt_metadata: Optional[dict]
    raw_extraction: Optional[dict]
    retry_count: int
    expense: Optional[ExpenseCreate]
    error: Optional[str]
    success: bool


def _make_transcribe_node(stt: STTService):
    def transcribe(state: ExpenseState) -> dict:
        if state.get("text_input"):
            return {"transcript": state["text_input"], "stt_metadata": None}
        if not state.get("audio_bytes"):
            return {"error": "No input provided", "success": False}
        try:
            result = stt.transcribe_bytes(state["audio_bytes"])
            return {"transcript": result["transcript"], "stt_metadata": result}
        except Exception as e:
            return {"error": f"STT failed: {e}", "success": False}
    return transcribe


def _make_extract_node(llm: ExpenseExtractionChain):
    def extract(state: ExpenseState) -> dict:
        # Do NOT check state["error"] here — on retries error is set from
        # previous attempt and that is expected. Routing controls flow.
        transcript = state.get("transcript", "").strip()
        if not transcript:
            return {"error": "Empty transcript", "success": False}

        result = llm.extract(transcript)
        if not result.success:
            return {
                "raw_extraction": None,
                "error": result.error,
                "retry_count": state.get("retry_count", 0) + 1,
            }
        return {
            "raw_extraction": result.expense.model_dump(),
            "error": None,
            "retry_count": state.get("retry_count", 0),
        }
    return extract


def resolve_date(state: ExpenseState) -> dict:
    if state.get("error") or not state.get("raw_extraction"):
        return {}
    raw = dict(state["raw_extraction"])
    date_str = raw.get("date", "today")
    if date_str == "today":
        resolved = date.today()
    elif date_str == "yesterday":
        resolved = date.today() - timedelta(days=1)
    else:
        parsed = dateparser.parse(date_str, settings={"PREFER_DAY_OF_MONTH": "first", "RETURN_AS_TIMEZONE_AWARE": False})
        resolved = parsed.date() if parsed else date.today()
    raw["date"] = resolved
    return {"raw_extraction": raw}


def validate(state: ExpenseState) -> dict:
    if state.get("error") or not state.get("raw_extraction"):
        return {"success": False}
    raw = state["raw_extraction"]
    try:
        expense = ExpenseCreate(
            amount=raw["amount"],
            currency=raw.get("currency", "INR"),
            category=ExpenseCategory(raw["category"]),
            description=raw.get("description"),
            date=raw["date"],
            payment_method=PaymentMethod(raw.get("payment_method", "unknown")),
            transaction_type=TransactionType(raw.get("transaction_type", "expense")),
            raw_text=state.get("transcript"),
        )
        return {"expense": expense, "success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": f"Validation: {e}"}


def _route_after_transcribe(state: ExpenseState) -> str:
    return "fail" if state.get("error") else "extract"


def _route_after_extract(state: ExpenseState) -> str:
    if not state.get("error"):
        return "resolve_date"
    if state.get("retry_count", 0) < 2:
        logger.info(f"Retrying extraction (attempt {state['retry_count'] + 1})")
        return "retry"
    return "fail"


def build_expense_graph(stt_service: STTService, llm_chain: ExpenseExtractionChain):
    g = StateGraph(ExpenseState)
    g.add_node("transcribe", _make_transcribe_node(stt_service))
    g.add_node("extract", _make_extract_node(llm_chain))
    g.add_node("resolve_date", resolve_date)
    g.add_node("validate", validate)
    g.set_entry_point("transcribe")
    g.add_conditional_edges("transcribe", _route_after_transcribe, {"extract": "extract", "fail": END})
    g.add_conditional_edges("extract", _route_after_extract, {"resolve_date": "resolve_date", "retry": "extract", "fail": END})
    g.add_edge("resolve_date", "validate")
    g.add_edge("validate", END)
    return g.compile()


def make_initial_state(audio_bytes=None, text_input=None) -> ExpenseState:
    return ExpenseState(
        audio_bytes=audio_bytes, text_input=text_input,
        transcript=None, stt_metadata=None, raw_extraction=None,
        retry_count=0, expense=None, error=None, success=False,
    )
