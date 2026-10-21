import json
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import generate_data
import review_pack


class DataTests(unittest.TestCase):
    def test_shape_and_story(self):
        df = generate_data.generate()
        self.assertEqual(len(df), 8 * 4 * 2)
        conv = df.assign(c=df.opportunities / df.leads)
        dach = conv[conv.region == "DACH"]
        base = dach[dach.week.between(4, 7)].c.mean()
        now = dach[dach.week == 8].c.mean()
        self.assertAlmostEqual(now / base - 1, -0.40, delta=0.08)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.b = review_pack.bridge(generate_data.generate())

    def test_bridge_finds_dach_as_biggest_drag(self):
        self.assertEqual(review_pack.biggest_drag(self.b), "DACH")

    def test_effects_add_up_to_the_change(self):
        for frame in (self.b["segments"], self.b["regions"]):
            total = frame["volume_effect"] + frame["conversion_effect"]
            for got, want in zip(total, frame["change"]):
                self.assertAlmostEqual(got, want, places=9)

    def test_uki_is_the_biggest_lift_and_mostly_volume(self):
        self.assertEqual(review_pack.biggest_lift(self.b), "UKI")
        uki = self.b["regions"].set_index("region").loc["UKI"]
        self.assertGreater(uki["volume_effect"], abs(uki["conversion_effect"]))

    def test_draft_flags_the_shared_dach_pattern(self):
        draft = review_pack.draft_what_changed(self.b)
        self.assertEqual(draft["shared_regions"], ["DACH"])
        self.assertIn("DACH conversion fell in every segment", " ".join(draft["shared_text"]))
        self.assertIn("Lead volume moved", draft["shared_text"][0])


class ApprovalTests(unittest.TestCase):
    def test_pack_is_draft_until_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            draft = review_pack.build_pack(out_dir=out_dir)
            text = draft["path"].read_text(encoding="utf-8")
            self.assertEqual(draft["status"], "DRAFT")
            self.assertIn("DRAFT", text)
            self.assertNotIn("APPROVED", text)
            self.assertFalse((out_dir / review_pack.APPROVAL_LOG).exists())

            approved = review_pack.build_pack(approve="Jane Doe", out_dir=out_dir)
            text = approved["path"].read_text(encoding="utf-8")
            self.assertIn("APPROVED by Jane Doe", text)
            self.assertNotIn("DRAFT.", text)

            log = (out_dir / review_pack.APPROVAL_LOG).read_text(encoding="utf-8").splitlines()
            entry = json.loads(log[-1])
            self.assertEqual(entry["name"], "Jane Doe")
            self.assertEqual(entry["sha256"], review_pack.content_hash(approved["content"]))
            self.assertEqual(entry["sha256"], draft["sha256"])

    def test_blank_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                review_pack.build_pack(approve="  ", out_dir=Path(tmp))


if __name__ == "__main__":
    unittest.main()
