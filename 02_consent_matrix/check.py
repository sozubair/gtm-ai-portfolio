#!/usr/bin/env python3
"""Consent checker for outbound plays across six EMEA markets.

Two modes:
    lead    Can I contact this lead this way, and why?
    matrix  Class each play as "Run once for EMEA" or "Localise".

Rules live in rules.json. This file only applies them. Not legal advice.

Usage:
    python 02_consent_matrix/check.py lead --country DE --channel email --recipient company
    python 02_consent_matrix/check.py matrix
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUTS = ROOT / "outputs"
RULES_PATH = HERE / "rules.json"
PLAYS_PATH = HERE / "plays.json"

CHANNELS = ("email", "call")
RECIPIENTS = ("company", "sole_trader")
BASES = ("opt_out", "consent", "presumed_consent")
RUN_ONCE = "Run once for EMEA"
LOCALISE = "Localise"


def load_rules(path: Path = RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_plays(path: Path = PLAYS_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["plays"]


def rule_key(channel: str, recipient: str) -> str:
    if channel not in CHANNELS:
        raise ValueError(f"Unknown channel '{channel}'. Use one of {CHANNELS}.")
    if recipient not in RECIPIENTS:
        raise ValueError(f"Unknown recipient '{recipient}'. Use one of {RECIPIENTS}.")
    return f"{channel}_{recipient}"


def country_rules(rules: dict, country: str) -> dict:
    try:
        return rules["countries"][country]
    except KeyError:
        known = ", ".join(rules["countries"])
        raise ValueError(f"Unknown country '{country}'. Use one of {known}.") from None


def check(rules: dict, country: str, channel: str, recipient: str, *,
          consent: bool = False, existing_customer: bool = False, objected: bool = False,
          on_screening_list: bool = False, mobile: bool = False,
          presumed_interest: bool = False) -> dict:
    """Decide one lead. Outcome is 'yes', 'no' or 'review', with reasons."""
    market = country_rules(rules, country)
    rule = market["rules"][rule_key(channel, recipient)]
    basis = rule["basis"]
    if mobile and "mobile_basis" in rule:
        basis = rule["mobile_basis"]

    decision = {
        "country": country,
        "channel": channel,
        "recipient": recipient,
        "basis": basis,
        "rule": rule["summary"],
        "law": market["law"],
        "regulator": market["regulator"],
        "sources": market["sources"],
        "verification": market["verification"],
        "reasons": [],
    }
    reasons = decision["reasons"]

    def done(outcome: str) -> dict:
        decision["outcome"] = outcome
        return decision

    # An objection overrides every basis, including consent.
    if objected:
        reasons.append("The lead has objected. An objection overrides every other basis.")
        return done("no")

    if on_screening_list and rule["screening"] and not consent:
        lists = " or ".join(rule["screening"])
        reasons.append(f"The number is on {lists}. Do not contact without specific consent.")
        return done("no")

    if basis == "opt_out":
        reasons.append("Allowed without consent. Identify yourself and offer an opt out.")
        if rule["screening"]:
            reasons.append(f"Screen against {' and '.join(rule['screening'])} before contact.")
        return done("yes")

    if consent:
        reasons.append("The lead gave prior consent. Keep a record of it.")
        return done("yes")

    if basis == "consent":
        if existing_customer and rule["existing_customer_exception"]:
            reasons.append(f"Existing customer exception applies. {market['existing_customer']}")
            return done("yes")
        reasons.append("Prior consent is needed and none is recorded.")
        if rule["existing_customer_exception"]:
            reasons.append("An existing customer exception exists but does not apply to this lead.")
        return done("no")

    # presumed_consent
    if presumed_interest:
        reasons.append("Presumed consent needs a concrete, documented business reason. "
                       "Get a legal review before the call.")
        return done("review")
    reasons.append("Presumed consent needs a concrete, documented business reason and none is recorded.")
    return done("no")


def matrix(rules: dict, plays: list[dict]) -> list[dict]:
    """Run each play through every country and class it."""
    rows = []
    for play in plays:
        flags = {k: bool(play.get(k, False)) for k in
                 ("consent", "existing_customer", "mobile", "presumed_interest")}
        outcomes = {
            country: check(rules, country, play["channel"], play["recipient"], **flags)
            for country in rules["countries"]
        }
        blocked = [c for c, d in outcomes.items() if d["outcome"] != "yes"]
        rows.append({
            "play": play["name"],
            "channel": play["channel"],
            "recipient": play["recipient"],
            "outcomes": {c: d["outcome"] for c, d in outcomes.items()},
            "class": RUN_ONCE if not blocked else LOCALISE,
            "localise_in": blocked,
        })
    return rows


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
OUTCOME_WORDS = {"yes": "Yes", "no": "No", "review": "Review"}


def render_lead(decision: dict) -> str:
    v = decision["verification"]
    checked = v["checked_on"] or "not yet"
    lines = [
        f"# Consent check: {decision['country']}, {decision['channel']}, "
        f"{decision['recipient'].replace('_', ' ')}",
        "",
        f"**Answer: {OUTCOME_WORDS[decision['outcome']]}.**",
        "",
        "## Why",
        "",
        *[f"- {r}" for r in decision["reasons"]],
        "",
        "## Rule",
        "",
        f"- Law: {decision['law']}",
        f"- Regulator: {decision['regulator']}",
        f"- Basis: {decision['basis'].replace('_', ' ')}",
        f"- Rule: {decision['rule']}",
        f"- Verification: {v['level']} (checked {checked})",
        *[f"- Source: [{s['title']}]({s['url']})" for s in decision["sources"]],
        "",
        "Not legal advice.",
        "",
    ]
    return "\n".join(lines)


def render_matrix(rules: dict, rows: list[dict]) -> str:
    countries = list(rules["countries"])
    run_once = sum(r["class"] == RUN_ONCE for r in rows)
    lines = [
        "# Consent matrix",
        "",
        f"**Answer.** {run_once} of {len(rows)} plays can run once for EMEA. "
        f"{len(rows) - run_once} need local rules.",
        "",
        "| Play | " + " | ".join(countries) + " | Class |",
        "| --- | " + " | ".join(":---:" for _ in countries) + " | --- |",
    ]
    for r in rows:
        cells = " | ".join(OUTCOME_WORDS[r["outcomes"][c]] for c in countries)
        cls = r["class"] if not r["localise_in"] else f"{r['class']} ({', '.join(r['localise_in'])})"
        lines.append(f"| {r['play']} | {cells} | {cls} |")
    lines += ["", "## Verification", "", "| Market | Level | Checked |", "| --- | --- | --- |"]
    for code, market in rules["countries"].items():
        v = market["verification"]
        lines.append(f"| {market['name']} | {v['level']} | {v['checked_on'] or 'not yet'} |")
    lines += ["", "Not legal advice. Check each source before you rely on a rule.", ""]
    return "\n".join(lines)


def write(text: str, name: str, out_dir: Path = OUTPUTS) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(text, encoding="utf-8")
    return path


def run_matrix(rules_path: Path = RULES_PATH, plays_path: Path = PLAYS_PATH,
               out_dir: Path = OUTPUTS) -> dict:
    rules = load_rules(rules_path)
    rows = matrix(rules, load_plays(plays_path))
    md = write(render_matrix(rules, rows), "consent_matrix.md", out_dir)
    js = write(json.dumps(rows, indent=2, ensure_ascii=False), "consent_matrix.json", out_dir)
    return {"rules": rules, "rows": rows, "markdown_path": md, "json_path": js}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check outbound consent rules.")
    parser.add_argument("--rules", default=str(RULES_PATH))
    parser.add_argument("--out-dir", default=str(OUTPUTS))
    sub = parser.add_subparsers(dest="mode", required=True)

    lead = sub.add_parser("lead", help="Check one lead")
    lead.add_argument("--country", required=True)
    lead.add_argument("--channel", required=True, choices=CHANNELS)
    lead.add_argument("--recipient", required=True, choices=RECIPIENTS)
    for flag in ("consent", "existing-customer", "objected", "on-screening-list",
                 "mobile", "presumed-interest"):
        lead.add_argument(f"--{flag}", action="store_true")

    mat = sub.add_parser("matrix", help="Class every play")
    mat.add_argument("--plays", default=str(PLAYS_PATH))

    args = parser.parse_args(argv)
    try:
        if args.mode == "lead":
            rules = load_rules(Path(args.rules))
            decision = check(
                rules, args.country.upper(), args.channel, args.recipient,
                consent=args.consent, existing_customer=args.existing_customer,
                objected=args.objected, on_screening_list=args.on_screening_list,
                mobile=args.mobile, presumed_interest=args.presumed_interest,
            )
            text = render_lead(decision)
            path = write(text, "consent_check.md", Path(args.out_dir))
            print(text)
        else:
            out = run_matrix(Path(args.rules), Path(args.plays), Path(args.out_dir))
            path = out["markdown_path"]
            print(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
