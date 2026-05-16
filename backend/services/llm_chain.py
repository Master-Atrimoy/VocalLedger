from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from omegaconf import DictConfig
from ..schemas.expense import ExtractedExpense, ExtractedExpenseOrError
import logging, json, re

logger = logging.getLogger(__name__)

SYSTEM_TEMPLATE = """\
You are a financial ledger engine. Extract ONE transaction from the user's text and return ONLY valid JSON.
If no clear transaction is present, return: {{"error": "no transaction found"}}
If multiple transactions are mentioned, extract only the FIRST one and ignore the rest.
Never return a list or array — always a single flat JSON object.

Determine transaction_type carefully:
- "expense": money going OUT — spent, bought, paid, purchased, ordered, got [physical item]
  Key rule: if "got" is followed by a physical object (backpack, phone, groceries, shirt, food etc.) = expense
- "income": money coming IN — received [money/payment], got paid, earned, collected [fees/rent/salary], got [amount] for [service]
  Key rule: "got" = income ONLY when followed directly by an amount or payment word, not a physical object

Examples of the distinction:
- "got a backpack for 3400" → expense (got a physical item)
- "got groceries for 500" → expense (got a physical item)
- "got 1200 for tuition fees" → income (got an amount)
- "got paid 5000" → income (got payment)
Output format (flat JSON, no extra keys):
{{"amount": <number>, "currency": "INR", "category": "<Food|Transport|Shopping|Bills|Health|Entertainment|Income|Other>", "description": "<max 10 words>", "date": "<today|yesterday|YYYY-MM-DD>", "payment_method": "<cash|card|upi|unknown>", "transaction_type": "<expense|income>"}}

Parsing rules:
- "2k" or "2K" = 2000, "fifty" = 50, "two hundred" = 200
- "₹", "rs", "rupees", "rupe" = INR
- "$", "dollar", "dollars", "USD" are valid currency — extract the amount and set currency to "USD"
- For a different currency like pound or euro - make sure to set currency accordingly.
- "around", "about", "approximately", "roughly" before a number → extract the number that follows, ignore the qualifier
- date: return "today", "yesterday", or YYYY-MM-DD
- "yesterday" in input ALWAYS means date = "yesterday" — never return "today" if yesterday is mentioned
- description: name the actual item or service, never repeat currency or amount words

Examples:
Input: spent 200 on groceries at Big Bazaar
Output: {{"amount":200,"currency":"INR","category":"Food","description":"groceries at Big Bazaar","date":"today","payment_method":"unknown","transaction_type":"expense"}}

Input: auto fare 85 rupees yesterday paid cash
Output: {{"amount":85,"currency":"INR","category":"Transport","description":"auto fare","date":"yesterday","payment_method":"cash","transaction_type":"expense"}}

Input: got 1200 from students for tuition fees
Output: {{"amount":1200,"currency":"INR","category":"Income","description":"tuition fees from students","date":"today","payment_method":"unknown","transaction_type":"income"}}

Input: received salary 45000 credited to account
Output: {{"amount":45000,"currency":"INR","category":"Income","description":"monthly salary","date":"today","payment_method":"upi","transaction_type":"income"}}

Input: electricity bill 1200 via upi
Output: {{"amount":1200,"currency":"INR","category":"Bills","description":"electricity bill","date":"today","payment_method":"upi","transaction_type":"expense"}}

Input: got a backpack for 3400 yesterday
Output: {{"amount":3400,"currency":"INR","category":"Shopping","description":"backpack","date":"yesterday","payment_method":"unknown","transaction_type":"expense"}}

Input: got a phone 15000 paid card
Output: {{"amount":15000,"currency":"INR","category":"Shopping","description":"phone","date":"today","payment_method":"card","transaction_type":"expense"}}

Input: hello how are you
Output: {{"error":"no transaction found"}}
"""


class ExpenseExtractionChain:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.llm = ChatOllama(
            model=cfg.model_id,
            temperature=cfg.temperature,
            base_url=cfg.base_url,
            timeout=cfg.request_timeout,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_TEMPLATE),
            ("human", "{input}"),
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    def extract(self, text: str) -> ExtractedExpenseOrError:
        try:
            raw = self.chain.invoke({"input": text})
            logger.debug(f"LLM raw: {raw!r}")
            return self._parse_raw(raw)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ExtractedExpenseOrError(success=False, error=f"LLM error: {e}")

    def _parse_raw(self, raw: str) -> ExtractedExpenseOrError:
        cleaned = self._strip_markdown(raw)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed: {e} | raw={cleaned!r}")
            return ExtractedExpenseOrError(success=False, error=f"JSON parse error: {e}", raw_output=raw)

        # Guard: LLM returned a list instead of a single object
        if isinstance(payload, list):
            if not payload:
                return ExtractedExpenseOrError(success=False, error="Empty list returned", raw_output=raw)
            payload = payload[0]
            logger.warning("LLM returned list — using first item only")

        if "error" in payload:
            return ExtractedExpenseOrError(success=False, error=payload["error"], raw_output=raw)

        try:
            expense = ExtractedExpense(**payload)
            return ExtractedExpenseOrError(success=True, expense=expense, raw_output=raw)
        except Exception as e:
            logger.warning(f"Pydantic validation failed: {e}")
            return ExtractedExpenseOrError(success=False, error=f"Validation: {e}", raw_output=raw)

    @staticmethod
    def _strip_markdown(text: str) -> str:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return match.group(0) if match else text
