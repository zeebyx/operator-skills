"""Tests for the skill scripts and the repo validator.

Standard library only. Run from the repo root:
    python3 -m unittest discover -s tests -v

Fake secrets and personal-inbox addresses are assembled at runtime so that no
string in this file looks like a real key or a real person's email.
"""
from __future__ import annotations

import csv
import json
import secrets
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "skills" / "lead-list-cleanup" / "scripts" / "clean_leads.py"
LINT = ROOT / "skills" / "n8n-workflow-review" / "scripts" / "lint_workflow.py"
VALIDATE = ROOT / "scripts" / "validate_skills.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, timeout=60,
    )


def free_mail() -> str:
    """A random address at a free-mail provider, generated so it is never a real one."""
    return f"test-{secrets.token_hex(8)}@" + "gm" + "ail.com"


class CleanLeadsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name: str, text: str, encoding="utf-8") -> Path:
        p = self.dir / name
        p.write_text(text, encoding=encoding)
        return p

    def rows(self, path: Path) -> list[dict]:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_example_runs_and_dedupes(self):
        src = ROOT / "skills" / "lead-list-cleanup" / "examples" / "sample_leads.csv"
        out, rep = self.dir / "o.csv", self.dir / "r.json"
        r = run(CLEAN, str(src), "--out", str(out), "--report", str(rep))
        self.assertEqual(r.returncode, 0, r.stderr)
        stats = json.loads(rep.read_text())
        self.assertEqual(stats["duplicates"], 1)
        self.assertEqual(stats["invalid_email"], 1)

    def test_default_outputs_sit_next_to_input(self):
        src = self.write("leads.csv", "email\na@acme.example\n")
        r = run(CLEAN, str(src))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.dir / "leads.cleaned.csv").exists())
        self.assertTrue((self.dir / "leads.report.json").exists())

    def test_formula_cells_are_escaped(self):
        src = self.write("f.csv", 'email,company\na@acme.example,"=HYPERLINK(""x"")"\nb@acme.example,@SUM(A1)\n')
        out = self.dir / "o.csv"
        run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"))
        companies = [r["company"] for r in self.rows(out)]
        self.assertTrue(all(c.startswith("'") for c in companies), companies)

    def test_formula_escape_can_be_disabled(self):
        src = self.write("f.csv", "email,phone\na@acme.example,+15550100\n")
        out = self.dir / "o.csv"
        run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"), "--no-formula-escape")
        self.assertEqual(self.rows(out)[0]["phone"], "+15550100")

    def test_missing_dedupe_column_is_an_error(self):
        src = self.write("n.csv", "person,company\nA,B\nA,B\n")
        r = run(CLEAN, str(src))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not found", r.stderr)

    def test_typo_in_dedupe_key_is_an_error(self):
        src = self.write("n.csv", "email\na@acme.example\n")
        self.assertEqual(run(CLEAN, str(src), "--dedupe-key", "emial").returncode, 2)

    def test_same_output_paths_refused(self):
        src = self.write("s.csv", "email\na@acme.example\n")
        x = str(self.dir / "x.csv")
        self.assertEqual(run(CLEAN, str(src), "--out", x, "--report", x).returncode, 2)
        self.assertEqual(run(CLEAN, str(src), "--out", str(src)).returncode, 2)

    def test_unwritable_output_is_clean_error(self):
        src = self.write("s.csv", "email\na@acme.example\n")
        r = run(CLEAN, str(src), "--out", str(self.dir / "missing" / "x.csv"))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_semicolon_delimiter(self):
        src = self.write("semi.csv", "email;company\na@acme.example;Acme\n")
        out = self.dir / "o.csv"
        r = run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows(out)[0]["company"], "Acme")

    def test_huge_field(self):
        src = self.write("big.csv", "email,notes\na@acme.example," + "x" * 300_000 + "\n")
        r = run(CLEAN, str(src))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bom_and_non_utf8(self):
        bom = self.write("bom.csv", "﻿Email\na@acme.example\n")
        self.assertEqual(run(CLEAN, str(bom)).returncode, 0)
        latin = self.dir / "latin.csv"
        latin.write_bytes("email,name\na@acme.example,Jos\xe9\n".encode("latin-1"))
        r = run(CLEAN, str(latin))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_empty_and_header_only(self):
        self.assertEqual(run(CLEAN, str(self.write("e.csv", ""))).returncode, 2)
        src = self.write("h.csv", "email,company\n")
        out = self.dir / "o.csv"
        r = run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out.read_text().startswith("email,company"))

    def test_free_mail_rows_do_not_merge_on_domain(self):
        src = self.write("fm.csv", f"email\n{free_mail()}\n{free_mail()}\n")
        out = self.dir / "o.csv"
        run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"), "--dedupe-key", "domain")
        self.assertEqual(len(self.rows(out)), 2)

    def test_role_address_not_split_into_names(self):
        src = self.write("role.csv", "full name,email\nSales Team,sales@acme.example\n")
        out = self.dir / "o.csv"
        run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"))
        row = self.rows(out)[0]
        self.assertEqual(row["role_address"], "true")
        self.assertFalse(row.get("first_name"))

    def test_company_case_preserved(self):
        src = self.write("c.csv", "email,company\na@acme.example,NASA LLC\n")
        out = self.dir / "o.csv"
        run(CLEAN, str(src), "--out", str(out), "--report", str(self.dir / "r.json"))
        self.assertEqual(self.rows(out)[0]["company"], "NASA LLC")

    def test_email_validation(self):
        src = self.write("v.csv", "email\na..b@acme.example\n.a@acme.example\nok@xn--80ak6aa92e.xn--p1ai\n")
        out, rep = self.dir / "o.csv", self.dir / "r.json"
        run(CLEAN, str(src), "--out", str(out), "--report", str(rep))
        self.assertEqual(json.loads(rep.read_text())["invalid_email"], 2)


PIPELINE = ROOT / "skills" / "pipeline-hygiene" / "scripts" / "flag_deals.py"


class PipelineHygieneTests(unittest.TestCase):
    HEADER = "deal_id,name,stage,amount,close_date,last_activity,next_step,stage_entered\n"
    TODAY = "2026-10-29"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text: str, name: str = "deals.csv") -> Path:
        p = self.dir / name
        p.write_text(self.HEADER + text, encoding="utf-8")
        return p

    def run_script(self, src: Path, *extra):
        out = self.dir / "out.csv"
        report = self.dir / "report.json"
        proc = run(PIPELINE, str(src), "--out", str(out), "--report", str(report),
                   "--today", self.TODAY, *extra)
        return proc, out, report

    def rows(self, path: Path) -> list[dict]:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_flags_each_condition_once(self):
        src = self.write(
            "1,Clean deal,Proposal,1000,2026-12-01,2026-10-28,Legal review call,2026-10-10\n"
            "2,Stale deal,Proposal,2000,2026-12-02,2026-08-01,Send proposal,2026-10-20\n"
            "3,No close date,Discovery,3000,,2026-10-27,Send proposal,2026-10-20\n"
            "4,No next step,Discovery,4000,2026-12-04,2026-10-27,Follow up,2026-10-20\n"
            "5,Stuck deal,Negotiation,5000,2026-12-05,2026-10-27,Legal review call,2026-06-01\n"
        )
        proc, out, report = self.run_script(src)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["deals"], 5)
        self.assertEqual(data["by_flag"]["stale"]["deals"], 1)
        self.assertEqual(data["by_flag"]["missing_close_date"]["deals"], 1)
        self.assertEqual(data["by_flag"]["missing_next_step"]["deals"], 1)
        self.assertEqual(data["by_flag"]["stuck"]["deals"], 1)
        self.assertEqual(data["flagged"], 4)
        flagged = {r["name"]: r["flags"] for r in self.rows(out)}
        self.assertEqual(flagged["Clean deal"], "")
        self.assertEqual(flagged["Stale deal"], "stale")
        self.assertEqual(flagged["No close date"], "missing_close_date")
        self.assertEqual(flagged["No next step"], "missing_next_step")
        self.assertEqual(flagged["Stuck deal"], "stuck")

    def test_missing_required_column_is_an_error(self):
        src = self.dir / "noamount.csv"
        src.write_text("deal_id,name\n1,Acme\n", encoding="utf-8")
        proc = run(PIPELINE, str(src), "--today", self.TODAY)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing required column(s)", proc.stderr)

    def test_formula_cells_are_escaped(self):
        src = self.write('1,"=HYPERLINK(""x"")",Proposal,1000,2026-12-01,2026-10-28,Call,2026-10-10\n')
        proc, out, _ = self.run_script(src)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.rows(out)[0]["name"].startswith("'"), self.rows(out))

    def test_formula_escape_can_be_disabled(self):
        src = self.write('1,"=HYPERLINK(""x"")",Proposal,1000,2026-12-01,2026-10-28,Call,2026-10-10\n')
        proc, out, _ = self.run_script(src, "--no-formula-escape")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.rows(out)[0]["name"], '=HYPERLINK("x")')

    def test_unparseable_amount_is_counted(self):
        src = self.write("1,Clean deal,Proposal,n/a,2026-12-01,2026-10-28,Call,2026-10-10\n")
        proc, _, report = self.run_script(src)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["rows_with_bad_amount"], 1)
        self.assertEqual(data["total_value"], 0)
        self.assertIn("no parseable amount", proc.stdout)

    def test_non_utf8_input_is_a_clean_error(self):
        src = self.dir / "latin.csv"
        src.write_bytes(("deal_id,name\n1," + "Jos\xe9" + "\n").encode("latin-1"))
        proc = run(PIPELINE, str(src), "--today", self.TODAY)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_output_paths_must_not_reuse_the_input(self):
        src = self.write("1,Clean deal,Proposal,1000,2026-12-01,2026-10-28,Call,2026-10-10\n")
        same_out = run(PIPELINE, str(src), "--out", str(src), "--today", self.TODAY)
        self.assertEqual(same_out.returncode, 2)
        same_report = run(PIPELINE, str(src), "--out", str(self.dir / "x.csv"),
                          "--report", str(self.dir / "x.csv"), "--today", self.TODAY)
        self.assertEqual(same_report.returncode, 2)

    def test_example_export_runs(self):
        src = ROOT / "skills" / "pipeline-hygiene" / "examples" / "deals.csv"
        proc, _, report = self.run_script(src)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(report.read_text())["deals"], 4)


class LintWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def lint_json(self, data) -> subprocess.CompletedProcess:
        p = self.dir / "wf.json"
        p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return run(LINT, str(p), "--format", "json")

    def test_example_has_high_findings(self):
        ex = ROOT / "skills" / "n8n-workflow-review" / "examples" / "risky_workflow.json"
        r = run(LINT, str(ex), "--format", "json")
        self.assertEqual(r.returncode, 1, r.stderr)
        findings = json.loads(r.stdout)[0]["findings"]
        self.assertGreaterEqual(sum(f["severity"] == "high" for f in findings), 2)

    def test_malformed_inputs_exit_2_without_traceback(self):
        cases = [
            '{"nodes": null}', '{"nodes": {"a": 1}}', '"hello"', "42", "[1, 2]", "[]",
            "{not json", '{"meta": "x"}',
        ]
        for case in cases:
            with self.subTest(case=case):
                r = self.lint_json(case)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_odd_node_shapes_do_not_crash(self):
        wf = {"nodes": [
            "x", {"name": None, "type": None},
            {"name": "A", "type": "n8n-nodes-base.set", "parameters": ["a"]},
            {"name": "B", "type": "n8n-nodes-base.code", "parameters": {"jsCode": 5}},
        ], "meta": "x", "settings": None}
        r = self.lint_json(wf)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_deep_nesting(self):
        r = self.lint_json("[" * 5000 + "]" * 5000)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_directory_and_missing_file(self):
        self.assertEqual(run(LINT, str(self.dir)).returncode, 2)
        self.assertEqual(run(LINT, str(self.dir / "nope.json")).returncode, 2)

    def test_secret_detection(self):
        anthropic_key = "sk-" + "ant-" + secrets.token_hex(16)
        wf = {"nodes": [
            {"name": "Call API", "type": "n8n-nodes-base.httpRequest", "retryOnFail": True,
             "parameters": {"jsonBody": '{"api_key": "' + secrets.token_hex(8) + '"}'}},
            {"name": "Claude", "type": "n8n-nodes-base.httpRequest", "retryOnFail": True,
             "parameters": {"headerParameters": {"parameters": [
                 {"name": "Authorization", "value": "Bearer " + secrets.token_hex(16)}]},
                 "note": anthropic_key}},
        ], "settings": {"errorWorkflow": "1"}}
        r = self.lint_json(wf)
        self.assertEqual(r.returncode, 1)
        msgs = [f["message"] for f in json.loads(r.stdout)[0]["findings"] if f["severity"] == "high"]
        self.assertTrue(any("api_key" in m for m in msgs), msgs)
        self.assertTrue(any("Anthropic" in m for m in msgs), msgs)
        bearer = [m for m in msgs if "headerParameters" in m]
        self.assertEqual(len(bearer), 1, msgs)

    def test_public_triggers(self):
        for t in ("webhook", "formTrigger", "chatTrigger"):
            with self.subTest(trigger=t):
                wf = {"nodes": [{"name": "In", "type": f"n8n-nodes-base.{t}", "parameters": {}}]}
                self.assertEqual(self.lint_json(wf).returncode, 1)

    def test_clean_workflow_passes(self):
        wf = {"nodes": [{"name": "Nightly", "type": "n8n-nodes-base.scheduleTrigger", "parameters": {}}],
              "settings": {"errorWorkflow": "1"}, "meta": {"description": "demo"}}
        r = self.lint_json(wf)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)[0]["findings"], [])


class ValidatorTests(unittest.TestCase):
    def test_repo_passes(self):
        r = run(VALIDATE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
