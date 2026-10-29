---
name: hubspot-property-audit
description: Audit a HubSpot property export for unused properties, duplicate labels, inconsistent picklists and missing descriptions. Use when the user asks to clean up HubSpot properties, review a property export, find duplicate or undocumented fields, or prepare a CRM data model cleanup.
---

# HubSpot property audit

A property export grows into hundreds of fields, and nobody remembers which ones still matter. This skill runs one script over the export and returns a reviewable list instead of a guess.

## Steps

1. **Run the script.** Do not audit rows by hand.

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/audit_properties.py properties.csv --report audit.json
   ```

   Add `--usage usage.csv` when the user can export property usage (columns `property` and `count`); without it, `unused` stays unknown. The script refuses to write over the input file, or to send the report and the flagged copy to the same path.

   The flagged copy prefixes any cell starting with `=`, `+`, `-` or `@` with an apostrophe, so spreadsheet apps keep the value as text instead of running it as a formula. Pass `--no-formula-escape` when you need the raw values.

2. **Read the report.** It prints counts per finding and writes a JSON report plus a flagged copy of the CSV.
3. **Review the four findings in this order:** duplicate labels, inconsistent picklists, missing descriptions, unused properties.
4. **Present a short cleanup list** with the internal name, the finding, and the recommended action (rename, merge, delete, document).

## What the script flags

- `duplicate_label`: two or more properties share the same label, case-insensitively.
- `missing_description`: the description is empty. HubSpot shows this text in the editor, so an empty one is a real gap.
- `inconsistent_picklist`: properties in the same group use the same option set with different spelling (compared after trimming and lowercasing, so unrelated picklists are not drift), or one property defines the same option value twice. Each drift entry lists the group, the normalised options, the raw `variants` and the affected properties.
- `unused`: only when `--usage` is given; the property's count is zero.

Header aliases are matched case-insensitively (`internal name`, `property name`, `name`; `label`, `display label`; `group`, `group name`; `description`; `options`, `choices`; `type`, `field type`).

## Output format

```text
Properties: 612, findings: 94
- duplicate_label: 12 groups, 27 properties
- missing_description: 41 properties
- inconsistent_picklist: 6 groups
- unused: 20 properties (usage export supplied)

Cleanup list
| Internal name | Finding | Action |
| --- | --- | --- |
```

## Rules

- Never delete or rename a property in HubSpot; this audit only reports.
- Say `unknown` for usage when no usage export is supplied; never assume a property is unused.
- Keep internal names exactly as exported; they are the stable identifier.
- A duplicate label is not automatically a merge candidate; check the type and description before recommending a merge.
- If the export has fewer than ten properties, say the sample is too small to draw conclusions.

Credits: zeebyx/operator-skills contributors
