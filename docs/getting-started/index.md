---
title: Getting Started with Homeschool Hero
description: Everything you need to go from zero to running your homeschool in Homeschool Hero.
---

# Getting Started

Homeschool Hero is a self-hosted, open-source platform for families who educate at home. It handles
assignment tracking, PDF/photo submission, AI-assisted grading, curriculum planning, academic
records, and compliance tracking — all from a single Docker container on hardware you control.

## What you'll find in this section

| Page | What it covers |
|------|----------------|
| [Try the Demo](./demo) | Spin up the live demo data and take a guided tour of every feature |
| [Quick Start](./quick-start) | Docker-based installation from zero to running in under 10 minutes |
| [Setup Wizard](./setup-wizard) | Walk through the first-run owner bootstrap and initial family configuration |

## Who is this for?

Homeschool Hero is built for **parents and co-parents** who are the primary managers of their
homeschool. The platform is oriented around a parent workflow:

- Parents create students, subjects, curriculum, and assignments.
- Students complete work on paper or digitally and submit scans or file uploads.
- Homeschool Hero OCRs and AI-grades submissions, routing low-confidence results back to parents
  for human review.
- Parents keep official academic records, generate report cards and transcripts, and track
  state compliance requirements.

Teachers and tutors can be added to a family with narrower educational permissions. Full
platform administration is available to owners through the Administration section.

## Platform at a glance

```
homeschool-hero/
├── app          FastAPI backend + React 18 frontend (single container)
├── db           PostgreSQL 16
├── ollama       Local LLM for AI grading (optional)
├── smtp         Mailpit local SMTP relay (optional, dev/test)
└── backup       Scheduled backup worker (optional)
```

The React app is compiled into the Docker image and served directly by FastAPI — no separate
Node.js runtime is needed in production.

## Minimum requirements

| Resource | Base stack | With AI grading |
|----------|-----------|-----------------|
| CPU | 2 vCPU | 2 vCPU |
| RAM | 4 GB | 12–16 GB |
| Disk | 20 GB | 20 GB + model cache |

For a typical family running without AI grading on a home server or NAS, the base stack comfortably
fits in 4 GB RAM.

## Next step

If you want to explore features before committing, start with the **[Demo →](./demo)**.

If you're ready to install, go straight to **[Quick Start →](./quick-start)**.
