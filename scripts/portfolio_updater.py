#!/usr/bin/env python3
"""
portfolio_updater.py

Refreshes the live portfolio table on my-portfolio.html using yfinance.

Pipeline:
  1. Fetch current prices for each holding from yfinance.
  2. Compute total return, return %, market value (CAD-normalized).
  3. Patch the table body, hero stat tiles, and "As of …" date string in
     my-portfolio.html in place.

Runs in two contexts:
  - GitHub Actions (.github/workflows/portfolio.yml) — weekdays at market close.
  - Manual:  cd live_website && python3 scripts/portfolio_updater.py

Paths are resolved relative to this file. Adapted from the original
update_portfolio.py at the repo root.
"""

import os
import re
import sys
from datetime import datetime

import yfinance as yf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
HTML_FILE  = os.path.join(REPO_ROOT, "my-portfolio.html")

# ── HOLDINGS ────────────────────────────────────────────────────────────────
HOLDINGS = [
    {"symbol": "BIP.UN", "qty": 2.0499, "cost_basis_cad": 102.72},
    {"symbol": "CMI",    "qty": 0.2532, "cost_basis_usd": 101.19},
    {"symbol": "CSU",    "qty": 0.0474, "cost_basis_cad": 200.58},
    {"symbol": "DOL",    "qty": 0.0005, "cost_basis_cad": 174.38},
    {"symbol": "HCA",    "qty": 0.2850, "cost_basis_usd": 150.18},
    {"symbol": "IDCC",   "qty": 0.2265, "cost_basis_usd": 126.45},
    {"symbol": "MRK",    "qty": 1.0123, "cost_basis_usd":  87.98},
    {"symbol": "RCI.B",  "qty": 2.0603, "cost_basis_cad":  46.02},
    {"symbol": "SBUX",   "qty": 1.0000, "cost_basis_cad":  26.30},
    {"symbol": "TIH",    "qty": 1.0091, "cost_basis_cad": 142.58},
    {"symbol": "UNH",    "qty": 0.3358, "cost_basis_usd": 101.80},
]

USD_TO_CAD = 1.38


def fetch_portfolio_data():
    print("Fetching live prices from yfinance...")
    data = {}
    for h in HOLDINGS:
        sym = h["symbol"]
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            # Fallback: fast history lookup
            if not price:
                hist = t.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price:
                data[sym] = {
                    "price":    round(float(price), 2),
                    "currency": "CAD" if ".UN" in sym or sym in ["DOL", "RCI.B", "SBUX", "TIH"] else "USD",
                    "qty":      h["qty"],
                    "cost_basis_cad": h.get("cost_basis_cad"),
                    "cost_basis_usd": h.get("cost_basis_usd"),
                }
                print(f"  {sym:<6} ${price:>8.2f}")
            else:
                print(f"  ⚠ {sym}: could not fetch price")
        except Exception as e:
            print(f"  ✗ {sym}: {e}")
    return data


def calculate_returns(portfolio_data):
    out = []
    for h in HOLDINGS:
        sym = h["symbol"]
        if sym not in portfolio_data:
            continue
        d = portfolio_data[sym]
        price = d["price"]; qty = d["qty"]
        if d["currency"] == "CAD":
            cost_basis = d["cost_basis_cad"]
            market_value = price * qty
            market_value_cad = market_value
            total_return = market_value - cost_basis * qty
            return_pct = ((price - cost_basis) / cost_basis) * 100
        else:
            cost_basis = d["cost_basis_usd"]
            market_value = price * qty
            market_value_cad = market_value * USD_TO_CAD
            total_return = market_value_cad - cost_basis * qty * USD_TO_CAD
            return_pct = ((price - cost_basis) / cost_basis) * 100
        out.append({
            "symbol":           sym,
            "price":            price,
            "qty":              qty,
            "currency":         d["currency"],
            "market_value":     round(market_value, 2),
            "market_value_cad": round(market_value_cad, 2),
            "total_return":     round(total_return, 2),
            "return_pct":       round(return_pct, 2),
        })
    return out


def generate_table_rows(results):
    rows = []
    for p in results:
        cls = "g" if p["return_pct"] >= 0 else "r"
        bar = "#4ec97a" if p["return_pct"] >= 0 else "#e05252"
        w = min(abs(p["return_pct"]), 100)
        rows.append(
            f"""        <tr>
          <td>
            <div class="td-sym">{p['symbol']}</div>
            <div class="td-name">{p['symbol']}</div>
          </td>
          <td>${p['price']:.2f} <span class="ccy">{p['currency']}</span></td>
          <td>{p['qty']:.4f}</td>
          <td>${p['market_value']:.2f} <span class="ccy">{p['currency']}</span></td>
          <td class="{cls}">${p['total_return']:+.2f}</td>
          <td>
            <div class="td-bar-wrap">
              <div class="td-bar"><div class="td-bar-fill" style="width:{w}%;background:{bar};"></div></div>
              <span class="{cls}">{p['return_pct']:+.2f}%</span>
            </div>
          </td>
          <td>—</td>
          <td>—</td>
        </tr>
""")
    return "".join(rows)


def update_html_file(results):
    if not results:
        print("ERROR: no results to write — aborting.")
        sys.exit(1)

    with open(HTML_FILE, "r") as f:
        html = f.read()

    total_return = sum(p["total_return"] for p in results)
    total_value  = sum(p["market_value_cad"] for p in results)
    pf_ytd_pct   = (total_return / total_value * 100) if total_value > 0 else 0
    best   = max(results, key=lambda x: x["return_pct"])
    worst  = min(results, key=lambda x: x["return_pct"])
    now    = datetime.now().strftime("%B %d, %Y")

    # Replace table body
    new_tbody = f"<tbody>\n{generate_table_rows(results)}\n      </tbody>"
    html = re.sub(r"<tbody>.*?</tbody>", new_tbody, html, flags=re.DOTALL)

    # Update "As of …" date string
    html = re.sub(r"As of \w+ \d+, \d+", f"As of {now}", html)

    # Update hero stat tiles
    hero_stats = f"""    <div class="pf-hero-stats">
    <div class="pf-hero-stat">
      <div class="pf-hero-stat-val g">{pf_ytd_pct:+.1f}%</div>
      <div class="pf-hero-stat-label">YTD Return</div>
    </div>
    <div class="pf-hero-stat">
      <div class="pf-hero-stat-val">{len(results)}</div>
      <div class="pf-hero-stat-label">Active Holdings</div>
    </div>
    <div class="pf-hero-stat">
      <div class="pf-hero-stat-val g">{best['return_pct']:+.0f}%</div>
      <div class="pf-hero-stat-label">Best · {best['symbol']}</div>
    </div>
    <div class="pf-hero-stat">
      <div class="pf-hero-stat-val r">{worst['return_pct']:+.0f}%</div>
      <div class="pf-hero-stat-label">Laggard · {worst['symbol']}</div>
    </div>
  </div>"""
    html = re.sub(r"<div class=\"pf-hero-stats\">.*?</div>", hero_stats, html, flags=re.DOTALL)

    with open(HTML_FILE, "w") as f:
        f.write(html)

    print(f"\n✓ Updated {HTML_FILE}")
    print(f"  Portfolio YTD : {pf_ytd_pct:+.2f}%")
    print(f"  Best          : {best['symbol']}  {best['return_pct']:+.2f}%")
    print(f"  Worst         : {worst['symbol']} {worst['return_pct']:+.2f}%")


def main():
    data    = fetch_portfolio_data()
    results = calculate_returns(data)
    update_html_file(results)


if __name__ == "__main__":
    main()
