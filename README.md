# operator-skills

Free, open-source Agent Skills for the people who run the business: operations, GTM, RevOps, customer success and automation builders.

Each skill is a folder with a `SKILL.md` that teaches Claude (or any agent that reads the Agent Skills format) how to do one recurring job the same way every time. Where a step is mechanical, like deduping a list or scanning a workflow file, the skill ships a small script so the agent runs real code instead of guessing.

> Status: early and small. These skills come from my own ops and automation work. Issues and contributions are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Skills

| Skill | What it does | Script |
|---|---|---|
| [lead-list-cleanup](skills/lead-list-cleanup) | Normalizes, validates and dedupes prospect CSVs before they hit a CRM or sequencer | Yes |
| [icp-lead-scoring](skills/icp-lead-scoring) | Scores leads against a written ICP rubric with a reason for every score | No |
| [cold-outreach-sequence](skills/cold-outreach-sequence) | Writes a short, specific 3-step outbound sequence from a lead and an offer | No |
| [n8n-workflow-review](skills/n8n-workflow-review) | Checks an exported n8n workflow JSON for common reliability and security problems | Yes |
| [sop-writer](skills/sop-writer) | Turns a messy process description into a standard operating procedure | No |
| [call-notes-to-crm](skills/call-notes-to-crm) | Converts call notes or transcripts into CRM fields, next steps and a follow-up email | No |
| [weekly-ops-report](skills/weekly-ops-report) | Builds a one-page weekly status report with RAG status, risks and asks | No |
| [churn-risk-review](skills/churn-risk-review) | Scores an account's churn risk from usage, tickets and NPS, with reasons and a save plan | No |
| [invoice-chaser](skills/invoice-chaser) | Writes a polite, escalating 3-step payment reminder sequence | No |
| [qbr-deck-outline](skills/qbr-deck-outline) | Turns account metrics and notes into a quarterly business review outline | No |
| [job-post-to-icp](skills/job-post-to-icp) | Pulls buying signals from a job post and scores the company against your ICP | No |
| [zapier-to-n8n-migration](skills/zapier-to-n8n-migration) | Plans a Zapier to n8n migration: node mapping, credentials, risks and order | No |
| [pipeline-hygiene](skills/pipeline-hygiene) | Flags stale, incomplete or stuck deals in a CRM export and values each flag | Yes |

## Install

### Claude Code: plugin (easiest)

Inside Claude Code, run:

```
/plugin marketplace add zeebyx/operator-skills
/plugin install operator-skills@operator-skills
```

### Claude Code: copy the folders

```bash
git clone https://github.com/zeebyx/operator-skills.git

# For all your projects
mkdir -p ~/.claude/skills
cp -r operator-skills/skills/* ~/.claude/skills/

# Or for one project (run inside that project)
mkdir -p .claude/skills
cp -r /path/to/operator-skills/skills/* .claude/skills/
```

### Claude apps (claude.ai and desktop)

1. Zip one skill folder so the folder itself is at the top of the zip (for example the zip contains `sop-writer/SKILL.md`, not a bare `SKILL.md`).
2. In Claude, open **Customize > Skills** and upload the zip.

Menu names can change; if you cannot find it, see Anthropic's help article on using skills in Claude.

### Claude API and Agent SDK

See Anthropic's [Agent Skills documentation](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) for uploading skill folders through the API or loading them in the Agent SDK. Each folder under `skills/` is a standard skill and needs no changes.

## Safety

- Scripts use only the Python standard library (3.9+). Nothing to install.
- Scripts read only the file you give them, write only the output files you name (or files next to the input), and make no network calls.
- `lead-list-cleanup` escapes spreadsheet formulas in its output by default.
- No skill sends data anywhere. Skills that write messages (outreach, follow-ups) only draft them for you to review.

To report a security problem, see [SECURITY.md](SECURITY.md).

## Design rules

Every skill in this repo follows the same rules, so they behave predictably:

1. **One job per skill.** If the description needs "and", it is probably two skills.
2. **The description decides when it runs.** It states the trigger in plain words a user would actually type.
3. **Mechanical work goes in scripts.** Dedupe, parse, validate and count in code. Use the model for judgment and writing.
4. **Scripts use only the Python standard library.** No install step.
5. **Output formats are spelled out.** The skill shows the exact shape of what it returns.
6. **No secrets, no real people or companies.** Examples use reserved `.example` domains.

`python3 scripts/validate_skills.py` checks the rules that can be checked automatically, and `python3 -m unittest discover -s tests` tests the scripts. CI runs both on Python 3.9 and 3.13 for every pull request.

## Repo layout

```
skills/<skill-name>/SKILL.md        required, with name + description frontmatter
skills/<skill-name>/scripts/        optional helper scripts (standard library only)
skills/<skill-name>/examples/       optional sample inputs
templates/SKILL_TEMPLATE.md         start here for a new skill
scripts/validate_skills.py          repo linter
tests/                              script tests
.claude-plugin/marketplace.json     lets Claude Code install the repo as a plugin
```

## Roadmap

Skills we want next. Each has an open issue labelled `good first issue`:

- `pipeline-hygiene` for stale deals and missing fields (pull request in review)
- `hubspot-property-audit` for CRM property cleanup (pull request in review)
- Add example inputs for `icp-lead-scoring`

Have an idea for a skill you use every week? Open an issue with the "New skill idea" template.

## License

MIT. Use these in commercial work. Attribution appreciated, not required.

Maintained by [Nitin Sarkar](https://github.com/zeebyx) at [After Machines](https://aftermachines.com).
