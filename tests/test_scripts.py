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


class HubspotPropertyAuditTests(unittest.TestCase):
    SCRIPT = ROOT / "skills" / "hubspot-property-audit" / "scripts" / "audit_properties.py"
    HEADER = "name,label,group,description,options\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_audit(self, text, *extra):
        src = self.dir / "p.csv"
        src.write_text(self.HEADER + text, encoding="utf-8")
        report = self.dir / "r.json"
        proc = run(self.SCRIPT, str(src), "--report", str(report), *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(report.read_text()), proc

    def test_flags_duplicates_and_missing_descriptions(self):
        report, proc = self.run_audit(
            "a,A,G,Used,x;y\n"
            "b,A,G,Also used,x;y\n"
            "c,C,G,,\n"
        )
        self.assertEqual(report["properties"], 3)
        self.assertEqual(report["by_finding"]["duplicate_label"], 2)
        self.assertEqual(report["by_finding"]["missing_description"], 1)
        self.assertEqual(report["duplicate_labels"][0]["label"], "a")
        self.assertIn("missing_description", proc.stdout)

    def test_flags_picklist_case_drift(self):
        report, _ = self.run_audit(
            "a,One,G,x,Lead;MQL;SQL\n"
            "b,Two,G,y,lead;mql;sql\n"
        )
        self.assertEqual(len(report["picklist_drift"]), 1)
        self.assertIn("inconsistent_picklist", report["by_finding"])

    def test_usage_export_marks_zero_counts_unused(self):
        usage = self.dir / "u.csv"
        usage.write_text("property,count\na,10\nb,0\n", encoding="utf-8")
        report, _ = self.run_audit(
            "a,A,G,x,\n"
            "b,B,G,y,\n",
            "--usage", str(usage),
        )
        self.assertTrue(report["usage_supplied"])
        self.assertEqual(report["by_finding"]["unused"], 1)

    def test_unrelated_picklists_in_one_group_are_not_drift(self):
        report, _ = self.run_audit(
            "a,Red type,G,x,Red;Blue\n"
            "b,Lead type,G,y,Lead;MQL\n"
        )
        self.assertEqual(report["picklist_drift"], [])
        self.assertNotIn("inconsistent_picklist", report["by_finding"])

    def test_picklist_drift_reports_the_raw_spellings(self):
        report, _ = self.run_audit(
            "a,One,G,x,Lead;MQL\n"
            "b,Two,G,y,lead;mql\n"
        )
        self.assertEqual(len(report["picklist_drift"]), 1)
        drift = report["picklist_drift"][0]
        self.assertEqual(drift["group"], "G")
        self.assertEqual(drift["variants"], [["Lead", "MQL"], ["lead", "mql"]])
        self.assertEqual(drift["properties"], ["a", "b"])

    def test_duplicate_option_within_a_property_is_flagged(self):
        report, _ = self.run_audit("a,One,G,x,Lead;lead\n")
        self.assertEqual(report["by_finding"]["inconsistent_picklist"], 1)

    def test_formula_cells_are_escaped(self):
        report, _ = self.run_audit("a,=SUM(A1),G,x,One;Two\n")
        self.assertTrue(report["formula_escape"])
        with open(self.dir / "p.audited.csv", newline="", encoding="utf-8") as f:
            row = list(csv.DictReader(f))[0]
        self.assertTrue(row["label"].startswith("'"), row["label"])

    def test_formula_escape_can_be_disabled(self):
        self.run_audit("a,=SUM(A1),G,x,One;Two\n", "--no-formula-escape")
        with open(self.dir / "p.audited.csv", newline="", encoding="utf-8") as f:
            row = list(csv.DictReader(f))[0]
        self.assertEqual(row["label"], "=SUM(A1)")

    def test_non_utf8_input_is_a_clean_error(self):
        src = self.dir / "latin.csv"
        src.write_bytes(("name,label\na,Jos\xe9\n").encode("latin-1"))
        proc = run(self.SCRIPT, str(src))
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_output_paths_must_not_reuse_the_input(self):
        src = self.dir / "p.csv"
        src.write_text(self.HEADER + "a,A,G,x,One;Two\n", encoding="utf-8")
        self.assertEqual(run(self.SCRIPT, str(src), "--out", str(src)).returncode, 2)
        same = self.dir / "x.csv"
        self.assertEqual(run(self.SCRIPT, str(src), "--out", str(same), "--report", str(same)).returncode, 2)

    def test_missing_name_column_is_rejected(self):
        src = self.dir / "bad.csv"
        src.write_text("label,group\nA,G\n", encoding="utf-8")
        proc = run(self.SCRIPT, str(src))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("name and label", proc.stderr)


class ValidatorTests(unittest.TestCase):
    def test_repo_passes(self):
        r = run(VALIDATE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
