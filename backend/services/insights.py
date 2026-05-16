"""
Insights Engine — Python does all math, LLM writes narrative only.
Requires minimum 14 days of data before generating insights.
"""
import json, logging
from datetime import date, timedelta
from collections import defaultdict
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from langchain_core.messages import HumanMessage

from ..database.models import Expense, Insight, SplitShare, Person

logger = logging.getLogger(__name__)
MIN_DAYS = 14


class InsightsEngine:
    def __init__(self, llm):
        self.llm = llm

    def generate_all(self, db: Session) -> List[Insight]:
        oldest = db.query(func.min(Expense.date)).scalar()
        if not oldest or (date.today() - oldest).days < MIN_DAYS:
            logger.info("Not enough data for insights")
            return []

        db.query(Insight).filter(Insight.is_dismissed == False).delete()
        db.commit()

        insights = []
        for gen in [self._anomaly, self._trend, self._recurring, self._pattern, self._summary, self._splits]:
            try:
                result = gen(db)
                if result:
                    insights.extend(result if isinstance(result, list) else [result])
            except Exception as e:
                logger.error(f"{gen.__name__} failed: {e}")

        for i in insights:
            db.add(i)
        db.commit()
        logger.info(f"Generated {len(insights)} insights")
        return insights

    def _anomaly(self, db: Session) -> List[Insight]:
        today = date.today()
        this_month = today.replace(day=1)
        three_ago = (this_month - timedelta(days=90))

        current = {
            r.category: float(r.total)
            for r in db.query(Expense.category, func.sum(Expense.amount).label("total"))
            .filter(Expense.date >= this_month, Expense.transaction_type == "expense")
            .group_by(Expense.category).all()
        }
        hist = {
            r.category: float(r.total) / max(r.months, 1)
            for r in db.query(
                Expense.category,
                func.sum(Expense.amount).label("total"),
                func.count(func.distinct(func.strftime("%Y-%m", Expense.date))).label("months")
            ).filter(Expense.date >= three_ago, Expense.date < this_month, Expense.transaction_type == "expense")
            .group_by(Expense.category).all()
        }

        results = []
        for cat, cur in current.items():
            avg = hist.get(cat)
            if avg and avg > 100:
                pct = (cur - avg) / avg * 100
                if pct > 30:
                    data = {"category": cat, "current": cur, "average": avg, "pct_change": pct}
                    results.append(Insight(
                        insight_type="anomaly",
                        title=f"{cat} spending is {pct:.0f}% above your average",
                        body=self._narrative("anomaly_high", data),
                        severity="warning", data_json=json.dumps(data),
                    ))
                elif pct < -25:
                    data = {"category": cat, "current": cur, "average": avg, "pct_change": pct}
                    results.append(Insight(
                        insight_type="anomaly",
                        title=f"You're spending less on {cat} this month",
                        body=self._narrative("anomaly_low", data),
                        severity="positive", data_json=json.dumps(data),
                    ))
        return results

    def _trend(self, db: Session) -> List[Insight]:
        today = date.today()
        months = []
        for i in range(3):
            ref = today.replace(day=1) - timedelta(days=i * 30)
            start = ref.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            total = db.query(func.sum(Expense.amount)).filter(
                Expense.date >= start, Expense.date <= end, Expense.transaction_type == "expense"
            ).scalar() or 0
            months.append({"month": start.strftime("%b %Y"), "total": float(total)})
        months.reverse()

        m0, m1, m2 = months[0]["total"], months[1]["total"], months[2]["total"]
        if m0 > 0 and m1 > 0 and m2 > 0:
            trend = "up" if m2 > m1 > m0 else "down" if m2 < m1 < m0 else "flat"
            if trend != "flat":
                pct = (m2 - m0) / m0 * 100
                data = {"months": months, "trend": trend, "pct_change": pct}
                return [Insight(
                    insight_type="trend",
                    title=f"Spending has been {'rising' if trend == 'up' else 'falling'} for 3 months",
                    body=self._narrative("trend", data),
                    severity="warning" if trend == "up" else "positive",
                    data_json=json.dumps(data),
                )]
        return []

    def _recurring(self, db: Session) -> List[Insight]:
        three_ago = date.today() - timedelta(days=90)
        expenses = db.query(Expense).filter(
            Expense.date >= three_ago, Expense.transaction_type == "expense"
        ).order_by(Expense.date).all()

        by_desc = defaultdict(list)
        for e in expenses:
            key = (e.description or "").lower().strip()
            if key:
                by_desc[key].append(e)

        results = []
        for desc, txns in by_desc.items():
            if len(txns) >= 2:
                amounts = [t.amount for t in txns]
                avg = sum(amounts) / len(amounts)
                if (max(amounts) - min(amounts)) / avg < 0.10 and avg > 50:
                    dates = sorted([t.date for t in txns])
                    gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    avg_gap = sum(gaps) / len(gaps)
                    freq = "monthly" if 25 <= avg_gap <= 35 else "weekly" if 6 <= avg_gap <= 8 else None
                    if freq:
                        data = {"description": desc, "amount": avg, "frequency": freq, "occurrences": len(txns)}
                        results.append(Insight(
                            insight_type="recurring",
                            title=f"Recurring {freq}: {desc.title()} (~₹{avg:,.0f})",
                            body=self._narrative("recurring", data),
                            severity="info", data_json=json.dumps(data),
                        ))
        return results[:3]

    def _pattern(self, db: Session) -> List[Insight]:
        thirty_ago = date.today() - timedelta(days=30)
        expenses = db.query(Expense).filter(
            Expense.date >= thirty_ago, Expense.transaction_type == "expense"
        ).all()
        if len(expenses) < 10:
            return []

        wd_total = sum(e.amount for e in expenses if e.date.weekday() < 5)
        we_total = sum(e.amount for e in expenses if e.date.weekday() >= 5)
        wd_days = max(sum(1 for e in expenses if e.date.weekday() < 5), 1)
        we_days = max(sum(1 for e in expenses if e.date.weekday() >= 5), 1)

        wd_avg, we_avg = wd_total / wd_days, we_total / we_days
        if we_avg > wd_avg * 1.5:
            data = {"weekday_avg": wd_avg, "weekend_avg": we_avg}
            return [Insight(
                insight_type="pattern",
                title=f"You spend {we_avg/wd_avg:.1f}x more on weekends",
                body=self._narrative("weekend_pattern", data),
                severity="info", data_json=json.dumps(data),
            )]
        return []

    def _summary(self, db: Session) -> List[Insight]:
        today = date.today()
        rows = db.query(
            Expense.transaction_type,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        ).filter(Expense.date >= today.replace(day=1)).group_by(Expense.transaction_type).all()

        if not rows:
            return []

        exp_total = sum(r.total for r in rows if r.transaction_type == "expense")
        inc_total = sum(r.total for r in rows if r.transaction_type == "income")
        data = {
            "month": today.strftime("%B %Y"),
            "total_expense": exp_total, "total_income": inc_total,
            "net": inc_total - exp_total, "days_elapsed": today.day,
        }
        return [Insight(
            insight_type="summary",
            title=f"{today.strftime('%B')} so far — ₹{exp_total:,.0f} spent",
            body=self._narrative("monthly_summary", data),
            severity="info", data_json=json.dumps(data),
        )]

    def _splits(self, db: Session) -> List[Insight]:
        me = db.query(Person).filter(Person.is_self == True).first()
        if not me:
            return []
        owed = sum(
            s.share_amount for s in db.query(SplitShare).join(SplitShare.event).filter(
                SplitShare.is_settled == False,
                SplitShare.person_id != me.id,
            ).all() if s.event.paid_by_person_id == me.id
        )
        i_owe = sum(
            s.share_amount for s in db.query(SplitShare).join(SplitShare.event).filter(
                SplitShare.is_settled == False,
                SplitShare.person_id == me.id,
            ).all() if s.event.paid_by_person_id != me.id
        )
        if owed == 0 and i_owe == 0:
            return []
        data = {"owed_to_me": owed, "i_owe": i_owe, "net": owed - i_owe}
        return [Insight(
            insight_type="split",
            title=f"Outstanding splits: ₹{owed:,.0f} owed to you, ₹{i_owe:,.0f} you owe",
            body=self._narrative("split_balance", data),
            severity="warning" if i_owe > owed else "info",
            data_json=json.dumps(data),
        )]

    def _narrative(self, insight_type: str, data: dict) -> str:
        prompts = {
            "anomaly_high": f"Write 2 sentences explaining this spending spike to a user (be specific with numbers, suggest one action): {data}",
            "anomaly_low":  f"Write 2 sentences congratulating reduced spending (warm, specific with numbers): {data}",
            "trend":        f"Write 2 sentences explaining this 3-month spending trend (specific, suggest one thing to watch): {data}",
            "recurring":    f"Write 2 sentences identifying this recurring expense (note pattern, suggest budgeting for it): {data}",
            "weekend_pattern": f"Write 2 sentences about this weekend vs weekday spending pattern (conversational): {data}",
            "monthly_summary": f"Write 3 sentences summarising this month's finances (include net position and one observation): {data}",
            "split_balance":   f"Write 2 sentences summarising outstanding split balances clearly: {data}",
        }
        try:
            prompt = prompts.get(insight_type, f"Summarise this financial data in 2 sentences: {data}")
            response = self.llm.llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM narrative failed for {insight_type}: {e}")
            return json.dumps(data)
