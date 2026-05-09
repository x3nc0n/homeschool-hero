import json
from pathlib import Path

from scripts.security_automation import (
    TRIAGE_MARKER,
    apply_patch_plan,
    build_patch_plan,
    classify_security_issue,
    parse_security_issue,
    update_npm_specifier,
)


def make_issue(body: str, labels: list[str] | None = None, title: str = '[Security] HIGH: Example') -> dict:
    return {
        'number': 42,
        'title': title,
        'body': body,
        'labels': [{'name': label} for label in (labels or ['security', 'severity:high', 'squad'])],
    }


def test_classify_dependency_issue_as_auto_patchable(tmp_path: Path):
    (tmp_path / 'requirements.txt').write_text('jinja2==3.1.0\n', encoding='utf-8')
    body = '\n'.join(
        [
            '<!-- security-finding:abc123 -->',
            '<!-- security-scanner:trivy -->',
            '',
            '- **Scanner:** Trivy',
            '- **Severity:** HIGH',
            '- **Identifier:** `CVE-2026-77777`',
            '- **Affected location:** `requirements.txt`',
            '- **Affected package:** `jinja2`',
            '- **Installed version:** `3.1.0`',
            '- **Fixed version:** `3.1.6`',
        ]
    )

    result = classify_security_issue(make_issue(body), tmp_path)

    assert result.managed is True
    assert result.category == 'auto-patch-eligible'
    assert result.patch_plan is not None
    assert result.patch_plan.ecosystem == 'pip'
    assert result.patch_plan.manifests == ['requirements.txt']
    assert TRIAGE_MARKER in result.comment_body


def test_classify_codeql_issue_as_human_review(tmp_path: Path):
    body = '\n'.join(
        [
            '<!-- security-finding:def456 -->',
            '<!-- security-scanner:codeql -->',
            '',
            '- **Scanner:** CodeQL',
            '- **Severity:** CRITICAL',
            '- **Identifier:** `py/sql-injection`',
            '- **Affected location:** `backend/routers/auth.py:84`',
            '- **Affected package:** `n/a`',
            '- **Installed version:** `n/a`',
            '- **Fixed version:** `not provided`',
        ]
    )

    result = classify_security_issue(make_issue(body, labels=['security', 'severity:critical', 'squad']), tmp_path)

    assert result.category == 'needs-human-review'
    assert result.patch_plan is None
    assert result.finding_type == 'source-code-finding'


def test_apply_patch_plan_updates_python_requirement(tmp_path: Path):
    requirements = tmp_path / 'requirements.txt'
    requirements.write_text('jinja2==3.1.0\nfastapi==0.115.12\n', encoding='utf-8')
    issue = parse_security_issue(
        make_issue(
            '\n'.join(
                [
                    '<!-- security-finding:abc123 -->',
                    '<!-- security-scanner:trivy -->',
                    '',
                    '- **Scanner:** Trivy',
                    '- **Severity:** HIGH',
                    '- **Identifier:** `CVE-2026-77777`',
                    '- **Affected location:** `requirements.txt`',
                    '- **Affected package:** `jinja2`',
                    '- **Installed version:** `3.1.0`',
                    '- **Fixed version:** `3.1.6`',
                ]
            )
        )
    )

    plan = build_patch_plan(issue, tmp_path)
    assert plan is not None

    changed = apply_patch_plan(plan, tmp_path)

    assert changed == ['requirements.txt']
    assert requirements.read_text(encoding='utf-8').splitlines()[0] == 'jinja2==3.1.6'


def test_apply_patch_plan_updates_npm_dependency_and_preserves_prefix(tmp_path: Path):
    frontend = tmp_path / 'frontend'
    frontend.mkdir()
    package_json = frontend / 'package.json'
    package_json.write_text(
        json.dumps(
            {
                'dependencies': {'vite': '^8.0.10'},
                'devDependencies': {'eslint': '~10.2.1'},
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    issue = parse_security_issue(
        make_issue(
            '\n'.join(
                [
                    '<!-- security-finding:abc123 -->',
                    '<!-- security-scanner:trivy -->',
                    '',
                    '- **Scanner:** Trivy',
                    '- **Severity:** HIGH',
                    '- **Identifier:** `CVE-2026-12345`',
                    '- **Affected location:** `frontend/package.json`',
                    '- **Affected package:** `vite`',
                    '- **Installed version:** `8.0.10`',
                    '- **Fixed version:** `8.0.11`',
                ]
            )
        )
    )

    plan = build_patch_plan(issue, tmp_path)
    assert plan is not None
    assert plan.ecosystem == 'npm'

    changed = apply_patch_plan(plan, tmp_path)
    updated = json.loads(package_json.read_text(encoding='utf-8'))

    assert changed == ['frontend/package.json']
    assert updated['dependencies']['vite'] == '^8.0.11'
    assert update_npm_specifier('~10.2.1', '10.3.0') == '~10.3.0'
