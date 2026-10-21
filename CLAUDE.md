# Project rules

Follow these rules for every change in this repository.

## Scope and data
- This is a public portfolio of three GTM tools.
- Use only fictional or public data.
- Never reference any employer's internal data, systems or names.

## Stack
- Python 3.11 or newer.
- Pinned dependencies: numpy and pandas only. See requirements.txt.
- Tests use the standard library unittest. Run them with:
  `python -m unittest discover -s tests -v`

## Numbers
- The code computes every number.
- AI only rewrites wording. AI must never change a number.

## Writing style
- British English.
- Short sentences.
- No em dashes.
- No hyphenated compounds in prose.
- Never use these words: delve, leverage, seamless, pivotal, tapestry.

## Outputs and checks
- Every tool writes its output to /outputs.
- Run the tests after every change.
- Fix failures before saying something is done.
