# Triage and labels

This document defines the issue triage flow and label usage.

## Intake flow

1. New issue is opened
2. `needs-triage` is applied automatically
3. Maintainer adds at least one `area:*` or `priority:*` label
4. `needs-triage` is removed automatically

## Required triage labels

- **Area** (where):
  - `area: integration`
  - `area: dashboard`
  - `area: automation/services`
  - `area: docs`

- **Priority** (urgency):
  - `priority: low`
  - `priority: medium`
  - `priority: high`

## Status labels

- `status: ready` — triaged and ready for implementation
- `status: in-progress` — actively being worked
- `status: blocked` — waiting on dependency/decision

## Enhancement qualifiers

- `enh: feature`
- `enh: ux`
- `enh: performance`
- `enh: refactor`
- `enh: proposal`
- `enh: breaking-change`
- `enh: roadmap`
- `enh: deferred`

## Contributor-focused labels

- `good first issue`
- `help wanted`
- `needs-info`

## Suggested maintainer practice

- Keep one status label at a time
- Keep one priority label at a time
- Prefer one primary area label (add more only when truly cross-cutting)
