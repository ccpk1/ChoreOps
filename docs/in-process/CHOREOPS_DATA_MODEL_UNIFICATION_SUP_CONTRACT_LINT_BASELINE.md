# Supporting Doc: Hard-fork contract-lint baseline

## Purpose

Provide the required baseline violation artifact for the Phase 4 contract-lint gate.
This baseline allows the boundary check to block only **new** legacy-contract usage
while remaining cleanup work is completed in controlled batches.

## Scope

Runtime hard-fork surfaces scanned:

- `custom_components/choreops/services.py`
- `custom_components/choreops/notification_action_handler.py`
- `custom_components/choreops/config_flow.py`
- `custom_components/choreops/options_flow.py`
- `custom_components/choreops/helpers/flow_helpers.py`
- `custom_components/choreops/data_builders.py`

Rule classes tracked:

- `legacy-field`: `kid_name`, `parent_name`, and legacy service field constants
- `legacy-lexical`: `kidschores`, `shadow_*`, `linked_*`

## Baseline artifact

- File: `docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CONTRACT_LINT_BASELINE.txt`
- Signature format: `<rule>|<relative_path>|<line_content>`
- Snapshot count: **103 signatures**
- Generated: 2026-02-20

## Gate behavior

`utils/check_boundaries.py` now runs the hard-fork contract-lint check and compares
findings against this baseline.

- Existing baseline signatures: allowed temporarily
- New signatures not in baseline: fail boundary check

## Exit criteria for plan sign-off

- Baseline shrunk to zero (or removed) after runtime cleanup completion
- Contract-lint gate reports zero unresolved legacy-contract findings
- Evidence attached in Phase 4 completion notes
