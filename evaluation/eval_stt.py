"""
STT evaluation — Word Error Rate on reference audio samples.
Place pairs in evaluation/stt_samples/:
  001.wav + 001.txt (reference transcript)

Run: python -m evaluation.eval_stt
"""
import sys, time, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.config import load_config
from backend.services.stt import STTService

logging.basicConfig(level=logging.WARNING)

SAMPLES_DIR = Path(__file__).parent / "stt_samples"
REPORT_DIR  = Path(__file__).parent / "reports"


def wer(ref: str, hyp: str) -> float:
    r, h = ref.lower().split(), hyp.lower().split()
    n, m = len(r), len(h)
    dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): dp[i][0] = i
    for j in range(m+1): dp[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            dp[i][j] = dp[i-1][j-1] if r[i-1]==h[j-1] else 1+min(dp[i-1][j],dp[i][j-1],dp[i-1][j-1])
    return dp[n][m] / max(n, 1)


class STTEvaluator:
    def __init__(self, stt):
        self.stt = stt
        self.results = []

    def run(self):
        if not SAMPLES_DIR.exists():
            print(f"No samples at {SAMPLES_DIR}. Create .wav + .txt pairs to run STT eval.")
            return {"total_samples": 0, "avg_wer": None}

        pairs = [(f, f.with_suffix(".txt")) for f in sorted(SAMPLES_DIR.glob("*.wav"))
                 if f.with_suffix(".txt").exists()]
        if not pairs:
            print("No .wav/.txt pairs found.")
            return {"total_samples": 0, "avg_wer": None}

        print(f"\n{'─'*60}\n  STT Evaluation — {len(pairs)} samples\n{'─'*60}\n")
        for wav, txt in pairs:
            ref = txt.read_text().strip()
            t0  = time.perf_counter()
            out = self.stt.transcribe_file(str(wav))
            ms  = round((time.perf_counter() - t0) * 1000)
            hyp = out["transcript"]
            w   = wer(ref, hyp)
            self.results.append({"file": wav.name, "reference": ref,
                                  "hypothesis": hyp, "wer": round(w, 3), "latency_ms": ms})
            icon = "✅" if w < 0.1 else "⚠️" if w < 0.3 else "❌"
            print(f"  {icon} {wav.name:<20} WER={w:.1%}  ({ms}ms)")
            print(f"     REF: {ref[:60]}")
            print(f"     HYP: {hyp[:60]}\n")

        avg = sum(r["wer"] for r in self.results) / len(self.results)
        metrics = {"total_samples": len(self.results), "avg_wer": round(avg, 3),
                   "avg_latency_ms": round(sum(r["latency_ms"] for r in self.results)/len(self.results))}
        print(f"  Avg WER: {avg:.1%}")
        return metrics

    def report(self, metrics):
        REPORT_DIR.mkdir(exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = REPORT_DIR / f"stt_eval_{ts}.md"
        lines = [f"# STT Evaluation\n", f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
                 "## Summary\n", "| Metric | Value |", "|--------|-------|"]
        for k, v in metrics.items():
            lines.append(f"| {k} | {v} |")
        if self.results:
            lines += ["\n## Per-file\n", "| File | WER | ms |", "|----|----|----|"]
            for r in self.results:
                lines.append(f"| {r['file']} | {r['wer']:.1%} | {r['latency_ms']} |")
        path.write_text("\n".join(lines))
        print(f"\n  Report → {path}")


if __name__ == "__main__":
    cfg = load_config()
    stt = STTService(cfg.whisper)
    ev  = STTEvaluator(stt)
    metrics = ev.run()
    ev.report(metrics)
