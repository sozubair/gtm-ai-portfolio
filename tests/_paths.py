"""Put each tool folder on sys.path so tests can import the modules."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in ("01_measurement_planner", "02_consent_matrix", "03_review_pack", "showcase"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
