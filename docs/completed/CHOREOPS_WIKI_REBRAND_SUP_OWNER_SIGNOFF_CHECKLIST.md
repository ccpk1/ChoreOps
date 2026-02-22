# Owner sign-off checklist: wiki rebrand gates

## Purpose

This checklist captures the remaining owner approvals required to close the wiki rebrand initiative.

## Approval gates

- [x] **Gate 3.1**: Approve external-link retention set
- [x] **Gate 4.1**: Approve navigation coverage model (top-level + deep-linked references)
- [x] **Gate 4.2**: Approve logo placement strategy (Option A)

---

## Gate 3.1: External-link retention set

### Decision request

Approve the following external-link categories as intentionally retained:

### A) Home Assistant docs and helper links

- `https://www.home-assistant.io/integrations/tag/`
- `https://www.home-assistant.io/integrations/calendar/`
- `https://my.home-assistant.io/redirect/config_flow_start?domain=choreops`

### B) Community post reference

- `https://community.home-assistant.io/t/simple-and-effective-alerting/394027?u=ccpk1`

### C) Project references

- `https://github.com/ccpk1/choreops`
- `https://github.com/ccpk1/choreops/releases`
- `https://github.com/ccpk1/choreops/issues`
- `../ARCHITECTURE.md`
- `../DEVELOPMENT_STANDARDS.md`
- `https://github.com/ccpk1/choreops-ha-dashboard`

### D) App stores and installation references

- `https://hacs.xyz/docs/installation/manual`
- `https://apps.apple.com/app/home-assistant/id1099568401`
- `https://play.google.com/store/apps/details?id=io.homeassistant.companion.android`

### E) Image assets

- `https://github.com/user-attachments/assets/...` (13 unique URLs currently referenced)

---

## Gate 4.1: Navigation coverage model

### Decision request

Approve the current navigation model:

- Home and Sidebar include curated top-level links for onboarding, configuration, services/examples, advanced topics, technical references, troubleshooting, and project docs.
- Deep/long-tail pages remain discoverable via section links without forcing all detail pages into flat top-level menus.
- Current audit status: no top-level wiki pages are missing from the Home+Sidebar coverage union.

---

## Gate 4.2: Logo placement strategy

### Decision request

Approve **Option A**:

- Branding emphasis on Home and optional compact sidebar context only.
- No repeated per-page logo headers.
- Rationale: improves readability and reduces maintenance churn.

---

## Verification summary

- Legacy-pattern scan (top-level wiki pages): 0 files, 0 matches
- Internal-link validation (decoded-target pass): 0 unresolved links
- Legacy old-wiki URL scan (`ad-ha/kidschores-ha/wiki`): 0 matches
- Home+Sidebar coverage audit: 0 pages missing

---

## Owner decision record

- Decision date: `2026-02-22`
- Gate 3.1 approved: [x] Yes [ ] No
- Gate 4.1 approved: [x] Yes [ ] No
- Gate 4.2 approved: [x] Yes [ ] No
- Notes:

- Decision lock imported into `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md` Phase 1B.

- Approved by: `CCPK1`
