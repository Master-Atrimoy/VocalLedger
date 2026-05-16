from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ..schemas.splits import ParsedSplit, ParsedSplitOrError
import json, re, logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a split expense parser. Extract split details from the input and return ONLY valid JSON.
If no split is described, return: {{"error": "no split found"}}
Always return a single flat JSON object — never a list.

Output format:
{{"description": "<what was split>", "total_amount": <number>, "paid_by_name": "<name or 'me'>", "participant_names": ["<name1>", ...], "split_type": "<equal|custom>", "date_str": "<today|yesterday|YYYY-MM-DD>"}}

Rules:
- paid_by_name: use "me" if the speaker paid, otherwise use the person's name
- participant_names: always include the payer in this list
- 2k = 2000, "two thousand" = 2000
- Always include "me" in participant_names if the speaker is part of the split

Examples:
Input: split 1800 dinner with Rahul and Priya, I paid
Output: {{"description":"dinner","total_amount":1800,"paid_by_name":"me","participant_names":["me","Rahul","Priya"],"split_type":"equal","date_str":"today"}}

Input: Amit paid 2400 for hotel split 4 ways between me Amit Sneha and Rohan
Output: {{"description":"hotel","total_amount":2400,"paid_by_name":"Amit","participant_names":["me","Amit","Sneha","Rohan"],"split_type":"equal","date_str":"today"}}

Input: split yesterday's cab 350 with Kavya she paid
Output: {{"description":"cab","total_amount":350,"paid_by_name":"Kavya","participant_names":["me","Kavya"],"split_type":"equal","date_str":"yesterday"}}

Input: hello
Output: {{"error":"no split found"}}
"""


class SplitParserService:
    def __init__(self, llm):
        self.chain = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{input}"),
        ]) | llm | StrOutputParser()

    def parse(self, text: str) -> ParsedSplitOrError:
        try:
            raw = self.chain.invoke({"input": text})
            logger.debug(f"Split LLM raw: {raw!r}")
            cleaned = self._clean(raw)
            payload = json.loads(cleaned)

            if not isinstance(payload, dict):
                return ParsedSplitOrError(success=False, error=f"Unexpected LLM response type: {type(payload)}")

            if "error" in payload:
                return ParsedSplitOrError(success=False, error=payload["error"])

            return ParsedSplitOrError(
                success=True,
                parsed=ParsedSplit(
                    description=payload["description"],
                    total_amount=float(payload["total_amount"]),
                    paid_by_name=payload.get("paid_by_name", "me"),
                    participant_names=payload.get("participant_names", []),
                    split_type=payload.get("split_type", "equal"),
                    date_str=payload.get("date_str", "today"),
                )
            )
        except json.JSONDecodeError as e:
            return ParsedSplitOrError(success=False, error=f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Split parse failed: {e}")
            return ParsedSplitOrError(success=False, error=str(e))

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return match.group(0) if match else text
