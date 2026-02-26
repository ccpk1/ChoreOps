# Dashboard registry architecture standards (supporting)

## Purpose

This document defines architecture standards and decision gates for the ChoreOps dashboard registry ecosystem. It intentionally avoids implementation details so maintainers can ratify the model before coding.

## 1) Architecture principles (non-negotiable)

1. **Contract-first design**
   - Runtime behavior is driven by an explicit manifest contract, not implied file naming.
   - Every user-visible template option must map to a stable manifest identity.

2. **Deterministic runtime behavior**
   - Given the same local+remote inputs, resolution must always produce the same selected template.
   - All fallback rules are explicit and testable.

3. **Offline-safe baseline**
   - Core templates and a valid manifest are always vendored in integration releases.
   - Remote fetch failure must not block dashboard generation.

4. **Low cognitive load**
   - Naming, taxonomy, and metadata should be obvious to maintainers and contributors.
   - Avoid redundant fields that create ambiguity.

5. **Scale through governance**
   - Community contributions must pass policy checks for naming, metadata, and dependencies.
   - Schema changes require stricter approval than template-only changes.

6. **Observable behavior**
   - Runtime decisions should be explainable via structured logs and diagnostics.
   - Users should be informed when dependency requirements block template usage.

## 2) Explicit non-goals (for this initiative)

- Defining a new visual design system for dashboards.
- Rewriting Home Assistant Lovelace internals.
- Supporting arbitrary remote code execution or dynamic scripts.
- Building a full template marketplace UI in this phase.

## 3) Manifest contract standards (v1 target)

## Required identity fields

- `template_id` (immutable canonical key)
- `slug` (human-readable stable key)
- `display_name`
- `version` (template content version)
- `lifecycle_state` (`active`/`deprecated`/`archived`)

## Required compatibility fields

- `min_integration_version`
- `max_integration_version` (optional if open-ended)
- `schema_version` (manifest schema version)

## Required asset fields

- `source.type` (`vendored`/`remote`)
- `source.path` (for vendored)
- `source.ref` (for remote ref when applicable)

## Required dependency fields

- `dependencies.required[]`
- `dependencies.recommended[]`
- Dependency entries should be machine-readable with stable IDs and optional human labels.

## Required metadata fields

- `category` (e.g., `family`, `admin`, `minimal`)
- `audience` (e.g., `assignee`, `approver`, `mixed`)
- `maintainer` (or ownership pointer)

## 4) Naming and organization standards

- Template file naming should be deterministic and variant-safe.
- `template_id` is immutable; display names can evolve.
- Variant naming must use explicit suffix conventions (e.g., `-compact`, `-minimal`) rather than overloaded labels.
- Deprecated templates must keep discoverable aliases until retirement period ends.

## 5) Runtime resolution model standards

1. Local vendored manifest loads first.
2. Remote manifest fetch is attempted with timeout budget.
3. Merge is by `template_id` with remote override on valid records only.
4. Invalid remote records are ignored and logged; local baseline remains authoritative.
5. Selection engine filters by lifecycle state, compatibility, and dependency policy.
6. Generator resolves to one explicit source asset and records why that source won.

## 6) Dependency handling policy

- **Required dependency missing**
  - Template selection is blocked.
  - User receives clear remediation guidance.

- **Recommended dependency missing**
  - Selection allowed.
  - User receives warning with impact summary.

- **Unknown dependency keys**
  - Treated as validation errors in registry CI.

## 7) Submission and review model

## Submission requirements

- Manifest record with complete required fields.
- YAML asset parseable and mapped to a valid `template_id`.
- Dependencies declared with stable keys.
- Changelog/notes for behavioral differences.

## Review gates

- Schema validation pass.
- Naming policy pass.
- Dependency key validation pass.
- Asset existence and parse validation pass.
- Compatibility metadata present and valid.

## Approval rules

- Template-only PR: normal maintainer approval.
- Manifest schema change: architecture-owner approval required.

## 8) Lifecycle governance

- **Active**: available for selection.
- **Deprecated**: available with warning; replacement guidance required.
- **Archived**: hidden from new selections; retained for migration/backward compatibility window.

Deprecation must include a minimum communication window and explicit replacement path.

## 9) Decision gates (must be resolved before implementation phase)

1. Canonical identity: `template_id` format and immutability rule.
2. Schema versioning strategy: strict semver vs simplified major/minor policy.
3. Merge conflict rule: remote override always vs scoped override.
4. Dependency catalog source of truth: integration constants vs registry-maintained list.
5. Submission governance: who can approve schema-level changes.
6. Deprecation window length and enforcement process.

## 10) Suggested defaults for ratification

- Use immutable kebab-case `template_id` values.
- Use explicit manifest schema version with backward-compatible minor evolution.
- Use local baseline + remote override by `template_id` for valid records only.
- Keep dependency key source of truth in integration constants with mirrored docs in dashboard repo.
- Require architecture-owner approval for schema changes.
- Set a defined deprecation window before archive state.
