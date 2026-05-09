from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


MANAGED_REQUIREMENT_FILES = (
    'requirements.txt',
    'requirements-prod.txt',
    'backend/requirements-test.txt',
)
MANAGED_NPM_FILES = ('frontend/package.json',)
TRIAGE_MARKER = '<!-- squad-security-triage -->'

SCANNER_RE = re.compile(r'<!-- security-scanner:([a-z0-9_-]+) -->')
FINGERPRINT_RE = re.compile(r'<!-- security-finding:([a-f0-9]+) -->')
FIELD_RE = re.compile(r'^- \*\*(.+?):\*\* (.+)$', re.MULTILINE)
LOCATION_LINE_RE = re.compile(r'^(?P<path>.+?)(?::(?P<line>\d+))?$')
REQUIREMENT_RE = re.compile(
    r'^(?P<indent>\s*)(?P<name>[A-Za-z0-9_.-]+(?:\[[^\]]+\])?)(?P<specifier>[^#;\r\n]*)(?P<suffix>\s*(?:;[^\r\n#]+)?\s*(?:#.*)?)$'
)
REQ_SPEC_PART_RE = re.compile(r'(?P<op>===|==|>=|<=|~=|!=|>|<)\s*(?P<version>[^,\s]+)')
SIMPLE_NPM_SPEC_RE = re.compile(r'^(?P<prefix>\^|~)?(?P<version>\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?)$')


def normalize_package_name(value: str | None) -> str:
    return (value or '').strip().lower().replace('_', '-')


def _strip_markdown(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.startswith('`') and cleaned.endswith('`'):
        cleaned = cleaned[1:-1]
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
    return cleaned.strip() or None


@dataclass
class RequirementTarget:
    path: str
    line_number: int
    requirement_name: str
    current_specifier: str
    update_mode: str


@dataclass
class NpmTarget:
    path: str
    section: str
    current_specifier: str
    update_mode: str


@dataclass
class PatchPlan:
    ecosystem: str
    package_name: str
    fixed_version: str
    manifests: list[str]
    pip_targets: list[RequirementTarget] = field(default_factory=list)
    npm_targets: list[NpmTarget] = field(default_factory=list)
    branch_name: str | None = None
    commit_message: str | None = None
    pr_title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['manifests'] = list(self.manifests)
        return payload


@dataclass
class TriageResult:
    managed: bool
    category: str
    severity: str | None
    scanner: str | None
    finding_type: str
    affected_file: str | None
    affected_package: str | None
    analysis: list[str]
    labels_to_add: list[str]
    labels_to_remove: list[str]
    comment_body: str
    patch_plan: PatchPlan | None = None
    requires_explicit_human_review: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.patch_plan:
            payload['patch_plan'] = self.patch_plan.to_dict()
        return payload


def parse_issue_body(body: str | None) -> dict[str, str | None]:
    text = body or ''
    fields: dict[str, str | None] = {}
    for label, value in FIELD_RE.findall(text):
        fields[label.strip().lower()] = _strip_markdown(value)

    location = fields.get('affected location') or 'n/a'
    location_match = LOCATION_LINE_RE.match(location) if location and location != 'n/a' else None
    if location_match:
        fields['affected_path'] = location_match.group('path')
        fields['affected_line'] = location_match.group('line')
    else:
        fields['affected_path'] = None
        fields['affected_line'] = None

    scanner_match = SCANNER_RE.search(text)
    fingerprint_match = FINGERPRINT_RE.search(text)
    fields['scanner_marker'] = scanner_match.group(1) if scanner_match else None
    fields['fingerprint'] = fingerprint_match.group(1) if fingerprint_match else None
    return fields


def parse_security_issue(issue: dict[str, Any]) -> dict[str, Any]:
    body_fields = parse_issue_body(issue.get('body'))
    labels = [label['name'] for label in issue.get('labels', [])]
    severity_label = next((label.split(':', 1)[1] for label in labels if label.startswith('severity:')), None)
    severity = (body_fields.get('severity') or severity_label or '').lower() or None
    scanner = body_fields.get('scanner_marker') or (body_fields.get('scanner') or '').lower() or None
    scanner = scanner.lower() if scanner else None
    if scanner == 'trivy':
        scanner_display = 'Trivy'
    elif scanner == 'codeql':
        scanner_display = 'CodeQL'
    else:
        scanner_display = body_fields.get('scanner')

    return {
        'number': issue.get('number'),
        'title': issue.get('title'),
        'body': issue.get('body') or '',
        'labels': labels,
        'severity': severity,
        'scanner': scanner,
        'scanner_display': scanner_display,
        'identifier': body_fields.get('identifier'),
        'affected_location': body_fields.get('affected location'),
        'affected_path': body_fields.get('affected_path'),
        'affected_line': body_fields.get('affected_line'),
        'package_name': body_fields.get('affected package'),
        'installed_version': body_fields.get('installed version'),
        'fixed_version': body_fields.get('fixed version'),
        'fingerprint': body_fields.get('fingerprint'),
    }


def _requirement_update_mode(specifier: str) -> str | None:
    spec = (specifier or '').strip()
    if not spec:
        return None
    parts = list(REQ_SPEC_PART_RE.finditer(spec))
    if not parts:
        return None
    first = parts[0]
    if first.start() != 0:
        return None
    if first.group('op') == '==':
        return 'exact'
    if first.group('op') == '>=':
        disallowed = {match.group('op') for match in parts[1:]} - {'<', '<='}
        return None if disallowed else 'minimum'
    return None


def _find_requirement_targets(repo_root: Path, package_name: str) -> list[RequirementTarget]:
    normalized_package = normalize_package_name(package_name)
    targets: list[RequirementTarget] = []
    for relative_path in MANAGED_REQUIREMENT_FILES:
        path = repo_root / relative_path
        if not path.exists():
            continue
        for index, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
            match = REQUIREMENT_RE.match(line)
            if not match:
                continue
            requirement_name = match.group('name')
            base_name = normalize_package_name(requirement_name.split('[', 1)[0])
            if base_name != normalized_package:
                continue
            update_mode = _requirement_update_mode(match.group('specifier'))
            if not update_mode:
                continue
            targets.append(
                RequirementTarget(
                    path=relative_path,
                    line_number=index,
                    requirement_name=requirement_name,
                    current_specifier=match.group('specifier').strip(),
                    update_mode=update_mode,
                )
            )
    return targets


def _find_npm_targets(repo_root: Path, package_name: str) -> list[NpmTarget]:
    normalized_package = normalize_package_name(package_name)
    targets: list[NpmTarget] = []
    for relative_path in MANAGED_NPM_FILES:
        path = repo_root / relative_path
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding='utf-8'))
        for section in ('dependencies', 'devDependencies'):
            entries = payload.get(section) or {}
            for dependency_name, specifier in entries.items():
                if normalize_package_name(dependency_name) != normalized_package:
                    continue
                update_mode = _npm_update_mode(str(specifier))
                if not update_mode:
                    continue
                targets.append(
                    NpmTarget(
                        path=relative_path,
                        section=section,
                        current_specifier=str(specifier),
                        update_mode=update_mode,
                    )
                )
    return targets


def _npm_update_mode(specifier: str) -> str | None:
    return 'semver' if SIMPLE_NPM_SPEC_RE.match((specifier or '').strip()) else None


def build_patch_plan(issue: dict[str, Any], repo_root: Path | str = '.') -> PatchPlan | None:
    repo_root = Path(repo_root)
    package_name = issue.get('package_name')
    fixed_version = issue.get('fixed_version')
    scanner = issue.get('scanner')
    if scanner != 'trivy' or not package_name or not fixed_version or fixed_version == 'not provided':
        return None

    pip_targets = _find_requirement_targets(repo_root, package_name)
    npm_targets = _find_npm_targets(repo_root, package_name)
    ecosystems = {'pip' if pip_targets else None, 'npm' if npm_targets else None} - {None}
    if len(ecosystems) != 1:
        return None

    ecosystem = next(iter(ecosystems))
    manifests = sorted({target.path for target in (pip_targets if ecosystem == 'pip' else npm_targets)})
    issue_number = issue.get('number') or 'unknown'
    safe_package_slug = re.sub(r'[^a-z0-9]+', '-', normalize_package_name(package_name)).strip('-') or 'dependency'
    branch_name = f'squad/auto-patch-issue-{issue_number}-{safe_package_slug}'
    title = issue.get('title') or f'[Security] {package_name}'
    commit_message = f"chore(security): patch issue #{issue_number} ({package_name})"
    pr_title = f"{title} [auto-patch]"
    return PatchPlan(
        ecosystem=ecosystem,
        package_name=package_name,
        fixed_version=fixed_version,
        manifests=manifests,
        pip_targets=pip_targets,
        npm_targets=npm_targets,
        branch_name=branch_name,
        commit_message=commit_message,
        pr_title=pr_title,
    )


def _replace_requirement_specifier(specifier: str, fixed_version: str) -> str:
    parts = list(REQ_SPEC_PART_RE.finditer(specifier.strip()))
    if not parts:
        raise ValueError(f'Unsupported requirement specifier: {specifier}')

    first = parts[0]
    op = first.group('op')
    updated_first = f'{op}{fixed_version}'
    if op == '>=':
        remaining = specifier.strip()[first.end() :]
        return f'{updated_first}{remaining}'
    if op == '==':
        remaining = specifier.strip()[first.end() :]
        return f'{updated_first}{remaining}'
    raise ValueError(f'Unsupported requirement update operator: {op}')


def apply_patch_plan(plan: PatchPlan, repo_root: Path | str = '.') -> list[str]:
    repo_root = Path(repo_root)
    changed_files: list[str] = []
    if plan.ecosystem == 'pip':
        by_path: dict[str, list[RequirementTarget]] = {}
        for target in plan.pip_targets:
            by_path.setdefault(target.path, []).append(target)
        for relative_path, targets in by_path.items():
            path = repo_root / relative_path
            lines = path.read_text(encoding='utf-8').splitlines()
            changed = False
            for target in targets:
                index = target.line_number - 1
                original_line = lines[index]
                match = REQUIREMENT_RE.match(original_line)
                if not match:
                    continue
                new_specifier = _replace_requirement_specifier(match.group('specifier'), plan.fixed_version)
                updated_line = (
                    f"{match.group('indent')}{match.group('name')}{new_specifier}{match.group('suffix')}"
                )
                if updated_line != original_line:
                    lines[index] = updated_line
                    changed = True
            if changed:
                path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                changed_files.append(relative_path)
        return changed_files

    if plan.ecosystem == 'npm':
        for target in plan.npm_targets:
            path = repo_root / target.path
            payload = json.loads(path.read_text(encoding='utf-8'))
            current = payload[target.section][plan.package_name]
            payload[target.section][plan.package_name] = update_npm_specifier(str(current), plan.fixed_version)
            path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
            if target.path not in changed_files:
                changed_files.append(target.path)
        return changed_files

    raise ValueError(f'Unsupported ecosystem: {plan.ecosystem}')


def update_npm_specifier(current_specifier: str, fixed_version: str) -> str:
    match = SIMPLE_NPM_SPEC_RE.match((current_specifier or '').strip())
    if not match:
        raise ValueError(f'Unsupported npm specifier: {current_specifier}')
    prefix = match.group('prefix') or ''
    return f'{prefix}{fixed_version}'


def render_triage_comment(issue: dict[str, Any], result: TriageResult) -> str:
    severity = (result.severity or 'unknown').upper()
    scanner = issue.get('scanner_display') or (result.scanner or 'unknown')
    affected_file = result.affected_file or 'n/a'
    affected_package = result.affected_package or 'n/a'
    decision = result.category.replace('-', ' ')
    lines = [
        TRIAGE_MARKER,
        '### 🛡️ Squad Security Triage',
        '',
        f"- **Severity:** {severity}",
        f"- **Scanner:** {scanner}",
        f"- **Affected file:** `{affected_file}`",
        f"- **Affected package:** `{affected_package}`",
        f"- **Finding type:** `{result.finding_type}`",
        f"- **Decision:** `{decision}`",
    ]
    if result.patch_plan:
        manifests = ', '.join(f'`{manifest}`' for manifest in result.patch_plan.manifests)
        lines.extend(
            [
                f"- **Auto-patch strategy:** `{result.patch_plan.ecosystem}` direct dependency bump",
                f"- **Managed manifests:** {manifests}",
            ]
        )
    lines.extend(
        [
            '',
            '**Why this was routed this way**',
            '',
            *[f'- {reason}' for reason in result.analysis],
            '',
            '**Safety gates**',
            '',
            '- Automation is limited to direct dependency version bumps in tracked manifests.',
            '- Full CI-equivalent validation runs before an auto-generated PR is opened.',
            '- Critical findings and all non-dependency findings still require explicit human review before merge.',
        ]
    )
    return '\n'.join(lines)


def classify_security_issue(issue_payload: dict[str, Any], repo_root: Path | str = '.') -> TriageResult:
    issue = parse_security_issue(issue_payload)
    labels = set(issue['labels'])
    is_security_issue = 'security' in labels or str(issue.get('title') or '').startswith('[Security]')
    if not is_security_issue:
        return TriageResult(
            managed=False,
            category='ignored',
            severity=issue.get('severity'),
            scanner=issue.get('scanner'),
            finding_type='non-security-issue',
            affected_file=issue.get('affected_path'),
            affected_package=issue.get('package_name'),
            analysis=['Issue is not part of the managed security issue stream.'],
            labels_to_add=[],
            labels_to_remove=[],
            comment_body='',
        )

    analysis: list[str] = []
    finding_type = 'unknown-security-finding'
    patch_plan = build_patch_plan(issue, repo_root)

    if issue['scanner'] == 'trivy' and patch_plan:
        finding_type = 'dependency-update'
        analysis.append(
            f"Trivy reported `{issue['package_name']}` with a published fixed version `{issue['fixed_version']}`."
        )
        analysis.append(
            f"Automation found a direct {patch_plan.ecosystem} manifest match in {', '.join(patch_plan.manifests)}."
        )
        analysis.append('The change can be limited to a manifest version bump plus standard CI validation.')
        result = TriageResult(
            managed=True,
            category='auto-patch-eligible',
            severity=issue.get('severity'),
            scanner=issue.get('scanner'),
            finding_type=finding_type,
            affected_file=issue.get('affected_path'),
            affected_package=issue.get('package_name'),
            analysis=analysis,
            labels_to_add=['auto-patch-eligible'],
            labels_to_remove=['needs-human-review'],
            comment_body='',
            patch_plan=patch_plan,
            requires_explicit_human_review=True,
        )
        result.comment_body = render_triage_comment(issue, result)
        return result

    if issue['scanner'] == 'trivy':
        affected_path = issue.get('affected_path') or 'n/a'
        if affected_path.startswith(('python:', 'node:', 'ghcr.io/', 'docker.io/')):
            finding_type = 'container-image-vulnerability'
            analysis.append(
                'The finding affects a container or OS package rather than a tracked application dependency manifest.'
            )
            analysis.append('Container base image refreshes can change multiple packages and require human validation.')
        else:
            finding_type = 'dependency-update'
            analysis.append('The finding is dependency-related, but the package is not a direct safe-match in a managed manifest.')
            analysis.append('Transitive or ambiguous dependency updates are routed to a human for review.')
    elif issue['scanner'] == 'codeql':
        finding_type = 'source-code-finding'
        analysis.append('CodeQL findings point to source-code behavior, data flow, or security design decisions.')
        analysis.append('These require a human to validate the exploit path and choose the least-risk remediation.')
    else:
        analysis.append('The issue did not expose enough normalized metadata to prove a low-risk automated fix path.')
        analysis.append('Unknown scanners and incomplete finding records default to human review.')

    result = TriageResult(
        managed=True,
        category='needs-human-review',
        severity=issue.get('severity'),
        scanner=issue.get('scanner'),
        finding_type=finding_type,
        affected_file=issue.get('affected_path'),
        affected_package=issue.get('package_name'),
        analysis=analysis,
        labels_to_add=['needs-human-review'],
        labels_to_remove=['auto-patch-eligible'],
        comment_body='',
        patch_plan=None,
        requires_explicit_human_review=True,
    )
    result.comment_body = render_triage_comment(issue, result)
    return result


def load_issue_event(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    return payload['issue']
