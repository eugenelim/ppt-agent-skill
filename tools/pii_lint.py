#!/usr/bin/env python3
"""
Pre-commit / commit-msg PII linter.

Scans staged diff or a commit message file for patterns that indicate
personal information. Prints violations and exits 1 if any are found.

Usage:
  python tools/pii_lint.py                      # pre-commit: scan staged diff
  python tools/pii_lint.py --commit-msg F       # commit-msg: scan file F
  python tools/pii_lint.py --diff-range BASE    # CI: scan git diff BASE...HEAD
  python tools/pii_lint.py --pr-metadata F      # CI: scan PR title/body/commits
"""
import re
import subprocess
import sys
from pathlib import Path

# Extensions whose content is never scanned (binary / generated).
SKIP_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".pyc", ".pyo", ".whl"}
)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "example.io",
        # RFC 6761 reserved TLD — never resolvable, used in agent-pack
        # eval fixtures for synthetic prompt-injection URLs.
        "example.test",
        "users.noreply.github.com",
    }
)

# ---------------------------------------------------------------------------
# User filesystem paths  (generic — works in CI where getuser() != developer)
# ---------------------------------------------------------------------------

_USER_PATH_RE = re.compile(r"/(?:Users|home)/([a-zA-Z][a-zA-Z0-9._-]+)/")

_SAFE_PATH_USERNAMES = frozenset(
    {
        "user", "username", "example", "runner", "ubuntu", "root", "ci",
        "test", "admin", "guest", "github", "actions", "nobody", "www",
        "vagrant", "deploy", "jenkins", "circleci", "travis",
    }
)

# ---------------------------------------------------------------------------
# Phone numbers  (formatted; context-gated to reduce version-string FPs)
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(
    r"\b(?:\+1[-.\s]?)?\(?(\d{3})\)?[-.\s](\d{3})[-.\s](\d{4})\b"
)

_PHONE_CONTEXT_WORDS = frozenset(
    {
        "phone", "tel", "mobile", "cell", "fax", "contact", "call",
        "sms", "whatsapp", "number", "num",
    }
)

# ---------------------------------------------------------------------------
# US Social Security Numbers
# ---------------------------------------------------------------------------

_SSN_RE = re.compile(
    r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"
)

# ---------------------------------------------------------------------------
# Credit card numbers  (formatted + Luhn validation)
# ---------------------------------------------------------------------------

_CC_RE = re.compile(
    r"\b(?:"
    r"\d{4}[-\s]\d{6}[-\s]\d{5}"
    r"|\d{4}[-\s]\d{6}[-\s]\d{4}"
    r"|\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}"
    r"|\d{13,19}"
    r")\b"
)


def _luhn_ok(digits: str) -> bool:
    ns = [int(d) for d in digits]
    ns.reverse()
    total = 0
    for i, n in enumerate(ns):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# ---------------------------------------------------------------------------
# Blocklist
# ---------------------------------------------------------------------------

def _get_blocklist() -> list[str]:
    """Return lower-cased terms from ~/.pii-blocklist.txt."""
    path = Path.home() / ".pii-blocklist.txt"
    if not path.exists():
        return []
    terms = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        term = raw.strip()
        if term and not term.startswith("#"):
            terms.append(term.lower())
    return terms


# ---------------------------------------------------------------------------
# Per-line check
# ---------------------------------------------------------------------------

def _is_allowed_email(email: str) -> bool:
    local, _, domain = email.partition("@")
    if domain.lower() in ALLOWED_EMAIL_DOMAINS:
        return True
    if domain.lower().startswith("odata."):  # OData annotation keys
        return True
    return False


def _check_line(line: str, blocklist: list[str]) -> list[str]:
    findings: list[str] = []
    for match in EMAIL_RE.finditer(line):
        email = match.group(0)
        if not _is_allowed_email(email):
            findings.append(f"non-placeholder email: {email}")
    for m in _USER_PATH_RE.finditer(line):
        uname = m.group(1).lower()
        if uname not in _SAFE_PATH_USERNAMES:
            findings.append(f"real user path: {m.group(0)}")
    if any(kw in line.lower() for kw in _PHONE_CONTEXT_WORDS):
        for m in _PHONE_RE.finditer(line):
            if m.group(2) == "000" or m.group(3) == "0000":
                continue
            findings.append(f"phone number: {m.group(0).strip()}")
    for m in _SSN_RE.finditer(line):
        findings.append(f"US SSN pattern: {m.group(0)}")
    for m in _CC_RE.finditer(line):
        digits = re.sub(r"[-\s]", "", m.group(0))
        if _luhn_ok(digits):
            findings.append(f"credit card number: {m.group(0)}")
    line_lower = line.lower()
    for term in blocklist:
        if term in line_lower:
            findings.append(f"blocklisted term: {term!r}")
    return findings


# ---------------------------------------------------------------------------
# Diff scanning (pre-commit + CI diff-range mode)
# ---------------------------------------------------------------------------

def _scan_diff(blocklist: list[str], diff_range: str | None = None) -> list[tuple]:
    if diff_range is not None:
        cmd = ["git", "diff", "--unified=0", "--diff-filter=ACMR", f"{diff_range}...HEAD"]
    else:
        cmd = ["git", "diff", "--cached", "--unified=0", "--diff-filter=ACMR"]
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        print(f"pii-lint: 'git diff' failed (exit {result.returncode}); aborting", file=sys.stderr)
        sys.exit(1)
    diff_lines = result.stdout.splitlines()
    violations = []
    current_file = None
    current_lineno = 0
    saw_minus_header = False
    for line in diff_lines:
        if line.startswith("--- "):
            saw_minus_header = True
            continue
        if line.startswith("+++ b/") and saw_minus_header:
            saw_minus_header = False
            current_file = line[6:]
            if any(current_file.endswith(ext) for ext in SKIP_EXTENSIONS):
                current_file = None
            continue
        saw_minus_header = False
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                current_lineno = int(m.group(1)) - 1
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current_lineno += 1
            content = line[1:]
            for finding in _check_line(content, blocklist):
                violations.append((current_file, current_lineno, finding, content.strip()))
        elif not line.startswith("-") and not line.startswith("\\"):
            current_lineno += 1
    return violations


# ---------------------------------------------------------------------------
# Text file scanning (commit-msg, pr-metadata modes)
# ---------------------------------------------------------------------------

def _scan_text_file(path_str: str, blocklist: list[str]) -> list[tuple]:
    path = Path(path_str)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"pii-lint: cannot read file: {exc}", file=sys.stderr)
        return []
    violations = []
    for lineno, raw in enumerate(lines, start=1):
        for finding in _check_line(raw, blocklist):
            violations.append(("(text)", lineno, finding, raw.strip()))
    return violations


# ---------------------------------------------------------------------------
# Output + main
# ---------------------------------------------------------------------------

def _report(violations: list[tuple]) -> None:
    print("pii-lint: commit blocked — personal information detected:\n", file=sys.stderr)
    for filepath, lineno, finding, content in violations:
        print(f"  {filepath}:{lineno}: {finding}", file=sys.stderr)
        snippet = content[:120] + ("…" if len(content) > 120 else "")
        print(f"    {snippet}", file=sys.stderr)
    print(file=sys.stderr)
    print(
        "Replace with placeholders: user@example.com, +1-555-000-0000, 000-00-0000,\n"
        "  /home/user/, [service type], Example User, etc.",
        file=sys.stderr,
    )
    print("Policy: AGENTS.md § Non-negotiables", file=sys.stderr)
    print("Emergency bypass: git commit --no-verify  (avoid; audit if used)", file=sys.stderr)


def main() -> int:
    args = sys.argv[1:]
    blocklist = _get_blocklist()
    if len(args) >= 2 and args[0] == "--commit-msg":
        violations = _scan_text_file(args[1], blocklist)
    elif len(args) >= 2 and args[0] == "--pr-metadata":
        violations = _scan_text_file(args[1], blocklist)
    elif len(args) >= 2 and args[0] == "--diff-range":
        violations = _scan_diff(blocklist, diff_range=args[1])
    else:
        violations = _scan_diff(blocklist)
    if not violations:
        return 0
    _report(violations)
    return 1


if __name__ == "__main__":
    sys.exit(main())
