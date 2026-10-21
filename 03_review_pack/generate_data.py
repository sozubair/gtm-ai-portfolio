#!/usr/bin/env python3
"""Generate 8 weeks of fictional pipeline data with a planted week 8 story.

Regions: UKI, DACH, France, Nordics. Segments: Enterprise, Mid market.
Columns: week, region, segment, leads, opportunities, pipeline_gbp, days_to_opportunity.

Planted story in week 8:
    DACH conversion falls by about 40% in both segments.
    UKI Mid market lead volume rises by about 35%.

Usage:
    python 03_review_pack/generate_data.py [--seed 8]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
DATA_FILE = "pipeline_weekly.csv"

WEEKS = 8
REGIONS = ("UKI", "DACH", "France", "Nordics")
SEGMENTS = ("Enterprise", "Mid market")
WEEKLY_TARGET_OPPORTUNITIES = 215

BASE_LEADS = {
    ("UKI", "Enterprise"): 120, ("UKI", "Mid market"): 400,
    ("DACH", "Enterprise"): 100, ("DACH", "Mid market"): 350,
    ("France", "Enterprise"): 80, ("France", "Mid market"): 260,
    ("Nordics", "Enterprise"): 60, ("Nordics", "Mid market"): 180,
}
BASE_CONVERSION = {"Enterprise": 0.18, "Mid market": 0.12}
AVERAGE_DEAL_GBP = {"Enterprise": 42000, "Mid market": 11000}
DAYS_TO_OPPORTUNITY = {"Enterprise": 21.0, "Mid market": 12.0}

STORY_WEEK = 8
DACH_CONVERSION_FACTOR = 0.60   # conversion falls about 40%
UKI_MID_MARKET_LEAD_FACTOR = 1.35  # lead volume rises about 35%


def generate(seed: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for week in range(1, WEEKS + 1):
        for region in REGIONS:
            for segment in SEGMENTS:
                lead_factor, conv_factor = 1.0, 1.0
                if week == STORY_WEEK and region == "DACH":
                    conv_factor = DACH_CONVERSION_FACTOR
                if week == STORY_WEEK and (region, segment) == ("UKI", "Mid market"):
                    lead_factor = UKI_MID_MARKET_LEAD_FACTOR

                leads = round(BASE_LEADS[(region, segment)] * lead_factor * rng.normal(1, 0.03))
                conversion = BASE_CONVERSION[segment] * conv_factor * rng.normal(1, 0.03)
                opportunities = round(leads * conversion)
                pipeline = opportunities * AVERAGE_DEAL_GBP[segment] * rng.normal(1, 0.04)
                days = DAYS_TO_OPPORTUNITY[segment] * rng.normal(1, 0.06)
                rows.append({
                    "week": week,
                    "region": region,
                    "segment": segment,
                    "leads": int(leads),
                    "opportunities": int(opportunities),
                    "pipeline_gbp": int(round(pipeline, -2)),
                    "days_to_opportunity": round(float(days), 1),
                })
    return pd.DataFrame(rows)


def write(df: pd.DataFrame, out_dir: Path = OUTPUTS) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / DATA_FILE
    df.to_csv(path, index=False)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate fictional weekly pipeline data.")
    parser.add_argument("--seed", type=int, default=8)
    parser.add_argument("--out-dir", default=str(OUTPUTS))
    args = parser.parse_args(argv)
    path = write(generate(args.seed), Path(args.out_dir))
    print(f"Fictional pipeline data written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
