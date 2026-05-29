#!/usr/bin/env python3
"""
portfolio_update.py
Run from the live_website/ directory:  python3 scripts/portfolio_update.py

Updates:
  my-portfolio.html  — table prices/returns, hero stats, dates, memo return values
  static/js/main.js  — ticker tape day %

After running:
  git add my-portfolio.html static/js/main.js
  git commit -m "Update portfolio prices <date>"
  git push
"""

import subprocess, sys, re
from datetime import date

# ── Auto-install yfinance ─────────────────────────────────────────────────────
try:
    import yfinance as yf
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'yfinance', '-q'])
    import yfinance as yf

# ── Holdings config ───────────────────────────────────────────────────────────
# Update avg_cost if you average down / add to a position.
# CRM is a CI CDR on NEO/CBOE Canada — may not be in yfinance (see fallback below).
H = {
    # sym        yf_ticker    qty       avg_cost    ccy
    'BIP.UN': ('BIP-UN.TO',  2.0499,   50.11,   'CAD'),
    'CMI':    ('CMI',        0.2532,   395.22,  'USD'),
    'CRM':    ('CRM.NE',     21.2027,  12.97,   'CAD'),  # CI CDR (hedged)
    'CSU':    ('CSU.TO',     0.0474,   4232.0,  'CAD'),
    'FDS':    ('FDS',        0.6474,   231.30,  'USD'),
    'HCA':    ('HCA',        0.2850,   527.00,  'USD'),
    'IDCC':   ('IDCC',       0.2268,   353.88,  'USD'),
    'TIH':    ('TIH.TO',     1.0091,   141.29,  'CAD'),
    'TTD':    ('TTD',        5.0000,   20.00,   'USD'),
    'UNH':    ('UNH',        0.3358,   303.21,  'USD'),
}

NAMES = {
    'BIP.UN': 'Brookfield Infrastructure Partners L.P.',
    'CMI':    'Cummins Inc.',
    'CRM':    'Salesforce CDR (CAD Hedged)',
    'CSU':    'Constellation Software Inc.',
    'FDS':    'FactSet Research Systems Inc.',
    'HCA':    'HCA Healthcare Inc.',
    'IDCC':   'InterDigital Inc.',
    'TIH':    'Toromont Industries Ltd.',
    'TTD':    'The Trade Desk Inc.',
    'UNH':    'UnitedHealth Group Inc.',
}

PORTFOLIO = 'my-portfolio.html'
MAINJS    = 'static/js/main.js'
MINUS     = '−'   # Unicode minus for display

# ── Fetch prices ──────────────────────────────────────────────────────────────
print('Fetching prices…')
fx = yf.Ticker('USDCAD=X').fast_info.last_price
print(f'  USD/CAD  {fx:.4f}')

D = {}
for sym, (ytick, qty, cost, ccy) in H.items():
    try:
        fi   = yf.Ticker(ytick).fast_info
        px   = fi.last_price
        prev = fi.previous_close or px
        day  = (px - prev) / prev * 100
        mv   = px * qty
        rd   = mv - cost * qty
        rp   = (px - cost) / cost * 100
        cad  = fx if ccy == 'USD' else 1.0
        D[sym] = dict(qty=qty, cost=cost, ccy=ccy,
                      px=px, day=day, mv=mv, rd=rd, rp=rp,
                      mvcad=mv * cad, bkcad=cost * qty * cad)
        print(f'  {sym:8s}  {px:>10.2f} {ccy}   day {day:+.2f}%   ret {rp:+.1f}%')
    except Exception as e:
        print(f'  {sym:8s}  SKIP — {e}')
        print(f'           (update {sym} manually in the HTML if needed)')

if not D:
    sys.exit('No prices fetched. Check your internet connection.')

# ── Portfolio-level calculations ──────────────────────────────────────────────
tmv = sum(v['mvcad'] for v in D.values())
tbk = sum(v['bkcad'] for v in D.values())
prt = (tmv - tbk) / tbk * 100          # total return since purchase (proxy for display)
for sym, v in D.items():
    v['w'] = v['mvcad'] / tmv * 100

best = max(D, key=lambda s: D[s]['rp'])
lag  = min(D, key=lambda s: D[s]['rp'])
mxr  = max(abs(v['rp']) for v in D.values())
mxw  = max(v['w']       for v in D.values())

d     = date.today()
today = f"{d.strftime('%B')} {d.day}, {d.year}"

print(f'\nPortfolio ret  {prt:+.1f}%')
print(f'Best    {best:8s}  {D[best]["rp"]:+.1f}%')
print(f'Laggard {lag:8s}  {D[lag]["rp"]:+.1f}%')
print(f'Date    {today}')

# ── Formatting helpers ────────────────────────────────────────────────────────
def fp(p):   return f'${p:,.2f}' if p >= 1000 else f'${p:.2f}'
def fr(p):   return f'+{p:.1f}%' if p >= 0 else f'{MINUS}{abs(p):.1f}%'
def fd(v):   return f'+${abs(v):.2f}' if v >= 0 else f'{MINUS}${abs(v):.2f}'
def gc(v):   return 'g' if v >= 0 else 'r'
def bc(v):   return '#4ec97a' if v >= 0 else '#e05252'

# ── Build table row HTML ──────────────────────────────────────────────────────
def build_row(sym):
    v  = D[sym]
    wb = round(v['w']       / mxw * 100)
    rb = round(abs(v['rp']) / mxr * 100)
    return (
        f'        <tr>\n'
        f'          <td><div class="td-sym">{sym}</div><div class="td-name">{NAMES[sym]}</div></td>\n'
        f'          <td>{fp(v["px"])} <span class="ccy">{v["ccy"]}</span></td>\n'
        f'          <td>{v["qty"]}</td>\n'
        f'          <td>{fp(v["mv"])} <span class="ccy">{v["ccy"]}</span></td>\n'
        f'          <td><div class="td-bar-wrap"><div class="td-bar">'
        f'<div class="td-bar-fill" style="width:{wb}%;background:rgba(201,168,76,0.6);"></div>'
        f'</div><span>{v["w"]:.1f}%</span></div></td>\n'
        f'          <td class="{gc(v["rd"])}">{fd(v["rd"])}</td>\n'
        f'          <td><div class="td-bar-wrap"><div class="td-bar">'
        f'<div class="td-bar-fill" style="width:{rb}%;background:{bc(v["rp"])};"></div>'
        f'</div><span class="{gc(v["rp"])}">{fr(v["rp"])}</span></div></td>\n'
        f'        </tr>'
    )

# ── Update my-portfolio.html ──────────────────────────────────────────────────
print(f'\nUpdating {PORTFOLIO}…')
with open(PORTFOLIO, encoding='utf-8') as f:
    html = f.read()

# 1. Table rows
for sym in D:
    pat = re.compile(
        r'        <tr>\s*<td><div class="td-sym">' + re.escape(sym) + r'</div>[\s\S]*?</tr>'
    )
    if pat.search(html):
        html = pat.sub(build_row(sym), html, count=1)
    else:
        print(f'  WARNING: row for {sym} not found')

# 2. Memo return values (in the embedded MEMOS JS object)
ms = html.find('const MEMOS = {')
me = html.find('}; // end MEMOS')
if ms >= 0 and me >= 0:
    memos = html[ms:me]
    for sym, v in D.items():
        rs = f"+{v['rp']:.1f}%" if v['rp'] >= 0 else f"-{abs(v['rp']):.1f}%"
        rd = 'g' if v['rp'] >= 0 else 'r'
        sp = memos.find(f"'{sym}':")
        if sp < 0:
            continue
        seg = memos[sp: sp + 500]
        seg = re.sub(r"(ret: ')[^']*(')",    rf'\g<1>{rs}\g<2>', seg, count=1)
        seg = re.sub(r"(retDir: ')[^']*(')", rf'\g<1>{rd}\g<2>', seg, count=1)
        memos = memos[:sp] + seg + memos[sp + 500:]
    html = html[:ms] + memos + html[me:]
else:
    print('  WARNING: MEMOS block not found — memo returns not updated')

# 3. Date tags
html = re.sub(r'As of [A-Z][a-z]+ \d+, \d{4}',           f'As of {today}',           html)
html = re.sub(r'10 positions · [A-Z][a-z]+ \d+, \d{4}',   f'10 positions · {today}',  html)
html = re.sub(r'Data as of [A-Z][a-z]+ \d+, \d{4}',       f'Data as of {today}',      html)

# 4. Hero stat values
ytd_str  = f'+{abs(prt):.1f}%'
best_str = f'+{D[best]["rp"]:.0f}%'
lag_str  = f'{MINUS}{abs(D[lag]["rp"]):.0f}%'
bg_num   = f'{abs(prt):.1f}'

html = re.sub(
    r'(<div class="pf-hero-stat-val g">)\+[\d\.]+%(<\/div>\s*<div class="pf-hero-stat-label">YTD)',
    lambda m: m.group(1) + ytd_str + m.group(2), html)
html = re.sub(
    r'(<div class="pf-hero-stat-val g">)\+[\d]+%(<\/div>\s*<div class="pf-hero-stat-label">Best)',
    lambda m: m.group(1) + best_str + m.group(2), html)
html = re.sub(
    r'(<div class="pf-hero-stat-val r">)[^<]*?(<\/div>\s*<div class="pf-hero-stat-label">Laggard)',
    lambda m: m.group(1) + lag_str + m.group(2), html)
html = re.sub(
    r'(<div class="pf-hero-bg-num">)[\d\.]+(<\/div>)',
    lambda m: m.group(1) + bg_num + m.group(2), html)
# Best/Laggard labels (e.g. "Best · CMI")
html = re.sub(r'(Best · )[A-Z\.]+', rf'\g<1>{best}', html)
html = re.sub(r'(Laggard · )[A-Z\.]+', rf'\g<1>{lag}', html)
# YTD in disclaimer
html = re.sub(r'YTD return \(\+[\d\.]+%\)', f'YTD return ({ytd_str})', html)
html = re.sub(r'\+[\d\.]+% YTD return',     f'{ytd_str} YTD return', html)

with open(PORTFOLIO, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'  Done.')

# ── Update static/js/main.js ticker tape ──────────────────────────────────────
print(f'Updating {MAINJS}…')
with open(MAINJS, encoding='utf-8') as f:
    js = f.read()

for sym, v in D.items():
    js = re.sub(
        r"(\{ sym: '" + re.escape(sym) + r"',\s*day: )[-\d.]+(\s*\})",
        lambda m, d=v['day']: m.group(1) + f'{d:.2f}' + m.group(2),
        js
    )

with open(MAINJS, 'w', encoding='utf-8') as f:
    f.write(js)
print(f'  Done.')

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"""
All done. To deploy:
  git add my-portfolio.html static/js/main.js
  git commit -m "Update portfolio prices — {today}"
  git push
""")
