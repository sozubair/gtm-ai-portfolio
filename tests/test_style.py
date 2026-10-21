"""House style checks on every generated document and on the rules prose."""
import html
import json
import re
import tempfile
import unittest
from pathlib import Path

import _paths
import build_showcase
import check

BANNED = re.compile(r"\b(delv\w*|leverag\w*|seamless\w*|pivotal|tapestr\w*)\b", re.I)
HYPHENATED = re.compile(r"\b[A-Za-z]+-[A-Za-z]+\b")
AMERICAN = re.compile(r"\b(color|colors|program|programs|optimiz\w*|analyz\w*|behavior\w*|center|"
                      r"organiz\w*|randomiz\w*|prioritiz\w*|recogniz\w*|favor\w*)\b")
EM_DASH = "\u2014"


def prose_from_html(text: str) -> str:
    text = re.sub(r"<(style|script|title)\b.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def prose_from_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    return text


def strip_urls(text: str) -> str:
    return re.sub(r"https?://\S+", " ", text)


class StyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        cls.showcase = build_showcase.build(out, allow_fetch=False)
        import review_pack
        review_pack.build_pack(out_dir=out)
        rules = check.load_rules()
        for code in rules["countries"]:
            decision = check.check(rules, code, "email", "company")
            check.write(check.render_lead(decision), f"lead_{code}.md", out)
        cls.docs = {}
        for path in out.iterdir():
            raw = path.read_text(encoding="utf-8") if path.suffix in {".md", ".html"} else None
            if raw is None:
                continue
            prose = prose_from_html(raw) if path.suffix == ".html" else prose_from_markdown(raw)
            cls.docs[path.name] = strip_urls(prose)

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k not in {"url", "basis", "mobile_basis", "level", "checked_on"}:
                        yield from walk(v)
            elif isinstance(node, list):
                for v in node:
                    yield from walk(v)
            elif isinstance(node, str):
                yield node

        cls.docs["rules.json"] = strip_urls(" ".join(walk(rules)))
        readme = (_paths.ROOT / "README.md").read_text(encoding="utf-8")
        cls.docs["README.md"] = strip_urls(prose_from_markdown(readme))
        briefs = _paths.ROOT / "01_measurement_planner" / "briefs"
        for brief in briefs.glob("*.json"):
            data = json.loads(brief.read_text(encoding="utf-8"))
            cls.docs[brief.name] = " ".join(walk({k: v for k, v in data.items() if isinstance(v, (str, list))}))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_documents_were_found(self):
        for name in ("showcase.html", "review_pack.html", "consent_matrix.md",
                     "measurement_plan_customer_workshops.md",
                     "measurement_plan_enterprise_executive_briefings.md"):
            self.assertIn(name, self.docs)

    def test_no_em_dashes(self):
        for name, text in self.docs.items():
            with self.subTest(doc=name):
                self.assertNotIn(EM_DASH, text)

    def test_no_banned_words(self):
        for name, text in self.docs.items():
            with self.subTest(doc=name):
                self.assertEqual(BANNED.findall(text), [])

    def test_no_hyphenated_compounds_in_prose(self):
        for name, text in self.docs.items():
            with self.subTest(doc=name):
                self.assertEqual(HYPHENATED.findall(text), [])

    def test_british_spelling(self):
        for name, text in self.docs.items():
            with self.subTest(doc=name):
                self.assertEqual(AMERICAN.findall(text), [])


class ShowcaseTests(unittest.TestCase):
    def test_showcase_has_every_section_and_no_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build_showcase.build(Path(tmp), allow_fetch=False)
            page = out["html"]
            for text in ("Project 1", "Project 2", "Project 3", "Decision", "<svg", "class='consent'"):
                self.assertIn(text, page)
            self.assertEqual(page.count("<svg"), 4)
            self.assertNotIn("nan", prose_from_html(page).lower().split())
            self.assertIn("DRAFT", page)

    def test_fonts_are_embedded_when_available(self):
        if not build_showcase.fetch_fonts.MANIFEST.exists():
            self.skipTest("Fonts not downloaded")
        css = build_showcase.font_css(allow_fetch=False)
        self.assertIn("font-family:'Fraunces'", css)
        self.assertIn("font-family:'Inter'", css)
        self.assertIn("data:font/woff2;base64,", css)


if __name__ == "__main__":
    unittest.main()
