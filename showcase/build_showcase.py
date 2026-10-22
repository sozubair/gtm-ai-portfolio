#!/usr/bin/env python3
"""Build outputs/showcase.html from the three tools.

Every number on the page is computed at build time by importing the tools.
Fonts are embedded as base64 so the page works offline. Charts are inline SVG
with labels on the data and no legends. Prints one project per A4 page.

Usage:
    python showcase/build_showcase.py
"""
from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for folder in ("01_measurement_planner", "02_consent_matrix", "03_review_pack"):
    if str(ROOT / folder) not in sys.path:
        sys.path.insert(0, str(ROOT / folder))

import check  # noqa: E402
import planner  # noqa: E402
import review_pack  # noqa: E402

import fetch_fonts  # noqa: E402

OUTPUTS = ROOT / "outputs"
BRIEFS = ROOT / "01_measurement_planner" / "briefs"
SIM_UPLIFT = 0.30
SIM_SEED = 7
MINUS = "\u2212"

INK, PAPER, GOLD, YELLOW, GREEN, RED = "#17153A", "#F6F2EA", "#B07A00", "#FFC83D", "#2E7D5B", "#C2412D"
MUTED, RULE = "#5F5C7E", "#DDD6C8"

e = html.escape


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def pct(x: float, dp: int = 1, signed: bool = True) -> str:
    return planner.fmt_pct(x, dp, signed)


def millions(x: float) -> str:
    sign = MINUS if x < 0 else ""
    return f"{sign}£{abs(x) / 1e6:,.2f}m"


def num(x: float, dp: int = 0) -> str:
    sign = MINUS if x < 0 else ""
    return f"{sign}{abs(x):,.{dp}f}"


def snum(x: float, dp: int = 1) -> str:
    return ("+" if x >= 0 else MINUS) + f"{abs(x):,.{dp}f}"


# --------------------------------------------------------------------------
# Compute
# --------------------------------------------------------------------------
def pack_status(out_dir: Path, digest: str) -> tuple[str, dict | None]:
    """APPROVED only if the log holds an approval for this exact content."""
    log = Path(out_dir) / review_pack.APPROVAL_LOG
    if log.exists():
        for line in reversed(log.read_text(encoding="utf-8").splitlines()):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("sha256") == digest:
                return "APPROVED", entry
    return "DRAFT", None


def compute(out_dir: Path = OUTPUTS) -> dict:
    out_dir = Path(out_dir)
    p1 = planner.run(BRIEFS / "workshops.json", SIM_UPLIFT, SIM_SEED, out_dir)
    p1e = planner.run(BRIEFS / "enterprise.json", None, SIM_SEED, out_dir)
    p2 = check.run_matrix(out_dir=out_dir)

    df = review_pack.load_data(out_dir)
    b = review_pack.bridge(df)
    draft = review_pack.draft_what_changed(b)
    digest = review_pack.content_hash(review_pack.render_content(b, draft))
    status, approval = pack_status(out_dir, digest)
    return {"p1": p1, "p1e": p1e, "p2": p2,
            "p3": {"bridge": b, "draft": draft, "sha256": digest, "status": status,
                   "approval": approval}}


# --------------------------------------------------------------------------
# SVG charts
# --------------------------------------------------------------------------
def _scale(d0: float, d1: float, r0: float, r1: float):
    return lambda v: r0 + (v - d0) / (d1 - d0) * (r1 - r0)


def _text(x, y, s, cls="lbl", anchor="start", fill=INK, weight=None, size=None) -> str:
    extra = f' font-weight="{weight}"' if weight else ""
    extra += f' font-size="{size}"' if size else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}" '
            f'fill="{fill}"{extra}>{e(s)}</text>')


def _svg(w: int, h: int, body: list[str], title: str) -> str:
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{e(title)}" '
            f'xmlns="http://www.w3.org/2000/svg"><title>{e(title)}</title>{"".join(body)}</svg>')


def chart_sourced_vs_measured(sim: dict) -> str:
    w, h = 600, 180
    x0, x1 = 190, 585
    s, m = sim["sourced_value"], sim["incremental_value"]
    lo, hi = sim["incremental_value_low"], sim["incremental_value_high"]
    X = _scale(min(0.0, lo), max(s, hi) * 1.04, x0, x1)
    zero, bh, y1, y2 = X(0), 36, 22, 104
    out = [
        _text(x0 - 12, y1 + 16, "Sourced claim", anchor="end", weight=600),
        _text(x0 - 12, y1 + 31, "every touched converter", anchor="end", fill=MUTED, size=11),
        f'<rect x="{min(zero, X(s)):.1f}" y="{y1}" width="{abs(X(s) - zero):.1f}" height="{bh}" fill="{GOLD}" rx="2"/>',
        _text(X(s) - 8, y1 + 23, millions(s), anchor="end", fill=PAPER, weight=700),
        _text(x0 - 12, y2 + 16, "Measured", anchor="end", weight=600),
        _text(x0 - 12, y2 + 31, "against the holdout", anchor="end", fill=MUTED, size=11),
        f'<rect x="{min(zero, X(m)):.1f}" y="{y2}" width="{abs(X(m) - zero):.1f}" height="{bh}" fill="{GREEN}" rx="2"/>',
    ]
    yc = y2 + bh / 2
    out += [
        f'<line x1="{X(lo):.1f}" y1="{yc}" x2="{X(hi):.1f}" y2="{yc}" stroke="{INK}" stroke-width="2"/>',
        f'<line x1="{X(lo):.1f}" y1="{yc - 8}" x2="{X(lo):.1f}" y2="{yc + 8}" stroke="{INK}" stroke-width="2"/>',
        f'<line x1="{X(hi):.1f}" y1="{yc - 8}" x2="{X(hi):.1f}" y2="{yc + 8}" stroke="{INK}" stroke-width="2"/>',
        _text(X(m), y2 - 7, millions(m), anchor="middle", weight=700),
        _text((X(lo) + X(hi)) / 2, y2 + bh + 17, f"range {millions(lo)} to {millions(hi)}",
              anchor="middle", fill=MUTED, size=12),
        f'<line x1="{zero:.1f}" y1="{y1 - 6}" x2="{zero:.1f}" y2="{y2 + bh + 4}" stroke="{INK}" stroke-width="1"/>',
    ]
    return _svg(w, h, out, "Sourced claim against measured incremental value")


def chart_uplift_interval(sim: dict, target: float) -> str:
    w, h = 600, 130
    x0, x1 = 30, 570
    low, high, est = sim["uplift_low"], sim["uplift_high"], sim["uplift"]
    X = _scale(min(0.0, low) - 0.04, max(high, target) + 0.04, x0, x1)
    yl = 64
    colour = GREEN if low > 0 else INK
    out = [
        f'<line x1="{x0}" y1="{yl}" x2="{x1}" y2="{yl}" stroke="{RULE}" stroke-width="1"/>',
        f'<line x1="{X(0):.1f}" y1="28" x2="{X(0):.1f}" y2="{yl + 22}" stroke="{INK}" stroke-width="1.5"/>',
        _text(X(0), 20, "No effect 0%", anchor="middle", fill=MUTED, size=12),
        f'<line x1="{X(target):.1f}" y1="28" x2="{X(target):.1f}" y2="{yl + 22}" stroke="{GOLD}" '
        f'stroke-width="2" stroke-dasharray="5 4"/>',
        _text(X(target), 20, f"Target {pct(target, 0)}", anchor="middle", fill=GOLD, weight=700, size=12),
        f'<line x1="{X(low):.1f}" y1="{yl}" x2="{X(high):.1f}" y2="{yl}" stroke="{colour}" '
        f'stroke-width="8" stroke-linecap="round"/>',
        f'<circle cx="{X(est):.1f}" cy="{yl}" r="9" fill="{INK}" stroke="{PAPER}" stroke-width="3"/>',
        _text(X(low), yl + 38, pct(low), anchor="middle", fill=MUTED, size=12),
        _text(X(high), yl + 38, pct(high), anchor="middle", fill=MUTED, size=12),
        _text(X(est), yl + 38, f"{pct(est)} measured", anchor="middle", weight=700),
        _text((x0 + x1) / 2, h - 6, "95% interval for the relative uplift", anchor="middle",
              fill=MUTED, size=11),
    ]
    return _svg(w, h, out, "Measured uplift with its 95% interval against zero and the target")


def chart_weekly(weekly, target: float) -> str:
    w, h = 600, 176
    x0, x1, yt, yb = 20, 580, 20, 150
    opps = [int(v) for v in weekly["opportunities"]]
    weeks = [int(v) for v in weekly["week"]]
    Y = _scale(0, max(max(opps), target) * 1.1, yb, yt)
    slot = (x1 - x0) / len(opps)
    bw = slot * 0.62
    out = []
    for i, (wk, v) in enumerate(zip(weeks, opps)):
        cx = x0 + slot * (i + 0.5)
        last = i == len(opps) - 1
        fill = (RED if v < target else GREEN) if last else INK
        out.append(f'<rect x="{cx - bw / 2:.1f}" y="{Y(v):.1f}" width="{bw:.1f}" '
                   f'height="{yb - Y(v):.1f}" fill="{fill}" rx="2"/>')
        out.append(_text(cx, Y(v) + 18, num(v), anchor="middle", fill=PAPER, weight=700, size=13))
        out.append(_text(cx, yb + 18, f"Wk {wk}", anchor="middle", fill=MUTED, size=12,
                         weight=700 if last else None))
    out.append(f'<line x1="{x0}" y1="{Y(target):.1f}" x2="{x1}" y2="{Y(target):.1f}" stroke="{GOLD}" '
               f'stroke-width="2" stroke-dasharray="6 4"/>')
    out.append(_text(x1, Y(target) - 6, f"Target {num(target)}", anchor="end", fill=GOLD, weight=700, size=12))
    return _svg(w, h, out, "Weekly opportunities against the weekly target")


def chart_waterfall(regions, base: float, now: float) -> str:
    w, h = 600, 196
    x0, x1, yt, yb = 20, 580, 24, 160
    steps = [("4 week avg", base, "total")]
    cum = base
    for r in regions.itertuples():
        steps.append((r.region, float(r.change), "delta"))
        cum += float(r.change)
    steps.append(("Week 8", now, "total"))

    levels, running = [base], base
    for _, v, kind in steps[1:-1]:
        running += v
        levels.append(running)
    levels.append(now)
    floor = int((min(levels) - 25) // 10 * 10)
    Y = _scale(floor, max(levels) + 12, yb, yt)
    slot = (x1 - x0) / len(steps)
    bw = slot * 0.6

    out, running, prev_top = [], 0.0, None
    for i, (name, v, kind) in enumerate(steps):
        cx = x0 + slot * (i + 0.5)
        if kind == "total":
            top, bottom, fill = v, floor, INK
            running = v
            label_y = Y(top) + 18
            out.append(f'<rect x="{cx - bw / 2:.1f}" y="{Y(top):.1f}" width="{bw:.1f}" '
                       f'height="{Y(bottom) - Y(top):.1f}" fill="{fill}" rx="2"/>')
            out.append(_text(cx, label_y, num(v, 1), anchor="middle", fill=PAPER, weight=700, size=13))
        else:
            start, end = running, running + v
            running = end
            top, bottom = max(start, end), min(start, end)
            fill = GREEN if v >= 0 else RED
            out.append(f'<rect x="{cx - bw / 2:.1f}" y="{Y(top):.1f}" width="{bw:.1f}" '
                       f'height="{max(Y(bottom) - Y(top), 1.5):.1f}" fill="{fill}" rx="2"/>')
            ly = Y(top) - 6 if v >= 0 else Y(bottom) + 16
            out.append(_text(cx, ly, snum(v), anchor="middle", fill=fill, weight=700, size=13))
        if prev_top is not None:
            px = x0 + slot * (i - 0.5) + bw / 2
            out.append(f'<line x1="{px:.1f}" y1="{Y(prev_top):.1f}" x2="{cx - bw / 2:.1f}" '
                       f'y2="{Y(prev_top):.1f}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="2 3"/>')
        prev_top = running
        out.append(_text(cx, yb + 18, name, anchor="middle", fill=INK, size=12, weight=600))
    out.append(f'<line x1="{x0}" y1="{yb}" x2="{x1}" y2="{yb}" stroke="{RULE}"/>')
    out.append(_text(x0, h - 4, f"Scale starts at {floor} opportunities", fill=MUTED, size=11))
    return _svg(w, h, out, "Bridge from the four week average to week 8 by region")


# --------------------------------------------------------------------------
# HTML pieces
# --------------------------------------------------------------------------
BASIS_LABEL = {"opt_out": "Opt out", "consent": "Consent", "presumed_consent": "Presumed consent"}
BASIS_CLASS = {"opt_out": "ok", "consent": "stop", "presumed_consent": "care"}
RULE_COLUMNS = [("email_company", "Email, company"), ("email_sole_trader", "Email, sole trader"),
                ("call_company", "Call, company"), ("call_sole_trader", "Call, sole trader")]


def consent_table(rules: dict) -> str:
    head = "".join(f"<th>{e(label)}</th>" for _, label in RULE_COLUMNS)
    rows = []
    for code, market in rules["countries"].items():
        cells = []
        for key, _ in RULE_COLUMNS:
            rule = market["rules"][key]
            label = BASIS_LABEL[rule["basis"]]
            notes = []
            if "mobile_basis" in rule:
                notes.append(f"mobile: {BASIS_LABEL[rule['mobile_basis']].lower()}")
            if rule["screening"]:
                notes.append("screen " + ", ".join(rule["screening"]))
            note = f"<small>{e('; '.join(notes))}</small>" if notes else ""
            cells.append(f"<td class='{BASIS_CLASS[rule['basis']]}'>{e(label)}{note}</td>")
        v = market["verification"]
        level = e(v["level"]) + (f"<small>{e(v['checked_on'])}</small>" if v["checked_on"] else "")
        rows.append(f"<tr><th>{e(market['name'])}</th>{''.join(cells)}"
                    f"<td class='lvl {e(v['level'])}'>{level}</td></tr>")
    return (f"<table class='consent'><tr><th>Market</th>{head}<th>Verified</th></tr>"
            f"{''.join(rows)}</table>")


def plays_table(rows: list[dict]) -> str:
    out = []
    for r in rows:
        if r["class"] == check.RUN_ONCE:
            cls = f"<span class='pill ok'>{e(r['class'])}</span>"
        else:
            cls = (f"<span class='pill care'>{e(r['class'])}</span> "
                   f"<small>{e(', '.join(r['localise_in']))}</small>")
        out.append(f"<tr><td>{e(r['play'])}</td><td>{cls}</td></tr>")
    return f"<table class='plays'><tr><th>Play</th><th>Class</th></tr>{''.join(out)}</table>"


def verification_summary(rules: dict) -> tuple[int, list[str], str, str]:
    """Count markets checked against a regulator or statute and name the rest."""
    markets = rules["countries"].values()
    total = len(rules["countries"])
    verified = sum(m["verification"]["level"] in ("regulator", "statute") for m in markets)
    open_markets = [f"{m['name']} ({m['verification']['level']})" for m in markets
                    if m["verification"]["level"] not in ("regulator", "statute")]
    short = f"{verified} of {total} markets verified against source."
    if open_markets:
        action = f"Finish checking {', '.join(open_markets)} before launch there."
    else:
        action = "Every market is verified against its source. Recheck before each launch."
    return verified, open_markets, short, action


def tile(label: str, value: str, comparison: str, tone: str = "") -> str:
    return (f"<div class='tile {tone}'><div class='tl'>{e(label)}</div>"
            f"<div class='tv'>{e(value)}</div><div class='tc'>{e(comparison)}</div></div>")


def decision(text: str) -> str:
    return f"<div class='decision'><span>Decision</span><p>{e(text)}</p></div>"


def font_css(allow_fetch: bool = True) -> str:
    """@font-face rules with base64 fonts. Empty string if fonts are unavailable."""
    if not fetch_fonts.MANIFEST.exists():
        if not allow_fetch:
            return ""
        try:
            fetch_fonts.fetch()
        except Exception as exc:  # stay usable offline with system fonts
            print(f"Warning: fonts not embedded ({exc})", file=sys.stderr)
            return ""
    entries = json.loads(fetch_fonts.MANIFEST.read_text(encoding="utf-8"))
    groups: dict[tuple[str, str, str], list[int]] = {}
    for item in entries:
        weights = [int(x) for x in item["weight"].split()]
        groups.setdefault((item["family"], item["style"], item["file"]), []).extend(weights)
    rules = []
    for (family, style, file), weights in groups.items():
        data = base64.b64encode((fetch_fonts.FONTS_DIR / file).read_bytes()).decode("ascii")
        weight = f"{min(weights)} {max(weights)}" if min(weights) != max(weights) else str(weights[0])
        rules.append(
            f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{weight};"
            f"font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )
    return "".join(rules)


CSS = f"""
:root{{--ink:{INK};--paper:{PAPER};--gold:{GOLD};--yellow:{YELLOW};--green:{GREEN};--red:{RED};
--muted:{MUTED};--rule:{RULE}}}
*{{box-sizing:border-box}}
html{{background:#E6DFD0}}
body{{margin:0;font-family:Inter,'Segoe UI',Arial,sans-serif;font-variant-numeric:tabular-nums;
font-feature-settings:'tnum' 1;color:var(--ink);line-height:1.45;font-size:14px}}
.page{{width:210mm;min-height:297mm;margin:24px auto;padding:15mm 16mm 12mm;background:var(--paper);
box-shadow:0 2px 14px rgba(23,21,58,.14);display:flex;flex-direction:column;gap:4.5mm}}
h1,h2,h3,.tv,.big{{font-family:Fraunces,Georgia,serif;font-weight:700;margin:0;line-height:1.1}}
h1{{font-size:46px}}h2{{font-size:30px}}h3{{font-size:16px;font-weight:600}}
.kicker{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);font-weight:700}}
.answer{{font-size:18px;font-weight:600;margin:0}}
mark{{background:var(--yellow);color:var(--ink);padding:0 5px;border-radius:3px}}
.chart svg{{width:100%;height:auto;display:block}}
.chart text{{font-family:Inter,'Segoe UI',Arial,sans-serif;font-variant-numeric:tabular-nums;font-size:13px}}
.facts{{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm}}
.fact{{border-top:2px solid var(--ink);padding-top:2mm}}
.fact b{{display:block;font-size:20px}}.fact span{{font-size:11.5px;color:var(--muted)}}
.tiles{{display:grid;grid-template-columns:1fr 1fr;gap:4mm}}
.tile{{background:#fff;border:1px solid var(--rule);border-radius:6px;padding:5mm}}
.tl{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--muted)}}
.tv{{font-size:40px;margin:2mm 0}}.tile.good .tv{{color:var(--green)}}.tile.bad .tv{{color:var(--red)}}
.tc{{font-size:13px}}
.decision{{margin-top:auto;background:var(--ink);color:var(--paper);border-radius:6px;padding:4.5mm 6mm}}
.decision span{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--yellow);font-weight:700}}
.decision p{{margin:1.5mm 0 0;font-size:14.5px}}
table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;padding:2.2mm 2.5mm;border-bottom:1px solid var(--rule);vertical-align:top}}
.consent td{{font-weight:700;font-size:13px}}.consent small,.plays small{{display:block;font-weight:400;font-size:11px}}
.consent .ok{{background:#DCEBE3;color:var(--green)}}.consent .stop{{background:#F5DDD7;color:var(--red)}}
.consent .care{{background:#FFF0C4;color:#7A5500}}.consent .lvl{{font-weight:600;color:var(--muted)}}
.pill{{display:inline-block;padding:.5mm 2.5mm;border-radius:10px;font-weight:700;font-size:12px}}
.pill.ok{{background:#DCEBE3;color:var(--green)}}.pill.care{{background:#FFF0C4;color:#7A5500}}
.plays small{{display:inline;margin-left:1mm}}
ul.changes{{margin:0;padding-left:5mm}}ul.changes li{{margin-bottom:1.5mm}}
.status{{font-weight:700;padding:.5mm 2.5mm;border-radius:3px}}
.status.DRAFT{{background:var(--yellow)}}.status.APPROVED{{background:var(--green);color:#fff}}
.foot{{font-size:10px;color:var(--muted);border-top:1px solid var(--rule);padding-top:2mm}}
.cover{{background:var(--ink);color:var(--paper);justify-content:space-between}}
.cover .kicker{{color:var(--yellow)}}.cover p.lede{{font-size:17px;max-width:150mm;color:#D9D5E8}}
.heads{{display:grid;grid-template-columns:repeat(3,1fr);gap:6mm}}
.head{{border-top:3px solid var(--yellow);padding-top:4mm}}
.big{{font-size:54px;color:var(--yellow)}}.head p{{margin:2mm 0 0;color:#D9D5E8;font-size:13px}}
.cover .foot{{color:#9C98B8;border-color:#3A3766}}
.summary p{{margin:0 0 3mm;font-size:15px}}
@page{{size:A4;margin:0}}
@media print{{html{{background:none}}.page{{margin:0;box-shadow:none;height:297mm;overflow:hidden;
break-after:page;page-break-after:always}}.page:last-child{{break-after:auto;page-break-after:auto}}
*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
"""


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
def render(data: dict, fonts: str) -> str:
    p1, p1e, p2, p3 = data["p1"], data["p1e"], data["p2"], data["p3"]
    brief, plan, sim = p1["brief"], p1["plan"], p1["sim"]
    eplan, ebrief = p1e["plan"], p1e["brief"]
    rules, rows = p2["rules"], p2["rows"]
    b, draft = p3["bridge"], p3["draft"]
    regions = b["regions"].set_index("region")

    target = brief["min_detectable_uplift"]
    ratio = sim["sourced_to_measured"]
    ratio_text = f"{ratio:.1f}x" if ratio is not None else "n/a"
    run_once = sum(r["class"] == check.RUN_ONCE for r in rows)
    localise = len(rows) - run_once
    verified, open_markets, verify_short, verify_action = verification_summary(rules)
    drag = draft["biggest_drag"]
    drag_conv = float(regions.loc[drag, "conv_change_pct"])
    drag_leads = float(regions.loc[drag, "leads_change_pct"])
    lift = draft["biggest_lift"]
    total_change = b["total_now"] - b["total_base"]
    weekly_target = review_pack.generate_data.WEEKLY_TARGET_OPPORTUNITIES
    emde = eplan["min_detectable_uplift"]
    emde_text = pct(emde, 0) if emde is not None else "no uplift"
    localise_email = next((r["localise_in"] for r in rows if r["play"] == "Cold email to target companies"), [])

    p1_answer = (f"The workshops lift opportunity creation by <mark>{e(pct(sim['uplift']))}</mark>, "
                 f"worth {e(millions(sim['incremental_value']))}. A sourced count would claim "
                 f"{e(millions(sim['sourced_value']))}, {e(ratio_text)} the measured value.")
    p2_answer = (f"<mark>{run_once} of {len(rows)}</mark> outbound plays can run once for EMEA. "
                 f"The other {localise} need local rules.")
    p3_answer = (f"Week 8 came in at {e(num(b['total_now']))} opportunities, "
                 f"{e(pct(total_change / b['total_base']))} on the four week average. "
                 f"<mark>{e(drag)} conversion fell {e(pct(abs(drag_conv), 0, False))}</mark> while its "
                 f"leads moved {e(pct(drag_leads, 0))}.")

    cover = f"""
<section class="page cover">
  <div>
    <div class="kicker">GTM tools portfolio</div>
    <h1 style="margin-top:6mm">Three GTM tools that<br>show their working</h1>
    <p class="lede">A measurement planner, a consent matrix and a weekly review pack.
    Code computes every number on these pages. All data is fictional or public.</p>
  </div>
  <div class="heads">
    <div class="head"><div class="big">{e(ratio_text)}</div>
      <p>How far a sourced count overstates the value a holdout measures.</p></div>
    <div class="head"><div class="big">{run_once} of {len(rows)}</div>
      <p>Outbound plays that can run once for EMEA across six markets.</p></div>
    <div class="head"><div class="big">{e(pct(drag_conv, 0))}</div>
      <p>{e(drag)} conversion in week 8, found by the bridge, not by eye.</p></div>
  </div>
  <div class="foot">Fictional data. Not legal advice. Built by showcase/build_showcase.py.</div>
</section>"""

    overview = f"""
<section class="page">
  <div class="kicker">At a glance</div>
  <h2>The answer first</h2>
  <div class="summary">
    <p><b>Measurement planner.</b> {p1_answer}</p>
    <p><b>Consent matrix.</b> {p2_answer}</p>
    <p><b>Review pack.</b> {p3_answer}</p>
  </div>
  <div class="tiles">
    {tile("Measured uplift", pct(sim["uplift"]),
          f"Target {pct(target, 0)}. 95% interval {pct(sim['uplift_low'])} to {pct(sim['uplift_high'])}.",
          "good" if sim["uplift_low"] > 0 else "")}
    {tile("Incremental value", millions(sim["incremental_value"]),
          f"Sourced claim {millions(sim['sourced_value'])}, {ratio_text} higher.")}
    {tile("Plays that run once for EMEA", f"{run_once} of {len(rows)}",
          f"{localise} plays need local rules. {verify_short}")}
    {tile("Week 8 opportunities", num(b["total_now"]),
          f"Four week average {num(b['total_base'], 1)} ({pct(total_change / b['total_base'])}). "
          f"Target {num(weekly_target)}.", "bad" if b["total_now"] < weekly_target else "good")}
  </div>
  <div class="foot">Every figure on this page is computed at build time from the three tools.</div>
</section>"""

    need = plan["need"]
    page1 = f"""
<section class="page">
  <div class="kicker">Project 1. Measurement planner</div>
  <h2>{e(brief['program'])}: measured, not sourced</h2>
  <p class="answer">{p1_answer}</p>
  <h3>Sourced claim against measured value</h3>
  <div class="chart">{chart_sourced_vs_measured(sim)}</div>
  <h3>Measured uplift against zero and the target</h3>
  <div class="chart">{chart_uplift_interval(sim, target)}</div>
  <div class="facts">
    <div class="fact"><b>{e(planner.fmt_int(brief['eligible_units']))}</b><span>eligible accounts</span></div>
    <div class="fact"><b>{e(planner.fmt_int(need['total']))}</b><span>needed to detect {e(pct(target, 0))} at an
      {round((1 - brief['holdout_share']) * 100)}/{round(brief['holdout_share'] * 100)} split</span></div>
    <div class="fact"><b>{e(planner.fmt_pct(plan['power_with_all_units'], 1))}</b><span>power using every account</span></div>
    <div class="fact"><b>{e(planner.fmt_p(sim['p_value']))}</b><span>p value in the simulated run</span></div>
  </div>
  {decision(f"Fund {brief['program'].lower()} on the measured {millions(sim['incremental_value'])}, "
            f"not the sourced {millions(sim['sourced_value'])}. Keep a "
            f"{round(brief['holdout_share'] * 100)}% holdout. {ebrief['program']} have "
            f"{planner.fmt_int(ebrief['eligible_units'])} accounts but need "
            f"{planner.fmt_int(eplan['need']['total'])} for a holdout, so roll out in stages and treat "
            f"any uplift below {emde_text} as directional.")}
  <div class="foot">Simulated run with a true uplift of {e(pct(SIM_UPLIFT, 0))}, seed {SIM_SEED}. Fictional data.</div>
</section>"""

    page2 = f"""
<section class="page">
  <div class="kicker">Project 2. Consent matrix</div>
  <h2>Which outbound plays travel across EMEA</h2>
  <p class="answer">{p2_answer}</p>
  <h3>Rules by market</h3>
  {consent_table(rules)}
  <h3>Plays</h3>
  {plays_table(rows)}
  {decision(f"Run the {run_once} plays built on consent or existing customers once for EMEA. "
            f"Localise cold email in {', '.join(localise_email)}. "
            f"{verify_action}")}
  <div class="foot">Green: allowed with an opt out. Yellow: needs a documented reason. Red: needs consent.
  Not legal advice.</div>
</section>"""

    status = p3["status"]
    approved_by = (f" by {e(p3['approval']['name'])}" if p3["approval"] else "")
    shared = "".join(f"<li>{e(t)}</li>" for t in draft["shared_text"])
    page3 = f"""
<section class="page">
  <div class="kicker">Project 3. Weekly review pack</div>
  <h2>What changed in week 8</h2>
  <p class="answer">{p3_answer}</p>
  <h3>Weekly opportunities against target</h3>
  <div class="chart">{chart_weekly(b['weekly'], weekly_target)}</div>
  <h3>Bridge by region</h3>
  <div class="chart">{chart_waterfall(b['regions'], b['total_base'], b['total_now'])}</div>
  <ul class="changes">
    <li>{e(draft['biggest_drag_text'])}</li>
    <li>{e(draft['biggest_lift_text'])}</li>
    {shared}
  </ul>
  {decision(f"Review {drag} lead routing and qualification this week. Plan on the {lift} rise only "
            f"once a second week confirms it.")}
  <div class="foot">Pack status: <span class="status {status}">{status}{approved_by}</span>
  SHA-256 {e(p3['sha256'][:16])}. Fictional data.</div>
</section>"""

    return (
        "<!doctype html><html lang='en-GB'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>GTM tools portfolio</title>"
        f"<style>{fonts}{CSS}</style></head><body>"
        f"{cover}{overview}{page1}{page2}{page3}</body></html>"
    )


def build(out_dir: Path = OUTPUTS, allow_fetch: bool = True) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = compute(out_dir)
    fonts = font_css(allow_fetch)
    page = render(data, fonts)
    path = out_dir / "showcase.html"
    path.write_text(page, encoding="utf-8")
    return {"path": path, "html": page, "data": data, "fonts_embedded": bool(fonts)}


def main() -> int:
    out = build()
    print(f"Showcase written to {out['path']}")
    print(f"Fonts embedded: {'yes' if out['fonts_embedded'] else 'no, using system fonts'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
