# Security scanning

This repository uses a layered security scanning stack as of 2026-05-08.

## Scanning overview

| Tool | Trigger | Coverage | Output | Blocking policy |
| --- | --- | --- | --- | --- |
| CodeQL | Pull requests to `main`, weekly schedule, manual dispatch | Python backend and JavaScript/TypeScript frontend source analysis | GitHub Security tab + SARIF artifacts for issue automation | Findings are triaged by severity; critical and high findings open or refresh GitHub issues until resolved or explicitly accepted |
| Trivy | CI container checks on pushes and pull requests, plus the Security workflow image scan | Built Docker image, including OS packages and application libraries | Job logs, SARIF in the GitHub Security tab, and JSON artifacts for issue automation | `HIGH` and `CRITICAL` vulnerabilities fail policy checks unless the exact CVE is listed in `.trivyignore` |
| Security issue sync | After the `Security` workflow completes | High/critical CodeQL and Trivy findings | GitHub issues labeled `security`, `severity:*`, and `squad` | Creates or refreshes one issue per finding, comments on repeats, and closes resolved issues automatically |
| Gitleaks | Pull requests via CI and optional local pre-commit hook | Git history and committed files for secrets | CI summary and workflow artifacts | Any verified secret finding blocks merge and requires rotation/removal |
| Dependabot | Weekly schedule | Root pip dependencies, backend test pip dependencies, frontend npm dependencies, GitHub Actions | Dependabot pull requests | Updates must pass the full CI and security stack before merge |

## CodeQL

- Workflow: `.github/workflows/security.yml`
- Languages: `python`, `javascript-typescript`
- Query suites: `security-extended` and `security-and-quality`
- Purpose: catch unsafe server-side patterns, insecure dependency usage, client-side injection paths, and general code quality issues that can become vulnerabilities
- Issue automation: `.github/workflows/security-issues.yml` parses uploaded SARIF artifacts after each completed security run

### Handling CodeQL findings

1. Read the alert in the GitHub Security tab and confirm the data flow or source/sink path.
2. Fix the code first when the alert is valid.
3. If the alert is a false positive, document the reason in the linked GitHub issue first, add the `suppressed` label, and only then use an inline `// codeql[suppress]` annotation or dismiss the alert in GitHub.
4. Re-run the workflow or confirm the next scheduled run closes the alert after the code change lands.

## Trivy container scanning

- Workflow: `.github/workflows/ci.yml` (`Container checks`)
- Secondary workflow: `.github/workflows/security.yml` (`Trivy image scan`) uploads JSON for issue routing after each security run
- Scan target: the built `homeschool-hero:ci` Docker image
- Scan scope: OS packages and application libraries
- Severity gate: fails on `HIGH` and `CRITICAL`

### Trivy suppression policy

- Use `.trivyignore` only for reviewed exceptions.
- Every ignored CVE must be preceded by a comment line that explains the false positive or accepted-risk reason; the issue automation copies that reason into the linked `suppressed` issue.
- Every ignored CVE must have an owner, remediation plan, and a follow-up issue or note in the pull request that introduced the exception.
- Remove the ignore entry as soon as the base image or dependency upgrade is available.

Example:

```text
# Base image package has no fixed release yet; re-check next weekly image refresh.
CVE-2026-12345
```

## Issue routing behavior

- Title format: `[Security] {SEVERITY}: {finding title}`
- Labels: `security`, `severity:high` or `severity:critical`, and `squad`
- Suppressed findings also receive the `suppressed` label and must keep the explicit reason in the issue body
- The issue body includes the latest scan run link, affected location, remediation guidance, and a likely owner hint based on the touched path
- Repeated detections add a comment instead of creating a duplicate issue
- Resolved findings close automatically on the next completed security run unless the issue is intentionally kept open with `suppressed`

## Auto-triage workflow

- Workflow: `.github/workflows/squad-security-triage.yml`
- Trigger: security issue `opened`, `edited`, `reopened`, or newly `labeled`
- Output labels:
  - `auto-patch-eligible` for direct dependency bumps with a safe fixed version in a tracked manifest
  - `needs-human-review` for CodeQL findings, container/base-image updates, transitive dependency issues, architecture changes, and anything ambiguous
- Audit trail: the workflow upserts a `<!-- squad-security-triage -->` comment that records severity, affected file, finding type, routing decision, and the safety gates that were applied

### Current auto-patch eligibility rules

1. The finding must come from Trivy and include an explicit fixed version.
2. The vulnerable package must be a direct dependency in one managed manifest:
   - `requirements.txt`
   - `requirements-prod.txt`
   - `backend/requirements-test.txt`
   - `frontend/package.json`
3. The required version change must be a manifest-only bump that preserves the existing safe specifier pattern (`==`, `>=...`, `^`, or `~`).
4. Everything else defaults to `needs-human-review`.

## Auto-patch workflow

- Workflow: `.github/workflows/squad-auto-patch.yml`
- Trigger: issue labeled `auto-patch-eligible`
- Guardrails:
  - Respects repository variable `SQUAD_AUTO_PATCH_ENABLED`; set it to `false` to disable patch generation without turning off triage
  - Applies only direct dependency version bumps
  - Uses ecosystem tooling for the targeted package (`pip install --upgrade` for Python or `npm update` for frontend packages)
  - Runs the local mirror of the required CI gates before it opens a PR:
    - backend pytest + coverage gate
    - migration lint + upgrade/downgrade verification
    - frontend lint + build
    - Docker build
    - Trivy HIGH/CRITICAL image policy
    - Gitleaks secret scan
- Output:
  - creates a branch named `squad/auto-patch-issue-{issue}-{package}`
  - opens an auto-generated PR only after every gate above passes
  - labels the PR with `auto-patch` for visibility
  - comments back on the originating issue with the PR link

### PR review and approval policy

- **Never auto-merge high-risk findings.** Critical severity findings, CodeQL findings, design-level issues, and any patch that is not a direct manifest bump require explicit human review before merge.
- Low-risk dependency-only auto-patch PRs are the only class eligible for optional GitHub auto-merge, but this workflow does **not** enable auto-merge on its own.
- Reviewers should confirm the generated PR still references the original issue, limits the diff to dependency files, and keeps all CI checks green on the PR itself.

### How to disable auto-patching

1. Open repository **Settings → Secrets and variables → Actions → Variables**.
2. Create or update `SQUAD_AUTO_PATCH_ENABLED=false`.
3. Leave the triage workflow enabled so issues still receive `needs-human-review` or `auto-patch-eligible` analysis comments.
4. Re-enable by deleting the variable or setting it back to `true`.

## Gitleaks secret detection

- Workflow: `.github/workflows/ci.yml` (`Secret scan`)
- Config: `.gitleaks.toml`
- Local developer option: pre-commit hook in `README.md`

### What Gitleaks is expected to catch

- API keys
- access tokens
- passwords
- secret keys
- repo-specific runtime credentials committed into env, workflow, or compose files

### Gitleaks suppression policy

- Preferred fix: remove the secret from git history or replace it with a safe placeholder.
- For intentional test strings, use an inline `gitleaks:allow` comment on the exact line.
- For a reviewed false positive that cannot use an inline allow, add the specific fingerprint to `.gitleaksignore` and reference the review reason in the pull request.
- Never suppress a real secret before rotating or revoking it.

## Dependabot dependency scanning and updates

- Config: `.github/dependabot.yml`
- Ecosystems covered:
  - root `pip`
  - `backend` pip requirements
  - `frontend` npm
  - GitHub Actions
- Routing labels:
  - `dependencies`
  - `type:chore`
  - `squad:copilot`

### Dependency update process

1. Let Dependabot open the weekly update PR.
2. Review release notes and CI results.
3. Merge low-risk updates after all checks pass.
4. Split or defer updates that break tests, build output, or security posture.
5. Open a follow-up issue when an update is deferred because of an upstream blocker.

## Severity guidance

| Severity | Response expectation |
| --- | --- |
| Critical | Treat as a release blocker; assign immediately, patch or revoke within the same workday |
| High | Fix before merge unless a documented exception is approved |
| Medium | Prioritize into the active backlog with an owner |
| Low | Track and batch with normal maintenance work |

## Escalation path

1. Open or update a `priority:p0` issue for any critical finding.
2. Notify John with the finding summary, impacted surface, and immediate containment step.
3. Stop release or merge activity touching the affected area until containment is in place.
4. If a credential is involved, rotate or revoke it before closing the incident.
5. Record any standing exception or routing change in squad decisions if it affects team policy.
