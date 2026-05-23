#!/usr/bin/env python3
"""
sector_rotation_updater.py

Refreshes the Sector Rotation Dashboard for the website.

Pipeline:
  1. Download 2y of weekly closes for SPY + 11 sector ETFs via yfinance.
  2. Compute RS-Ratio and RS-Momentum (RRG methodology) per sector.
  3. Render the Jinja2 template with the data baked in (static_mode = True,
     so notes save to browser localStorage instead of a backend).
  4. Write the result to ../sector-rotation.html at the repo root.

Runs in two contexts:
  - GitHub Actions (.github/workflows/sector-rotation.yml) — every Sunday, automatic.
  - Manual:  cd live_website && python3 scripts/sector_rotation_updater.py

Paths are resolved relative to this file, so the script works from any cwd.
"""

import os
import sys
from datetime import date, datetime

import pandas as pd
import yfinance as yf
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── PATHS (repo-relative, so this works under GitHub Actions and locally) ──
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
TEMPLATE    = "sector_rotation_template.html"
OUTPUT_HTML = os.path.join(REPO_ROOT, "sector-rotation.html")

# ── UNIVERSE ────────────────────────────────────────────────────────────────
BENCHMARK = "SPY"
SECTORS = {
    "XLB":  "Materials",
    "XLC":  "Communication Services",
    "XLE":  "Energy",
    "XLF":  "Financials",
    "XLI":  "Industrials",
    "XLK":  "Technology",
    "XLP":  "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
    "XLV":  "Health Care",
    "XLY":  "Consumer Discretionary",
}

QUADRANT_COLORS = {
    "LEADING":   "#00d4aa",
    "WEAKENING": "#c9a84c",
    "LAGGING":   "#e85d75",
    "IMPROVING": "#4a90e2",
    "UNKNOWN":   "#888888",
}


# ── CORE MATH ───────────────────────────────────────────────────────────────
def quadrant(rs_ratio, rs_mom):
    if rs_ratio is None or rs_mom is None or pd.isna(rs_ratio) or pd.isna(rs_mom):
        return "UNKNOWN"
    if rs_ratio >= 100 and rs_mom >= 100: return "LEADING"
    if rs_ratio >= 100 and rs_mom <  100: return "WEAKENING"
    if rs_ratio <  100 and rs_mom <  100: return "LAGGING"
    return "IMPROVING"


def compute_rrg(sector_close, spy_close):
    aligned = pd.concat([sector_close, spy_close], axis=1).dropna()
    aligned.columns = ["sector", "spy"]
    ratio = aligned["sector"] / aligned["spy"]
    smoothed = ratio.rolling(10).mean()
    rs_ratio = 100 + ((smoothed - smoothed.mean()) / smoothed.std()) * 10
    raw_mom = rs_ratio - rs_ratio.shift(1)
    rs_mom = 100 + ((raw_mom - raw_mom.mean()) / raw_mom.std()) * 10
    rs_mom = rs_mom.rolling(4).mean()
    return rs_ratio, rs_mom


# ── PRESENTATION HELPERS ────────────────────────────────────────────────────
def signal_for(prev_q, q):
    if not prev_q or prev_q == q:
        return (f"Holding {q}", "neutral")
    transitions = {
        ("IMPROVING", "LEADING"):   ("Entering LEADING",   "buy"),
        ("LAGGING",   "IMPROVING"): ("Entering IMPROVING", "watch"),
        ("LEADING",   "WEAKENING"): ("Entering WEAKENING", "trim"),
        ("WEAKENING", "LAGGING"):   ("Entering LAGGING",   "exit"),
    }
    return transitions.get((prev_q, q), (f"Moved to {q}", "neutral"))


def direction_arrow(history):
    if len(history) < 5:
        return "→"
    now, past = history[-1], history[-5]
    dr = now["rs_ratio"]    - past["rs_ratio"]
    dm = now["rs_momentum"] - past["rs_momentum"]
    if dr >= 0 and dm >= 0: return "↗"
    if dr >= 0 and dm <  0: return "↘"
    if dr <  0 and dm <  0: return "↙"
    return "↖"


def consecutive_weeks(history, current_q):
    n = 0
    for h in reversed(history):
        if quadrant(h["rs_ratio"], h["rs_momentum"]) == current_q:
            n += 1
        else:
            break
    return n


def market_regime(sector_quadrants):
    counts = {"LEADING": 0, "IMPROVING": 0, "WEAKENING": 0, "LAGGING": 0}
    for q in sector_quadrants:
        if q in counts:
            counts[q] += 1
    risk_on  = counts["LEADING"]  + counts["IMPROVING"]
    risk_off = counts["LAGGING"]  + counts["WEAKENING"]
    if risk_on  >= 5: return "Risk-On",  counts
    if risk_off >= 5: return "Risk-Off", counts
    return "Mixed", counts


# ── PIPELINE ────────────────────────────────────────────────────────────────
def fetch_and_compute():
    tickers = [BENCHMARK] + list(SECTORS.keys())
    print(f"[{datetime.now():%H:%M:%S}] Downloading {len(tickers)} tickers...")

    raw = yf.download(
        tickers, period="max", interval="1wk",
        auto_adjust=True, progress=False,
        group_by="ticker", threads=True,
    )

    closes = {}
    for t in tickers:
        try:
            series = raw[t]["Close"].dropna() if hasattr(raw.columns, "levels") else raw["Close"].dropna()
            if len(series) >= 20:
                closes[t] = series
            else:
                print(f"  WARN: {t} only {len(series)} bars, skipping")
        except Exception as e:
            print(f"  WARN: {t} fetch failed: {e}")

    if BENCHMARK not in closes:
        print(f"FATAL: benchmark {BENCHMARK} unavailable")
        sys.exit(1)

    spy = closes[BENCHMARK]
    output = {
        "last_updated": date.today().isoformat(),
        "benchmark":    BENCHMARK,
        "sectors":      {},
    }

    for ticker, name in SECTORS.items():
        if ticker not in closes:
            continue
        try:
            rs_ratio, rs_mom = compute_rrg(closes[ticker], spy)
            combined = pd.DataFrame({"rs_ratio": rs_ratio, "rs_momentum": rs_mom}).dropna()
            if len(combined) < 5:
                print(f"  WARN: {ticker} insufficient data")
                continue
            # Full history — used by the time-travel scrubber in the UI.
            history = [
                {"date": idx.strftime("%Y-%m-%d"),
                 "rs_ratio": round(float(r.rs_ratio), 3),
                 "rs_momentum": round(float(r.rs_momentum), 3)}
                for idx, r in combined.iterrows()
            ]
            cur = combined.iloc[-1]
            current = {"rs_ratio": round(float(cur.rs_ratio), 3),
                       "rs_momentum": round(float(cur.rs_momentum), 3)}
            q_now = quadrant(current["rs_ratio"], current["rs_momentum"])
            prev_q  = quadrant(*(combined.iloc[-2][["rs_ratio","rs_momentum"]])) if len(combined) >= 2 else None
            prior_q = quadrant(*(combined.iloc[-5][["rs_ratio","rs_momentum"]])) if len(combined) >= 5 else None

            output["sectors"][ticker] = {
                "name": name, "history": history, "current": current,
                "quadrant": q_now, "prev_quadrant": prev_q, "prior_quadrant": prior_q,
            }
        except Exception as e:
            print(f"  WARN: {ticker} compute failed: {e}")

    if not output["sectors"]:
        print("FATAL: no sectors computed")
        sys.exit(1)
    return output


def render_html(data):
    env = Environment(loader=FileSystemLoader(SCRIPT_DIR),
                      autoescape=select_autoescape(["html"]))
    tmpl = env.get_template(TEMPLATE)

    sectors_list, consec = [], {}
    for t, s in data["sectors"].items():
        sig_text, sig_kind = signal_for(s.get("prev_quadrant"), s["quadrant"])
        sectors_list.append({
            "ticker": t, "name": s["name"], "quadrant": s["quadrant"],
            "rs_ratio":    s["current"]["rs_ratio"],
            "rs_momentum": s["current"]["rs_momentum"],
            "direction":   direction_arrow(s["history"]),
            "signal_text": sig_text, "signal_kind": sig_kind,
            "color": QUADRANT_COLORS.get(s["quadrant"], "#888"),
            "note": "",
        })
        consec[t] = consecutive_weeks(s["history"], s["quadrant"])
    sectors_list.sort(key=lambda r: r["ticker"])

    regime, regime_counts = market_regime([s["quadrant"] for s in data["sectors"].values()])

    return tmpl.render(
        data=data, sectors=sectors_list,
        regime=regime, regime_counts=regime_counts,
        consecutive=consec, quadrant_colors=QUADRANT_COLORS,
        error=None, static_mode=True,
    )


def main():
    data = fetch_and_compute()
    html = render_html(data)
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    with open(OUTPUT_HTML, "w") as f:
        f.write(html)

    counts = {"LEADING": 0, "IMPROVING": 0, "WEAKENING": 0, "LAGGING": 0}
    for s in data["sectors"].values():
        counts[s["quadrant"]] = counts.get(s["quadrant"], 0) + 1

    print()
    print(f"  Wrote {OUTPUT_HTML} ({os.path.getsize(OUTPUT_HTML)/1024:.1f} KB)")
    print(f"  As of: {data['last_updated']}  ·  Sectors: {len(data['sectors'])}")
    print(f"  Leading {counts['LEADING']}  ·  Improving {counts['IMPROVING']}  ·  "
          f"Weakening {counts['WEAKENING']}  ·  Lagging {counts['LAGGING']}")


if __name__ == "__main__":
    main()
