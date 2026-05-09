from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote


MANAGED_LABELS = {
    'security',
    'severity:high',
    'severity:critical',
    'squad',
    'suppressed',
}


def stable_fingerprint(*parts: object) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part or '').encode('utf-8'))
        digest.update(b'\0')
    return digest.hexdigest()[:20]


def normalize_severity(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    if text in {'critical', 'crit'}:
        return 'critical'
    if text in {'high', 'error', 'warning'}:
        return 'high'

    try:
        numeric = float(text)
    except ValueError:
        return None

    if numeric >= 9.0:
        return 'critical'
    if numeric >= 7.0:
        return 'high'
    return None


def parse_trivy_ignorefile(ignorefile_path: str | os.PathLike[str] | None) -> dict[str, str | None]:
    if not ignorefile_path:
        return {}

    path = Path(ignorefile_path)
    if not path.exists():
        return {}

    ignored: dict[str, str | None] = {}
    pending_comments: list[str] = []

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line:
            pending_comments = []
            continue

        if line.startswith('#'):
            comment = line[1:].strip()
            if comment:
                pending_comments.append(comment)
            continue

        entry, _, inline_comment = line.partition('#')
        finding_id = entry.strip()
        if not finding_id:
            pending_comments = []
            continue

        reason_parts = [comment for comment in pending_comments if comment]
        if inline_comment.strip():
            reason_parts.append(inline_comment.strip())

        ignored[finding_id] = ' '.join(reason_parts) or None
        pending_comments = []

    return ignored


def discover_report_files(inputs: list[str], suffixes: tuple[str, ...]) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()
    for raw_input in inputs:
        candidate = Path(raw_input)
        if candidate.is_dir():
            matches = sorted(path for path in candidate.rglob('*') if path.is_file() and path.suffix.lower() in suffixes)
        elif candidate.is_file() and candidate.suffix.lower() in suffixes:
            matches = [candidate]
        else:
            matches = []

        for match in matches:
            resolved = match.resolve()
            if resolved not in seen:
                discovered.append(match)
                seen.add(resolved)
    return discovered


def _rule_descriptor(run: dict[str, Any], rule_id: str) -> dict[str, Any]:
    tool = run.get('tool', {})
    rule_lists = [tool.get('driver', {}).get('rules', [])]
    for extension in tool.get('extensions', []) or []:
        rule_lists.append(extension.get('rules', []))

    for rules in rule_lists:
        for rule in rules or []:
            if rule.get('id') == rule_id:
                return rule
    return {}


def parse_sarif_reports(paths: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for report_path in discover_report_files(paths, ('.sarif',)):
        payload = json.loads(report_path.read_text(encoding='utf-8'))
        for run in payload.get('runs', []):
            tool_name = (run.get('tool', {}).get('driver', {}) or {}).get('name', 'CodeQL')
            for result in run.get('results', []):
                rule_id = result.get('ruleId') or 'unknown-rule'
                rule = _rule_descriptor(run, rule_id)
                properties = result.get('properties', {})
                rule_properties = rule.get('properties', {})
                severity = (
                    normalize_severity(properties.get('security-severity'))
                    or normalize_severity(rule_properties.get('security-severity'))
                    or normalize_severity(properties.get('problem.severity'))
                    or normalize_severity(rule_properties.get('problem.severity'))
                    or normalize_severity(result.get('level'))
                )
                if severity not in {'high', 'critical'}:
                    continue

                location = ((result.get('locations') or [{}])[0] or {}).get('physicalLocation', {}) or {}
                artifact_location = location.get('artifactLocation', {}) or {}
                region = location.get('region', {}) or {}
                path = unquote(artifact_location.get('uri', '')).lstrip('./')
                line = region.get('startLine')
                title = (
                    rule.get('name')
                    or (rule.get('shortDescription') or {}).get('text')
                    or (result.get('message') or {}).get('text')
                    or rule_id
                )
                message = (result.get('message') or {}).get('text') or title
                remediation = (
                    (rule.get('help') or {}).get('markdown')
                    or (rule.get('help') or {}).get('text')
                    or (rule.get('fullDescription') or {}).get('text')
                    or ''
                )
                help_url = rule.get('helpUri')
                fingerprint_source = (
                    (result.get('partialFingerprints') or {}).get('primaryLocationLineHash')
                    or (result.get('fingerprints') or {}).get('primaryLocationLineHash')
                    or stable_fingerprint(tool_name, rule_id, path, line, message)
                )

                findings.append(
                    {
                        'scanner': 'codeql',
                        'title': title,
                        'severity': severity,
                        'identifier': rule_id,
                        'description': message,
                        'remediation': remediation,
                        'help_url': help_url,
                        'location': {
                            'path': path or None,
                            'line': line,
                        },
                        'source': {
                            'tool': tool_name,
                            'report': str(report_path),
                        },
                        'suppressed': False,
                        'suppression_reason': None,
                        'fingerprint': stable_fingerprint('codeql', rule_id, path, line, fingerprint_source),
                    }
                )

    return findings


def parse_trivy_reports(paths: list[str], ignorefile_path: str | None = None) -> list[dict[str, Any]]:
    ignored = parse_trivy_ignorefile(ignorefile_path)
    findings: list[dict[str, Any]] = []

    for report_path in discover_report_files(paths, ('.json',)):
        payload = json.loads(report_path.read_text(encoding='utf-8'))
        for result in payload.get('Results', []) or []:
            target = result.get('Target')
            target_class = result.get('Class')
            for vulnerability in result.get('Vulnerabilities', []) or []:
                severity = normalize_severity(vulnerability.get('Severity'))
                if severity not in {'high', 'critical'}:
                    continue

                vulnerability_id = vulnerability.get('VulnerabilityID') or 'unknown-vulnerability'
                title = vulnerability.get('Title') or vulnerability_id
                package_name = vulnerability.get('PkgName')
                installed_version = vulnerability.get('InstalledVersion')
                fixed_version = vulnerability.get('FixedVersion')
                description = vulnerability.get('Description') or title
                remediation_parts = []
                if fixed_version:
                    remediation_parts.append(f'Upgrade to {fixed_version}.')
                if vulnerability.get('PrimaryURL'):
                    remediation_parts.append(f"Reference: {vulnerability['PrimaryURL']}")
                remediation = ' '.join(remediation_parts)
                suppression_reason = ignored.get(vulnerability_id)

                findings.append(
                    {
                        'scanner': 'trivy',
                        'title': title,
                        'severity': severity,
                        'identifier': vulnerability_id,
                        'description': description,
                        'remediation': remediation,
                        'help_url': vulnerability.get('PrimaryURL'),
                        'package': package_name,
                        'installed_version': installed_version,
                        'fixed_version': fixed_version,
                        'location': {
                            'path': target,
                            'line': None,
                            'class': target_class,
                        },
                        'source': {
                            'tool': 'Trivy',
                            'report': str(report_path),
                        },
                        'suppressed': vulnerability_id in ignored,
                        'suppression_reason': suppression_reason,
                        'fingerprint': stable_fingerprint(
                            'trivy',
                            vulnerability_id,
                            target,
                            package_name,
                            installed_version,
                        ),
                    }
                )

    return findings


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for finding in findings:
        fingerprint = finding['fingerprint']
        existing = deduped.get(fingerprint)
        if not existing:
            deduped[fingerprint] = finding
            continue

        existing_path = (existing.get('location') or {}).get('path') or ''
        new_path = (finding.get('location') or {}).get('path') or ''
        if new_path and not existing_path:
            deduped[fingerprint] = finding

    return sorted(deduped.values(), key=lambda item: (item['scanner'], item['severity'], item['title'], item['fingerprint']))


def likely_owner_hint(path: str | None) -> str:
    normalized = (path or '').replace('\\', '/').lstrip('./').lower()
    if normalized.startswith(('python:', 'node:', 'ghcr.io/', 'docker.io/')) or ('/' not in normalized and ':' in normalized):
        return 'Likely owner: Winston (Tester) — container image or scanner configuration.'
    if normalized.startswith('backend/'):
        return 'Likely owner: Ray (Backend Dev) — backend API or service code.'
    if normalized.startswith('frontend/'):
        return 'Likely owner: Venkman (Frontend Dev) — frontend client code.'
    if normalized.startswith('.github/') or normalized.startswith('scripts/') or normalized.startswith('docs/') or normalized in {'dockerfile', 'docker-compose.yml', '.trivyignore'}:
        return 'Likely owner: Winston (Tester) — CI, security automation, or release tooling.'
    return 'Likely owner: Egon (Lead) — review and route this finding if ownership is unclear.'


def issue_title_for_finding(finding: dict[str, Any]) -> str:
    return f"[Security] {finding['severity'].upper()}: {finding['title']}"


def issue_labels_for_finding(finding: dict[str, Any]) -> list[str]:
    labels = ['security', f"severity:{finding['severity']}", 'squad']
    if finding.get('suppressed'):
        labels.append('suppressed')
    return labels


def render_issue_body(finding: dict[str, Any], scan_run_url: str, scan_date: str) -> str:
    location = finding.get('location') or {}
    path = location.get('path') or 'n/a'
    line = location.get('line')
    location_text = f'{path}:{line}' if path and line else path
    package_name = finding.get('package') or 'n/a'
    installed_version = finding.get('installed_version') or 'n/a'
    fixed_version = finding.get('fixed_version') or 'not provided'
    suppression_reason = finding.get('suppression_reason')
    if finding.get('suppressed') and not suppression_reason:
        suppression_reason = 'MISSING — document the explicit false-positive or accepted-risk reason before keeping this suppression.'

    suppression_status = 'Active suppression detected.' if finding.get('suppressed') else 'No active suppression recorded.'

    return '\n'.join(
        [
            f"<!-- security-finding:{finding['fingerprint']} -->",
            f"<!-- security-scanner:{finding['scanner']} -->",
            '',
            '## Finding summary',
            '',
            f"- **Scanner:** {finding['source']['tool']}",
            f"- **Severity:** {finding['severity'].upper()}",
            f"- **Identifier:** `{finding['identifier']}`",
            f"- **Affected location:** `{location_text}`",
            f"- **Affected package:** `{package_name}`",
            f"- **Installed version:** `{installed_version}`",
            f"- **Fixed version:** `{fixed_version}`",
            f"- **Likely owner hint:** {likely_owner_hint(location.get('path'))}",
            f"- **Latest scan run:** [workflow run]({scan_run_url})",
            f"- **Latest scan date:** {scan_date}",
            '',
            '## Details',
            '',
            finding.get('description') or 'No additional details were provided by the scanner.',
            '',
            '## Remediation guidance',
            '',
            finding.get('remediation') or 'Review the scanner output, validate the impacted code or dependency, and apply the least-risk fix available.',
            '',
            '## Suppression instructions',
            '',
            '- Trivy false positives must be added to `.trivyignore` with an adjacent comment explaining the reason for the suppression.',
            '- CodeQL false positives must document the reason here before using an inline `// codeql[suppress]` annotation.',
            f'- **Suppression status:** {suppression_status}',
            f"- **Suppression reason:** {suppression_reason or 'Not suppressed.'}",
            '',
            '> If this finding is intentionally suppressed, keep the `suppressed` label on this issue and update the reason before closing it.',
        ]
    ).strip()
