#!/usr/bin/env python3
"""
yield_curve_updater.py

Refreshes the Yield Curve Dashboard for the website.

Pipeline:
  1. Download max-available daily US Treasury constant-maturity yields from FRED
     (DGS1MO … DGS30) via the keyless fredgraph.csv endpoint.
  2. Download daily Canadian T-bill + benchmark bond yields from the Bank of
     Canada Valet API (groups `tbill_all` and `bond_yields_benchmark`).
  3. Forward-fill across short gaps, downsample to weekly Fridays for the 3D
     surface, and keep the latest daily curve separately.
  4. Render the Jinja2 template with all data baked in (static, no backend),
     producing a single self-contained HTML file.
  5. Write the result to ../yield-curve.html at the repo root.

Runs in two contexts:
  - GitHub Actions (.github/workflows/yield-curve.yml) — weekly, automatic.
  - Manual:  cd live_website && python3 scripts/yield_curve_updater.py

Paths are resolved relative to this file. Uses only stdlib + jinja2 — no
yfinance, no pandas, no API keys.
"""

import csv
import io
import json
import os
import sys
import time
from datetime import date, datetime
from urllib.request import Request, urlopen

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── PATHS (repo-relative; works under GitHub Actions and locally) ───────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
TEMPLATE    = "yield_curve_template.html"
OUTPUT_HTML = os.path.join(REPO_ROOT, "yield-curve.html")

# ── TENORS ──────────────────────────────────────────────────────────────────
TENOR_YEARS = {
    "1M":  1 / 12,
    "3M":  0.25,
    "6M":  0.5,
    "1Y":  1.0,
    "2Y":  2.0,
    "3Y":  3.0,
    "5Y":  5.0,
    "7Y":  7.0,
    "10Y": 10.0,
    "20Y": 20.0,
    "30Y": 30.0,
}
TENOR_ORDER = list(TENOR_YEARS.keys())

US_SERIES = {
    "1M":  "DGS1MO",
    "3M":  "DGS3MO",
    "6M":  "DGS6MO",
    "1Y":  "DGS1",
    "2Y":  "DGS2",
    "3Y":  "DGS3",
    "5Y":  "DGS5",
    "7Y":  "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

FRED_URL  = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
VALET_URL = "https://www.bankofcanada.ca/valet/observations/group/{group}/json?recent=20000"
CA_GROUPS = ["tbill_all", "bond_yields_benchmark"]


# ── HTTP ────────────────────────────────────────────────────────────────────
def _http_get(url, timeout=30):
    req = Request(url, headers={"User-Agent": "yield-curve-dashboard/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ── US (FRED) ───────────────────────────────────────────────────────────────
def fetch_fred_series(series_id):
    text = _http_get(FRED_URL.format(series=series_id))
    out = {}
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return out
    for row in reader:
        if len(row) < 2:
            continue
        d, v = row[0].strip(), row[1].strip()
        if not d or v in ("", "."):
            continue
        try:
            out[d] = float(v)
        except ValueError:
            continue
    return out


def fetch_us():
    print("Fetching US (FRED)...")
    per_tenor = {}
    all_dates = set()
    for tenor, series in US_SERIES.items():
        try:
            obs = fetch_fred_series(series)
            print(f"  {tenor:>4} {series:<8} {len(obs):>6} obs")
            per_tenor[tenor] = obs
            all_dates.update(obs.keys())
        except Exception as e:
            print(f"  WARNING: {series} failed: {e}")
            per_tenor[tenor] = {}
        time.sleep(0.2)
    return sorted(all_dates), per_tenor


# ── Canada (Bank of Canada Valet) ───────────────────────────────────────────
def _ca_tenor_from_label(label):
    s = label.lower()
    if "treasury bill" in s or "t-bill" in s or "tbill" in s:
        if "1-month" in s or "1 month" in s or "30 day" in s: return "1M"
        if "3-month" in s or "3 month" in s or "90 day" in s: return "3M"
        if "6-month" in s or "6 month" in s or "180 day" in s: return "6M"
        if "1-year"  in s or "1 year"  in s or "12 month" in s: return "1Y"
    if "benchmark bond" in s or "benchmark" in s or "marketable bond" in s:
        if "2-year"  in s or "2 year"  in s: return "2Y"
        if "3-year"  in s or "3 year"  in s: return "3Y"
        if "5-year"  in s or "5 year"  in s: return "5Y"
        if "7-year"  in s or "7 year"  in s: return "7Y"
        if "10-year" in s or "10 year" in s: return "10Y"
        if "long"    in s: return "30Y"
    return None


def fetch_ca():
    print("Fetching Canada (Bank of Canada Valet)...")
    per_tenor = {t: {} for t in TENOR_ORDER}
    all_dates = set()

    for group in CA_GROUPS:
        try:
            payload = json.loads(_http_get(VALET_URL.format(group=group)))
        except Exception as e:
            print(f"  WARNING: group {group} failed: {e}")
            continue

        details = payload.get("seriesDetail", {})
        series_to_tenor = {}
        for sid, meta in details.items():
            label = (meta.get("label") or "") + " " + (meta.get("description") or "")
            tenor = _ca_tenor_from_label(label)
            if tenor:
                series_to_tenor[sid] = tenor
        print(f"  group {group}: matched {len(series_to_tenor)} series → "
              f"{sorted(set(series_to_tenor.values()))}")

        for obs in payload.get("observations", []):
            d = obs.get("d")
            if not d:
                continue
            for sid, tenor in series_to_tenor.items():
                cell = obs.get(sid)
                if not cell: continue
                v = cell.get("v")
                if v in (None, "", "NA"): continue
                try:
                    per_tenor[tenor][d] = float(v)
                    all_dates.add(d)
                except (TypeError, ValueError):
                    continue
        time.sleep(0.2)
    return sorted(all_dates), per_tenor


# ── Resampling ──────────────────────────────────────────────────────────────
def to_weekly_fridays(dates_sorted, per_tenor):
    full = sorted(dates_sorted)
    if not full:
        return [], []

    # Forward-fill each tenor across the full date axis.
    filled = {}
    for tenor in TENOR_ORDER:
        series = per_tenor.get(tenor, {})
        last = None
        ff = {}
        for d in full:
            v = series.get(d)
            if v is not None:
                last = v
            ff[d] = last
        filled[tenor] = ff

    weekly_dates, matrix = [], []
    for d in full:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dt.weekday() != 4:  # Friday
            continue
        row, ok = [], False
        for tenor in TENOR_ORDER:
            v = filled[tenor].get(d)
            row.append(round(v, 3) if v is not None else None)
            if v is not None: ok = True
        if ok:
            weekly_dates.append(d)
            matrix.append(row)
    return weekly_dates, matrix


def build_country_payload(dates_sorted, per_tenor):
    weekly_dates, matrix = to_weekly_fridays(dates_sorted, per_tenor)
    latest = None
    if dates_sorted:
        for d in reversed(dates_sorted):
            row = {t: per_tenor.get(t, {}).get(d) for t in TENOR_ORDER}
            if any(v is not None for v in row.values()):
                latest = {
                    "date": d,
                    "yields": {t: round(v, 3) if v is not None else None
                               for t, v in row.items()},
                }
                break
    return {
        "tenor_order": TENOR_ORDER,
        "tenor_years": {t: round(TENOR_YEARS[t], 4) for t in TENOR_ORDER},
        "dates": weekly_dates,
        "matrix": matrix,
        "latest": latest,
        "n_dates": len(weekly_dates),
        "first_date": weekly_dates[0]  if weekly_dates else None,
        "last_date":  weekly_dates[-1] if weekly_dates else None,
    }


# ── Render ──────────────────────────────────────────────────────────────────
def render(data):
    env = Environment(
        loader=FileSystemLoader(SCRIPT_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template(TEMPLATE)
    return template.render(
        error=None,
        data=data,
        data_json=json.dumps(data, separators=(",", ":")),
        static_mode=True,
    )


# ── Main ────────────────────────────────────────────────────────────────────
def _load_existing_payload(country):
    """Pull a previously-saved country payload back out of yield-curve.html.
    Used as a fallback when today's upstream fetch returns nothing — so an
    API outage (e.g. FRED 504) can never wipe a working country off the page."""
    if not os.path.exists(OUTPUT_HTML):
        return None
    try:
        import re as _re
        with open(OUTPUT_HTML, encoding="utf-8") as f:
            html = f.read()
        m = _re.search(r'<script id="yc-data" type="application/json">(.*?)</script>',
                       html, _re.DOTALL)
        if not m:
            return None
        d = json.loads(m.group(1))
        p = d.get("countries", {}).get(country)
        if p and p.get("n_dates", 0) > 0:
            return p
    except Exception as e:
        print(f"  (could not read existing payload for {country}: {e})")
    return None


def main():
    us_dates, us_per_tenor = fetch_us()
    ca_dates, ca_per_tenor = fetch_ca()

    # Build fresh payloads, then fall back to last-known-good for any country
    # whose upstream fetch came back empty (FRED 504, BoC outage, etc).
    us_payload = build_country_payload(us_dates, us_per_tenor)
    ca_payload = build_country_payload(ca_dates, ca_per_tenor)

    if us_payload["n_dates"] == 0:
        prev = _load_existing_payload("US")
        if prev:
            print("⚠ US fetch returned no data — keeping previously deployed payload "
                  f"({prev.get('n_dates')} rows, last={prev.get('last_date')}).")
            us_payload = prev
        else:
            print("⚠ US fetch returned no data and no prior payload available.")
    if ca_payload["n_dates"] == 0:
        prev = _load_existing_payload("CA")
        if prev:
            print("⚠ Canada fetch returned no data — keeping previously deployed payload "
                  f"({prev.get('n_dates')} rows, last={prev.get('last_date')}).")
            ca_payload = prev
        else:
            print("⚠ Canada fetch returned no data and no prior payload available.")

    if us_payload["n_dates"] == 0 and ca_payload["n_dates"] == 0:
        print("ERROR: both US and Canada have no data (live + cached) — "
              "refusing to overwrite yield-curve.html with an empty page.")
        sys.exit(1)

    data = {
        "last_updated": date.today().isoformat(),
        "tenor_order": TENOR_ORDER,
        "tenor_years": {t: round(TENOR_YEARS[t], 4) for t in TENOR_ORDER},
        "countries": {"US": us_payload, "CA": ca_payload},
    }

    html = render(data)
    with open(OUTPUT_HTML, "w") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT_HTML) / 1024
    print(f"\nWrote {OUTPUT_HTML} ({size_kb:.1f} KB)")
    for c, p in data["countries"].items():
        print(f"  {c}: {p['n_dates']:>5} weekly rows "
              f"({p['first_date']} → {p['last_date']})")

    print("\n" + "=" * 72)
    print(f"  Yield Curve Snapshot — {data['last_updated']}")
    print("=" * 72)
    def cell(v):
        return f"{v:>5.2f}" if isinstance(v, (int, float)) else "  n/a"
    for c in ("US", "CA"):
        latest = data["countries"][c]["latest"]
        if not latest:
            continue
        ys = latest["yields"]
        print(f"  {c}  {latest['date']}  "
              f"3M {cell(ys.get('3M'))}%  "
              f"2Y {cell(ys.get('2Y'))}%  "
              f"10Y {cell(ys.get('10Y'))}%  "
              f"30Y {cell(ys.get('30Y'))}%")
    print("=" * 72)


if __name__ == "__main__":
    main()
