from pathlib import Path

from scripts.security_issue_utils import (
    issue_labels_for_finding,
    parse_sarif_reports,
    parse_trivy_reports,
    render_issue_body,
)


FIXTURES = Path(__file__).parent / 'fixtures' / 'security'


def test_parse_sarif_reports_filters_to_high_and_critical():
    findings = parse_sarif_reports([str(FIXTURES / 'codeql.sarif')])

    assert len(findings) == 2
    assert {finding['severity'] for finding in findings} == {'high', 'critical'}
    assert findings[0]['scanner'] == 'codeql'
    assert any(finding['location']['path'] == 'backend/routers/auth.py' for finding in findings)


def test_parse_trivy_reports_tracks_suppressions_and_reasons():
    findings = parse_trivy_reports(
        [str(FIXTURES / 'trivy-results.json')],
        str(FIXTURES / '.trivyignore'),
    )

    assert len(findings) == 2
    suppressed = next(finding for finding in findings if finding['identifier'] == 'CVE-2026-12345')
    unsuppressed = next(finding for finding in findings if finding['identifier'] == 'CVE-2026-77777')

    assert suppressed['suppressed'] is True
    assert 'pending upstream' in suppressed['suppression_reason']
    assert unsuppressed['suppressed'] is False


def test_issue_body_and_labels_include_suppression_guidance():
    finding = parse_trivy_reports(
        [str(FIXTURES / 'trivy-results.json')],
        str(FIXTURES / '.trivyignore'),
    )[0]

    body = render_issue_body(
        finding,
        scan_run_url='https://github.com/x3nc0n/homeschool-hero/actions/runs/123',
        scan_date='2026-05-08T23:15:58Z',
    )
    labels = issue_labels_for_finding(finding)

    assert '[workflow run]' in body
    assert 'Suppression reason' in body
    assert 'Ray (Backend Dev)' not in body
    assert 'Winston (Tester)' in body
    assert labels == ['security', 'severity:critical', 'squad', 'suppressed']
