#!/usr/bin/env python3
"""Measurement planner.

Reads a JSON brief, sizes a holdout test, chooses between a randomised
holdout and a staged rollout, simulates one run and writes a markdown report
to /outputs. Every number in the report is computed here.

Usage:
    python 01_measurement_planner/planner.py BRIEF.json [--simulate-uplift 0.30] [--seed 7]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
NORMAL = NormalDist()
CONFIDENCE = 0.95
CURRENCY_SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}

# Field name -> accepted types. Ints are accepted wherever floats are.
REQUIRED_FIELDS: dict[str, tuple[type, ...]] = {
    "program": (str,),
    "unit": (str,),
    "primary_metric": (str,),
    "eligible_units": (int,),
    "baseline_rate": (int, float),
    "min_detectable_uplift": (int, float),
    "holdout_share": (int, float),
    "alpha": (int, float),
    "power": (int, float),
    "outcome_window_days": (int,),
    "average_outcome_value": (int, float),
    "touch_rate_of_converters": (int, float),
    "guardrails": (list,),
}


# --------------------------------------------------------------------------
# Brief
# --------------------------------------------------------------------------
def validate_brief(brief: dict) -> dict:
    """Check the brief has every field with a sensible value. Returns the brief."""
    missing = [k for k in REQUIRED_FIELDS if k not in brief]
    if missing:
        raise ValueError(f"Brief is missing fields: {', '.join(missing)}")
    for key, types in REQUIRED_FIELDS.items():
        value = brief[key]
        if isinstance(value, bool) or not isinstance(value, types):
            raise ValueError(f"Field '{key}' has the wrong type: {type(value).__name__}")

    checks = [
        (brief["eligible_units"] > 0, "eligible_units must be above 0"),
        (0 < brief["baseline_rate"] < 1, "baseline_rate must be between 0 and 1"),
        (brief["min_detectable_uplift"] > 0, "min_detectable_uplift must be above 0"),
        (brief["baseline_rate"] * (1 + brief["min_detectable_uplift"]) < 1,
         "baseline_rate with the uplift must stay below 1"),
        (0 < brief["holdout_share"] < 1, "holdout_share must be between 0 and 1"),
        (0 < brief["alpha"] < 1, "alpha must be between 0 and 1"),
        (0 < brief["power"] < 1, "power must be between 0 and 1"),
        (brief["outcome_window_days"] > 0, "outcome_window_days must be above 0"),
        (brief["average_outcome_value"] >= 0, "average_outcome_value cannot be negative"),
        (0 <= brief["touch_rate_of_converters"] <= 1,
         "touch_rate_of_converters must be between 0 and 1"),
    ]
    for ok, message in checks:
        if not ok:
            raise ValueError(message)
    brief.setdefault("currency", "GBP")
    return brief


def load_brief(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return validate_brief(json.load(handle))


# --------------------------------------------------------------------------
# Sample size and power
# --------------------------------------------------------------------------
def _z(alpha: float, power: float) -> tuple[float, float]:
    """Critical values for a test with both tails, and for the power."""
    return NORMAL.inv_cdf(1 - alpha / 2), NORMAL.inv_cdf(power)


def per_arm_equal_split(p1: float, p2: float, alpha: float, power: float) -> float:
    """Units per arm for a two proportion z test with an even split.

    Uses the pooled variance under the null and the separate variances under
    the alternative (the standard normal approximation).
    """
    if p1 == p2:
        raise ValueError("The two rates must differ")
    z_alpha, z_beta = _z(alpha, power)
    p_bar = (p1 + p2) / 2
    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
        + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return numerator / (p1 - p2) ** 2


def split_factor(holdout_share: float) -> float:
    """How many more units an uneven split needs than an even one.

    The variance of a difference scales with 1/n_t + 1/n_c. With a total N
    and a holdout share h this is (1 / (h (1 - h))) / N. An even split gives
    4 / N, so the factor is 1 / (4 h (1 - h)). An 80/20 split gives 1.5625.
    """
    h = holdout_share
    return 1 / (4 * h * (1 - h))


def _total_needed_raw(p1: float, uplift: float, alpha: float, power: float, h: float) -> float:
    p2 = p1 * (1 + uplift)
    return 2 * per_arm_equal_split(p1, p2, alpha, power) * split_factor(h)


def sample_size(p1: float, uplift: float, alpha: float, power: float, holdout_share: float) -> dict:
    """Units needed to detect a relative uplift at the given split."""
    p2 = p1 * (1 + uplift)
    n_equal = per_arm_equal_split(p1, p2, alpha, power)
    factor = split_factor(holdout_share)
    total_raw = 2 * n_equal * factor
    treatment = math.ceil(total_raw * (1 - holdout_share) - 1e-9)
    holdout = math.ceil(total_raw * holdout_share - 1e-9)
    return {
        "baseline_rate": p1,
        "treated_rate": p2,
        "per_arm_equal": math.ceil(n_equal - 1e-9),
        "per_arm_equal_raw": n_equal,
        "split_factor": factor,
        "treatment": treatment,
        "holdout": holdout,
        "total": treatment + holdout,
    }


def achieved_power(p1: float, uplift: float, alpha: float, n_total: int, holdout_share: float) -> float:
    """Power of the test when every one of n_total units is used."""
    p2 = p1 * (1 + uplift)
    z_alpha, _ = _z(alpha, 0.5)
    n_equivalent = n_total / (2 * split_factor(holdout_share))
    p_bar = (p1 + p2) / 2
    z = (
        abs(p2 - p1) * math.sqrt(n_equivalent) - z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
    ) / math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return NORMAL.cdf(z)


def min_detectable_uplift(p1: float, alpha: float, power: float, holdout_share: float,
                          n_total: int) -> float | None:
    """Smallest relative uplift that n_total units can detect. None if no uplift can."""
    upper = (1 / p1 - 1) * 0.999  # the treated rate must stay below 1
    if _total_needed_raw(p1, upper, alpha, power, holdout_share) > n_total:
        return None
    lower = 0.0
    for _ in range(100):
        mid = (lower + upper) / 2
        if _total_needed_raw(p1, mid, alpha, power, holdout_share) <= n_total:
            upper = mid
        else:
            lower = mid
    return upper


def split_units(n_total: int, holdout_share: float) -> tuple[int, int]:
    """Treatment and holdout counts when every unit is used."""
    holdout = round(n_total * holdout_share)
    return n_total - holdout, holdout


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------
def plan(brief: dict) -> dict:
    p1 = brief["baseline_rate"]
    uplift = brief["min_detectable_uplift"]
    alpha, power, h = brief["alpha"], brief["power"], brief["holdout_share"]
    n = brief["eligible_units"]

    need = sample_size(p1, uplift, alpha, power, h)
    enough = need["total"] <= n
    treatment_n, holdout_n = split_units(n, h)
    return {
        "need": need,
        "enough_units": enough,
        "design": "randomised_holdout" if enough else "staged_rollout",
        "treatment_n": treatment_n,
        "holdout_n": holdout_n,
        "power_with_all_units": achieved_power(p1, uplift, alpha, n, h),
        "min_detectable_uplift": min_detectable_uplift(p1, alpha, power, h, n),
        "shortfall": max(0, need["total"] - n),
    }


# --------------------------------------------------------------------------
# Analysis and simulation
# --------------------------------------------------------------------------
def analyse(x_t: int, n_t: int, x_c: int, n_c: int) -> dict:
    """Compare treated and held out conversion counts.

    Relative uplift interval: log risk ratio. Rate difference interval:
    unpooled normal approximation. p value: pooled z test, both tails.
    """
    z = NORMAL.inv_cdf(1 - (1 - CONFIDENCE) / 2)
    p_t, p_c = x_t / n_t, x_c / n_c

    # Continuity correction only when a cell is empty.
    if x_t == 0 or x_c == 0:
        a_t, a_c, m_t, m_c = x_t + 0.5, x_c + 0.5, n_t + 1, n_c + 1
    else:
        a_t, a_c, m_t, m_c = x_t, x_c, n_t, n_c
    ratio = (a_t / m_t) / (a_c / m_c)
    se_log = math.sqrt(1 / a_t - 1 / m_t + 1 / a_c - 1 / m_c)
    uplift = ratio - 1
    uplift_low = math.exp(math.log(ratio) - z * se_log) - 1
    uplift_high = math.exp(math.log(ratio) + z * se_log) - 1

    diff = p_t - p_c
    se_diff = math.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)

    pooled = (x_t + x_c) / (n_t + n_c)
    se_null = math.sqrt(pooled * (1 - pooled) * (1 / n_t + 1 / n_c))
    z_stat = diff / se_null if se_null > 0 else 0.0
    p_value = 2 * (1 - NORMAL.cdf(abs(z_stat)))

    return {
        "rate_treated": p_t,
        "rate_holdout": p_c,
        "uplift": uplift,
        "uplift_low": uplift_low,
        "uplift_high": uplift_high,
        "diff": diff,
        "diff_low": diff - z * se_diff,
        "diff_high": diff + z * se_diff,
        "z": z_stat,
        "p_value": p_value,
    }


def simulate(brief: dict, true_uplift: float, seed: int = 7) -> dict:
    """Simulate one run that uses every eligible unit, then analyse it."""
    p1 = brief["baseline_rate"]
    p2 = min(p1 * (1 + true_uplift), 1.0)
    n_t, n_c = split_units(brief["eligible_units"], brief["holdout_share"])

    rng = np.random.default_rng(seed)
    x_c = int(rng.binomial(n_c, p1))
    x_t = int(rng.binomial(n_t, p2))
    result = analyse(x_t, n_t, x_c, n_c)

    value = brief["average_outcome_value"]
    inc = result["diff"] * n_t
    inc_low = result["diff_low"] * n_t
    inc_high = result["diff_high"] * n_t
    sourced = x_t * brief["touch_rate_of_converters"]
    inc_value = inc * value
    result.update({
        "true_uplift": true_uplift,
        "seed": seed,
        "treatment_n": n_t,
        "holdout_n": n_c,
        "conversions_treated": x_t,
        "conversions_holdout": x_c,
        "incremental_conversions": inc,
        "incremental_conversions_low": inc_low,
        "incremental_conversions_high": inc_high,
        "incremental_value": inc_value,
        "incremental_value_low": inc_low * value,
        "incremental_value_high": inc_high * value,
        "sourced_conversions": sourced,
        "sourced_value": sourced * value,
        "sourced_to_measured": (sourced * value / inc_value) if inc_value > 0 else None,
        "significant": result["p_value"] < brief["alpha"],
        "detected": result["p_value"] < brief["alpha"] and result["uplift"] > 0,
    })
    return result


def detection_rate(brief: dict, true_uplift: float, seeds) -> float:
    """Share of simulated runs that declare a positive, significant uplift."""
    seeds = list(seeds)
    hits = sum(simulate(brief, true_uplift, seed)["detected"] for seed in seeds)
    return hits / len(seeds)


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
MINUS = "\u2212"


def fmt_int(x: float) -> str:
    return f"{round(x):,}".replace("-", MINUS)


def fmt_pct(x: float, dp: int = 1, signed: bool = False) -> str:
    text = f"{abs(x) * 100:.{dp}f}%"
    if signed:
        return ("+" if x >= 0 else MINUS) + text
    return (MINUS if x < 0 else "") + text


def fmt_money(x: float, currency: str = "GBP") -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    sign = MINUS if x < 0 else ""
    return f"{sign}{symbol}{abs(round(x)):,}"


def fmt_p(p: float) -> str:
    return "below 0.001" if p < 0.001 else f"{p:.3f}"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def answer_sentence(brief: dict, result: dict, sim: dict | None) -> str:
    need = result["need"]
    unit = brief["unit"]
    target = fmt_pct(brief["min_detectable_uplift"], 0, signed=True)
    cur = brief["currency"]
    if result["design"] == "randomised_holdout":
        text = (
            f"Run a randomised holdout. The {fmt_int(brief['eligible_units'])} eligible {unit}s "
            f"are enough to detect a {target} uplift, which needs {fmt_int(need['total'])}."
        )
        if sim:
            text += (
                f" In the simulated run the measured uplift was {fmt_pct(sim['uplift'], 1, True)} "
                f"(95% interval {fmt_pct(sim['uplift_low'], 1, True)} to "
                f"{fmt_pct(sim['uplift_high'], 1, True)}), worth "
                f"{fmt_money(sim['incremental_value'], cur)} against a sourced claim of "
                f"{fmt_money(sim['sourced_value'], cur)}."
            )
        return text
    mde = result["min_detectable_uplift"]
    mde_text = fmt_pct(mde, 0, signed=True) if mde is not None else "no uplift at all"
    return (
        f"Do not run a holdout. Detecting a {target} uplift needs {fmt_int(need['total'])} "
        f"{unit}s and only {fmt_int(brief['eligible_units'])} are eligible. Use a staged rollout. "
        f"The smallest uplift this population can detect is {mde_text}."
    )


def render_report(brief: dict, result: dict, sim: dict | None) -> str:
    need = result["need"]
    cur = brief["currency"]
    unit = brief["unit"]
    h = brief["holdout_share"]
    treat_pct, hold_pct = round((1 - h) * 100), round(h * 100)
    mde = result["min_detectable_uplift"]
    mde_text = fmt_pct(mde, 1, signed=True) if mde is not None else "none"

    lines: list[str] = []
    add = lines.append
    add(f"# Measurement plan: {brief['program']}")
    add("")
    add(f"**Answer.** {answer_sentence(brief, result, sim)}")
    add("")
    add("All data in this report is fictional.")
    add("")

    add("## Brief")
    add("")
    add("| Item | Value |")
    add("| --- | --- |")
    add(f"| Programme | {brief['program']} |")
    add(f"| Unit | {unit} |")
    add(f"| Primary metric | {brief['primary_metric']} |")
    add(f"| Eligible units | {fmt_int(brief['eligible_units'])} |")
    add(f"| Baseline rate | {fmt_pct(brief['baseline_rate'])} |")
    add(f"| Target uplift (relative) | {fmt_pct(brief['min_detectable_uplift'], 1, True)} |")
    add(f"| Treated rate at target | {fmt_pct(need['treated_rate'], 2)} |")
    add(f"| Split (treated / held out) | {treat_pct} / {hold_pct} |")
    add(f"| Alpha | {brief['alpha']} |")
    add(f"| Power | {fmt_pct(brief['power'], 0)} |")
    add(f"| Outcome window | {brief['outcome_window_days']} days |")
    add(f"| Average outcome value | {fmt_money(brief['average_outcome_value'], cur)} |")
    add(f"| Share of converters touched | {fmt_pct(brief['touch_rate_of_converters'], 0)} |")
    add("")

    add("## Sample size")
    add("")
    add(f"- Test: difference between two proportions, both tails, alpha {brief['alpha']}, "
        f"power {fmt_pct(brief['power'], 0)}.")
    add(f"- {unit.capitalize()}s per arm with an even split: {fmt_int(need['per_arm_equal'])}.")
    add(f"- Adjustment for the {treat_pct}/{hold_pct} split: {need['split_factor']:.4f}x, "
        f"from 1 / (4 × h × (1 {MINUS} h)).")
    add(f"- Total needed: {fmt_int(need['total'])} ({fmt_int(need['treatment'])} treated, "
        f"{fmt_int(need['holdout'])} held out).")
    add(f"- Eligible: {fmt_int(brief['eligible_units'])}. "
        + ("That is enough." if result["enough_units"]
           else f"That is {fmt_int(result['shortfall'])} short."))
    add(f"- Power if every eligible {unit} is used: {fmt_pct(result['power_with_all_units'], 1)}.")
    add(f"- Smallest uplift {fmt_int(brief['eligible_units'])} {unit}s can detect: {mde_text}.")
    add("")

    add("## Design")
    add("")
    if result["design"] == "randomised_holdout":
        add("**Randomised holdout.**")
        add("")
        add(f"- Randomise at {unit} level before any outreach.")
        add(f"- Treat {fmt_int(result['treatment_n'])} {unit}s. Hold out "
            f"{fmt_int(result['holdout_n'])}. The holdout gets no programme contact.")
        add(f"- Measure {brief['primary_metric'].lower()} for both groups over "
            f"{brief['outcome_window_days']} days.")
        add("- Fix the metric, the test and the alpha before launch. Read the result once, "
            "at the end of the window.")
    else:
        add("**Staged rollout.** A holdout this small cannot give a firm answer.")
        add("")
        add(f"- Split the {fmt_int(brief['eligible_units'])} {unit}s into waves at random.")
        add("- Launch the waves in a random order.")
        add("- Compare live waves with waves not yet live over the same window.")
        add(f"- Treat any measured uplift below {mde_text} as directional only.")
        add("- If a firm answer is needed, pick an outcome with a higher base rate.")
    add("")

    if sim:
        add("## Simulated run")
        add("")
        intro = (f"Fictional run with a true uplift of {fmt_pct(sim['true_uplift'], 1, True)} "
                 f"(seed {sim['seed']}).")
        if result["design"] != "randomised_holdout":
            intro += (" It shows what a holdout of this size would report. "
                      "Read it as a picture of the noise.")
        add(intro)
        add("")
        add("| Group | Units | Conversions | Rate |")
        add("| --- | ---: | ---: | ---: |")
        add(f"| Treated | {fmt_int(sim['treatment_n'])} | {fmt_int(sim['conversions_treated'])} | "
            f"{fmt_pct(sim['rate_treated'], 2)} |")
        add(f"| Held out | {fmt_int(sim['holdout_n'])} | {fmt_int(sim['conversions_holdout'])} | "
            f"{fmt_pct(sim['rate_holdout'], 2)} |")
        add("")
        add("| Result | Value |")
        add("| --- | --- |")
        add(f"| Measured uplift | {fmt_pct(sim['uplift'], 1, True)} "
            f"(95% interval {fmt_pct(sim['uplift_low'], 1, True)} to "
            f"{fmt_pct(sim['uplift_high'], 1, True)}) |")
        add(f"| p value | {fmt_p(sim['p_value'])} |")
        add(f"| Significant at alpha {brief['alpha']} | {'Yes' if sim['significant'] else 'No'} |")
        add(f"| Incremental conversions | {fmt_int(sim['incremental_conversions'])} "
            f"(range {fmt_int(sim['incremental_conversions_low'])} to "
            f"{fmt_int(sim['incremental_conversions_high'])}) |")
        add(f"| Incremental value | {fmt_money(sim['incremental_value'], cur)} "
            f"(range {fmt_money(sim['incremental_value_low'], cur)} to "
            f"{fmt_money(sim['incremental_value_high'], cur)}) |")
        add(f"| Sourced claim | {fmt_int(sim['sourced_conversions'])} conversions worth "
            f"{fmt_money(sim['sourced_value'], cur)} |")
        ratio = sim["sourced_to_measured"]
        add(f"| Sourced claim against measured value | "
            f"{f'{ratio:.1f}x' if ratio is not None else 'no measured value to compare'} |")
        add("")
        add("## How to read this")
        add("")
        add("- The sourced count credits every converter the programme touched. "
            "It includes accounts that would have converted anyway.")
        add("- The holdout shows what happens without the programme. The gap between the two rates is the effect.")
        add("- The interval is the range of uplifts the data supports. If it includes zero, "
            "the run did not prove an effect.")
        add("- The value range comes from the interval on the rate difference, times the average outcome value.")
        add("")

    add("## Guardrails")
    add("")
    for item in brief["guardrails"]:
        add(f"- {item}")
    add("")
    add("## Method notes")
    add("")
    add("- Sample size uses the normal approximation for two proportions. "
        "The null uses the pooled variance.")
    add(f"- An uneven split scales the total by 1 / (4h(1 {MINUS} h)). "
        "An 80/20 split needs 1.5625x the units of an even split.")
    add("- The uplift interval comes from the log risk ratio.")
    add("- The p value comes from a pooled z test with both tails.")
    add("")
    return "\n".join(lines)


def write_report(brief: dict, result: dict, sim: dict | None, out_dir: Path = OUTPUTS) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"measurement_plan_{slug(brief['program'])}.md"
    path.write_text(render_report(brief, result, sim), encoding="utf-8")
    return path


def run(brief_path: str | Path, simulate_uplift: float | None = None, seed: int = 7,
        out_dir: Path = OUTPUTS) -> dict:
    """Load, plan, simulate and write. Returns everything the showcase needs."""
    brief = load_brief(brief_path)
    result = plan(brief)
    uplift = brief["min_detectable_uplift"] if simulate_uplift is None else simulate_uplift
    sim = simulate(brief, uplift, seed)
    path = write_report(brief, result, sim, out_dir)
    return {"brief": brief, "plan": result, "sim": sim, "report_path": path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan and simulate a holdout measurement.")
    parser.add_argument("brief", help="Path to a JSON brief")
    parser.add_argument("--simulate-uplift", type=float, default=None,
                        help="True relative uplift to simulate. Defaults to the brief's target.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for the simulation")
    parser.add_argument("--out-dir", default=str(OUTPUTS), help="Where to write the report")
    args = parser.parse_args(argv)

    try:
        out = run(args.brief, args.simulate_uplift, args.seed, Path(args.out_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(answer_sentence(out["brief"], out["plan"], out["sim"]))
    print(f"Report written to {out['report_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
