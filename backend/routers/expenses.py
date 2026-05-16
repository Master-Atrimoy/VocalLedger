from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from ..schemas.expense import ExpenseCreate, ExpenseResponse
from ..database.models import Expense
from ..dependencies import get_db

router = APIRouter()


@router.get("/", response_model=List[ExpenseResponse])
def list_expenses(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Expense)
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    if category:
        q = q.filter(Expense.category == category)
    return q.order_by(Expense.date.desc(), Expense.id.desc()).offset(offset).limit(limit).all()


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(expense_id: int, db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(404, "Expense not found")
    return e


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id: int, data: ExpenseCreate, db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(404, "Expense not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(404, "Expense not found")
    db.delete(e)
    db.commit()
    return {"deleted": expense_id}
