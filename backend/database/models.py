from sqlalchemy import Column, Integer, Float, String, Date, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(String(200), nullable=True)
    date = Column(Date, nullable=False)
    payment_method = Column(String(20), default="unknown", nullable=False)
    transaction_type = Column(String(10), default="expense", nullable=False)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    phone = Column(String(20), nullable=True)
    upi_id = Column(String(100), nullable=True)
    is_self = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    shares = relationship("SplitShare", back_populates="person")
    settlements_sent = relationship("Settlement", foreign_keys="Settlement.from_person_id", back_populates="from_person")
    settlements_received = relationship("Settlement", foreign_keys="Settlement.to_person_id", back_populates="to_person")


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    events = relationship("SplitEvent", back_populates="group")


class SplitEvent(Base):
    __tablename__ = "split_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(200), nullable=False)
    total_amount = Column(Float, nullable=False)
    paid_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    split_type = Column(String(20), default="equal")
    date = Column(Date, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    paid_by = relationship("Person", foreign_keys=[paid_by_person_id])
    shares = relationship("SplitShare", back_populates="event", cascade="all, delete-orphan")
    group = relationship("Group", back_populates="events")


class SplitShare(Base):
    __tablename__ = "split_shares"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("split_events.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    share_amount = Column(Float, nullable=False)
    is_settled = Column(Boolean, default=False, nullable=False)
    settled_at = Column(DateTime, nullable=True)

    event = relationship("SplitEvent", back_populates="shares")
    person = relationship("Person", back_populates="shares")


class Settlement(Base):
    __tablename__ = "settlements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    to_person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    notes = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    from_person = relationship("Person", foreign_keys=[from_person_id], back_populates="settlements_sent")
    to_person = relationship("Person", foreign_keys=[to_person_id], back_populates="settlements_received")


class Insight(Base):
    __tablename__ = "insights"
    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(String(10), default="info")
    data_json = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    is_dismissed = Column(Boolean, default=False)
