import tempfile
import unittest
from pathlib import Path

import _paths
import planner

BRIEFS = _paths.ROOT / "01_measurement_planner" / "briefs"


class SampleSizeTests(unittest.TestCase):
    def test_ten_vs_twelve_and_a_half_needs_about_2500_per_arm(self):
        need = planner.sample_size(0.10, 0.25, 0.05, 0.80, 0.5)
        self.assertAlmostEqual(need["treated_rate"], 0.125)
        self.assertGreaterEqual(need["per_arm_equal"], 2450)
        self.assertLessEqual(need["per_arm_equal"], 2550)
        self.assertEqual(need["treatment"], need["holdout"])

    def test_eighty_twenty_split_needs_1_5625x_the_units(self):
        self.assertAlmostEqual(planner.split_factor(0.2), 1.5625, places=12)
        even = planner.sample_size(0.10, 0.25, 0.05, 0.80, 0.5)
        uneven = planner.sample_size(0.10, 0.25, 0.05, 0.80, 0.2)
        self.assertAlmostEqual(uneven["total"] / even["total"], 1.5625, delta=0.001)

    def test_power_at_required_size_matches_target(self):
        need = planner.sample_size(0.10, 0.25, 0.05, 0.80, 0.2)
        power = planner.achieved_power(0.10, 0.25, 0.05, need["total"], 0.2)
        self.assertAlmostEqual(power, 0.80, delta=0.005)

    def test_min_detectable_uplift_inverts_sample_size(self):
        mde = planner.min_detectable_uplift(0.10, 0.05, 0.80, 0.2, 10000)
        need = planner.sample_size(0.10, mde, 0.05, 0.80, 0.2)
        self.assertLessEqual(need["total"], 10002)
        self.assertGreater(need["total"], 9990)


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.brief = planner.load_brief(BRIEFS / "workshops.json")

    def test_zero_uplift_gives_under_ten_percent_false_positives(self):
        hits = sum(planner.simulate(self.brief, 0.0, s)["significant"] for s in range(200))
        self.assertLess(hits / 200, 0.10)

    def test_twenty_five_percent_uplift_detected_over_eighty_percent(self):
        self.assertGreater(planner.detection_rate(self.brief, 0.25, range(200)), 0.80)

    def test_intervals_contain_estimates(self):
        sim = planner.simulate(self.brief, 0.30, 7)
        self.assertLessEqual(sim["incremental_value_low"], sim["incremental_value"])
        self.assertLessEqual(sim["incremental_value"], sim["incremental_value_high"])
        self.assertLess(sim["uplift_low"], sim["uplift"])
        self.assertLess(sim["uplift"], sim["uplift_high"])


class DesignTests(unittest.TestCase):
    def test_workshops_brief_gets_a_randomised_holdout(self):
        result = planner.plan(planner.load_brief(BRIEFS / "workshops.json"))
        self.assertEqual(result["design"], "randomised_holdout")

    def test_enterprise_brief_gets_a_staged_rollout(self):
        result = planner.plan(planner.load_brief(BRIEFS / "enterprise.json"))
        self.assertEqual(result["design"], "staged_rollout")
        self.assertFalse(result["enough_units"])
        self.assertGreater(result["min_detectable_uplift"], 0.25)

    def test_report_is_written_to_out_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = planner.run(BRIEFS / "workshops.json", 0.30, 7, Path(tmp))
            text = out["report_path"].read_text(encoding="utf-8")
            self.assertIn("Randomised holdout", text)
            self.assertIn("Sourced claim", text)

    def test_bad_brief_is_rejected(self):
        brief = planner.load_brief(BRIEFS / "workshops.json")
        brief["holdout_share"] = 1.5
        with self.assertRaises(ValueError):
            planner.validate_brief(brief)


if __name__ == "__main__":
    unittest.main()
