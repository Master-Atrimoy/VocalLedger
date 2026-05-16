from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, timedelta
import csv, io

from ..schemas.expense import ExpenseSummary, CategoryBreakdown, DailySpend, AnalyticsDashboard
from ..database.models import Expense
from ..dependencies import get_db

router = APIRouter()


def _from_date(period: str) -> date:
    today = date.today()
    if period == "week":
        return today - timedelta(days=7)
    elif period == "year":
        return today.replace(month=1, day=1)
    return today.replace(day=1)


@router.get("/summary", response_model=ExpenseSummary)
def get_summary(
    period: str = Query("month", pattern="^(week|month|year)$"),
    db: Session = Depends(get_db),
):
    from_date = _from_date(period)
    rows = db.query(
        Expense.transaction_type,
        func.coalesce(func.sum(Expense.amount), 0).label("total"),
        func.count(Expense.id).label("count"),
    ).filter(Expense.date >= from_date).group_by(Expense.transaction_type).all()

    total_expense = sum(r.total for r in rows if r.transaction_type == "expense")
    total_income  = sum(r.total for r in rows if r.transaction_type == "income")
    count = sum(r.count for r in rows)
    avg = round((total_expense + total_income) / count, 2) if count else 0.0

    return ExpenseSummary(
        total_expense=round(total_expense, 2),
        total_income=round(total_income, 2),
        net=round(total_income - total_expense, 2),
        count=count, period=period, average=avg,
    )


@router.get("/categories", response_model=List[CategoryBreakdown])
def get_categories(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(
        Expense.category,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count"),
    )
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    rows = q.group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    grand = sum(r.total for r in rows) or 1
    return [
        CategoryBreakdown(category=r.category, total=round(float(r.total), 2),
                          count=r.count, percentage=round(float(r.total) / grand * 100, 1))
        for r in rows
    ]


@router.get("/daily", response_model=List[DailySpend])
def get_daily(days: int = Query(30, ge=7, le=365), db: Session = Depends(get_db)):
    from_date = date.today() - timedelta(days=days)
    rows = db.query(
        Expense.date,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count"),
    ).filter(Expense.date >= from_date).group_by(Expense.date).order_by(Expense.date).all()
    return [DailySpend(date=r.date, total=round(float(r.total), 2), count=r.count) for r in rows]


@router.get("/dashboard", response_model=AnalyticsDashboard)
def get_dashboard(period: str = Query("month", pattern="^(week|month|year)$"), db: Session = Depends(get_db)):
    return AnalyticsDashboard(
        summary=get_summary(period=period, db=db),
        by_category=get_categories(db=db),
        daily_trend=get_daily(db=db),
    )


@router.get("/export")
def export_csv(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Expense)
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    expenses = q.order_by(Expense.date.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Date", "Amount", "Currency", "Category", "Description",
                     "Payment Method", "Transaction Type", "Raw Text", "Created At"])
    for e in expenses:
        writer.writerow([e.id, e.date, e.amount, e.currency, e.category, e.description,
                         e.payment_method, e.transaction_type, e.raw_text, e.created_at])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=expenses.csv"})
