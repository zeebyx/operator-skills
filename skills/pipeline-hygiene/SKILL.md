---
name: pipeline-hygiene
description: Take a CRM deal export and flag stale deals, missing close dates, missing next steps and deals stuck in a stage too long. Use when the user asks to clean a sales pipeline, review a CRM export, find stuck deals or prepare a pipeline review.
---

# Pipeline hygiene

A pipeline review is only useful if the same deals count as stale every week. This skill runs one script over the export and returns a ranked list of deals that need a human decision.

## Steps

1. **Run the script first.** Do not judge rows by reading them yourself.

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/flag_deals.py deals.csv --report deals.report.json
   ```

   It writes a flagged copy of the CSV next to the input (or to `--out`) and prints a one-screen summary. Exit code 2 means an input problem; the message says which column is missing. The script refuses to write over the input file, or to send the report and the flagged copy to the same path.

   The flagged copy prefixes any cell starting with `=`, `+`, `-` or `@` with an apostrophe, so spreadsheet apps keep the value as text instead of running it as a formula. Pass `--no-formula-escape` when you need the raw values.

2. **Read the report.** Start with the counts per flag and the total pipeline value in each flag.
3. **Rank by money, not count.** Sort the flagged deals by amount and present the top ten with their flags.
4. **Explain the rule for each flag** in one line, using the threshold the script used.

## What the script flags

- `missing_close_date`: the close date is empty or not a date.
- `missing_next_step`: the next step is empty or says only "follow up".
- `stale`: the last activity is older than 30 days (`--stale-days`).
- `stuck`: the deal entered its current stage more than 45 days ago (`--stuck-days`).

Columns are matched case-insensitively and common aliases are accepted (`Deal Name`, `Opportunity`, `Amount`, `Value`, `Close Date`, `Expected Close`, `Last Activity`, `Stage Entered`).

## Output format

```text
Deals: 412, flagged: 87 (21 percent), value flagged: 1,240,000 EUR
- stale: 41 deals, 620,000 EUR
- missing close date: 19 deals, 310,000 EUR
- missing next step: 22 deals, 210,000 EUR
- stuck: 14 deals, 100,000 EUR

Top 10 by amount
| Deal | Amount | Flags |
```

The JSON report also carries `rows_with_bad_amount`: rows whose amount could not be parsed. They count as 0 in the totals, so say so when the count is greater than zero.

## Rules

- Never edit the source export; write the flagged copy next to it.
- Do not treat a date in the future as missing.
- A deal can carry several flags; count it once in the total and once per flag.
- Do not invent an owner, stage or amount that is not in the file.
- If more than half the rows are flagged, say the export itself is the problem before reviewing individual deals.

Credits: zeebyx/operator-skills contributors
