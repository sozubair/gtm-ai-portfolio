import itertools
import re
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import check

RULES = check.load_rules()
FLAG_NAMES = ("consent", "existing_customer", "on_screening_list", "mobile", "presumed_interest")


def every_lead():
    for country in RULES["countries"]:
        for channel, recipient in itertools.product(check.CHANNELS, check.RECIPIENTS):
            yield country, channel, recipient


class ObjectionTests(unittest.TestCase):
    def test_an_objection_always_blocks(self):
        for country, channel, recipient in every_lead():
            for values in itertools.product([False, True], repeat=len(FLAG_NAMES)):
                flags = dict(zip(FLAG_NAMES, values))
                with self.subTest(country=country, channel=channel, recipient=recipient, **flags):
                    d = check.check(RULES, country, channel, recipient, objected=True, **flags)
                    self.assertEqual(d["outcome"], "no")


class RulesMatchTests(unittest.TestCase):
    def test_each_country_rule_matches_rules_json(self):
        for country, channel, recipient in every_lead():
            market = RULES["countries"][country]
            rule = market["rules"][f"{channel}_{recipient}"]
            with self.subTest(country=country, channel=channel, recipient=recipient):
                d = check.check(RULES, country, channel, recipient)
                self.assertEqual(d["basis"], rule["basis"])
                self.assertEqual(d["rule"], rule["summary"])
                self.assertEqual(d["law"], market["law"])
                expected = "yes" if rule["basis"] == "opt_out" else "no"
                self.assertEqual(d["outcome"], expected)
                if "mobile_basis" in rule:
                    m = check.check(RULES, country, channel, recipient, mobile=True)
                    self.assertEqual(m["basis"], rule["mobile_basis"])

    def test_rules_json_is_complete(self):
        expected = {"UK", "IE", "DE", "FR", "NL", "ES"}
        self.assertEqual(set(RULES["countries"]), expected)
        levels = set(RULES["verification_levels"])
        for code, market in RULES["countries"].items():
            with self.subTest(country=code):
                for field in ("law", "regulator", "existing_customer", "sources", "verification"):
                    self.assertTrue(market[field], field)
                for source in market["sources"]:
                    self.assertTrue(source["url"].startswith("https://"))
                v = market["verification"]
                self.assertIn(v["level"], levels)
                if v["level"] != "unverified":
                    self.assertRegex(v["checked_on"] or "", r"^\d{4}-\d{2}-\d{2}$")
                for key in ("email_company", "email_sole_trader", "call_company", "call_sole_trader"):
                    self.assertIn(market["rules"][key]["basis"], check.BASES)


class BehaviourTests(unittest.TestCase):
    def test_existing_customer_exception(self):
        self.assertEqual(check.check(RULES, "UK", "email", "sole_trader")["outcome"], "no")
        d = check.check(RULES, "UK", "email", "sole_trader", existing_customer=True)
        self.assertEqual(d["outcome"], "yes")

    def test_screening_list_blocks_opt_out_call(self):
        d = check.check(RULES, "UK", "call", "company", on_screening_list=True)
        self.assertEqual(d["outcome"], "no")

    def test_presumed_interest_needs_review(self):
        d = check.check(RULES, "DE", "call", "company", presumed_interest=True)
        self.assertEqual(d["outcome"], "review")

    def test_matrix_classes_plays(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = check.run_matrix(out_dir=Path(tmp))
            classes = {r["play"]: r for r in out["rows"]}
            self.assertEqual(classes["Email to companies that opted in"]["class"], check.RUN_ONCE)
            cold = classes["Cold email to target companies"]
            self.assertEqual(cold["class"], check.LOCALISE)
            self.assertIn("DE", cold["localise_in"])
            self.assertTrue(out["markdown_path"].exists())


if __name__ == "__main__":
    unittest.main()
