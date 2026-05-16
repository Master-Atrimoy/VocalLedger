from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import date, datetime


class PersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    upi_id: Optional[str] = None
    is_self: bool = False


class PersonResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    upi_id: Optional[str]
    is_self: bool
    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class ShareInput(BaseModel):
    person_id: int
    share_amount: float = Field(..., gt=0)


class SplitEventCreate(BaseModel):
    description: str
    total_amount: float = Field(..., gt=0)
    paid_by_person_id: int
    split_type: Literal["equal", "custom", "percentage"] = "equal"
    participant_ids: List[int]
    custom_shares: Optional[List[ShareInput]] = None
    date: date
    group_id: Optional[int] = None
    expense_id: Optional[int] = None
    raw_text: Optional[str] = None


class SplitShareResponse(BaseModel):
    id: int
    person_id: int
    person_name: str
    share_amount: float
    is_settled: bool
    settled_at: Optional[datetime]
    model_config = {"from_attributes": True}


class SplitEventResponse(BaseModel):
    id: int
    description: str
    total_amount: float
    paid_by_person_id: int
    paid_by_name: str
    split_type: str
    date: date
    group_id: Optional[int]
    shares: List[SplitShareResponse]
    created_at: datetime
    model_config = {"from_attributes": True}


class SettlementCreate(BaseModel):
    from_person_id: int
    to_person_id: int
    amount: float = Field(..., gt=0)
    date: date
    notes: Optional[str] = None


class SettlementResponse(BaseModel):
    id: int
    from_person_id: int
    from_person_name: str
    to_person_id: int
    to_person_name: str
    amount: float
    date: date
    notes: Optional[str]
    model_config = {"from_attributes": True}


class PersonBalance(BaseModel):
    person_id: int
    person_name: str
    net_amount: float
    owes_you: float
    you_owe: float


class BalanceSummary(BaseModel):
    balances: List[PersonBalance]
    total_you_are_owed: float
    total_you_owe: float
    net: float


class ParsedSplit(BaseModel):
    description: str
    total_amount: float
    paid_by_name: str
    participant_names: List[str]
    split_type: str = "equal"
    date_str: str = "today"


class ParsedSplitOrError(BaseModel):
    success: bool
    parsed: Optional[ParsedSplit] = None
    error: Optional[str] = None


class InsightResponse(BaseModel):
    id: int
    insight_type: str
    title: str
    body: str
    severity: str
    generated_at: datetime
    model_config = {"from_attributes": True}
