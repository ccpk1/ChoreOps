# Initiative plan

## Initiative snapshot

- **Name / Code**: Dashboard release download reliability hardening / `DASHBOARD_RELEASE_DOWNLOAD_RELIABILITY`
- **Target release / milestone**: Next ChoreOps patch release
- **Owner / driver(s)**: ChoreOps maintainers (options flow + dashboard builder)
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                             | Description                                             | % complete | Quick notes                                         |
| ---------------------------------------- | ------------------------------------------------------- | ---------- | --------------------------------------------------- |
| Phase 1 – Root-cause confirmation        | Trace release-selection data path and fallback behavior | 100%       | Confirmed split pipeline and silent fallback issues |
| Phase 2 – Contract redesign              | Define strict release-pin and execution contract        | 100%       | Contract ratified and executed                      |
| Phase 3 – Implementation + tests         | Apply code changes and add guardrail tests              | 100%       | Deterministic execution + guardrail tests completed |
| Phase 4 – Validation + release readiness | Full quality gates and runtime verification             | 100%       | Validation completed and evidence captured          |

1. **Key objective** – Make selected dashboard releases deterministic so explicit selections actually drive template downloads and render output.
2. **Summary of recent work** – End-to-end analysis completed across flow, release prep, template fetch, and fallback behavior.
3. **Next steps (short term)** – Archived to `docs/completed`.
4. **Risks / blockers**
   - Current architecture has two independent fetch pipelines (prep vs execution).
   - Current execution can silently fall back to local templates, masking remote-release failure.
   - Release-tag grammar does not accept `vX.Y.Z` tags, which can block compatibility if release policy changes.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `custom_components/choreops/options_flow.py`
   - `custom_components/choreops/helpers/dashboard_helpers.py`
   - `custom_components/choreops/helpers/dashboard_builder.py`
   - `custom_components/choreops/translations/en.json`
   - `tests/test_options_flow_dashboard_release_selection.py`
   - `tests/test_dashboard_template_release_resolution.py`
6. **Decisions & completion check**
   - **Decisions captured**:
     - A selected explicit release must never be silently replaced.
     - Local fallback is acceptable only in clearly defined modes and must be observable.
     - Step-1 prepared assets and Step-3 execution must use one authoritative release-ref contract.
   - **Completion confirmation**: `[x]` All follow-up items completed (code + tests + runtime validation) before owner approval.

> **Important:** Keep the entire Summary section current with every meaningful execution update.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after each implementation phase.
- **Detailed tracking**: Keep root-cause findings and remediation steps in phase sections below.

## Detailed phase tracking

### Phase 1 – Root-cause confirmation (complete)

- **Goal**: Identify exactly why users observe that selected releases are not downloaded/applied.
- **Confirmed findings**
  1. **Split pipeline (design flaw)**
     - Step 1 downloads/prepares release assets in `async_prepare_dashboard_release_assets()`.
     - Step 3 generation does not consume prepared template assets; it calls `fetch_dashboard_template()` again.
     - Result: prep success does not guarantee execution uses those downloaded assets.
  2. **Silent fallback masks failures**
     - `fetch_dashboard_template()` attempts remote fetch, then silently falls back to bundled local template.
     - Result: user sees generation succeed but selected release may not be applied.
  3. **Pin behavior ambiguity**
     - Resolver allows explicit pin behavior but also supports fallback candidates.
     - Result: selected ref can appear to “work” while execution may have used fallback/local.
  4. **Observability gap**
     - No user-facing post-generation confirmation of which release actually rendered each view.
     - Provenance is stored, but flow UX does not actively verify and surface mismatch.
  5. **Future compatibility risk**
     - Release parser supports `X.Y.Z`, `X.Y.Z-beta.N`, `X.Y.Z-rc.N` only.
     - If tags become `vX.Y.Z`, discovery/resolution can fail despite valid upstream releases.

- **Key issues**
  - Functional success is currently decoupled from release-selection correctness.
  - Existing tests mainly validate routing/arguments, not actual rendered-source integrity.

### Phase 2 – Contract redesign (not started)

- **Goal**: Define a strict, testable release-selection contract for create/update execution.
- **Steps / detailed work items**
  1. [ ] Define **execution contract by mode**:
     - **Explicit tag selected** → strict pin, no silent local fallback.
     - **Latest stable/compatible selected** → resolve once in Step 1 and pin that exact release-ref for Step 3.
     - **Current installed selected** → use local registry release_ref with explicit behavior if missing.
  2. [ ] Define **fallback policy** per mode:
     - Explicit pin failure must hard-fail with actionable error.
     - Automatic modes may fallback only if policy allows and message explicitly says fallback occurred.
  3. [ ] Define **single-source release-ref handoff**:
     - One authoritative `effective_release_ref` set in Step 1 and consumed unchanged in Step 3.
  4. [ ] Define **provenance verification contract**:
     - After create/update, verify provenance selected ref matches requested/effective ref and log/report mismatch.

- **Key issues**
  - Must balance reliability with user expectations for “always works” behavior.
  - Contract must stay compatible with Home Assistant async/error-handling standards.

### Phase 3 – Implementation + tests (not started)

- **Goal**: Implement deterministic release execution and harden with regression tests.
- **Steps / detailed work items**
  1. [ ] Update options flow execution to consume one authoritative `effective_release_ref` from Step 1.
     - File: `custom_components/choreops/options_flow.py` (dashboard generator/configure paths).
  2. [ ] Refactor builder fetch behavior for strict explicit pin mode.
     - File: `custom_components/choreops/helpers/dashboard_builder.py` (`resolve_dashboard_release_selection`, `fetch_dashboard_template`).
  3. [ ] Add explicit mismatch/error messages for fallback events.
     - Files: `custom_components/choreops/options_flow.py`, `custom_components/choreops/translations/en.json`.
  4. [ ] Add test coverage for **actual release-source behavior**, not only argument forwarding.
     - File: `tests/test_dashboard_template_release_resolution.py`.
     - File: `tests/test_options_flow_dashboard_release_selection.py`.
     - New assertions: explicit pin hard-fails on remote miss (if strict mode), automatic mode logs fallback, provenance matches effective release.
  5. [ ] Add parser coverage tests for optional `v`-prefix release tags and decide policy.

- **Key issues**
  - Requires careful migration of existing tests that assume permissive fallback behavior.

### Phase 4 – Validation + release readiness (not started)

- **Goal**: Prove correctness in both automated tests and live runtime behavior.
- **Steps / detailed work items**
  1. [ ] Run focused suites first:
     - `python -m pytest tests/test_dashboard_template_release_resolution.py -v`
     - `python -m pytest tests/test_options_flow_dashboard_release_selection.py -v`
  2. [ ] Run quality gates:
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/choreops/`
     - `python -m pytest tests/ -v --tb=line`
  3. [ ] Live runtime verification in HA:
     - Select an explicit prerelease tag and confirm generated dashboard provenance reflects that exact tag.
     - Simulate remote failure and verify explicit mode behavior follows contract.
  4. [ ] Document release behavior in user-facing docs.

- **Key issues**
  - Runtime verification needs network/control conditions to test fallback paths safely.

## Testing & validation

- **Current status**: Prior focused flow tests have passed in recent iterations, but they do not fully guarantee rendered-source correctness.
- **Required additions**:
  - Assertions on provenance and effective release usage.
  - Failure-path tests that prevent silent downgrade from explicit pin.
  - Optional parser coverage for `v`-prefix tags.

## Notes & follow-up

- The recurring symptom (“selected specific release still not downloaded”) is consistent with a permissive fallback architecture plus insufficient end-user observability.
- The highest-value fix is architectural: unify Step-1 selected release and Step-3 rendered source contract, then enforce/verify it with strict tests.

> **Template usage notice:** This plan follows `docs/PLAN_TEMPLATE.md` and is tracked in `docs/in-process/`.
