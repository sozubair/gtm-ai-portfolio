# Project notes

Where this project stands and how to pick it up again. Last updated 22 October 2026.

## Where things live

- Repository: https://github.com/sozubair/gtm-ai-portfolio (branch `main`)
- Live showcase: https://sozubair.github.io/gtm-ai-portfolio/
- Local copy on the original machine: `C:\Users\sozubair\Projects\gtm-ai-portfolio`
- House rules: [CLAUDE.md](CLAUDE.md). How each tool works: [README.md](README.md).

## Status

- All seven build steps are done: the three tools, their tests and the showcase.
- 39 tests pass.
- GitHub Pages publishes `main`. The site updates a minute or two after each push.
- Consent rules were checked against their sources on 22 October 2026. UK is verified at regulator level. Ireland, Germany, the Netherlands and Spain are verified at statute level. France is partial.
- The review pack is still DRAFT. Nobody has approved it.

## Open items

1. **France.** Confirm that the CNIL email prospecting page says professionals can be emailed on an opt out basis. Then change the France verification level in `02_consent_matrix/rules.json`. The CNIL and Légifrance pages could not be loaded on 22 October.
2. **Netherlands.** Article 11.7 does not mention the three year window for calling customers. Check the ACM guidance before relying on it.
3. **Spain.** Lista Robinson screening comes from data protection law and AEPD guidance, not from LSSI article 21 or LGTel article 66. It has not been checked.
4. **Germany.** UWG §7 was read on buzer.de because the official site could not be reached. Recheck it on `gesetze-im-internet.de`.
5. **Verification dates.** The `checked_on` dates are the day the sources were read for that commit. Replace them with the date of your own check if it differs.
6. **Review pack approval.** Optional. Run `python 03_review_pack/review_pack.py --approve "Your Name"`, rebuild the showcase and push. The showcase then shows APPROVED.

## Pick it up again

On the original machine:

```
cd C:\Users\sozubair\Projects\gtm-ai-portfolio
.venv\Scripts\activate
python -m unittest discover -s tests -v
```

On a new machine, install Python 3.11 or newer and Git first, then:

```
git clone https://github.com/sozubair/gtm-ai-portfolio.git
cd gtm-ai-portfolio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
git config --global user.name "zubair.s"
git config --global user.email "346003053+sozubair@users.noreply.github.com"
```

To carry on with Kiro, open the project folder. The steering file loads these notes and the house rules, so you can ask something like "work on open item 1".

## Make a change and publish

```
python -m unittest discover -s tests -v
python 03_review_pack/review_pack.py
python showcase/build_showcase.py
git add <the files you changed> outputs
git commit -m "Describe the change"
git push
```

`build_showcase.py` reruns the planner and the consent matrix itself. Run the review pack first if its data or wording changed.

## To verify or change a consent rule

1. Read the source listed for that market in `rules.json`.
2. Update the rule's `basis` and `summary` if the source disagrees.
3. Update the market's `verification` block: `level`, `checked_on` and `notes`.
4. Add a test to `VerifiedRuleTests` in `tests/test_consent.py`.
5. Run the tests, rebuild and push.

## Decisions made

- The code computes every number. The README carries no results, so it cannot go out of date.
- `outputs/` is committed so GitHub Pages can serve the showcase.
- Fonts were downloaded once into `showcase/fonts/` and are embedded as base64. Run `python showcase/fetch_fonts.py` to refresh them.
- Commits use the GitHub noreply address, so no personal email appears in the history.
- Ireland email to sole traders is opt out under Regulation 13(2). Mobile calls in Ireland need consent for every subscriber under 13(6).
- UK calls to companies are screened against both the TPS and the CTPS, as the ICO advises.
