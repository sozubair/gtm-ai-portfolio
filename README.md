# GTM tools portfolio

Three small tools for GTM teams. Each one answers a question that usually gets settled by opinion.

**[Open the live showcase](https://sozubair.github.io/gtm-ai-portfolio/outputs/showcase.html)**

Every number in this repository is computed by the code at build time. AI only rewrites wording and never changes a number. All data is fictional or public.

## The tools

| Tool | The question it answers |
| --- | --- |
| [01 Measurement planner](01_measurement_planner/planner.py) | Did the programme cause the result? How many accounts does a fair test need? |
| [02 Consent matrix](02_consent_matrix/check.py) | Can I contact this lead this way, and why? Which plays can run once for EMEA? |
| [03 Review pack](03_review_pack/review_pack.py) | What changed this week? Was it volume or conversion? |

### 01 Measurement planner

Reads a JSON brief and sizes a test of two proportions with both tails, adjusted for an uneven split. If there are enough accounts, it designs a randomised holdout. If not, it recommends a staged rollout and reports the smallest uplift the population can detect. It then simulates a run. The report shows the uplift with a 95% interval, the p value, the incremental value with a range, and what a sourced count would have claimed.

### 02 Consent matrix

Holds the outbound rules for the UK, Ireland, Germany, France, the Netherlands and Spain in [rules.json](02_consent_matrix/rules.json). Each market has the law, the regulator, the rule for email and calls to companies and sole traders, screening lists, the existing customer exception and a source. Each market also carries a verification level and the date it was checked. The checker answers one lead at a time or classes every play as "Run once for EMEA" or "Localise". An objection always blocks. This is not legal advice.

### 03 Review pack

Generates eight weeks of fictional pipeline data for four regions and two segments. It bridges week 8 against the four week average and splits each change into a volume effect and a conversion effect. It drafts a "what changed" note. The HTML pack stays DRAFT until a named person approves it. Each approval is logged with a SHA-256 hash of the content.

### Showcase

[build_showcase.py](showcase/build_showcase.py) imports all three tools and writes one HTML page. It puts the answer first, then charts drawn as inline SVG with labels on the data. The page prints one project per A4 page. The Fraunces and Inter fonts are embedded, so the page works offline.

## Run it

Python 3.11 or newer.

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS or Linux
pip install -r requirements.txt

python -m unittest discover -s tests -v

python 01_measurement_planner/planner.py 01_measurement_planner/briefs/workshops.json --simulate-uplift 0.30
python 02_consent_matrix/check.py lead --country DE --channel email --recipient company
python 02_consent_matrix/check.py matrix
python 03_review_pack/generate_data.py
python 03_review_pack/review_pack.py --approve "Your Name"
python showcase/build_showcase.py
```

Every tool writes to `outputs/`.

## Layout

```
01_measurement_planner/   planner.py and two briefs
02_consent_matrix/        check.py, rules.json and plays.json
03_review_pack/           generate_data.py and review_pack.py
showcase/                 build_showcase.py, fetch_fonts.py and the embedded fonts
tests/                    unittest suites, including house style checks
outputs/                  reports, the review pack and showcase.html
```

## House rules

- Python with pinned numpy and pandas only. Tests use the standard library unittest.
- The code computes every number.
- British English and short sentences. A test checks every generated document for style.
- The full rules are in [CLAUDE.md](CLAUDE.md).

Fraunces and Inter are used under the SIL Open Font License.
