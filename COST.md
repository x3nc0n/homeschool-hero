# AI Development Costs

This document tracks the AI-related costs incurred during development of homeschool-hero.

## Platform

- **Tool:** GitHub Copilot (CLI agent + Squad orchestration)
- **Subscription:** GitHub Copilot Pro+ (included in Microsoft employee benefit)
- **Effective cost to developer:** $0 (covered by employer benefit)

## Models Used

| Model | Role | Usage Context |
|-------|------|---------------|
| Claude Opus 4.6 | Coordinator | Squad orchestration, routing, synthesis |
| Claude Sonnet 4.6 | Agent (code) | Implementation, refactoring, security fixes |
| Claude Haiku 4.5 | Agent (fast) | Triage, logging, mechanical ops |

## Session History

| Date | Session | Work Performed |
|------|---------|----------------|
| 2026-05-08 | Initial setup | Squad team creation, project scaffolding |
| 2026-05-09 | CI/CD & security | GitHub Actions setup, Trivy remediation, Azure deployment review |
| 2026-05-12 | Infrastructure | Azure deployment pipeline setup |
| 2026-05-13 | Docker | Docker build fixes (macOS compatibility) |
| 2026-05-14 | Auth & RBAC | OIDC/SAML RBAC triage and implementation |
| 2026-05-18 | Triage | Issue triage, enhancement planning |
| 2026-05-22 | RBAC & infra | RBAC model redesign, infrastructure fixes |
| 2026-06-09 | Security | CodeQL security issue triage & remediation (XSS, path injection, stack trace exposure, log injection) |

## Estimated Token Usage

Exact token counts are not available, but approximate usage per session:

- **Light sessions** (triage, status checks): ~50K–100K tokens
- **Heavy sessions** (implementation, multi-agent fan-out): ~200K–500K tokens
- **Estimated total across 12 sessions:** ~2M–4M tokens

## Cost Transparency

While the subscription cost is covered by employer benefit, the approximate market-rate costs (if paid per-token) would be:

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Claude Opus 4.6 | $15.00 | $75.00 |
| Claude Sonnet 4.6 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $0.80 | $4.00 |

**Estimated market-rate equivalent:** ~$50–$150 total across all sessions (rough estimate based on typical multi-agent workloads).

## Notes

- All code was generated, reviewed, and tested by AI agents under human oversight
- The Squad system (Egon, Venkman, Ray, Winston) routes work to specialized agents
- Security fixes are verified by both automated tests and CodeQL re-scans
- No external API costs beyond the GitHub Copilot subscription
