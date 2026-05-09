# Security scanning

This repository uses a layered security scanning stack as of 2026-05-08.

## Scanning overview

| Tool | Trigger | Coverage | Output | Blocking policy |
| --- | --- | --- | --- | --- |
| CodeQL | Pull requests to `main`, weekly schedule, manual dispatch | Python backend and JavaScript/TypeScript frontend source analysis | GitHub Security tab (code scanning) | Findings are triaged by severity; critical and high findings block merge until resolved or explicitly accepted |
| Trivy | CI container checks on pushes and pull requests | Built Docker image, including OS packages and application libraries | Job logs + SARIF in the GitHub Security tab | `HIGH` and `CRITICAL` vulnerabilities fail CI unless the exact CVE is listed in `.trivyignore` |
| Gitleaks | Pull requests via CI and optional local pre-commit hook | Git history and committed files for secrets | CI summary and workflow artifacts | Any verified secret finding blocks merge and requires rotation/removal |
| Dependabot | Weekly schedule | Root pip dependencies, backend test pip dependencies, frontend npm dependencies, GitHub Actions | Dependabot pull requests | Updates must pass the full CI and security stack before merge |

## CodeQL

- Workflow: `.github/workflows/security.yml`
- Languages: `python`, `javascript-typescript`
- Query suites: `security-extended` and `security-and-quality`
- Purpose: catch unsafe server-side patterns, insecure dependency usage, client-side injection paths, and general code quality issues that can become vulnerabilities

### Handling CodeQL findings

1. Read the alert in the GitHub Security tab and confirm the data flow or source/sink path.
2. Fix the code first when the alert is valid.
3. If the alert is a false positive, dismiss it in GitHub with the clearest matching reason and a note describing why the current code is safe.
4. Re-run the workflow or confirm the next scheduled run closes the alert.

## Trivy container scanning

- Workflow: `.github/workflows/ci.yml` (`Container checks`)
- Scan target: the built `homeschool-hero:ci` Docker image
- Scan scope: OS packages and application libraries
- Severity gate: fails on `HIGH` and `CRITICAL`

### Trivy suppression policy

- Use `.trivyignore` only for reviewed exceptions.
- Every ignored CVE must have an owner, remediation plan, and a follow-up issue or note in the pull request that introduced the exception.
- Remove the ignore entry as soon as the base image or dependency upgrade is available.

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
