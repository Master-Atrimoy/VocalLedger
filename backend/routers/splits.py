from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime

from ..database.models import Person, Group, SplitEvent, SplitShare, Settlement
from ..schemas.splits import (
    PersonCreate, PersonResponse, GroupCreate, GroupResponse,
    SplitEventCreate, SplitShareResponse, SplitEventResponse,
    SettlementCreate, SettlementResponse, BalanceSummary, PersonBalance,
)
from ..dependencies import get_db

router = APIRouter()


# ── People ────────────────────────────────────────────────────────────────────

@router.get("/people", response_model=List[PersonResponse])
def list_people(db: Session = Depends(get_db)):
    return db.query(Person).order_by(Person.name).all()


@router.post("/people", response_model=PersonResponse)
def create_person(body: PersonCreate, db: Session = Depends(get_db)):
    existing = db.query(Person).filter(Person.name == body.name).first()
    if existing:
        raise HTTPException(400, f"'{body.name}' already exists")
    if body.is_self:
        db.query(Person).filter(Person.is_self == True).update({"is_self": False})
    person = Person(**body.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/people/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    p = db.query(Person).filter(Person.id == person_id).first()
    if not p:
        raise HTTPException(404, "Person not found")
    db.delete(p)
    db.commit()
    return {"deleted": person_id}


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("/groups", response_model=List[GroupResponse])
def list_groups(db: Session = Depends(get_db)):
    return db.query(Group).order_by(Group.created_at.desc()).all()


@router.post("/groups", response_model=GroupResponse)
def create_group(body: GroupCreate, db: Session = Depends(get_db)):
    group = Group(**body.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


# ── Split Events ──────────────────────────────────────────────────────────────

@router.get("/events")
def list_events(group_id: Optional[int] = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(SplitEvent)
    if group_id:
        q = q.filter(SplitEvent.group_id == group_id)
    return [_fmt_event(e) for e in q.order_by(SplitEvent.date.desc()).limit(limit).all()]


@router.post("/events")
def create_event(body: SplitEventCreate, db: Session = Depends(get_db)):
    payer = db.query(Person).filter(Person.id == body.paid_by_person_id).first()
    if not payer:
        raise HTTPException(404, "Payer not found")
    event = SplitEvent(
        description=body.description, total_amount=body.total_amount,
        paid_by_person_id=body.paid_by_person_id, split_type=body.split_type,
        date=body.date, group_id=body.group_id, expense_id=body.expense_id, raw_text=body.raw_text,
    )
    db.add(event)
    db.flush()
    for share in _compute_shares(body, event.id):
        db.add(share)
    db.commit()
    db.refresh(event)
    return _fmt_event(event)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    e = db.query(SplitEvent).filter(SplitEvent.id == event_id).first()
    if not e:
        raise HTTPException(404, "Event not found")
    db.delete(e)
    db.commit()
    return {"deleted": event_id}


@router.patch("/events/{event_id}/shares/{share_id}/settle")
def settle_share(event_id: int, share_id: int, db: Session = Depends(get_db)):
    share = db.query(SplitShare).filter(SplitShare.id == share_id, SplitShare.event_id == event_id).first()
    if not share:
        raise HTTPException(404, "Share not found")
    share.is_settled = True
    share.settled_at = datetime.utcnow()
    db.commit()
    return {"settled": share_id, "amount": share.share_amount}


# ── Settlements ───────────────────────────────────────────────────────────────

@router.post("/settlements")
def create_settlement(body: SettlementCreate, db: Session = Depends(get_db)):
    s = Settlement(**body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return _fmt_settlement(s, db)


@router.get("/settlements")
def list_settlements(limit: int = 50, db: Session = Depends(get_db)):
    return [_fmt_settlement(s, db) for s in
            db.query(Settlement).order_by(Settlement.date.desc()).limit(limit).all()]


# ── Balances ──────────────────────────────────────────────────────────────────

@router.get("/balances", response_model=BalanceSummary)
def get_balances(db: Session = Depends(get_db)):
    me = db.query(Person).filter(Person.is_self == True).first()
    if not me:
        raise HTTPException(400,
            "No 'self' person set. Go to Splits → People tab, add yourself and check 'This is me'.")

    people = db.query(Person).filter(Person.is_self == False).all()
    balances = []
    for person in people:
        they_owe = db.query(func.sum(SplitShare.share_amount)).join(SplitShare.event).filter(
            SplitEvent.paid_by_person_id == me.id,
            SplitShare.person_id == person.id,
            SplitShare.is_settled == False,
        ).scalar() or 0.0

        i_owe = db.query(func.sum(SplitShare.share_amount)).join(SplitShare.event).filter(
            SplitEvent.paid_by_person_id == person.id,
            SplitShare.person_id == me.id,
            SplitShare.is_settled == False,
        ).scalar() or 0.0

        they_paid_me = db.query(func.sum(Settlement.amount)).filter(
            Settlement.from_person_id == person.id, Settlement.to_person_id == me.id,
        ).scalar() or 0.0

        i_paid_them = db.query(func.sum(Settlement.amount)).filter(
            Settlement.from_person_id == me.id, Settlement.to_person_id == person.id,
        ).scalar() or 0.0

        net = (they_owe - they_paid_me) - (i_owe - i_paid_them)
        if abs(net) > 0.01:
            balances.append(PersonBalance(
                person_id=person.id, person_name=person.name,
                net_amount=round(net, 2), owes_you=round(max(net, 0), 2), you_owe=round(max(-net, 0), 2),
            ))

    owed = sum(b.owes_you for b in balances)
    owing = sum(b.you_owe for b in balances)
    return BalanceSummary(
        balances=sorted(balances, key=lambda b: abs(b.net_amount), reverse=True),
        total_you_are_owed=round(owed, 2), total_you_owe=round(owing, 2),
        net=round(owed - owing, 2),
    )


# ── Smart split — LLM parses, auto-creates people, returns preview ────────────

@router.post("/smart-split")
def smart_split(text: str, request: Request, db: Session = Depends(get_db)):
    """
    Full LLM-first flow: parse text → auto-create unknown people → return preview.
    No manual people setup needed.
    """
    # Detect balance queries — not a split creation request
    query_keywords = ["who owes", "how much", "owe each other", "tally", "settle up"]
    if any(kw in text.lower() for kw in query_keywords):
        raise HTTPException(422,
            "This looks like a balance query. Use the Balances tab to see who owes whom. "
            "To log splits, describe each payment separately.")

    parser = request.app.state.split_parser
    result = parser.parse(text)

    if not result.success:
        raise HTTPException(422,
            f"Could not parse as a split: {result.error}. "
            "Try: 'Split 1800 dinner with Rahul and Priya, I paid'")

    parsed = result.parsed

    # Auto-create self if not set up
    me = db.query(Person).filter(Person.is_self == True).first()
    if not me:
        me = Person(name="Me", is_self=True)
        db.add(me)
        db.flush()

    # Resolve or auto-create every participant
    resolved = []
    for name in parsed.participant_names:
        key = name.lower().strip()
        if key in ("me", "i", "myself"):
            resolved.append({"name": me.name, "person_id": me.id, "created": False})
        else:
            existing = db.query(Person).filter(func.lower(Person.name) == key).first()
            if existing:
                resolved.append({"name": existing.name, "person_id": existing.id, "created": False})
            else:
                new_p = Person(name=name.strip().title(), is_self=False)
                db.add(new_p)
                db.flush()
                resolved.append({"name": new_p.name, "person_id": new_p.id, "created": True})

    db.commit()

    # Resolve payer
    payer_key = parsed.paid_by_name.lower().strip()
    if payer_key in ("me", "i", "myself"):
        paid_by_id, paid_by_name = me.id, me.name
    else:
        match = next((r for r in resolved if r["name"].lower() == payer_key), None)
        paid_by_id = match["person_id"] if match else me.id
        paid_by_name = match["name"] if match else me.name

    # Compute equal shares preview
    n = max(len(resolved), 1)
    base = round(parsed.total_amount / n, 2)
    remainder = round(parsed.total_amount - base * n, 2)
    shares_preview = [
        {
            "person_id": r["person_id"],
            "person_name": r["name"],
            "share_amount": base + (remainder if i == 0 else 0),
            "created": r["created"],
        }
        for i, r in enumerate(resolved)
    ]

    return {
        "description": parsed.description,
        "total_amount": parsed.total_amount,
        "paid_by_person_id": paid_by_id,
        "paid_by_name": paid_by_name,
        "split_type": parsed.split_type,
        "date_str": parsed.date_str,
        "shares_preview": shares_preview,
        "auto_created": [r["name"] for r in resolved if r["created"]],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_shares(body: SplitEventCreate, event_id: int) -> list:
    shares = []
    if body.split_type == "equal":
        n = len(body.participant_ids)
        base = round(body.total_amount / n, 2)
        remainder = round(body.total_amount - base * n, 2)
        for i, pid in enumerate(body.participant_ids):
            shares.append(SplitShare(event_id=event_id, person_id=pid,
                                     share_amount=base + (remainder if i == 0 else 0)))
    elif body.split_type in ("custom", "percentage") and body.custom_shares:
        for cs in body.custom_shares:
            amt = round(body.total_amount * cs.share_amount / 100, 2) if body.split_type == "percentage" else cs.share_amount
            shares.append(SplitShare(event_id=event_id, person_id=cs.person_id, share_amount=amt))
    return shares


def _fmt_event(event: SplitEvent) -> dict:
    return {
        "id": event.id, "description": event.description,
        "total_amount": event.total_amount,
        "paid_by_person_id": event.paid_by_person_id,
        "paid_by_name": event.paid_by.name if event.paid_by else "—",
        "split_type": event.split_type, "date": event.date,
        "group_id": event.group_id, "created_at": event.created_at,
        "shares": [{"id": s.id, "person_id": s.person_id,
                    "person_name": s.person.name if s.person else "—",
                    "share_amount": s.share_amount, "is_settled": s.is_settled,
                    "settled_at": s.settled_at}
                   for s in event.shares],
    }


def _fmt_settlement(s: Settlement, db: Session) -> dict:
    fp = db.query(Person).filter(Person.id == s.from_person_id).first()
    tp = db.query(Person).filter(Person.id == s.to_person_id).first()
    return {"id": s.id, "from_person_id": s.from_person_id,
            "from_person_name": fp.name if fp else "—",
            "to_person_id": s.to_person_id,
            "to_person_name": tp.name if tp else "—",
            "amount": s.amount, "date": s.date, "notes": s.notes}
