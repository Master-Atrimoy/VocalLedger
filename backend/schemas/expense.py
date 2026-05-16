from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class ExpenseCategory(str, Enum):
    FOOD = "Food"
    TRANSPORT = "Transport"
    SHOPPING = "Shopping"
    BILLS = "Bills"
    HEALTH = "Health"
    ENTERTAINMENT = "Entertainment"
    INCOME = "Income"
    OTHER = "Other"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    UNKNOWN = "unknown"


class TransactionType(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"


# ── LLM extraction target ─────────────────────────────────────────────────────

class ExtractedExpense(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="INR")
    category: ExpenseCategory
    description: str = Field(..., max_length=100)
    date: str = Field(...)
    payment_method: PaymentMethod = Field(default=PaymentMethod.UNKNOWN)
    transaction_type: TransactionType = Field(default=TransactionType.EXPENSE)


class ExtractedExpenseOrError(BaseModel):
    success: bool
    expense: Optional[ExtractedExpense] = None
    error: Optional[str] = None
    raw_output: Optional[str] = None


# ── API schemas ───────────────────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(default="INR")
    category: ExpenseCategory
    description: Optional[str] = None
    date: date
    payment_method: PaymentMethod = PaymentMethod.UNKNOWN
    transaction_type: TransactionType = TransactionType.EXPENSE
    raw_text: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def round_amount(cls, v: float) -> float:
        return round(v, 2)


class ExpenseResponse(BaseModel):
    id: int
    amount: float
    currency: str
    category: str
    description: Optional[str]
    date: date
    payment_method: str
    transaction_type: str
    raw_text: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class VoiceExpenseResponse(BaseModel):
    transcript: str
    language_detected: Optional[str] = None
    expense: ExpenseResponse
    extraction_confidence: float = Field(..., ge=0, le=1)


# ── Analytics schemas ─────────────────────────────────────────────────────────

class ExpenseSummary(BaseModel):
    total_expense: float
    total_income: float
    net: float
    count: int
    period: str
    currency: str = "INR"
    average: float = 0.0


class CategoryBreakdown(BaseModel):
    category: str
    total: float
    count: int
    percentage: float


class DailySpend(BaseModel):
    date: date
    total: float
    count: int


class AnalyticsDashboard(BaseModel):
    summary: ExpenseSummary
    by_category: List[CategoryBreakdown]
    daily_trend: List[DailySpend]
