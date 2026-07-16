#!/usr/bin/env python3
"""Local security audit script for NeuroLab.

Runs static analysis (Bandit) and a dependency vulnerability scan (pip-audit) on
the backend code.  The script is intended to be run locally before releases and
is also invoked by .github/workflows/security-audit.yml on a weekly schedule.

Usage:
    python security_audit.py

Requirements:
    pip install bandit pip-audit
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
REQUIREMENTS = BASE / "requirements.txt"


def run_bandit():
    report = BASE / "bandit-report.json"
    cmd = ["bandit", "-r", str(BASE), "-f", "json", "-o", str(report)]
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("Bandit not installed. Run: pip install bandit", file=sys.stderr)
        sys.exit(1)
    with open(report, "r", encoding="utf-8") as f:
        data = json.load(f)
    findings = data.get("results", [])
    print(f"Bandit findings: {len(findings)}")
    for item in findings:
        print(
            f"  [{item.get('issue_severity', '?')}] {item.get('filename')}:{item.get('line_number')} "
            f"{item.get('issue_text')} ({item.get('test_id')})"
        )
    return findings


def run_pip_audit():
    report = BASE / "pip-audit-report.json"
    cmd = ["pip-audit", "-r", str(REQUIREMENTS), "-f", "json", "-o", str(report)]
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("pip-audit not installed. Run: pip install pip-audit", file=sys.stderr)
        sys.exit(1)
    with open(report, "r", encoding="utf-8") as f:
        data = json.load(f)
    vulns = data.get("vulnerabilities", [])
    print(f"pip-audit findings: {len(vulns)}")
    for item in vulns:
        print(f"  {item.get('name')} {item.get('version')}: {item.get('vulnerability_id')}")
    return vulns


def main():
    print("NeuroLab security audit")
    print("=" * 40)
    bandit_findings = run_bandit()
    pip_findings = run_pip_audit()
    total = len(bandit_findings) + len(pip_findings)
    print("=" * 40)
    if total == 0:
        print("No security findings. Great!")
        sys.exit(0)
    else:
        print(f"Total findings: {total}")
        sys.exit(1)


if __name__ == "__main__":
    main()
