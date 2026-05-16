"""
Extraction evaluation — run against 25 test cases, generate markdown report.
Run: python -m evaluation.eval_extraction
     python -m evaluation.eval_extraction --model llama
"""
import sys, json, time, argparse, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.config import load_config
from backend.services.llm_chain import ExpenseExtractionChain

logging.basicConfig(level=logging.WARNING)

TEST_CASES = Path(__file__).parent / "test_cases.json"
REPORT_DIR = Path(__file__).parent / "reports"


def _amount_ok(pred, exp, tol=0.01):
    if pred is None or exp is None:
        return False
    return abs(pred - exp) / max(exp, 1) <= tol


def _date_type(s):
    if s in ("today", "yesterday"):
        return s
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return "specific"
    except Exception:
        return "unknown"


class ExtractionEvaluator:
    def __init__(self, chain):
        self.chain = chain
        self.results = []

    def run(self, cases):
        print(f"\n{'─'*60}\n  Running {len(cases)} test cases\n{'─'*60}\n")
        for tc in cases:
            t0 = time.perf_counter()
            out = self.chain.extract(tc["input"])
            ms = round((time.perf_counter() - t0) * 1000)
            exp = tc["expected"]
            r = {"id": tc["id"], "input": tc["input"], "expected": exp,
                 "latency_ms": ms, "predicted_success": out.success,
                 "error": out.error, "raw_output": out.raw_output}
            r["success_match"] = out.success == exp["should_succeed"]
            if out.success and exp["should_succeed"] and out.expense:
                e = out.expense
                r["predicted_amount"]   = e.amount
                r["predicted_category"] = e.category.value
                r["predicted_payment"]  = e.payment_method.value
                r["predicted_date_type"] = _date_type(e.date)
                r["predicted_tx_type"]  = e.transaction_type.value
                r["amount_ok"]   = _amount_ok(e.amount, exp.get("amount"))
                r["category_ok"] = e.category.value == exp.get("category")
                r["payment_ok"]  = e.payment_method.value == exp.get("payment_method") or exp.get("payment_method") == "any"
                r["date_ok"]     = _date_type(e.date) == exp.get("date_type") or exp.get("date_type") == "any"
                r["tx_ok"]       = not exp.get("transaction_type") or e.transaction_type.value == exp.get("transaction_type")
            else:
                r["amount_ok"] = r["category_ok"] = r["payment_ok"] = r["date_ok"] = r["tx_ok"] = None
            self.results.append(r)
            self._print_row(r)
        return self._metrics()

    def _print_row(self, r):
        s = "✅" if r["success_match"] else "❌"
        def sym(v): return "✓" if v is True else "✗" if v is False else "-"
        print(f"  [{r['id']:>2}] {s} {r['input'][:40]:<40}  "
              f"amt={sym(r.get('amount_ok'))} cat={sym(r.get('category_ok'))} "
              f"pay={sym(r.get('payment_ok'))} dt={sym(r.get('date_ok'))}  ({r['latency_ms']}ms)")

    def _metrics(self):
        n  = len(self.results)
        sm = sum(1 for r in self.results if r["success_match"])
        pos = [r for r in self.results if r.get("amount_ok") is not None]
        np = len(pos) or 1
        metrics = {
            "total_cases": n,
            "success_rate":    round(sm / n, 3),
            "amount_accuracy": round(sum(1 for r in pos if r["amount_ok"]) / np, 3),
            "category_accuracy": round(sum(1 for r in pos if r["category_ok"]) / np, 3),
            "payment_accuracy":  round(sum(1 for r in pos if r["payment_ok"]) / np, 3),
            "date_accuracy":     round(sum(1 for r in pos if r["date_ok"]) / np, 3),
        }
        metrics["overall_score"] = round(
            metrics["amount_accuracy"] * 0.35 + metrics["category_accuracy"] * 0.30 +
            metrics["payment_accuracy"] * 0.15 + metrics["date_accuracy"] * 0.20, 3)
        metrics["avg_latency_ms"] = round(sum(r["latency_ms"] for r in self.results) / n)
        print(f"\n{'─'*60}\n  RESULTS\n{'─'*60}")
        for k, v in metrics.items():
            bar = "█" * int(v * 20) if isinstance(v, float) and v <= 1 else ""
            val = f"{v*100:.1f}%" if isinstance(v, float) and v <= 1 else str(v)
            print(f"  {k.replace('_',' ').title():<22} {val:>7}  {bar}")
        return metrics

    def report(self, metrics, model_id):
        REPORT_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"eval_{ts}.md"
        lines = [f"# Extraction Evaluation\n",
                 f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
                 f"**Model:** `{model_id}`  ", f"**Cases:** {metrics['total_cases']}\n",
                 "## Metrics\n", "| Metric | Score |", "|--------|-------|"]
        for k, v in metrics.items():
            val = f"{v*100:.1f}%" if isinstance(v, float) and v <= 1 else str(v)
            lines.append(f"| {k.replace('_',' ').title()} | {val} |")
        lines += ["\n## Results\n", "| ID | Input | ✓ | Amt | Cat | Pay | Date | ms |",
                  "|----|-------|---|-----|-----|-----|------|----|"]
        for r in self.results:
            def sym(v): return "✓" if v is True else "✗" if v is False else "-"
            ok = "✅" if r["success_match"] else "❌"
            lines.append(f"| {r['id']} | {r['input'][:35]} | {ok} | "
                         f"{sym(r.get('amount_ok'))} | {sym(r.get('category_ok'))} | "
                         f"{sym(r.get('payment_ok'))} | {sym(r.get('date_ok'))} | {r['latency_ms']} |")
        path.write_text("\n".join(lines))
        print(f"\n  Report → {path}")
        return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    overrides = [f"model={args.model}"] if args.model else []
    cfg = load_config(overrides=overrides)
    chain = ExpenseExtractionChain(cfg.model)
    cases = json.loads(TEST_CASES.read_text())
    ev = ExtractionEvaluator(chain)
    metrics = ev.run(cases)
    ev.report(metrics, cfg.model.model_id)
