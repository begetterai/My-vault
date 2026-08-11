#!/usr/bin/env python3
"""Генератор презентации для совета директоров — группа Ромашка/ЗБ/ОВИР.
Все координаты графиков считаются, а не подбираются."""
import io, math, re

OUT = "/tmp/claude-0/-home-user-My-vault/606dd1b1-a624-5ef2-a06e-c6a894e680ba/scratchpad/sovet-direktorov.html"

def fmt(n, dec=0):
    s = f"{abs(n):,.{dec}f}".replace(",", " ")
    return ("−" if n < 0 else "") + s

# ─────────────────────── ДАННЫЕ ───────────────────────
YEARS = [2023, 2024, 2025, 2026]
REV   = {2023:1384114, 2024:4070835, 2025:4139758, 2026:3129420}   # 2026 = 6 мес
EBIT  = {2023:389085,  2024:1049812, 2025:717498,  2026:537853}
COGS  = {2023:672953,  2024:1949275, 2025:1747763, 2026:1303878}
OPEX  = {2023:322077,  2024:1071748, 2025:1674498, 2026:1287688}
RENT  = {2023:39500,   2024:93100,   2025:246093,  2026:269756}
FOT   = {2023:168060,  2024:541321,  2025:574232,  2026:543827}

MARGIN = {y: EBIT[y]/REV[y]*100 for y in YEARS}
GMPCT  = {y: (1-COGS[y]/REV[y])*100 for y in YEARS}
OPCT   = {y: OPEX[y]/REV[y]*100 for y in YEARS}
RPCT   = {y: RENT[y]/REV[y]*100 for y in YEARS}
FPCT   = {y: FOT[y]/REV[y]*100 for y in YEARS}

A_REV = REV[2026]*2; A_EBIT = EBIT[2026]*2; A_OPEX = OPEX[2026]*2
A_RENT = RENT[2026]*2; A_FOT = FOT[2026]*2
A_OTHER = A_OPEX - A_RENT - A_FOT
GM26 = GMPCT[2026]/100

CASH_POINTS = [("ОВИР", 272915), ("Зелёный базар", -127567), ("Ромашка", -42175),
               ("Сиёма", -14235), ("Касса (наличные)", 111762)]
CASH_TOTAL = sum(v for _, v in CASH_POINTS)
LOAN_AP = 450000; OTHER_LIAB = 468468; DEBT_TOTAL = LOAN_AP + OTHER_LIAB

POINTS = [
    ("Ромашка",       6471657, 1686060, 362166,  30, "закрыта",  "июль 2023 – 2025"),
    ("ОВИР",          1298181, 309270,  1114411, 6,  "работает", "с янв 2026"),
    ("Зелёный базар", 4696570, 713153,  991508,  14, "работает", "с мая 2025"),
    ("Сиёма",         257719,  -14235,  474964,  12, "закрыта",  "2024"),
]

DIV = [("Мага", 198630, 61, 53270), ("Устин", 145949, 30, 145710), ("Шоира", 120060, 5, 13400)]
DIV_TOTAL = sum(d[1] for d in DIV)
INV_PEOPLE = sum(d[3] for d in DIV)

SCEN = [("A", "Осторожный", 0.38), ("B", "Целевой", 0.35), ("C", "Амбициозный", 0.32)]

LEVERS = [
    ("Аренда", "8,6% → 6,0% от выручки", A_RENT, 0.060*A_REV),
    ("ФОТ", "17,4% → 15,0% от выручки", A_FOT, 0.150*A_REV),
    ("Прочий OPEX", "сокращение на 10%", A_OTHER, A_OTHER*0.9),
]
LEVER_TOTAL = sum(now-t for _, _, now, t in LEVERS)

# ─────────────────────── ГРАФИКИ (SVG) ───────────────────────
def svg_open(w, h, cls=""):
    return (f'<svg class="chart {cls}" viewBox="0 0 {w} {h}" role="img" '
            f'preserveAspectRatio="xMidYMid meet">')

def chart_revenue_margin():
    W, H = 760, 330
    L, R, T, B = 62, 58, 26, 54
    pw, ph = W-L-R, H-T-B
    vals = [REV[y] for y in YEARS[:3]] + [A_REV]
    labels = ["2023", "2024", "2025", "2026\nпрогноз"]
    maxv = 7_000_000
    n = len(vals); slot = pw/n; bw = slot*0.44
    s = [svg_open(W, H, "chart-combo")]
    # сетка + ось выручки
    for i in range(5):
        v = maxv*i/4; y = T+ph-ph*(v/maxv)
        s.append(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}"/>')
        s.append(f'<text class="ax" x="{L-10}" y="{y+4:.1f}" text-anchor="end">{v/1_000_000:.1f}М</text>')
    # столбцы выручки
    for i, (v, lb) in enumerate(zip(vals, labels)):
        x = L+slot*i+(slot-bw)/2; bh = ph*(v/maxv); y = T+ph-bh
        proj = " proj" if i == 3 else ""
        s.append(f'<rect class="bar{proj}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2"/>')
        s.append(f'<text class="barval" x="{x+bw/2:.1f}" y="{y-8:.1f}" text-anchor="middle">{fmt(v/1000)}k</text>')
        for j, part in enumerate(lb.split("\n")):
            s.append(f'<text class="ax" x="{x+bw/2:.1f}" y="{T+ph+20+j*13}" text-anchor="middle">{part}</text>')
    # линия маржи (правая ось 0–30%)
    mmax = 30
    pts = []
    for i, y_ in enumerate(YEARS):
        m = MARGIN[y_]; cx = L+slot*i+slot/2; cy = T+ph-ph*(m/mmax)
        pts.append((cx, cy, m))
    s.append('<polyline class="line" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts) + '"/>')
    for i, (x, y, m) in enumerate(pts):
        s.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
        dy = -14 if i < 2 else 22
        s.append(f'<text class="lineval" x="{x:.1f}" y="{y+dy:.1f}" text-anchor="middle">{m:.1f}%</text>')
    for i in range(4):
        v = mmax*i/3; y = T+ph-ph*(v/mmax)
        s.append(f'<text class="ax accent-ax" x="{L+pw+10}" y="{y+4:.1f}">{v:.0f}%</text>')
    s.append('</svg>')
    return "".join(s)

def chart_bridge():
    W, H = 760, 320
    L, R, T, B = 54, 20, 34, 62
    pw, ph = W-L-R, H-T-B
    start, end = MARGIN[2023], MARGIN[2026]
    dgm = GMPCT[2026]-GMPCT[2023]
    drent = -(RPCT[2026]-RPCT[2023]); dfot = -(FPCT[2026]-FPCT[2023])
    oth23 = OPCT[2023]-RPCT[2023]-FPCT[2023]; oth26 = OPCT[2026]-RPCT[2026]-FPCT[2026]
    doth = -(oth26-oth23)
    steps = [("2023", start, "total"), ("Валовая\nмаржа", dgm, "up"),
             ("Аренда", drent, "down"), ("ФОТ", dfot, "down"),
             ("Прочий\nOPEX", doth, "down"), ("2026", end, "total")]
    maxv = 40.0
    n = len(steps); slot = pw/n; bw = slot*0.52
    s = [svg_open(W, H, "chart-bridge")]
    y0 = T+ph
    for i in range(5):
        v = maxv*i/4; y = y0-ph*(v/maxv)
        s.append(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}"/>')
        s.append(f'<text class="ax" x="{L-9}" y="{y+4:.1f}" text-anchor="end">{v:.0f}%</text>')
    run = 0.0
    for i, (lab, val, kind) in enumerate(steps):
        x = L+slot*i+(slot-bw)/2
        if kind == "total":
            h = ph*(val/maxv); y = y0-h; run = val
            cls = "wf-total"
            txt = f"{val:.1f}%"
        else:
            top = run+val if val > 0 else run
            h = ph*(abs(val)/maxv); y = y0-ph*(top/maxv)
            cls = "wf-up" if val > 0 else "wf-down"
            txt = f"{val:+.1f}"
            run += val
        s.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h,2):.1f}" rx="2"/>')
        s.append(f'<text class="wfval {cls}-t" x="{x+bw/2:.1f}" y="{y-8:.1f}" text-anchor="middle">{txt}</text>')
        if i < n-1:
            yc = y if val > 0 or kind == "total" else y+h
            s.append(f'<line class="conn" x1="{x+bw:.1f}" y1="{yc:.1f}" x2="{L+slot*(i+1)+(slot-bw)/2:.1f}" y2="{yc:.1f}"/>')
        for j, part in enumerate(lab.split("\n")):
            s.append(f'<text class="ax" x="{x+bw/2:.1f}" y="{y0+20+j*13}" text-anchor="middle">{part}</text>')
    s.append('</svg>')
    return "".join(s)

def chart_opex_split():
    W, H = 760, 260
    L, R, T, B = 130, 90, 34, 34
    pw, ph = W-L-R, H-T-B
    rows = [("Аренда", RPCT[2023], RPCT[2026]), ("ФОТ", FPCT[2023], FPCT[2026]),
            ("Прочий OPEX", OPCT[2023]-RPCT[2023]-FPCT[2023], OPCT[2026]-RPCT[2026]-FPCT[2026]),
            ("OPEX всего", OPCT[2023], OPCT[2026])]
    maxv = 45.0
    rh = ph/len(rows)
    s = [svg_open(W, H, "chart-split")]
    for i, (lab, a, b) in enumerate(rows):
        yc = T+rh*i+rh/2
        bh = rh*0.30
        s.append(f'<text class="rowlab" x="{L-14}" y="{yc+4:.1f}" text-anchor="end">{lab}</text>')
        wa = pw*(a/maxv); wb = pw*(b/maxv)
        s.append(f'<rect class="bar-old" x="{L}" y="{yc-bh-2:.1f}" width="{wa:.1f}" height="{bh:.1f}" rx="2"/>')
        s.append(f'<rect class="bar-new" x="{L}" y="{yc+2:.1f}" width="{wb:.1f}" height="{bh:.1f}" rx="2"/>')
        s.append(f'<text class="sm" x="{L+wa+8:.1f}" y="{yc-bh+9:.1f}">{a:.1f}%</text>')
        s.append(f'<text class="sm strong" x="{L+wb+8:.1f}" y="{yc+bh:.1f}">{b:.1f}%</text>')
    s.append(f'<text class="legend" x="{L}" y="{H-8}">▬ 2023 &#160;&#160; ▬ 2026 (доля от выручки)</text>')
    s.append('</svg>')
    return "".join(s)

def chart_scenarios():
    W, H = 760, 300
    L, R, T, B = 62, 30, 34, 66
    pw, ph = W-L-R, H-T-B
    base = A_EBIT
    bars = [("Сейчас", OPCT[2026]/100, base, "now")]
    for code, name, op in SCEN:
        eb = A_REV*(GM26-op)
        bars.append((f"{code}. {name}", op, eb, "scen"))
    maxv = 1_800_000
    n = len(bars); slot = pw/n; bw = slot*0.46
    s = [svg_open(W, H, "chart-scen")]
    for i in range(5):
        v = maxv*i/4; y = T+ph-ph*(v/maxv)
        s.append(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}"/>')
        s.append(f'<text class="ax" x="{L-9}" y="{y+4:.1f}" text-anchor="end">{v/1_000_000:.1f}М</text>')
    for i, (lab, op, eb, kind) in enumerate(bars):
        x = L+slot*i+(slot-bw)/2; bh = ph*(eb/maxv); y = T+ph-bh
        s.append(f'<rect class="bar-{kind}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2"/>')
        s.append(f'<text class="barval" x="{x+bw/2:.1f}" y="{y-22:.1f}" text-anchor="middle">{fmt(eb)}</text>')
        s.append(f'<text class="barpct" x="{x+bw/2:.1f}" y="{y-7:.1f}" text-anchor="middle">{(eb/A_REV*100):.1f}% маржа</text>')
        if kind == "scen":
            d = eb-base
            s.append(f'<text class="delta" x="{x+bw/2:.1f}" y="{T+ph+38:.1f}" text-anchor="middle">+{fmt(d)}</text>')
        s.append(f'<text class="ax" x="{x+bw/2:.1f}" y="{T+ph+20:.1f}" text-anchor="middle">{lab}</text>')
        s.append(f'<text class="ax dim" x="{x+bw/2:.1f}" y="{T+ph+55:.1f}" text-anchor="middle">OPEX {op*100:.1f}%</text>')
    s.append('</svg>')
    return "".join(s)

def chart_cash():
    W, H = 760, 230
    L, R, T, B = 252, 96, 28, 30
    pw, ph = W-L-R, H-T-B
    rows = [("Свободные деньги", CASH_TOTAL, "pos"),
            ("Заём Accelerate Prosperity", -LOAN_AP, "neg"),
            ("Прочие обязательства", -OTHER_LIAB, "neg")]
    maxv = 1_000_000
    rh = ph/len(rows)
    s = [svg_open(W, H, "chart-cash")]
    for i, (lab, v, kind) in enumerate(rows):
        yc = T+rh*i+rh/2; bh = rh*0.44
        w = pw*(abs(v)/maxv)
        s.append(f'<text class="rowlab" x="{L-14}" y="{yc+4:.1f}" text-anchor="end">{lab}</text>')
        s.append(f'<rect class="bar-{kind}" x="{L}" y="{yc-bh/2:.1f}" width="{w:.1f}" height="{bh:.1f}" rx="2"/>')
        s.append(f'<text class="sm strong" x="{L+w+9:.1f}" y="{yc+4:.1f}">{fmt(v)}</text>')
    s.append('</svg>')
    return "".join(s)

def chart_points():
    W, H = 760, 260
    L, R, T, B = 132, 128, 30, 26          # L — правый край подписей
    Z = L + 92                              # нулевая линия (слева от неё — отрицательные)
    pwp, ph = W-Z-R, H-T-B                  # ширина положительной зоны
    maxv = 30.0
    rh = ph/len(POINTS)
    s = [svg_open(W, H, "chart-points")]
    for i, (name, rev, eb, inv, mo, status, period) in enumerate(POINTS):
        m = eb/rev*100
        yc = T+rh*i+rh/2; bh = rh*0.44
        cls = "closed" if status == "закрыта" else ("best" if m >= 23 else "weak")
        s.append(f'<text class="rowlab" x="{L-14}" y="{yc:.1f}" text-anchor="end">{name}</text>')
        s.append(f'<text class="rowsub" x="{L-14}" y="{yc+14:.1f}" text-anchor="end">{period}</text>')
        if m < 0:
            w_ = pwp*(abs(m)/maxv)
            s.append(f'<rect class="bar-neg" x="{Z-w_:.1f}" y="{yc-bh/2:.1f}" width="{w_:.1f}" height="{bh:.1f}" rx="2"/>')
            tx, anchor = Z+9, "start"     # значение справа от нуля — там пусто, нет наложения
        else:
            w_ = pwp*(m/maxv)
            s.append(f'<rect class="bar-{cls}" x="{Z}" y="{yc-bh/2:.1f}" width="{w_:.1f}" height="{bh:.1f}" rx="2"/>')
            tx, anchor = Z+w_+9, "start"
        s.append(f'<text class="sm strong" x="{tx:.1f}" y="{yc+1:.1f}" text-anchor="{anchor}">{m:.1f}%</text>')
        pay = f"окуп. {inv/(eb/mo):.0f} мес" if eb > 0 else "не окупилась"
        s.append(f'<text class="sm dim" x="{tx:.1f}" y="{yc+15:.1f}" text-anchor="{anchor}">{pay}</text>')
    # нулевая линия и планка ОВИР
    s.append(f'<line class="zero" x1="{Z}" y1="{T-4}" x2="{Z}" y2="{T+ph+2}"/>')
    tgt = Z+pwp*(23.8/maxv)
    s.append(f'<line class="target" x1="{tgt:.1f}" y1="{T-4}" x2="{tgt:.1f}" y2="{T+ph+2}"/>')
    s.append('</svg>')
    return "".join(s)

# ─────────────────────── HTML ───────────────────────
def kpi(label, value, sub, tone=""):
    return f'''<div class="kpi {tone}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>'''

def prob(num, title, sev, sev_label, body, metrics):
    mrows = "".join(
        f'<div class="mrow"><span class="mlab">{a}</span><span class="mval">{b}</span></div>'
        for a, b in metrics)
    return f'''<article class="problem">
      <header class="problem-head">
        <span class="pnum">{num}</span>
        <h3>{title}</h3>
        <span class="sev sev-{sev}">{sev_label}</span>
      </header>
      <div class="problem-body">
        <div class="problem-text">{body}</div>
        <div class="metrics">{mrows}</div>
      </div>
    </article>'''

def ru_decimals(doc):
    """Десятичная точка → запятая ТОЛЬКО в видимом тексте (между > и <).
    Атрибуты, CSS и JS не трогаем — там точка синтаксически значима."""
    parts = re.split(r'(<style>.*?</style>|<script>.*?</script>)', doc, flags=re.S)
    out = []
    for i, part in enumerate(parts):
        if part.startswith('<style>') or part.startswith('<script>'):
            out.append(part); continue
        out.append(re.sub(r'>([^<]*)<',
            lambda m: '>' + re.sub(r'(\d)\.(\d)', r'\1,\2', m.group(1)) + '<', part))
    return "".join(out)

def build():
    d_gm = GMPCT[2026]-GMPCT[2023]
    d_margin = MARGIN[2026]-MARGIN[2023]
    cov = CASH_TOTAL/DEBT_TOTAL*100
    zb_rev_y = 4696570/14*12
    zb_gain = zb_rev_y*(0.238-0.152)
    scen_b = A_REV*(GM26-0.35)

    # доли вложений vs дивидендов (только люди)
    div_rows = []
    for name, amt, cnt, inv in DIV:
        share_d = amt/DIV_TOTAL*100
        share_i = inv/INV_PEOPLE*100
        gap = share_d-share_i
        div_rows.append((name, amt, cnt, inv, share_d, share_i, gap))

    html = io.StringIO()
    w = html.write

    w('''<title>Совет директоров — Ромашка Групп · Финансовый разбор</title>
<style>
:root{
  --ground:#FAF7F1; --surface:#FFFFFF; --surface-2:#F4EFE5;
  --ink:#1F2A37; --body:#3D444E; --muted:#7A736A; --hair:#DED6C7;
  --accent:#B08D3E; --accent-deep:#8C6D28; --accent-soft:#EFE3C7;
  --crit:#A33B2C; --crit-soft:#F3DCD7;
  --pos:#3D6B50; --pos-soft:#DCE9E0;
  --navy:#1F2A37; --navy-2:#2A3746;
  --on-navy:#F3EEE0; --on-navy-dim:#A9B0BA;
  --shadow:0 1px 2px rgba(31,42,55,.05),0 8px 24px -12px rgba(31,42,55,.14);
  --on-navy-crit:#E8917E; --on-navy-pos:#8FCBA5;
  --font-display:"Times New Roman",Times,serif;
  --font-body:"Times New Roman",Times,serif;
  --font-mono:"Times New Roman",Times,serif;
  --maxw:1080px;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#12161C; --surface:#191F27; --surface-2:#222932;
    --ink:#F1ECE1; --body:#C7C2B8; --muted:#8D877D; --hair:#2E3742;
    --accent:#D0A94F; --accent-deep:#E0BC6A; --accent-soft:#3A3222;
    --crit:#D4705E; --crit-soft:#3A2420;
    --pos:#79AE8D; --pos-soft:#1E2E25;
    --navy:#0D1117; --navy-2:#161C24;
    --on-navy:#F1ECE1; --on-navy-dim:#8D949E;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.6);
    --on-navy-crit:#E8917E; --on-navy-pos:#8FCBA5;
  }
}
:root[data-theme="dark"]{
  --ground:#12161C; --surface:#191F27; --surface-2:#222932;
  --ink:#F1ECE1; --body:#C7C2B8; --muted:#8D877D; --hair:#2E3742;
  --accent:#D0A94F; --accent-deep:#E0BC6A; --accent-soft:#3A3222;
  --crit:#D4705E; --crit-soft:#3A2420;
  --pos:#79AE8D; --pos-soft:#1E2E25;
  --navy:#0D1117; --navy-2:#161C24;
  --on-navy:#F1ECE1; --on-navy-dim:#8D949E;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.6);
  --on-navy-crit:#E8917E; --on-navy-pos:#8FCBA5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--body);
  font-family:var(--font-body);font-size:17.5px;line-height:1.62;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 28px}
h1,h2,h3,h4{font-family:var(--font-display);color:var(--ink);
  text-wrap:balance;margin:0;font-weight:600;letter-spacing:-.01em}
p{margin:0}
.num{font-variant-numeric:tabular-nums}

/* ── Прогресс-полоса ── */
.progress{position:fixed;top:0;left:0;height:3px;background:var(--accent);
  width:0;z-index:99;transition:width .1s linear}

/* ── Обложка ── */
.cover{background:var(--navy);color:var(--on-navy);padding:76px 0 56px;
  border-bottom:3px solid var(--accent)}
.cover .eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent);font-weight:600;margin-bottom:20px}
.cover h1{color:var(--on-navy);font-size:clamp(34px,5.2vw,54px);line-height:1.08;
  max-width:20ch;margin-bottom:18px}
.cover .lead{color:var(--on-navy-dim);font-size:17px;max-width:60ch;line-height:1.65}
.cover-meta{display:flex;flex-wrap:wrap;gap:26px;margin-top:30px;
  padding-top:22px;border-top:1px solid rgba(255,255,255,.14);
  font-size:14px;color:var(--on-navy-dim)}
.cover-meta b{color:var(--on-navy);font-weight:600}

/* ── KPI ── */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:1px;background:rgba(255,255,255,.12);margin-top:40px;
  border:1px solid rgba(255,255,255,.12)}
.kpi{background:var(--navy);padding:20px 18px}
.kpi-label{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--on-navy-dim);margin-bottom:10px;font-weight:600}
.kpi-value{font-family:var(--font-display);font-size:29px;color:var(--on-navy);
  line-height:1.05;font-variant-numeric:tabular-nums}
.kpi-sub{font-size:13.5px;color:var(--on-navy-dim);margin-top:7px;line-height:1.45}
.kpi.crit .kpi-value{color:var(--on-navy-crit)}
.kpi.pos .kpi-value{color:var(--on-navy-pos)}
.kpi.gold .kpi-value{color:var(--accent)}

/* ── Секции ── */
section{padding:64px 0;border-bottom:1px solid var(--hair)}
section:last-of-type{border-bottom:none}
.sec-head{display:flex;align-items:baseline;gap:16px;margin-bottom:14px}
.sec-num{font-family:var(--font-mono);font-size:12px;color:var(--accent);
  font-weight:700;letter-spacing:.06em;padding-top:6px}
.sec-head h2{font-size:clamp(24px,3.2vw,33px);line-height:1.15}
.sec-lead{max-width:68ch;font-size:16.5px;margin-bottom:34px;color:var(--body)}
.sec-lead strong{color:var(--ink);font-weight:600}

/* ── Карточка графика ── */
.card{background:var(--surface);border:1px solid var(--hair);border-radius:3px;
  padding:26px 24px 20px;box-shadow:var(--shadow);margin-bottom:26px}
.card-title{font-family:var(--font-display);font-size:17px;color:var(--ink);
  margin-bottom:4px;font-weight:600}
.card-sub{font-size:14px;color:var(--muted);margin-bottom:20px}
.chart-scroll{overflow-x:auto}
.chart{width:100%;height:auto;min-width:520px;display:block}

/* ── SVG стили ── */
.grid{stroke:var(--hair);stroke-width:1}
.ax{font-family:var(--font-body);font-size:13px;fill:var(--muted)}
.ax.dim{font-size:12px;opacity:.85}
.accent-ax{fill:var(--accent)}
.bar{fill:var(--navy-2);opacity:.88}
.bar.proj{fill:var(--navy-2);opacity:.42}
.barval{font-family:var(--font-mono);font-size:13px;fill:var(--ink);font-weight:600}
.barpct{font-family:var(--font-body);font-size:12.5px;fill:var(--muted)}
.line{fill:none;stroke:var(--accent);stroke-width:2.6;stroke-linejoin:round}
.dot{fill:var(--surface);stroke:var(--accent);stroke-width:2.6}
.lineval{font-family:var(--font-mono);font-size:13.5px;fill:var(--accent-deep);font-weight:700}
.wf-total{fill:var(--navy-2)}
.wf-up{fill:var(--pos)}
.wf-down{fill:var(--crit)}
.wfval{font-family:var(--font-mono);font-size:13.5px;font-weight:700}
.wf-total-t{fill:var(--ink)}
.wf-up-t{fill:var(--pos)}
.wf-down-t{fill:var(--crit)}
.conn{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3;opacity:.6}
.rowlab{font-family:var(--font-body);font-size:14px;fill:var(--ink);font-weight:600}
.rowsub{font-family:var(--font-body);font-size:12px;fill:var(--muted)}
.sm{font-family:var(--font-mono);font-size:13px;fill:var(--muted)}
.sm.strong{fill:var(--ink);font-weight:700;font-size:14px}
.sm.dim{fill:var(--muted);font-size:12px}
.bar-old{fill:var(--muted);opacity:.45}
.bar-new{fill:var(--crit)}
.bar-pos{fill:var(--pos)}
.bar-neg{fill:var(--crit)}
.bar-now{fill:var(--navy-2);opacity:.55}
.bar-scen{fill:var(--accent)}
.bar-best{fill:var(--pos)}
.bar-weak{fill:var(--accent)}
.bar-closed{fill:var(--muted);opacity:.5}
.zero{stroke:var(--muted);stroke-width:1;opacity:.55}
.target{stroke:var(--pos);stroke-width:1.5;stroke-dasharray:4 4;opacity:.75}
.delta{font-family:var(--font-mono);font-size:13.5px;fill:var(--pos);font-weight:700}
.legend{font-family:var(--font-body);font-size:12.5px;fill:var(--muted)}

/* ── Таблица ── */
.tbl-scroll{overflow-x:auto;margin-bottom:26px}
table{width:100%;border-collapse:collapse;font-size:15.5px;min-width:560px}
th,td{padding:11px 12px;text-align:right;border-bottom:1px solid var(--hair)}
th:first-child,td:first-child{text-align:left}
thead th{background:var(--surface-2);color:var(--ink);font-weight:600;
  font-size:12px;letter-spacing:.05em;text-transform:uppercase;
  border-bottom:2px solid var(--hair)}
tbody td{font-variant-numeric:tabular-nums;color:var(--body)}
tbody tr:hover{background:var(--surface-2)}
td.strong,th.strong{color:var(--ink);font-weight:700}
tr.total td{border-top:2px solid var(--ink);border-bottom:none;
  font-weight:700;color:var(--ink);background:var(--surface-2)}
.neg{color:var(--crit);font-weight:600}
.pos-t{color:var(--pos);font-weight:600}

/* ── Проблемы ── */
.problem{background:var(--surface);border:1px solid var(--hair);
  border-radius:3px;margin-bottom:18px;box-shadow:var(--shadow);overflow:hidden}
.problem-head{display:flex;align-items:center;gap:14px;padding:18px 22px;
  background:var(--surface-2);border-bottom:1px solid var(--hair)}
.pnum{font-family:var(--font-mono);font-size:12px;font-weight:700;
  color:var(--navy);background:var(--accent);width:26px;height:26px;
  display:grid;place-items:center;border-radius:2px;flex:none}
.problem-head h3{font-size:18px;flex:1;line-height:1.3}
.sev{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  font-weight:700;padding:4px 9px;border-radius:2px;flex:none;white-space:nowrap}
.sev-1{background:var(--crit-soft);color:var(--crit)}
.sev-2{background:var(--accent-soft);color:var(--accent-deep)}
.problem-body{display:grid;grid-template-columns:1.55fr 1fr;gap:0}
.problem-text{padding:20px 22px;font-size:16.5px;line-height:1.68}
.problem-text strong{color:var(--ink);font-weight:600}
.problem-text p+p{margin-top:12px}
.metrics{border-left:1px solid var(--hair);padding:16px 20px;
  display:flex;flex-direction:column;gap:0;background:var(--surface)}
.mrow{display:flex;justify-content:space-between;align-items:baseline;
  gap:12px;padding:9px 0;border-bottom:1px solid var(--hair)}
.mrow:last-child{border-bottom:none}
.mlab{font-size:13.5px;color:var(--muted);line-height:1.35}
.mval{font-family:var(--font-mono);font-size:15.5px;font-weight:700;
  color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums}
.mval.crit{color:var(--crit)}
.mval.pos{color:var(--pos)}
@media (max-width:720px){.problem-body{grid-template-columns:1fr}
  .metrics{border-left:none;border-top:1px solid var(--hair)}}

/* ── Решения ── */
.solutions{display:grid;gap:16px}
.sol{display:grid;grid-template-columns:auto 1fr auto;gap:20px;
  align-items:center;background:var(--surface);border:1px solid var(--hair);
  border-radius:3px;padding:20px 24px;box-shadow:var(--shadow)}
.sol-icon{font-family:var(--font-mono);font-size:12px;font-weight:700;
  color:var(--accent-deep);background:var(--accent-soft);
  width:32px;height:32px;display:grid;place-items:center;border-radius:2px}
.sol-name{font-family:var(--font-display);font-size:17px;color:var(--ink);
  font-weight:600;margin-bottom:3px}
.sol-desc{font-size:14.5px;color:var(--muted)}
.sol-gain{font-family:var(--font-mono);font-size:19px;font-weight:700;
  color:var(--pos);white-space:nowrap;text-align:right}
.sol-gain small{display:block;font-family:var(--font-body);font-size:11px;
  color:var(--muted);font-weight:400;margin-top:2px}
@media (max-width:620px){.sol{grid-template-columns:auto 1fr}
  .sol-gain{grid-column:2;text-align:left}}

/* ── План ── */
.timeline{border-left:2px solid var(--hair);margin-left:8px;
  display:flex;flex-direction:column;gap:26px}
.tl-item{position:relative;padding-left:26px}
.tl-item::before{content:"";position:absolute;left:-7px;top:6px;width:12px;
  height:12px;border-radius:50%;background:var(--accent);
  border:2px solid var(--ground)}
.tl-when{font-family:var(--font-mono);font-size:11px;letter-spacing:.07em;
  text-transform:uppercase;color:var(--accent-deep);font-weight:700;
  margin-bottom:5px}
.tl-title{font-family:var(--font-display);font-size:17px;color:var(--ink);
  font-weight:600;margin-bottom:6px}
.tl-body{font-size:16px;line-height:1.62}
.tl-body strong{color:var(--ink);font-weight:600}

/* ── Полоса-выноска ── */
.pull{background:var(--navy);color:var(--on-navy);padding:34px 32px;
  border-radius:3px;margin:26px 0;border-left:4px solid var(--accent)}
.pull-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin-bottom:12px}
.pull p{font-family:var(--font-display);font-size:20px;line-height:1.5;
  color:var(--on-navy);max-width:58ch}
.pull .num-big{font-size:34px;color:var(--accent);font-weight:700;
  font-variant-numeric:tabular-nums}

/* ── Хорошее ── */
.wins{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.win{background:var(--pos-soft);border:1px solid var(--hair);border-radius:3px;
  padding:18px 20px}
.win-v{font-family:var(--font-display);font-size:24px;color:var(--pos);
  font-weight:700;margin-bottom:5px;font-variant-numeric:tabular-nums}
.win-t{font-size:14.5px;color:var(--body);line-height:1.5}

/* ── Сноски ── */
.notes{background:var(--surface-2);border:1px solid var(--hair);
  border-radius:3px;padding:22px 24px;font-size:15px;line-height:1.65}
.notes h4{font-size:14px;margin-bottom:12px;letter-spacing:.03em}
.notes ul{margin:0;padding-left:18px}
.notes li{margin-bottom:7px}
.notes li:last-child{margin-bottom:0}

footer{background:var(--navy);color:var(--on-navy-dim);padding:34px 0;
  font-size:13px;line-height:1.6}
footer b{color:var(--on-navy)}
</style>
<div class="progress" id="prog"></div>
''')

    # ─── ОБЛОЖКА ───
    w(f'''<div class="cover">
  <div class="wrap">
    <div class="eyebrow">Совет директоров · Закрытый документ</div>
    <h1>Растём вширь, теряем вглубь</h1>
    <p class="lead">Финансовый разбор группы за 2023–2026 на данных отчёта Accelerate Prosperity.
      Выручка выросла в 4,5 раза. Прибыльность с каждого сомони упала почти вдвое.
      Ниже — что именно её съело, сколько это стоит и что вернёт.</p>
    <div class="cover-meta">
      <span><b>Периметр:</b> Ромашка · Сиёма · Зелёный базар · ОВИР</span>
      <span><b>Период:</b> июль 2023 — июнь 2026</span>
      <span><b>Валюта:</b> сомони</span>
      <span><b>Источник:</b> отчёт AP + пересчёт</span>
    </div>
    <div class="kpis">
      {kpi("Выручка 2026", "6,26 М", "прогноз года ×2 от полугодия · ×4,5 к 2023", "gold")}
      {kpi("EBITDA-маржа", "17,2%", f"было 28,1% в 2023 · {fmt(d_margin,1)} п.п.", "crit")}
      {kpi("Свободные деньги", fmt(CASH_TOTAL), f"при долге {fmt(DEBT_TOTAL)} · покрытие {cov:.0f}%".replace(".",","), "crit")}
      {kpi("Потенциал", f"+{fmt(LEVER_TOTAL)}", "в год при возврате OPEX к норме", "pos")}
      {kpi("Требует сверки", fmt(140906), "разрыв в капитале — данные не закрыты", "crit")}
    </div>
  </div>
</div>''')

    # ─── 1. РЕАЛЬНАЯ КАРТИНА ───
    rows = ""
    for y in YEARS:
        star = "*" if y == 2026 else ""
        rows += (f'<tr><td class="strong">{y}{star}</td>'
                 f'<td>{fmt(REV[y])}</td>'
                 f'<td>{GMPCT[y]:.1f}%</td>'
                 f'<td class="neg">{OPCT[y]:.1f}%</td>'
                 f'<td class="strong">{fmt(EBIT[y])}</td>'
                 f'<td class="strong">{MARGIN[y]:.1f}%</td></tr>')
    w(f'''<section id="s1"><div class="wrap">
  <div class="sec-head"><span class="sec-num">01</span><h2>Реальная картина: что мы имеем</h2></div>
  <p class="sec-lead">Группа <strong>прибыльна все четыре года</strong> и ни разу не уходила в минус по операционной
    деятельности. Но за ростом оборота прячется главная проблема: <strong>EBITDA-маржа упала с 28,1% до 17,2%</strong> —
    почти вдвое. Каждый заработанный сомони приносит существенно меньше, чем три года назад.</p>

  <div class="card">
    <div class="card-title">Выручка растёт — маржа падает</div>
    <div class="card-sub">Столбцы — выручка (левая шкала). Линия — EBITDA-маржа (правая шкала). 2026 — прогноз года по полугодию.</div>
    <div class="chart-scroll">{chart_revenue_margin()}</div>
  </div>

  <div class="tbl-scroll">
  <table>
    <thead><tr><th>Год</th><th>Выручка</th><th>Валовая маржа</th><th>OPEX / выручка</th><th>EBITDA</th><th>Маржа</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
  <p class="sec-lead" style="margin-bottom:0">* 2026 — фактические 6 месяцев (янв–июнь). Проценты корректны, абсолютные суммы — половина года.</p>
</div></section>''')

    # ─── 2. МОСТИК ───
    oth23 = OPCT[2023]-RPCT[2023]-FPCT[2023]; oth26 = OPCT[2026]-RPCT[2026]-FPCT[2026]
    w(f'''<section id="s2"><div class="wrap">
  <div class="sec-head"><span class="sec-num">02</span><h2>Куда делись 10,9 процентных пункта</h2></div>
  <p class="sec-lead">Это главный график документа. <strong>Закупки и себестоимость мы научились вести лучше</strong> —
    валовая маржа выросла на {d_gm:.1f} п.п. Но операционные расходы съели этот выигрыш и ещё вдвое больше сверху.</p>
  <div class="card">
    <div class="card-title">Мостик EBITDA-маржи: 2023 → 2026</div>
    <div class="card-sub">Зелёное — что добавило маржу. Красное — что забрало. В процентных пунктах от выручки.</div>
    <div class="chart-scroll">{chart_bridge()}</div>
  </div>
  <div class="pull">
    <div class="pull-label">Что это значит на деле</div>
    <p>Мы стали лучше закупать — и полностью потеряли эту выгоду на аренде, зарплатах и прочей операционке.
      В деньгах: <span class="num-big">{fmt(abs(d_margin)/100*A_REV)}</span> в год — столько недополучает
      группа на текущем обороте по сравнению с эффективностью 2023 года.</p>
  </div>
</div></section>''')

    # ─── 3. ПРОБЛЕМЫ ───
    gap_worst = max(div_rows, key=lambda r: abs(r[6]))
    w(f'''<section id="s3"><div class="wrap">
  <div class="sec-head"><span class="sec-num">03</span><h2>Пять проблем — по порядку тяжести</h2></div>
  <p class="sec-lead">Каждая проблема ниже — с цифрой, которая её измеряет. Первые две определяют выживание,
    остальные три — управляемость и доверие к отчётности.</p>
''')

    w(prob(1, "Операционные расходы растут быстрее выручки", 1, "критично",
        f'''<p>С 2023 года OPEX вырос с <strong>23,3% до 41,1% от выручки</strong> — это и есть главный источник
        потери прибыльности. Два драйвера отвечают за 11 п.п. роста.</p>
        <p><strong>Аренда выросла втрое</strong> относительно выручки: новые точки арендуют существенно дороже
        по отношению к тому, что зарабатывают. <strong>ФОТ вырос на 5,3 п.п.</strong> — штат и зарплаты растут
        быстрее продаж.</p>
        <p>Это не разовое отклонение, а устойчивый тренд третий год подряд.</p>''',
        [("OPEX / выручка", "23,3% → 41,1%"),
         ("Аренда / выручка", "2,9% → 8,6%"),
         ("ФОТ / выручка", "12,1% → 17,4%"),
         ("Цена вопроса в год", f"{fmt(abs(d_margin)/100*A_REV)}")]))

    w(prob(2, "Долг в 4,6 раза больше свободных денег", 1, "критично",
        f'''<p>Свободных денег в группе — <strong>{fmt(CASH_TOTAL)}</strong>. Обязательств —
        <strong>{fmt(DEBT_TOTAL)}</strong> (заём Accelerate Prosperity {fmt(LOAN_AP)} + прочие {fmt(OTHER_LIAB)}).
        Покрытие — {cov:.0f}%.</p>
        <p><strong>Три денежные позиции из четырёх — отрицательные:</strong> Зелёный базар {fmt(-127567)},
        Ромашка {fmt(-42175)}, Сиёма {fmt(-14235)}. Положительный остаток держит только ОВИР и касса.</p>
        <p>Бизнес обслуживает долг за счёт оборота, а не за счёт подушки. Любой сбой — кассовый разрыв.</p>'''.replace("{cov:.0f}", f"{cov:.0f}"),
        [("Свободные деньги", fmt(CASH_TOTAL)),
         ("Все обязательства", fmt(DEBT_TOTAL)),
         ("Покрытие долга", f"{cov:.0f}%"),
         ("Дефицит", fmt(CASH_TOTAL-DEBT_TOTAL)),
         ("Месяцев EBITDA на закрытие", "10,2")]))

    w(prob(3, "Закрыли лучшую точку, новые работают хуже", 2, "важно",
        f'''<p>Самой эффективной точкой за всю историю была <strong>Ромашка — 26,1% маржи</strong> при вложениях
        всего {fmt(362166)} и окупаемости <strong>6,4 месяца</strong>. Она закрыта.</p>
        <p><strong>Зелёный базар</strong> — её замена — даёт 15,2% маржи при вложениях в 2,7 раза больше.
        <strong>ОВИР</strong> стартовал сильно (23,8%), но выборка всего полгода.</p>
        <p>Разрыв между Зелёным базаром и ОВИР — 8,6 п.п. При одинаковой бизнес-модели это означает,
        что на Зелёном базаре есть управляемая проблема: аренда, штат или закупочные условия.</p>''',
        [("Ромашка (закрыта)", "26,1%"),
         ("ОВИР", "23,8%"),
         ("Зелёный базар", "15,2%"),
         ("Сиёма (списана)", "−5,5%"),
         ("Если ЗБ выйдет на ОВИР", f"+{fmt(zb_gain)}/год")]))

    dr = "".join(
        f'<div class="mrow"><span class="mlab">{n}</span>'
        f'<span class="mval{" crit" if abs(g)>10 else ""}">{sd:.0f}% / {si:.0f}%</span></div>'
        for n, a, c, i, sd, si, g in div_rows)
    w(f'''<article class="problem">
      <header class="problem-head">
        <span class="pnum">4</span>
        <h3>Дивиденды не совпадают с долями вложений</h3>
        <span class="sev sev-2">важно</span>
      </header>
      <div class="problem-body">
        <div class="problem-text">
          <p>Выплачено <strong>{fmt(DIV_TOTAL)}</strong> дивидендов — это <strong>2,3 текущих остатка денег</strong>
          всей группы. Выплаты шли, пока денежные позиции точек уходили в минус.</p>
          <p>Отдельный вопрос — <strong>пропорции</strong>. Доля в выплаченных дивидендах у совладельцев
          не совпадает с долей во вложенном капитале: Устин вложил 68,6% денег участников, а получил 31,4% выплат;
          Шоира вложила 6,3%, получила 25,8%.</p>
          <p>Это может быть корректно, если официальные доли по уставу отличаются от сумм вложений —
          <strong>но в отчёте зарегистрированные доли не подтверждены</strong>. Требует сверки с уставом до следующей выплаты.</p>
        </div>
        <div class="metrics">
          <div class="mrow"><span class="mlab">Выплачено всего</span><span class="mval">{fmt(DIV_TOTAL)}</span></div>
          <div class="mrow"><span class="mlab">К остатку денег</span><span class="mval crit">2,3×</span></div>
          <div class="mrow"><span class="mlab" style="font-size:11px">доля выплат / доля вложений</span><span class="mval" style="font-size:11px">&#160;</span></div>
          {dr}
        </div>
      </div>
    </article>''')

    w(prob(5, "Отчётность не закрыта — капитал не сходится", 2, "важно",
        f'''<p>В отчёте AP <strong>капитал по балансу и по расчёту расходятся на {fmt(140906)}</strong>.
        Пока эта разница не объяснена, баланс группы нельзя считать точным.</p>
        <p>Сам отчёт помечает как неподтверждённые: уставный капитал {fmt(451576)} (взят из Word-документа,
        не из устава), возможное <strong>задвоение основных средств</strong>, незакрытые долги Ромашки
        на момент закрытия точки.</p>
        <p>Это не ошибка подрядчика — это нормальное состояние первого baseline-отчёта. Но принимать
        стратегические решения на этих цифрах пока рано.</p>''',
        [("Разрыв в капитале", fmt(140906)),
         ("Уставный капитал", "не подтверждён"),
         ("Основные средства", "возможно задвоение"),
         ("Долги Ромашки", "не закрыты")]))

    w('</div></section>')

    # ─── 4. ЧТО ХОРОШО ───
    w(f'''<section id="s4"><div class="wrap">
  <div class="sec-head"><span class="sec-num">04</span><h2>Что работает хорошо</h2></div>
  <p class="sec-lead">Картина не односторонняя. Есть четыре вещи, которые группа делает правильно —
    и на них строится план восстановления.</p>
  <div class="wins">
    <div class="win"><div class="win-v">4 года</div><div class="win-t">без единого убыточного года по группе —
      при закрытии двух точек и запуске двух новых</div></div>
    <div class="win"><div class="win-v">+{d_gm:.1f} п.п.</div><div class="win-t">рост валовой маржи: себестоимость,
      закупки и меню управляются заметно лучше, чем в 2023</div></div>
    <div class="win"><div class="win-v">23,8%</div><div class="win-t">маржа ОВИР в первое полугодие —
      второй результат за всю историю группы</div></div>
    <div class="win"><div class="win-v">{fmt(752792)}</div><div class="win-t">реинвестировано из прибыли Ромашки
      в запуск новых точек — без внешнего долга до 2025 года</div></div>
  </div>
</div></section>''')

    # ─── 5. РЕШЕНИЯ ───
    sols = ""
    for i, (name, desc, now, target) in enumerate(LEVERS, 1):
        save = now-target
        sols += f'''<div class="sol">
          <div class="sol-icon">P{i}</div>
          <div><div class="sol-name">{name}</div><div class="sol-desc">{desc} &#183; было {fmt(now)} → станет {fmt(target)}</div></div>
          <div class="sol-gain">+{fmt(save)}<small>в год</small></div>
        </div>'''
    w(f'''<section id="s5"><div class="wrap">
  <div class="sec-head"><span class="sec-num">05</span><h2>Как это чинится</h2></div>
  <p class="sec-lead">Три рычага, все — внутри операционного контроля. Цифры посчитаны на годовой выручке
    {fmt(A_REV)} (прогноз 2026). <strong>Ни один не требует роста выручки</strong> — только приведение
    расходов к норме, которая у нас уже была в 2023–2024.</p>
  <div class="solutions">{sols}
    <div class="sol" style="background:var(--surface-2);border-color:var(--accent)">
      <div class="sol-icon" style="background:var(--accent);color:#fff">Σ</div>
      <div><div class="sol-name">Суммарный эффект</div>
        <div class="sol-desc">EBITDA-маржа вырастет с 17,2% до 23,7% — уровень ОВИР</div></div>
      <div class="sol-gain" style="font-size:23px">+{fmt(LEVER_TOTAL)}<small>в год</small></div>
    </div>
  </div>
  <div class="card" style="margin-top:26px">
    <div class="card-title">Где именно расходы вышли из нормы</div>
    <div class="card-sub">Доля от выручки: 2023 (серое) против 2026 (красное)</div>
    <div class="chart-scroll">{chart_opex_split()}</div>
  </div>
  <div class="notes">
    <h4>Важно: не складывать дважды</h4>
    <p>Эффект «Зелёный базар выходит на маржу ОВИР» (+{fmt(zb_gain)}/год) — это <b>тот же самый выигрыш,
    показанный с другой стороны</b>: он реализуется через ту же аренду, ФОТ и прочий OPEX.
    Складывать его с тремя рычагами выше нельзя — получится двойной счёт.</p>
  </div>
</div></section>''')

    # ─── 6. СЦЕНАРИИ ───
    srows = ""
    for code, name, op in SCEN:
        eb = A_REV*(GM26-op); d = eb-A_EBIT
        months = DEBT_TOTAL/(eb/12)
        srows += (f'<tr><td class="strong">{code}. {name}</td><td>{op*100:.0f}%</td>'
                  f'<td>{(eb/A_REV*100):.1f}%</td><td>{fmt(eb)}</td>'
                  f'<td class="pos-t">+{fmt(d)}</td><td>{months:.1f} мес</td></tr>')
    now_months = DEBT_TOTAL/(A_EBIT/12)
    w(f'''<section id="s6"><div class="wrap">
  <div class="sec-head"><span class="sec-num">06</span><h2>К чему это приведёт</h2></div>
  <p class="sec-lead">Три сценария по глубине сокращения операционных расходов. Выручка во всех — неизменна
    ({fmt(A_REV)}), меняется только дисциплина расходов. <strong>Сценарий B возвращает группу
    к прибыльности уровня 2024 года.</strong></p>
  <div class="card">
    <div class="card-title">EBITDA при разной дисциплине расходов</div>
    <div class="card-sub">Серое — где мы сейчас. Золотое — сценарии. Внизу — прирост к текущему уровню.</div>
    <div class="chart-scroll">{chart_scenarios()}</div>
  </div>
  <div class="tbl-scroll">
  <table>
    <thead><tr><th>Сценарий</th><th>OPEX / выручка</th><th>EBITDA-маржа</th><th>EBITDA в год</th><th>Прирост</th><th>Закрытие долга</th></tr></thead>
    <tbody>
      <tr><td class="strong">Сейчас</td><td>41,1%</td><td>17,2%</td><td>{fmt(A_EBIT)}</td><td>—</td><td>{now_months:.1f} мес</td></tr>
      {srows}
    </tbody>
  </table>
  </div>
  <div class="pull">
    <div class="pull-label">Главный результат сценария B</div>
    <p>EBITDA вырастает до <span class="num-big">{fmt(scen_b)}</span> в год.
      Весь долг группы ({fmt(DEBT_TOTAL)}) закрывается за <b>7,5 месяцев</b> вместо {now_months:.1f} —
      и впервые появляется реальная подушка вместо жизни «в оборот».</p>
  </div>
</div></section>''')

    # ─── 7. КЭШ ───
    crows = "".join(
        f'<tr><td>{n}</td><td class="{"neg" if v<0 else ""}">{fmt(v)}</td></tr>'
        for n, v in CASH_POINTS)
    w(f'''<section id="s7"><div class="wrap">
  <div class="sec-head"><span class="sec-num">07</span><h2>Деньги против обязательств</h2></div>
  <p class="sec-lead">Самая срочная картина в документе. Пока не выправлена — любое стратегическое решение
    (новая точка, крупная закупка, дивиденды) повышает риск кассового разрыва.</p>
  <div class="card">
    <div class="card-title">Что есть и что должны</div>
    <div class="card-sub">Свободные деньги группы против всех обязательств, сомони</div>
    <div class="chart-scroll">{chart_cash()}</div>
  </div>
  <div class="tbl-scroll">
  <table>
    <thead><tr><th>Денежная позиция</th><th>Остаток</th></tr></thead>
    <tbody>{crows}<tr class="total"><td>Итого</td><td>{fmt(CASH_TOTAL)}</td></tr></tbody>
  </table>
  </div>
</div></section>''')

    # ─── 8. ТОЧКИ ───
    prows = ""
    for name, rev, eb, inv, mo, status, period in POINTS:
        m = eb/rev*100
        pay = f"{inv/(eb/mo):.0f} мес" if eb > 0 else "—"
        prows += (f'<tr><td class="strong">{name}</td><td>{fmt(rev)}</td>'
                  f'<td class="{"neg" if eb<0 else ""}">{fmt(eb)}</td>'
                  f'<td class="{"neg" if m<0 else "strong"}">{m:.1f}%</td>'
                  f'<td>{fmt(inv)}</td><td>{pay}</td><td>{status}</td></tr>')
    w(f'''<section id="s8"><div class="wrap">
  <div class="sec-head"><span class="sec-num">08</span><h2>Юнит-экономика точек</h2></div>
  <p class="sec-lead">Пунктир — планка 23,8% (маржа ОВИР). <strong>Зелёный базар — единственная действующая точка
    заметно ниже планки</strong>, и именно там сосредоточен основной резерв роста прибыли.</p>
  <div class="card">
    <div class="card-title">EBITDA-маржа по точкам</div>
    <div class="card-sub">Пунктирная линия — уровень лучшей действующей точки (ОВИР, 23,8%)</div>
    <div class="chart-scroll">{chart_points()}</div>
  </div>
  <div class="tbl-scroll">
  <table>
    <thead><tr><th>Точка</th><th>Выручка</th><th>EBITDA</th><th>Маржа</th><th>Вложено</th><th>Окупаемость</th><th>Статус</th></tr></thead>
    <tbody>{prows}</tbody>
  </table>
  </div>
  <div class="notes">
    <h4>Что отсюда следует</h4>
    <ul>
      <li><b>Ромашка окупалась за 6,4 месяца</b> — эталон, к которому стоит вернуться при оценке новых точек.</li>
      <li><b>Новые точки окупаются в 3 раза дольше</b> (19–22 месяца) при вложениях в 3 раза больше. Модель запуска стала дороже — это нужно осознанно решить: так и должно быть или мы переплачиваем.</li>
      <li><b>Сиёма — урок стоимостью {fmt(474964)}</b>. Перед следующим запуском стоит зафиксировать критерии выхода: при какой марже и через сколько месяцев точка закрывается.</li>
    </ul>
  </div>
</div></section>''')

    # ─── 9. ПЛАН 90 ДНЕЙ ───
    w(f'''<section id="s9"><div class="wrap">
  <div class="sec-head"><span class="sec-num">09</span><h2>План на 90 дней</h2></div>
  <p class="sec-lead">Последовательность выбрана так, чтобы сначала закрыть риск (данные и деньги),
    потом взяться за маржу. Каждый шаг — с измеримым результатом.</p>
  <div class="timeline">
    <div class="tl-item">
      <div class="tl-when">Недели 1–2 · Закрыть данные</div>
      <div class="tl-title">Отчётность становится достоверной</div>
      <div class="tl-body">Объяснить разрыв капитала <strong>{fmt(140906)}</strong>. Поднять устав и зафиксировать
        официальные доли участников. Проверить задвоение основных средств. Закрыть долги Ромашки.
        <strong>Результат:</strong> баланс, на который можно опираться в решениях.</div>
    </div>
    <div class="tl-item">
      <div class="tl-when">Недели 1–4 · Остановить отток</div>
      <div class="tl-title">Мораторий на дивиденды</div>
      <div class="tl-body">Не выплачивать дивиденды, пока покрытие долга деньгами не достигнет <strong>50%</strong>
        (сейчас {cov:.0f}%). Вывести Зелёный базар из минуса по кэшу.
        <strong>Результат:</strong> подушка вместо жизни «в оборот».</div>
    </div>
    <div class="tl-item">
      <div class="tl-when">Месяц 2 · Главный рычаг</div>
      <div class="tl-title">Аренда и ФОТ под норматив</div>
      <div class="tl-body">Пересмотреть договоры аренды по обеим точкам (цель — <strong>6% от выручки</strong>).
        Ввести норматив ФОТ <strong>15% от выручки</strong> с помесячным контролем.
        <strong>Результат:</strong> +{fmt(163982+148828)} в год.</div>
    </div>
    <div class="tl-item">
      <div class="tl-when">Месяц 2–3 · Догнать лучшего</div>
      <div class="tl-title">Разбор Зелёного базара</div>
      <div class="tl-body">Построчно сравнить структуру расходов ЗБ и ОВИР — найти, откуда берутся
        <strong>8,6 п.п. разрыва</strong>. Проверить закупочные цены, штатное расписание, аренду.
        <strong>Результат:</strong> до +{fmt(zb_gain)} в год.</div>
    </div>
    <div class="tl-item">
      <div class="tl-when">Месяц 3 · Не повторить</div>
      <div class="tl-title">Правила для новых точек</div>
      <div class="tl-body">Зафиксировать критерии открытия: целевая маржа <strong>≥ 23%</strong>,
        окупаемость <strong>≤ 12 месяцев</strong>, аренда <strong>≤ 6% от плановой выручки</strong>.
        И критерий закрытия — чтобы второй Сиёмы не было.
        <strong>Результат:</strong> дисциплина роста.</div>
    </div>
  </div>
</div></section>''')

    # ─── 10. KPI ───
    kpis_tbl = [
        ("EBITDA-маржа по группе", "17,2%", "≥ 23%", "ежемесячно"),
        ("OPEX / выручка", "41,1%", "≤ 35%", "ежемесячно"),
        ("Аренда / выручка", "8,6%", "≤ 6%", "ежемесячно"),
        ("ФОТ / выручка", "17,4%", "≤ 15%", "ежемесячно"),
        ("Покрытие долга деньгами", f"{cov:.0f}%", "≥ 50%", "ежемесячно"),
        ("Денежный остаток", fmt(CASH_TOTAL), "≥ 1 мес OPEX", "еженедельно"),
        ("Маржа Зелёного базара", "15,2%", "≥ 23%", "ежемесячно"),
    ]
    krows = "".join(f'<tr><td class="strong">{a}</td><td class="neg">{b}</td>'
                    f'<td class="pos-t">{c}</td><td>{d}</td></tr>' for a, b, c, d in kpis_tbl)
    w(f'''<section id="s10"><div class="wrap">
  <div class="sec-head"><span class="sec-num">10</span><h2>Панель контроля</h2></div>
  <p class="sec-lead">Семь показателей, которые определяют, работает план или нет. Всё считается из данных,
    которые уже собираются — дополнительный учёт не нужен.</p>
  <div class="tbl-scroll">
  <table>
    <thead><tr><th>Показатель</th><th>Сейчас</th><th>Цель</th><th>Частота</th></tr></thead>
    <tbody>{krows}</tbody>
  </table>
  </div>
  <div class="notes" style="margin-top:24px">
    <h4>Оговорки к цифрам — читать обязательно</h4>
    <ul>
      <li><b>2026 — это полугодие.</b> Годовые цифры получены умножением на 2. Проценты и доли корректны,
        абсолютные суммы за год — оценка, а не факт. Сезонность не учтена.</li>
      <li><b>Отчёт AP — baseline, а не аудит.</b> Подрядчик сам помечает часть позиций как требующие
        подтверждения. Разрыв капитала {fmt(140906)} не объяснён.</li>
      <li><b>Сценарии — это арифметика, а не прогноз.</b> Они показывают, сколько денег даёт возврат
        расходов к норме, но не гарантируют, что аренду удастся пересогласовать.</li>
      <li><b>Доли участников не подтверждены уставом.</b> Сравнение «вложено / получено» построено
        на суммах вложений из Word-документа.</li>
    </ul>
  </div>
</div></section>''')

    w(f'''<footer><div class="wrap">
  <b>Ромашка Групп · Финансовый разбор для совета директоров</b><br>
  Источник данных: отчёт Accelerate Prosperity (июль 2023 — июнь 2026) + независимый пересчёт показателей.
  Все суммы в сомони. Документ подготовлен для внутреннего обсуждения.
</div></footer>
<script>
(function(){{
  var p=document.getElementById("prog");
  function upd(){{
    var h=document.documentElement,
        m=(h.scrollTop||document.body.scrollTop),
        t=(h.scrollHeight-h.clientHeight);
    p.style.width=(t>0?(m/t*100):0)+"%";
  }}
  window.addEventListener("scroll",upd,{{passive:true}});
  window.addEventListener("resize",upd); upd();
}})();
</script>''')

    out = ru_decimals(html.getvalue())
    open(OUT, "w", encoding="utf-8").write(out)
    print("OK →", OUT)
    print(f"размер: {len(out)/1024:.0f} КБ")

build()
