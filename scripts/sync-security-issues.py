from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any
from urllib import error, parse, request

if __package__ in {None, ''}:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.security_issue_utils import MANAGED_LABELS, issue_labels_for_finding, issue_title_for_finding, render_issue_body


FINGERPRINT_RE = re.compile(r'<!-- security-finding:([a-f0-9]+) -->')
SCANNER_RE = re.compile(r'<!-- security-scanner:([a-z0-9_-]+) -->')


def github_request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = request.Request(
        url,
        data=data,
        method=method,
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'homeschool-hero-security-automation',
        },
    )
    with request.urlopen(req) as response:
        if response.status == 204:
            return None
        body = response.read()
        return json.loads(body.decode('utf-8')) if body else None


def load_findings(paths: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in paths:
        with open(path, encoding='utf-8') as handle:
            findings.extend(json.load(handle))
    return findings


def list_open_security_issues(api_url: str, repository: str, token: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        query = parse.urlencode(
            {
                'state': 'open',
                'labels': 'security',
                'per_page': 100,
                'page': page,
            }
        )
        url = f'{api_url}/repos/{repository}/issues?{query}'
        batch = github_request('GET', url, token)
        batch = [issue for issue in batch if 'pull_request' not in issue]
        issues.extend(batch)
        if len(batch) < 100:
            return issues
        page += 1


def extract_marker(pattern: re.Pattern[str], text: str | None) -> str | None:
    if not text:
        return None
    match = pattern.search(text)
    return match.group(1) if match else None


def merge_labels(existing: list[dict[str, Any]], desired: list[str]) -> list[str]:
    labels = [label['name'] for label in existing if label['name'] not in MANAGED_LABELS]
    for label in desired:
        if label not in labels:
            labels.append(label)
    return labels


def issue_comment_for_finding(finding: dict[str, Any], scan_run_url: str, scan_date: str) -> str:
    if finding.get('suppressed'):
        reason = finding.get('suppression_reason') or 'MISSING — update the issue before keeping this suppression.'
        return f"Still detected in the latest security scan on {scan_date}. Suppression remains active: {reason}\n\nScan run: {scan_run_url}"
    return f"Still detected in the latest security scan on {scan_date}.\n\nScan run: {scan_run_url}"


def resolved_comment(scan_run_url: str, scan_date: str) -> str:
    return f"Automatically closing this issue because the finding was not present in the latest completed security scan on {scan_date}.\n\nScan run: {scan_run_url}"


def main() -> int:
    parser = argparse.ArgumentParser(description='Create, update, and close GitHub issues for security findings.')
    parser.add_argument('--findings', nargs='+', action='append', required=True, help='Normalized finding JSON file(s)')
    parser.add_argument('--scanner-present', action='append', default=[], help='Scanner names represented by the downloaded artifacts')
    parser.add_argument('--scan-run-url', required=True, help='Workflow run URL')
    parser.add_argument('--scan-date', required=True, help='Workflow completion timestamp')
    args = parser.parse_args()

    token = os.environ.get('GITHUB_TOKEN')
    repository = os.environ.get('GITHUB_REPOSITORY')
    api_url = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
    if not token or not repository:
        print('GITHUB_TOKEN and GITHUB_REPOSITORY are required.', file=sys.stderr)
        return 2

    finding_paths = [path for group in args.findings for path in group]
    findings = load_findings(finding_paths)
    open_issues = list_open_security_issues(api_url, repository, token)

    issues_by_fingerprint: dict[str, dict[str, Any]] = {}
    issues_by_title: dict[str, dict[str, Any]] = {}
    for issue in open_issues:
        fingerprint = extract_marker(FINGERPRINT_RE, issue.get('body'))
        if fingerprint:
            issues_by_fingerprint[fingerprint] = issue
        issues_by_title.setdefault(issue['title'], issue)

    created = 0
    updated = 0
    closed = 0
    missing_reasons: list[str] = []
    active_scanners = set(args.scanner_present)
    fingerprints_by_scanner: dict[str, set[str]] = {scanner: set() for scanner in active_scanners}

    for finding in findings:
        fingerprints_by_scanner.setdefault(finding['scanner'], set()).add(finding['fingerprint'])
        title = issue_title_for_finding(finding)
        desired_body = render_issue_body(finding, args.scan_run_url, args.scan_date)
        desired_labels = issue_labels_for_finding(finding)
        existing = issues_by_fingerprint.get(finding['fingerprint']) or issues_by_title.get(title)

        if finding.get('suppressed') and not finding.get('suppression_reason'):
            missing_reasons.append(finding['identifier'])

        if existing:
            github_request(
                'PATCH',
                f"{api_url}/repos/{repository}/issues/{existing['number']}",
                token,
                {
                    'title': title,
                    'body': desired_body,
                    'labels': merge_labels(existing.get('labels', []), desired_labels),
                },
            )
            github_request(
                'POST',
                f"{api_url}/repos/{repository}/issues/{existing['number']}/comments",
                token,
                {'body': issue_comment_for_finding(finding, args.scan_run_url, args.scan_date)},
            )
            updated += 1
            continue

        github_request(
            'POST',
            f'{api_url}/repos/{repository}/issues',
            token,
            {
                'title': title,
                'body': desired_body,
                'labels': desired_labels,
            },
        )
        created += 1

    for issue in open_issues:
        fingerprint = extract_marker(FINGERPRINT_RE, issue.get('body'))
        scanner = extract_marker(SCANNER_RE, issue.get('body'))
        labels = {label['name'] for label in issue.get('labels', [])}
        if not fingerprint or not scanner or scanner not in active_scanners:
            continue
        if 'suppressed' in labels:
            continue
        if fingerprint in fingerprints_by_scanner.get(scanner, set()):
            continue

        github_request(
            'POST',
            f"{api_url}/repos/{repository}/issues/{issue['number']}/comments",
            token,
            {'body': resolved_comment(args.scan_run_url, args.scan_date)},
        )
        github_request(
            'PATCH',
            f"{api_url}/repos/{repository}/issues/{issue['number']}",
            token,
            {'state': 'closed'},
        )
        closed += 1

    print(f'Created {created} issue(s), updated {updated} issue(s), closed {closed} issue(s).')
    if missing_reasons:
        print(
            'Suppressed findings are missing explicit reasons: '
            + ', '.join(sorted(set(missing_reasons))),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except error.HTTPError as exc:
        details = exc.read().decode('utf-8', errors='replace')
        print(f'GitHub API request failed: {exc.code} {exc.reason}\n{details}', file=sys.stderr)
        raise
