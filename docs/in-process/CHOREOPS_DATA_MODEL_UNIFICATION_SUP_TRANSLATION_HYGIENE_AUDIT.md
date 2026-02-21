# Supporting Doc: Translation hygiene audit (Phase 4 gate)

- Generated: 2026-02-21
- Scope (current requirement): `translations/en.json` and `translations_custom/en_*.json`
- Method: English-master normalization + key/value token scan + legacy field/orphan token checks

## English master snapshot

- `translations/en.json` flattened keys: **3866**
- `translations_custom/en_dashboard.json` flattened keys: **159**
- `translations_custom/en_notifications.json` flattened keys: **106**
- `translations_custom/en_report.json` flattened keys: **38**

## English-master hygiene checks

- Legacy-term scan (`grep -RInEi 'kid|parent|KidsChores'`) across target files: **0 matches**
- Key-path scan for legacy tokens (`kid`, `parent`, `kidschores`) across target files: **0 key-path matches**
- Legacy service actor-field keys in `translations/en.json` (`kid_name`, `parent_name`): **0 remaining where role-based equivalents exist**

## Orphan-key status (current requirement scope)

- No legacy-orphan keys remain in the English master surfaces for actor naming terms and role-bucket terminology.
- Role terminology in English masters is normalized to `user`, `assignee`, and `approver` contexts.

## Localization pipeline note

- Non-English locale reconciliation remains a separate pipeline task and is out of scope for this requirement slice.

## Gate status

- English master surfaces are aligned for this requirement slice and pass the naming-hygiene indicators.
- This gate is **complete** for `en.json` + `translations_custom/en_*.json`.
