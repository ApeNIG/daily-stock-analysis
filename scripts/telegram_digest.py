"""
DSA Telegram Digest — clean, scannable morning briefing.
Reads analysis_history from DSA's SQLite DB, formats a concise
Telegram message grouped by signal strength.

Usage:
  python scripts/telegram_digest.py              # today's analysis
  python scripts/telegram_digest.py --date 2026-06-27  # specific date
  python scripts/telegram_digest.py --dry-run     # print without sending
"""

import sqlite3
import json
import os
import sys
import argparse
import requests
from datetime import datetime, date
from pathlib import Path

# IBS universe markers
IBS_ALPACA = {"SPY","QQQ","IWM","DIA","AAPL","AMZN","META","NVDA","JPM","UNH","JNJ","WMT","HD"}
IBS_T212_ONLY = {"INTC","NKE","PYPL","SBUX","PFE","MRK","PEP","BAC","C","DIS","T","VZ","KO","PG","XOM"}

DB_PATH = Path(__file__).parent.parent / "data" / "stock_analysis.db"

def load_analyses(target_date: str) -> list[dict]:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT code, name, sentiment_score, operation_advice,
                  trend_prediction, analysis_summary, ideal_buy, stop_loss
           FROM analysis_history
           WHERE date(created_at) = ?
           ORDER BY sentiment_score DESC""",
        (target_date,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def format_digest(analyses: list[dict], target_date: str) -> str:
    if not analyses:
        return f"No DSA analysis found for {target_date}."

    # Market ETFs
    etfs = {a["code"]: a for a in analyses if a["code"] in ("SPY", "QQQ", "IWM", "DIA")}
    stocks = [a for a in analyses if a["code"] not in ("SPY", "QQQ", "IWM", "DIA")]

    # Header
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    lines = [f"US Market Brief — {dt.strftime('%d %b %Y')}", ""]

    # Market mood from ETFs
    if etfs:
        etf_scores = [a["sentiment_score"] or 0 for a in etfs.values()]
        avg = sum(etf_scores) / len(etf_scores)
        if avg >= 60:
            mood = "Bullish"
        elif avg >= 45:
            mood = "Neutral"
        elif avg >= 30:
            mood = "Bearish"
        else:
            mood = "Strongly Bearish"

        etf_parts = []
        for sym in ("SPY", "QQQ", "IWM", "DIA"):
            if sym in etfs:
                s = etfs[sym]["sentiment_score"] or 0
                etf_parts.append(f"{sym} {s}")
        lines.append(f"Market: {mood} ({' | '.join(etf_parts)})")
        lines.append("")

    # Split stocks by signal
    buys = [s for s in stocks if (s["sentiment_score"] or 0) >= 55]
    holds = [s for s in stocks if 40 <= (s["sentiment_score"] or 0) < 55]
    avoids = [s for s in stocks if (s["sentiment_score"] or 0) < 40]

    def fmt_stock(s):
        score = s["sentiment_score"] or 0
        tag = ""
        if s["code"] in IBS_ALPACA:
            tag = " [A]"
        elif s["code"] in IBS_T212_ONLY:
            tag = " [T]"
        advice = (s["operation_advice"] or "")[:30]
        return f"  {s['code']} {score}{tag} — {advice}"

    if buys:
        lines.append("BUY / ENTRY CANDIDATES:")
        for s in sorted(buys, key=lambda x: x["sentiment_score"] or 0, reverse=True):
            lines.append(fmt_stock(s))
        lines.append("")

    if holds:
        lines.append("HOLD / WATCH:")
        for s in sorted(holds, key=lambda x: x["sentiment_score"] or 0, reverse=True):
            lines.append(fmt_stock(s))
        lines.append("")

    if avoids:
        lines.append("AVOID / REDUCE:")
        for s in sorted(avoids, key=lambda x: x["sentiment_score"] or 0, reverse=True):
            lines.append(fmt_stock(s))
        lines.append("")

    # IBS sweet spot callout
    ibs_candidates = [s for s in analyses
                      if s["code"] in (IBS_ALPACA | IBS_T212_ONLY)
                      and (s["sentiment_score"] or 0) >= 50]
    if ibs_candidates:
        names = ", ".join(s["code"] for s in ibs_candidates[:5])
        lines.append(f"IBS watch: {names}")
        lines.append("")

    # Footer
    lines.append(f"{len(analyses)} symbols scanned. [A]=Alpaca [T]=T212 only")

    return "\n".join(lines)


def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        # Try loading from .env
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1]
                elif line.startswith("TELEGRAM_CHAT_ID="):
                    chat_id = line.split("=", 1)[1]

    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
        sys.exit(1)

    # Telegram max is 4096 chars
    if len(text) > 4096:
        text = text[:4090] + "\n..."

    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    if r.ok:
        print("Telegram digest sent.")
    else:
        print(f"Telegram error: {r.status_code} {r.text}")


def export_snapshot(analyses: list[dict], target_date: str):
    """Export a JSON snapshot for correlation tracking."""
    snapshot = {
        "date": target_date,
        "scores": {a["code"]: {
            "score": a["sentiment_score"],
            "advice": a["operation_advice"],
            "trend": a["trend_prediction"],
        } for a in analyses}
    }
    out_dir = Path(__file__).parent.parent / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"dsa_snapshot_{target_date}.json"
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Snapshot exported: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="DSA Telegram Digest")
    parser.add_argument("--date", default=date.today().isoformat(), help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Print without sending")
    args = parser.parse_args()

    analyses = load_analyses(args.date)
    digest = format_digest(analyses, args.date)

    print(digest)
    print(f"\n--- {len(digest)} chars ---")

    # Always export snapshot for correlation tracking
    if analyses:
        export_snapshot(analyses, args.date)

    if not args.dry_run:
        send_telegram(digest)


if __name__ == "__main__":
    main()
