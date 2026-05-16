from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import List

from ..database.models import Insight
from ..schemas.splits import InsightResponse
from ..dependencies import get_db

router = APIRouter()


@router.get("/", response_model=List[InsightResponse])
def get_insights(include_dismissed: bool = False, db: Session = Depends(get_db)):
    q = db.query(Insight)
    if not include_dismissed:
        q = q.filter(Insight.is_dismissed == False)
    return q.order_by(Insight.generated_at.desc()).all()


@router.post("/generate")
def generate_insights(request: Request, db: Session = Depends(get_db)):
    engine = request.app.state.insights_engine
    insights = engine.generate_all(db)
    return {
        "generated": len(insights),
        "insights": [{"id": i.id, "title": i.title, "type": i.insight_type,
                       "severity": i.severity} for i in insights]
    }


@router.patch("/{insight_id}/dismiss")
def dismiss(insight_id: int, db: Session = Depends(get_db)):
    i = db.query(Insight).filter(Insight.id == insight_id).first()
    if i:
        i.is_dismissed = True
        db.commit()
    return {"dismissed": insight_id}
