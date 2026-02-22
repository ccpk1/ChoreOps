# Supporting baseline: Phase 1 policy and link inventory

## Purpose

Capture Phase 1 baseline evidence and the owner-approval inventory for external links retained in the wiki.

## Baseline metrics (2026-02-19)

- Legacy branding matches (`KidsChores|kidschores`): **465** occurrences
- Legacy/encoded link pattern matches (`ad-ha/kidschores-ha|kidschores-ha/wiki|https%3A//|http%3A//`): **51** occurrences
- External absolute link occurrences (`https://`): **19** occurrences

## External links requiring owner permission if retained

The following destinations were found and should be explicitly approved if they remain after internal-link conversion.

### Home Assistant documentation

- `https://www.home-assistant.io/integrations/tag/`
- `https://www.home-assistant.io/integrations/calendar/`
- `https://my.home-assistant.io/redirect/config_flow_start?domain=kidschores`

### Home Assistant community forum

- `https://community.home-assistant.io/t/simple-and-effective-alerting/394027?u=ccpk1`

Decision update (2026-02-19):

- Removed from wiki per owner direction:
  - `https://community.home-assistant.io/t/kidschores-family-chore-management-integration`
  - `https://community.home-assistant.io/t/introducing-the-kidschores-and-rewards-dashboard`

### GitHub repositories / pages (legacy targets)

- `https://github.com/ad-ha/kidschores-ha`
- `https://github.com/ad-ha/kidschores-ha/releases`
- `https://github.com/ad-ha/kidschores-ha/issues`
- `https://github.com/ad-ha/kidschores-ha/wiki/Service:-Set-Chore-Due-Dates`
- `https://github.com/ad-ha/kidschores-ha/wiki/Chore-Status-and-Recurrence-Handling`
- `https://github.com/ad-ha/kidschores-ha/wiki/Access-Control:-Overview-&-Best-Practices`
- `https://github.com/ad-ha/kidschores-ha/wiki/Tips-&-Tricks:--Configure-Automatic-Approval-of-Chores`
- `https://github.com/ad-ha/kidschores-ha/wiki/Service:-Reset-All-Data`
- `https://github.com/ad-ha/kidschores-ha/wiki/Troubleshooting:-KidsChores-Troubleshooting-Guide`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/ARCHITECTURE.md`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/ARCHITECTURE.md#-lexicon-standards-critical`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/ARCHITECTURE.md#layered-architecture`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/DEVELOPMENT_STANDARDS.md`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/DEVELOPMENT_STANDARDS.md#3-constant-naming-standards`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/DEVELOPMENT_STANDARDS.md#2-localization--translation-standards`
- `https://github.com/ad-ha/kidschores-ha/blob/main/docs/DEVELOPMENT_STANDARDS.md#4-data-write-standards-crud-ownership`
- `https://github.com/ccpk1/kidschores-ha-dashboard`

### App stores and other external resources

- `https://apps.apple.com/app/home-assistant/id1099568401`
- `https://play.google.com/store/apps/details?id=io.homeassistant.companion.android`

### User-attached images (GitHub assets)

- `https://github.com/user-attachments/assets/...` (multiple occurrences)

## Notes

- Most `ad-ha/kidschores-ha/wiki/*` links should convert to relative internal wiki links.
- Dashboard repo links require confirmation of canonical target repository before replacement.
- Encoded links (`https%3A//...`) should be normalized to standard `https://...` format.

## Post-Phase 3 snapshot (2026-02-19)

- Internal wiki link validation (decoded-target pass): **0 unresolved internal links**
- Legacy old-wiki URL scan (`https://github.com/ad-ha/kidschores-ha/wiki/...`): **0 matches**
- External absolute link occurrences (`https://`): **42 occurrences**
- Unique external URLs: **29**

### Current external-link domains (unique URL count)

- `github.com` (22)
- `www.home-assistant.io` (2)
- `apps.apple.com` (1)
- `community.home-assistant.io` (1)
- `hacs.xyz` (1)
- `my.home-assistant.io` (1)
- `play.google.com` (1)

### Current external-link retention set (for owner approval gate)

Home Assistant docs and helpers:

- `https://www.home-assistant.io/integrations/tag/`
- `https://www.home-assistant.io/integrations/calendar/`
- `https://my.home-assistant.io/redirect/config_flow_start?domain=choreops`

Community/forum:

- `https://community.home-assistant.io/t/simple-and-effective-alerting/394027?u=ccpk1`

Project docs/repo pages:

- `https://github.com/ccpk1/choreops`
- `https://github.com/ccpk1/choreops/releases`
- `https://github.com/ccpk1/choreops/issues`
- `https://github.com/ccpk1/choreops/blob/main/docs/ARCHITECTURE.md`
- `https://github.com/ccpk1/choreops/blob/main/docs/ARCHITECTURE.md#-lexicon-standards-critical`
- `https://github.com/ccpk1/choreops/blob/main/docs/ARCHITECTURE.md#layered-architecture`
- `https://github.com/ccpk1/choreops/blob/main/docs/DEVELOPMENT_STANDARDS.md`
- `https://github.com/ccpk1/choreops/blob/main/docs/DEVELOPMENT_STANDARDS.md#2-localization--translation-standards`
- `https://github.com/ccpk1/choreops/blob/main/docs/DEVELOPMENT_STANDARDS.md#3-constant-naming-standards`
- `https://github.com/ccpk1/choreops/blob/main/docs/DEVELOPMENT_STANDARDS.md#4-data-write-standards-crud-ownership`
- `https://github.com/ccpk1/choreops-ha-dashboard`

App stores / install:

- `https://hacs.xyz/docs/installation/manual`
- `https://apps.apple.com/app/home-assistant/id1099568401`
- `https://play.google.com/store/apps/details?id=io.homeassistant.companion.android`

Image assets:

- `https://github.com/user-attachments/assets/...` (13 unique asset URLs currently referenced)
