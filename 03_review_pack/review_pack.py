#!/usr/bin/env python3
"""Weekly pipeline review pack.

Bridges week 8 against the average of the four weeks before it, by region and
segment. Splits each change in opportunities into a volume effect and a
conversion effect. Drafts a 'what changed' note. Writes an HTML pack that
stays DRAFT until a named person approves it. Approval is logged with a
SHA-256 hash of the pack content.

Usage:
    python 03_review_pack/review_pack.py
    python 03_review_pack/review_pack.py --approve "Jane Doe"
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import generate_data

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
PACK_FILE = "review_pack.html"
APPROVAL_LOG = "approvals.log"
CURRENT_WEEK = 8
BASE_WEEKS = 4
# A region's conversion "fell" in a segment if it dropped by more than this share.
MATERIAL_CONVERSION_FALL = 0.10
MINUS = "\u2212"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def load_data(out_dir: Path = OUTPUTS) -> pd.DataFrame:
    """Read the generated CSV, or generate it if it is missing."""
    path = Path(out_dir) / generate_data.DATA_FILE
    if path.exists():
        return pd.read_csv(path)
    df = generate_data.generate()
    generate_data.write(df, out_dir)
    return df


# --------------------------------------------------------------------------
# Bridge
# --------------------------------------------------------------------------
def _effects(frame: pd.DataFrame) -> pd.DataFrame:
    """Add conversion rates and the volume and conversion effects.

    opportunities = leads x conversion, so the change splits exactly:
        volume effect     = (leads_now - leads_base) x conversion_base
        conversion effect = leads_now x (conversion_now - conversion_base)
    """
    f = frame.copy()
    f["conv_base"] = f["opps_base"] / f["leads_base"]
    f["conv_now"] = f["opps_now"] / f["leads_now"]
    f["volume_effect"] = (f["leads_now"] - f["leads_base"]) * f["conv_base"]
    f["conversion_effect"] = f["leads_now"] * (f["conv_now"] - f["conv_base"])
    f["change"] = f["opps_now"] - f["opps_base"]
    f["leads_change_pct"] = f["leads_now"] / f["leads_base"] - 1
    f["conv_change_pct"] = f["conv_now"] / f["conv_base"] - 1
    f["pipeline_change"] = f["pipeline_now"] - f["pipeline_base"]
    return f


def bridge(df: pd.DataFrame, week: int = CURRENT_WEEK, base_weeks: int = BASE_WEEKS) -> dict:
    """Bridge one week against the average of the weeks before it."""
    base_range = list(range(week - base_weeks, week))
    if not set(base_range).issubset(set(df["week"])) or week not in set(df["week"]):
        raise ValueError(f"Data must contain weeks {base_range[0]} to {week}")
    keys = ["region", "segment"]
    cols = ["leads", "opportunities", "pipeline_gbp"]
    base = df[df["week"].isin(base_range)].groupby(keys)[cols].mean()
    now = df[df["week"] == week].groupby(keys)[cols].sum()
    joined = base.join(now, lsuffix="_base", rsuffix="_now").reset_index()
    joined = joined.rename(columns={
        "leads_base": "leads_base", "opportunities_base": "opps_base",
        "pipeline_gbp_base": "pipeline_base", "leads_now": "leads_now",
        "opportunities_now": "opps_now", "pipeline_gbp_now": "pipeline_now",
    })
    segments = _effects(joined)

    sums = ["leads_base", "leads_now", "opps_base", "opps_now", "pipeline_base", "pipeline_now"]
    regions = _effects(segments.groupby("region", sort=False)[sums].sum().reset_index())
    # The region effects must equal the sum of the segment effects.
    seg_sum = segments.groupby("region", sort=False)[["volume_effect", "conversion_effect"]].sum()
    regions = regions.set_index("region")
    regions[["volume_effect", "conversion_effect"]] = seg_sum
    regions = regions.reset_index()

    weekly = df.groupby("week")[cols].sum().reset_index()
    return {
        "week": week,
        "base_weeks": base_range,
        "segments": segments,
        "regions": regions,
        "weekly": weekly,
        "total_base": float(segments["opps_base"].sum()),
        "total_now": float(segments["opps_now"].sum()),
        "pipeline_base": float(segments["pipeline_base"].sum()),
        "pipeline_now": float(segments["pipeline_now"].sum()),
    }


def biggest_drag(b: dict) -> str:
    return str(b["regions"].sort_values("change").iloc[0]["region"])


def biggest_lift(b: dict) -> str:
    return str(b["regions"].sort_values("change").iloc[-1]["region"])


def shared_conversion_falls(b: dict, threshold: float = MATERIAL_CONVERSION_FALL) -> list[str]:
    """Regions where conversion fell by more than the threshold in every segment."""
    seg = b["segments"]
    out = []
    for region, group in seg.groupby("region", sort=False):
        if (group["conv_change_pct"] < -threshold).all():
            out.append(str(region))
    return out


# --------------------------------------------------------------------------
# Draft
# --------------------------------------------------------------------------
def signed(x: float, dp: int = 0) -> str:
    return ("+" if x >= 0 else MINUS) + f"{abs(x):,.{dp}f}"


def signed_pct(x: float, dp: int = 0) -> str:
    return ("+" if x >= 0 else MINUS) + f"{abs(x) * 100:.{dp}f}%"


def money(x: float) -> str:
    sign = MINUS if x < 0 else ""
    return f"{sign}£{abs(x) / 1e6:,.2f}m"


def draft_what_changed(b: dict) -> dict:
    """Draft the note. Every number comes from the bridge."""
    regions = b["regions"].set_index("region")
    segments = b["segments"]
    total_change = b["total_now"] - b["total_base"]

    headline = (
        f"Week {b['week']} produced {b['total_now']:,.0f} opportunities against a four week "
        f"average of {b['total_base']:,.1f}. That is {signed(total_change, 1)} "
        f"({signed_pct(total_change / b['total_base'], 1)})."
    )

    drag = biggest_drag(b)
    d = regions.loc[drag]
    drag_driver = "conversion" if abs(d["conversion_effect"]) >= abs(d["volume_effect"]) else "volume"
    drag_text = (
        f"Biggest drag: {drag}, {signed(d['change'], 1)} opportunities. "
        f"Conversion effect {signed(d['conversion_effect'], 1)}. "
        f"Volume effect {signed(d['volume_effect'], 1)}. The fall is mostly {drag_driver}."
    )

    lift = biggest_lift(b)
    l_ = regions.loc[lift]
    lift_segs = segments[segments["region"] == lift].sort_values("change")
    lead_seg = lift_segs.iloc[-1]
    lift_driver = "volume" if abs(l_["volume_effect"]) >= abs(l_["conversion_effect"]) else "conversion"
    lift_text = (
        f"Biggest lift: {lift}, {signed(l_['change'], 1)} opportunities, led by "
        f"{lead_seg['segment']} where leads moved {signed_pct(lead_seg['leads_change_pct'])}. "
        f"Volume effect {signed(l_['volume_effect'], 1)}. "
        f"Conversion effect {signed(l_['conversion_effect'], 1)}. The rise is mostly {lift_driver}."
    )

    shared = shared_conversion_falls(b)
    shared_lines = []
    for region in shared:
        rows = segments[segments["region"] == region]
        parts = ", ".join(f"{r.segment} {signed_pct(r.conv_change_pct)}" for r in rows.itertuples())
        vol = regions.loc[region, "leads_change_pct"]
        shared_lines.append(
            f"{region} conversion fell in every segment: {parts}. "
            f"Lead volume moved {signed_pct(vol)} over the same period, so demand held up."
        )

    notes = []
    if shared:
        notes.append(f"Treat {', '.join(shared)} as a conversion problem, not a demand problem. "
                     "Check lead routing, qualification rules and SDR capacity before the review.")
    if lift_driver == "volume":
        notes.append(f"The {lift} rise is volume. Confirm it holds for a second week before "
                     "you plan on it.")
    notes.append("This draft was generated from the bridge. A reviewer must approve it before it circulates.")

    return {
        "headline": headline,
        "biggest_drag": drag,
        "biggest_drag_text": drag_text,
        "biggest_lift": lift,
        "biggest_lift_text": lift_text,
        "shared_regions": shared,
        "shared_text": shared_lines,
        "review_note": " ".join(notes),
    }


# --------------------------------------------------------------------------
# HTML pack and approval
# --------------------------------------------------------------------------
def _table(frame: pd.DataFrame, label: str) -> str:
    head = (f"<tr><th>{label}</th><th>4 week avg</th><th>Week 8</th><th>Volume effect</th>"
            "<th>Conversion effect</th><th>Change</th><th>Leads</th><th>Conversion</th></tr>")
    body = []
    for r in frame.itertuples():
        name = r.region if label == "Region" else f"{r.region} {r.segment}"
        cls = "neg" if r.change < 0 else "pos"
        body.append(
            f"<tr><td>{html.escape(name)}</td><td>{r.opps_base:,.1f}</td><td>{r.opps_now:,.0f}</td>"
            f"<td>{signed(r.volume_effect, 1)}</td><td>{signed(r.conversion_effect, 1)}</td>"
            f"<td class='{cls}'>{signed(r.change, 1)}</td><td>{signed_pct(r.leads_change_pct)}</td>"
            f"<td>{signed_pct(r.conv_change_pct)}</td></tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def render_content(b: dict, draft: dict) -> str:
    """The reviewable content. This is what the approval hash covers."""
    esc = html.escape
    shared = "".join(f"<li>{esc(t)}</li>" for t in draft["shared_text"]) or "<li>None.</li>"
    weekly_rows = "".join(
        f"<tr><td>Week {int(r.week)}</td><td>{int(r.leads):,}</td><td>{int(r.opportunities):,}</td>"
        f"<td>{money(r.pipeline_gbp)}</td></tr>"
        for r in b["weekly"].itertuples()
    )
    return (
        "<section id='content'>"
        f"<h1>Pipeline review: week {b['week']}</h1>"
        "<p class='small'>Fictional data. Week 8 is bridged against the average of weeks "
        f"{b['base_weeks'][0]} to {b['base_weeks'][-1]}.</p>"
        "<h2>What changed</h2>"
        f"<p class='headline'>{esc(draft['headline'])}</p>"
        f"<ul><li>{esc(draft['biggest_drag_text'])}</li><li>{esc(draft['biggest_lift_text'])}</li></ul>"
        "<h3>Shared patterns</h3>"
        f"<ul>{shared}</ul>"
        "<h3>Review note</h3>"
        f"<p>{esc(draft['review_note'])}</p>"
        "<h2>Bridge by region</h2>"
        f"{_table(b['regions'], 'Region')}"
        "<h2>Bridge by region and segment</h2>"
        f"{_table(b['segments'], 'Segment')}"
        "<h2>Weekly totals</h2>"
        "<table><tr><th>Week</th><th>Leads</th><th>Opportunities</th><th>Pipeline</th></tr>"
        f"{weekly_rows}</table>"
        "</section>"
    )


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


STYLE = """
body{font-family:Inter,Segoe UI,Arial,sans-serif;color:#17153A;background:#F6F2EA;margin:0;padding:32px;
font-variant-numeric:tabular-nums}
.status{padding:14px 18px;border-radius:6px;font-weight:700;margin-bottom:24px}
.draft{background:#FFC83D;color:#17153A}.approved{background:#2E7D5B;color:#fff}
h1{font-family:Fraunces,Georgia,serif}h2{margin-top:28px}
table{border-collapse:collapse;margin:8px 0 16px}td,th{padding:6px 10px;border-bottom:1px solid #ddd6c8;text-align:right}
td:first-child,th:first-child{text-align:left}.neg{color:#C2412D;font-weight:700}.pos{color:#2E7D5B;font-weight:700}
.headline{font-size:1.15em;font-weight:600}.small{color:#5a577a;font-size:.9em}.hash{font-family:monospace;font-size:.8em}
"""


def render_pack(content: str, approval: dict | None) -> str:
    if approval:
        status = (
            f"<div class='status approved'>APPROVED by {html.escape(approval['name'])} on "
            f"{approval['approved_at']}. <span class='hash'>SHA-256 {approval['sha256']}</span></div>"
        )
    else:
        status = ("<div class='status draft'>DRAFT. Not for circulation. "
                  "Approve with --approve \"Name\" after review.</div>")
    return (
        "<!doctype html><html lang='en-GB'><head><meta charset='utf-8'>"
        "<title>Pipeline review pack</title>"
        f"<style>{STYLE}</style></head><body>{status}{content}</body></html>"
    )


def build_pack(approve: str | None = None, out_dir: Path = OUTPUTS,
               df: pd.DataFrame | None = None) -> dict:
    """Build the pack. Approval writes a log line with the content hash."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_data(out_dir) if df is None else df
    b = bridge(df)
    draft = draft_what_changed(b)
    content = render_content(b, draft)
    digest = content_hash(content)

    approval = None
    if approve is not None:
        name = approve.strip()
        if not name:
            raise ValueError("Approval needs a name")
        approval = {
            "name": name,
            "approved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "sha256": digest,
            "file": PACK_FILE,
        }
        with open(out_dir / APPROVAL_LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps(approval) + "\n")

    path = out_dir / PACK_FILE
    path.write_text(render_pack(content, approval), encoding="utf-8")
    return {
        "bridge": b,
        "draft": draft,
        "content": content,
        "sha256": digest,
        "status": "APPROVED" if approval else "DRAFT",
        "approval": approval,
        "path": path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the weekly pipeline review pack.")
    parser.add_argument("--approve", metavar="NAME", help="Approve the pack under this name")
    parser.add_argument("--out-dir", default=str(OUTPUTS))
    args = parser.parse_args(argv)
    try:
        out = build_pack(args.approve, Path(args.out_dir))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    d = out["draft"]
    print(d["headline"])
    print(d["biggest_drag_text"])
    print(d["biggest_lift_text"])
    for line in d["shared_text"]:
        print(line)
    print(f"Status: {out['status']}. SHA-256 {out['sha256']}")
    print(f"Pack written to {out['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
