#!/usr/bin/env python3
"""
portfolio_updater.py

Refreshes the personal portfolio dashboard using yfinance.

Source of truth = my-portfolio.html itself.  When you manually update
positions (e.g. from a Wealthsimple screenshot), edit my-portfolio.html
directly; this script then:

  1. Parses the current holdings (symbol, name, qty, currency, price,
     return %) out of the table tbody.
  2. Derives each position's cost basis from the parsed state, so it
     stays in sync with whatever you most recently wrote down.
  3. Fetches today's price for each ticker from yfinance.
     - On a fetch failure, the existing price is kept and a warning is
       logged.  We never silently drop a holding.
  4. Recomputes market value, weight, total return ($CAD), and return %.
  5. Rewrites the tbody in place, replaces the .pf-hero-stats inner
     content using a proper brace-counting helper (NOT the .*?</div>
     regex that caused the previous duplication bug), and refreshes the
     "As of" date + meta description.
  6. Updates index.html in four places:
       - <span class="hero-stat-val">  (the big +X.X% in the hero)
       - <span class="hero-stat-label">YTD Return · N Holdings</span>
       - "+X.X% YTD return" in the project description
       - "+X.X% YTD · N Holdings" next to the "View Portfolio" button

Run from anywhere — paths resolve relative to this file.
"""

import os
import re
import sys
from datetime import datetime

import yfinance as yf

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT      = os.path.dirname(SCRIPT_DIR)
PORTFOLIO_HTML = os.path.join(REPO_ROOT, "my-portfolio.html")
INDEX_HTML     = os.path.join(REPO_ROOT, "index.html")

USD_TO_CAD_FALLBACK = 1.38

MINUS = "−"   # the proper minus sign used throughout the site
PLUS  = "+"


# ───────────────────────── PARSE ─────────────────────────
def parse_holdings(html: str) -> list[dict]:
    """Extract current holdings + derived cost basis from the table tbody."""
    tbody_m = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    if not tbody_m:
        raise RuntimeError("No <tbody> found in my-portfolio.html")
    tbody = tbody_m.group(1)

    rows = re.findall(r"<tr>(.*?)</tr>", tbody, re.DOTALL)
    if not rows:
        raise RuntimeError("No <tr> rows found inside <tbody>")

    holdings: list[dict] = []
    for raw in rows:
        sym_m  = re.search(r'<div class="td-sym">([^<]+)</div>', raw)
        name_m = re.search(r'<div class="td-name">([^<]+)</div>', raw)
        tds    = re.findall(r"<td[^>]*>(.*?)</td>", raw, re.DOTALL)
        if not (sym_m and name_m and len(tds) >= 7):
            raise RuntimeError(
                "Row structure didn't match expected 7-column layout — "
                "aborting before we corrupt anything.\n"
                f"  Offending row begins: {raw[:160]}…"
            )

        symbol = sym_m.group(1).strip()
        name   = name_m.group(1).strip()

        price_m = re.search(r'\$([\d,.]+)\s*<span class="ccy">(\w+)</span>', tds[1])
        if not price_m:
            raise RuntimeError(f"Cannot parse price for {symbol}: {tds[1][:120]}")
        price = float(price_m.group(1).replace(",", ""))
        ccy   = price_m.group(2)

        try:
            qty = float(tds[2].strip())
        except ValueError:
            raise RuntimeError(f"Cannot parse qty for {symbol}: {tds[2]!r}")

        ret_m = re.search(r'<span class="[gr]">([+\-−]?[\d.]+)%</span>', tds[-1])
        if not ret_m:
            raise RuntimeError(f"Cannot parse return % for {symbol}: {tds[-1][:120]}")
        ret_txt = ret_m.group(1).replace("−", "-").lstrip("+")
        return_pct = float(ret_txt)

        cost_basis = round(price / (1 + return_pct / 100), 4)

        holdings.append({
            "symbol":     symbol,
            "name":       name,
            "qty":        qty,
            "ccy":        ccy,
            "old_price":  price,
            "return_pct": return_pct,
            "cost_basis": cost_basis,
        })
    return holdings


# ─────────────────────── FX + PRICES ──────────────────────
def get_usdcad_rate() -> float:
    try:
        t = yf.Ticker("USDCAD=X")
        rate = (t.info or {}).get("regularMarketPrice")
        if not rate:
            fi = t.fast_info
            rate = getattr(fi, "last_price", None)
        if rate:
            print(f"  USD/CAD: {rate:.4f}")
            return float(rate)
    except Exception as e:
        print(f"  ⚠ USD/CAD fetch failed: {e}")
    print(f"  USD/CAD: using fallback {USD_TO_CAD_FALLBACK}")
    return USD_TO_CAD_FALLBACK


def refresh_prices(holdings, usd_to_cad):
    """Fetch new prices.  Safeguards:
      - If yfinance reports a currency different from the HTML's stated
        currency (e.g. yfinance 'CRM' = USD but HTML lists CRM as a CAD
        CDR), treat the fetch as failed — keep the old price.  This
        prevents catastrophic mis-pricing when symbols collide with
        differently-listed securities.
      - If no price comes back at all, keep the old one and warn.
      - The price is never silently wrong: every kept-old or skipped
        position is surfaced in the failures list."""
    results, failures = [], []
    for h in holdings:
        sym = h["symbol"]
        new_price = None
        fetched_ccy = None
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            new_price = info.get("currentPrice") or info.get("regularMarketPrice")
            fetched_ccy = info.get("currency")
            if not new_price:
                fi = t.fast_info
                new_price = getattr(fi, "last_price", None)
                fetched_ccy = fetched_ccy or getattr(fi, "currency", None)
            if not new_price:
                hist = t.history(period="5d")
                if not hist.empty:
                    new_price = float(hist["Close"].iloc[-1])
        except Exception as e:
            failures.append((sym, str(e)))

        # Currency sanity check before trusting the fetched price.
        if new_price and fetched_ccy and fetched_ccy.upper() != h["ccy"].upper():
            failures.append((sym,
                f"currency mismatch — yfinance returned {fetched_ccy}, "
                f"your HTML lists this as {h['ccy']}.  Likely a CDR / "
                f"different listing; consider renaming the symbol to e.g. "
                f"{sym}.NE or {sym}.TO so yfinance returns the right security."))
            new_price = h["old_price"]
            note = "(kept old — ccy mismatch)"
        elif not new_price:
            if not any(s == sym for s, _ in failures):
                failures.append((sym, "no price data returned"))
            new_price = h["old_price"]
            note = "(kept old)"
        else:
            new_price = round(float(new_price), 2)
            note = ""

        cost = h["cost_basis"]
        new_return = (new_price - cost) / cost * 100 if cost else 0.0
        market_value = new_price * h["qty"]
        if h["ccy"] == "CAD":
            market_value_cad  = market_value
            total_return_cad  = (new_price - cost) * h["qty"]
        else:
            market_value_cad  = market_value * usd_to_cad
            total_return_cad  = (new_price - cost) * h["qty"] * usd_to_cad

        results.append({
            **h,
            "price":            new_price,
            "return_pct":       new_return,
            "market_value":     round(market_value, 2),
            "market_value_cad": round(market_value_cad, 2),
            "total_return_cad": round(total_return_cad, 2),
        })
        print(f"  {sym:<7}{h['ccy']}  ${new_price:>9,.2f}   ret {new_return:+7.2f}%  {note}")
    return results, failures


# ─────────────────────── BUILD HTML ───────────────────────
def build_row(r, total_cad) -> str:
    sym, name, ccy = r["symbol"], r["name"], r["ccy"]
    qty, price     = r["qty"], r["price"]
    mv             = r["market_value"]
    weight_pct     = (r["market_value_cad"] / total_cad * 100) if total_cad > 0 else 0
    weight_bar_w   = min(weight_pct * 5, 100)   # 20% weight = full bar
    tr             = r["total_return_cad"]
    ret_pct        = r["return_pct"]

    ret_cls   = "g" if ret_pct >= 0 else "r"
    ret_color = "#4ec97a" if ret_pct >= 0 else "#e05252"
    ret_sign  = PLUS if ret_pct >= 0 else MINUS
    ret_bar_w = min(abs(ret_pct), 100)

    tr_cls  = "g" if tr >= 0 else "r"
    tr_sign = PLUS if tr >= 0 else MINUS

    return (
        '        <tr>\n'
        f'          <td><div class="td-sym">{sym}</div><div class="td-name">{name}</div></td>\n'
        f'          <td>${price:.2f} <span class="ccy">{ccy}</span></td>\n'
        f'          <td>{qty:.4f}</td>\n'
        f'          <td>${mv:.2f} <span class="ccy">{ccy}</span></td>\n'
        f'          <td><div class="td-bar-wrap"><div class="td-bar"><div class="td-bar-fill" style="width:{weight_bar_w:.1f}%;background:rgba(201,168,76,0.6);"></div></div><span>{weight_pct:.1f}%</span></div></td>\n'
        f'          <td class="{tr_cls}">{tr_sign}${abs(tr):.2f}</td>\n'
        f'          <td><div class="td-bar-wrap"><div class="td-bar"><div class="td-bar-fill" style="width:{ret_bar_w:.0f}%;background:{ret_color};"></div></div><span class="{ret_cls}">{ret_sign}{abs(ret_pct):.1f}%</span></div></td>\n'
        '        </tr>'
    )


def replace_div_inner(html: str, class_name: str, new_inner: str) -> str:
    """Replace the *inner content* of `<div … class="…class_name…">…</div>`.
    Counts nested <div> open/close tags so the regex bug from the old
    updater (.*?</div> terminating at the first nested close) cannot recur.
    """
    open_re = re.compile(
        r'<div\b[^>]*\bclass="[^"]*\b' + re.escape(class_name) + r'\b[^"]*"[^>]*>'
    )
    m = open_re.search(html)
    if not m:
        return html
    inner_start = m.end()
    depth, pos = 1, inner_start
    inner_end = -1
    while depth > 0 and pos < len(html):
        nxt_open  = html.find("<div", pos)
        nxt_close = html.find("</div>", pos)
        if nxt_close < 0:
            return html   # malformed — bail safely
        if 0 <= nxt_open < nxt_close:
            depth += 1
            pos = nxt_open + 4
        else:
            depth -= 1
            inner_end = nxt_close
            pos = nxt_close + 6
    if inner_end < 0:
        return html
    return html[:inner_start] + new_inner + html[inner_end:]


def build_hero_stats_inner(pf_ytd, count, best, worst) -> str:
    ytd_cls  = "g" if pf_ytd >= 0 else "r"
    ytd_sign = PLUS if pf_ytd >= 0 else MINUS
    best_sign  = PLUS if best["return_pct"]  >= 0 else MINUS
    worst_sign = PLUS if worst["return_pct"] >= 0 else MINUS
    return (
        "\n"
        '    <div class="pf-hero-stat">\n'
        f'      <div class="pf-hero-stat-val {ytd_cls}">{ytd_sign}{abs(pf_ytd):.1f}%</div>\n'
        '      <div class="pf-hero-stat-label">YTD Return</div>\n'
        '    </div>\n'
        '    <div class="pf-hero-stat">\n'
        f'      <div class="pf-hero-stat-val">{count}</div>\n'
        '      <div class="pf-hero-stat-label">Active Holdings</div>\n'
        '    </div>\n'
        '    <div class="pf-hero-stat">\n'
        f'      <div class="pf-hero-stat-val g">{best_sign}{abs(best["return_pct"]):.0f}%</div>\n'
        f'      <div class="pf-hero-stat-label">Best · {best["symbol"]}</div>\n'
        '    </div>\n'
        '    <div class="pf-hero-stat">\n'
        f'      <div class="pf-hero-stat-val r">{worst_sign}{abs(worst["return_pct"]):.0f}%</div>\n'
        f'      <div class="pf-hero-stat-label">Laggard · {worst["symbol"]}</div>\n'
        '    </div>\n'
        '  '
    )


# ─────────────────────── WRITE ────────────────────────────
def update_portfolio_html(results):
    with open(PORTFOLIO_HTML, encoding="utf-8") as f:
        html = f.read()

    total_cad    = sum(r["market_value_cad"] for r in results)
    total_return = sum(r["total_return_cad"] for r in results)
    total_cost   = total_cad - total_return
    pf_ytd       = (total_return / total_cost * 100) if total_cost > 0 else 0.0
    best         = max(results, key=lambda x: x["return_pct"])
    worst        = min(results, key=lambda x: x["return_pct"])

    # ── tbody ──────────────────────────────────────────────
    rows = [build_row(r, total_cad) for r in results]
    new_tbody = "<tbody>\n\n" + "\n\n".join(rows) + "\n\n      </tbody>"
    html = re.sub(r"<tbody>.*?</tbody>", new_tbody, html, count=1, flags=re.DOTALL)

    # ── hero stats inner (brace-counted, NOT regex-greedy) ─
    html = replace_div_inner(
        html, "pf-hero-stats",
        build_hero_stats_inner(pf_ytd, len(results), best, worst),
    )

    # ── "As of" date + meta description + "N positions" tag
    now_long  = datetime.now().strftime("%B %d, %Y")
    now_short = datetime.now().strftime("%b %d, %Y")
    html = re.sub(r"As of \w+ \d+,? \d+", f"As of {now_long}", html)
    html = re.sub(
        r'(<meta name="description" content="Personal investment portfolio — )'
        r'\d+ holdings, [+\-−\d.]+% YTD return\." />',
        rf'\g<1>{len(results)} holdings, {PLUS if pf_ytd>=0 else MINUS}{abs(pf_ytd):.1f}% YTD return." />',
        html,
    )
    html = re.sub(
        r'\d+ positions (?:&middot;|·) \w+ \d+, \d{4}',
        f"{len(results)} positions · {now_short}",
        html,
    )

    with open(PORTFOLIO_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✓ Updated my-portfolio.html")
    print(f"   Total value : ${total_cad:,.2f} CAD")
    print(f"   Total cost  : ${total_cost:,.2f} CAD")
    print(f"   YTD return  : {PLUS if pf_ytd>=0 else MINUS}{abs(pf_ytd):.2f}%")
    print(f"   Best        : {best['symbol']}   {best['return_pct']:+.1f}%")
    print(f"   Laggard     : {worst['symbol']}  {worst['return_pct']:+.1f}%")
    return pf_ytd, len(results)


def update_index_html(pf_ytd, count):
    if not os.path.exists(INDEX_HTML):
        return
    with open(INDEX_HTML, encoding="utf-8") as f:
        html = f.read()

    sign  = PLUS if pf_ytd >= 0 else MINUS
    ytd_s = f"{sign}{abs(pf_ytd):.1f}%"

    # 1) Big hero stat value (first <span class="hero-stat-val">)
    html = re.sub(
        r'(<span class="hero-stat-val">)[+\-−\d.]+%(</span>)',
        rf'\g<1>{ytd_s}\g<2>',
        html, count=1,
    )
    # 2) "YTD Return · N Holdings" label
    html = re.sub(
        r'<span class="hero-stat-label">YTD Return · \d+ Holdings</span>',
        f'<span class="hero-stat-label">YTD Return · {count} Holdings</span>',
        html,
    )
    # 3) Project description line: "+X.X% YTD return."
    html = re.sub(
        r'[+\-−]\d+\.\d+% YTD return',
        f'{ytd_s} YTD return',
        html,
    )
    # 4) Project card subtitle: "+X.X% YTD · N Holdings"
    html = re.sub(
        r'[+\-−]\d+\.\d+% YTD · \d+ Holdings',
        f'{ytd_s} YTD · {count} Holdings',
        html,
    )
    # 5) About-section highlight-num — pinned to the "Personal Portfolio · YTD Return"
    #    label so we never accidentally overwrite the "Top 10", "4.0", or "9"
    #    highlights next to it.
    html = re.sub(
        r'(<div class="highlight-num">)[+\-−\d.]+%(</div>\s*<div class="highlight-label">Personal Portfolio · YTD Return</div>)',
        rf'\g<1>{ytd_s}\g<2>',
        html,
    )

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Updated index.html hero  →  {ytd_s} · {count} holdings")


# ─────────────────────── ENTRYPOINT ───────────────────────
def main():
    print("Reading current holdings from my-portfolio.html…")
    with open(PORTFOLIO_HTML, encoding="utf-8") as f:
        html = f.read()
    holdings = parse_holdings(html)
    print(f"  Parsed {len(holdings)} positions: "
          + ", ".join(h["symbol"] for h in holdings))

    print("\nFetching live prices from yfinance…")
    usd_to_cad = get_usdcad_rate()
    results, failures = refresh_prices(holdings, usd_to_cad)

    if failures:
        print(f"\n⚠ {len(failures)} fetch warning(s):")
        for sym, err in failures:
            print(f"    {sym}: {err}")
        print("  Existing prices kept for the above — they'll show stale return %.")

    pf_ytd, count = update_portfolio_html(results)
    update_index_html(pf_ytd, count)


if __name__ == "__main__":
    main()
