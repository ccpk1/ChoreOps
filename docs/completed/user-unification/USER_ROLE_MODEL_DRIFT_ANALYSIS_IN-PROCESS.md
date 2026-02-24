# Initiative Plan: User-role model drift analysis and remediation strategy

## Initiative snapshot

- **Name / Code**: User-role model drift analysis (`CHOREOPS-ROLE-DRIFT-001`)
- **Target release / milestone**: Post-Phase-4B hardening and closure
- **Owner / driver(s)**: Project manager + architecture lead + builder lead
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                      | Description                                                       | % complete | Quick notes                                    |
| --------------------------------- | ----------------------------------------------------------------- | ---------- | ---------------------------------------------- |
| Phase 1 – Drift measurement       | Quantify terminology/contract drift across runtime, tests, docs   | 100%       | Metrics captured from grep/runtime scan        |
| Phase 2 – Semantic classification | Separate acceptable role terms from lifecycle-contract violations | 100%       | Critical vs medium vs cosmetic buckets defined |
| Phase 3 – Remediation strategy    | Define what we **should do** vs **could do** with risk/cost       | 100%       | Sequenced plan with closure gates drafted      |

1. **Key objective** – Determine how far the codebase is from the user-first role model target and define a safe, high-confidence path to close the gap.
2. **Summary of recent work** – Performed runtime/test/doc scans and categorized drift into lifecycle/event/storage/API/test surfaces.
3. **Next steps (short term)** – Approve the “Should do now” tranche and execute Phase A/B below before any broad lexical rewrite.
4. **Risks / blockers**
   - Large lexical footprint means blind renames risk high regression churn.
   - Event-signal renames can silently break manager listeners and custom automations.
   - Some assignee/approver terms are valid role-domain language and should be retained.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `custom_components/choreops/const.py`
   - `custom_components/choreops/coordinator.py`
   - `custom_components/choreops/managers/user_manager.py`

- `docs/in-process/USER_ROLE_MODEL_DRIFT_ANALYSIS_SUP_FACT_TABLE.md`
- `docs/in-process/USER_FIRST_ITEM_ROLE_CONTRACT_HARD_FORK_EXECUTION_IN-PROCESS.md`

6. **Decisions & completion check**
   - **Decisions captured**:
     - User records are canonical lifecycle records.
     - Assignee/approver terms remain valid for role projections and role-scoped UX.
     - Migration-first approach is required for any breaking key/event contract changes.
   - **Completion confirmation**: `[ ]` Remediation phases approved and executed with closure gates green.

## Tracking expectations

- **Summary upkeep**: Update this analysis after each remediation tranche with fresh counts and closure-gate status.
- **Detailed tracking**: Keep this doc focused on architecture drift and remediation decisions; implementation evidence lives in initiative execution docs.

## Detailed phase tracking

### Phase 1 – Drift measurement

- **Goal**: Produce measurable evidence of model/terminology drift.
- **Steps / detailed work items**
  - [x] Quantify token footprint (runtime + docs + tests).
  - [x] Quantify event-signal drift and listener/caller blast radius.
  - [x] Quantify lifecycle API drift in manager methods and callsites.
  - [x] Quantify storage-bucket and projection dependency drift.
  - [x] Quantify test coupling to role-projection and legacy naming.
- **Key issues**
  - Raw token counts are not sufficient; they overstate true violation because many role terms are valid domain language.

#### Phase 1 evidence snapshot

- Terminology volume:
  - `assignee`/`assignees` matches (custom_components + docs + tests): **5921**
  - `approver`/`approvers` matches (custom_components + docs + tests): **907**
- Constants surface:
  - `DATA_ASSIGNEE_*` + `DATA_APPROVER_*` defs in `const.py`: **121**
  - `DATA_USER_*` defs in `const.py`: **8**
  - `CFOF_ASSIGNEES_*` + `CFOF_APPROVERS_*` defs: **10**
  - `CFOF_USERS_*` defs: **3**
- Signal/event surface:
  - `SIGNAL_SUFFIX_ASSIGNEE_*` + `SIGNAL_SUFFIX_APPROVER_*` defs: **6**
  - `SIGNAL_SUFFIX_USER_*` defs: **0**
  - Runtime refs to assignee/approver lifecycle signals: **21**
- Runtime projection dependence:
  - `coordinator.assignees_data` refs in runtime: **211**
  - `coordinator.users_data` refs in runtime: **6**
- Storage-bucket usage:
  - Runtime refs to `const.DATA_ASSIGNEES`: **43**
  - Runtime refs to `const.DATA_APPROVERS`: **17**
  - Runtime refs to `const.DATA_USERS`: **21**
- API/callsite split:
  - `user_manager.create/update/delete_assignee|approver` definitions: **6**
  - Runtime calls to role APIs: **3**
  - Runtime calls to user APIs: **3**
- Test coupling:
  - Tests referencing `coordinator.assignees_data`: **241**
  - Tests referencing `coordinator.users_data`: **5**
  - Test files containing assignee/approver terminology: **73**

### Phase 2 – Semantic classification

- **Goal**: Determine what is actually incorrect versus acceptable role language.
- **Steps / detailed work items**
  - [x] Classify critical lifecycle-model violations.
  - [x] Classify medium-priority contract-drift surfaces.
  - [x] Classify acceptable/intentional role-language surfaces.
- **Key issues**
  - Over-correcting all role terminology would harm readability and misrepresent domain semantics.

#### Classification

**A) Critical drift (should fix first)**

1. **Lifecycle event naming is role-entity based, not user-lifecycle based**
   - Example: `SIGNAL_SUFFIX_ASSIGNEE_CREATED/UPDATED/DELETED`, `SIGNAL_SUFFIX_APPROVER_CREATED/UPDATED/DELETED` in `const.py`.
   - Impact: Encodes a dual-lifecycle mental model in event contracts.
2. **Manager lifecycle APIs still role-centric with user wrappers**
   - `UserManager` owns `create_assignee/create_approver/...` and `create_user` delegates to approver path.
   - Impact: User model appears secondary in code authority.
3. **Flow/create-entry still writes role buckets directly**
   - `config_flow._create_entry` explicitly writes `DATA_ASSIGNEES` and derives users from role temps.
   - Impact: Fresh installs still preserve dual-bucket shape by default.

**B) Medium drift (plan and sequence)**

1. **Projection dependency is heavily skewed toward `assignees_data`**
   - 211 runtime references indicate role projection is used as primary operational surface.
2. **Constant namespace remains role-heavy**
   - `DATA_ASSIGNEE_*`/`DATA_APPROVER_*` dominates despite user-first contract.
3. **Flow constants and tests still role-labeled broadly**
   - High ref counts increase migration blast radius.

**C) Acceptable/intentional role language (do not remove globally)**

1. Assignment semantics: `assigned_assignees`, assignee-specific dashboards, assignee chore state.
2. Approval semantics: approver capability fields and approver actions.
3. Role-gating language in UX where the user is acting in a specific role.

### Phase 3 – Remediation strategy (what we could do vs should do)

- **Goal**: Provide a practical and safe path to target state.
- **Steps / detailed work items**
  - [x] Define “Should do now” tranche.
  - [x] Define “Could do later” tranche.
  - [x] Define closure gates and rollback strategy.
- **Key issues**
  - Hard-fork policy requires zero runtime compatibility bridges; only migration-file transformations are allowed.

#### How far off are we?

- **Model ownership**: **Partially aligned (~60–70%)**
  - Canonical users model exists and powers projections, but role buckets/events/APIs still shape control flow.
- **Runtime behavior correctness**: **Moderately aligned (~70–80%)**
  - Core gating now centralized and user-capability driven, but event and API surfaces still imply role entities.
- **Contract surface alignment**: **Low-to-moderate (~40–50%)**
  - Signals, constant namespace, and tests remain strongly role-labeled.

#### What we should do (recommended)

**Phase A (High-value, low-to-medium risk): Contract clarity hardening**

1. Introduce canonical user lifecycle signals:
   - Add `SIGNAL_SUFFIX_USER_CREATED/UPDATED/DELETED`.

- Replace role-lifecycle signal emission with canonical user lifecycle emission (no dual-emission).

2. Refactor manager internals to user-first authority:
   - Make `create_user/update_user/delete_user` primary implementations.

- Remove role-specific lifecycle wrappers from runtime manager API surfaces.

3. Stop writing role buckets on fresh-create path:
   - In `config_flow._create_entry`, write canonical `DATA_USERS` only; derive role views at runtime.
4. Lock hard-fork policy boundaries in docs and gates:

- Runtime compatibility/fallback aliases are prohibited.
- Legacy import compatibility is allowed only inside migration modules.

**Phase B (Medium risk): Runtime projection dependency reduction**

1. Move selected manager/flow read paths from `assignees_data` to `users_data` + explicit role filters.
2. Introduce typed role-view helpers (`get_assignment_users()`, `get_approval_users()`) and migrate high-churn callsites.
3. Add lint/grep gate to block new lifecycle-role API additions.

**Phase C (Higher risk): Namespace and test contract cleanup**

1. Consolidate constants where lifecycle meaning is duplicated by role-prefixed variants.
2. Migrate test fixtures and helpers to user-first baseline with role projections as explicit fixtures.
3. Remove residual role-lifecycle signal constants and role-lifecycle API expectations from runtime/tests.

#### What we could do (optional / lower ROI)

1. Full lexical rewrite of assignee/approver text in all docs/tests/translations.
   - Not recommended as an immediate goal; large churn with little architectural gain.
2. Rename every role-scoped variable to user-prefixed forms.
   - Avoid where role semantics are real and useful.
3. Single-shot breaking migration of all event names/constants.

- High breakage risk; if chosen, enforce migration-only conversion and strict runtime no-compatibility rule.

#### Suggested closure gates for this initiative

- [ ] Canonical user lifecycle signals exist and are primary in manager emit paths.
- [ ] No fresh-install path writes role buckets as authoritative lifecycle storage.
- [ ] New code does not introduce role-entity lifecycle APIs/signals.
- [ ] Runtime critical paths use user-first accessors with explicit role filtering.
- [ ] Regression suite green with zero runtime compatibility wrappers/fallbacks.

## Testing & validation

- **Analysis commands executed**: grep-based footprint and hotspot scans across runtime/docs/tests.
- **Not executed in this analysis-only pass**: implementation tests for proposed changes (intentionally out of scope).

## Notes & follow-up

- This is a semantic-contract migration, not a global terminology purge.
- Assignee/approver terms remain first-class role vocabulary; the target is to remove lifecycle ambiguity, not role language.
- Recommended execution order: Phase A → B → C with hard-fork closure gates and no runtime compatibility windows.

## Full retrofit map (100% correctness target)

### Complexity assessment

- **Overall complexity**: Medium-high
- **Why**: The difficult part is contract migration (signals, lifecycle APIs, and storage-shape authority), not bulk renaming.
- **Primary risk**: Regressions from changing event and manager contracts that currently look role-entity based.
- **Estimated execution shape**:
  - **Tranche 1 (contract layer)**: user lifecycle signals + manager authority flip + fresh-create storage write model
  - **Tranche 2 (runtime dependency layer)**: migrate critical read paths from role projections to user-first access + explicit role filters
  - **Tranche 3 (test and namespace layer)**: convert test baselines and remove any residual role-lifecycle contract surfaces

### What the full retrofit should include

1. **Lifecycle event contract correction (must do)**

- Add canonical `SIGNAL_SUFFIX_USER_CREATED/UPDATED/DELETED`
- Make user lifecycle signals the only runtime lifecycle emit path
- Remove assignee/approver lifecycle signal use from runtime emit/listener contracts

2. **Manager authority correction (must do)**

- Make `create_user/update_user/delete_user` primary implementation in manager internals
- Remove role-lifecycle wrapper methods from runtime-facing manager contract

3. **Storage authority correction (must do)**

- Ensure fresh create paths write canonical users lifecycle records only
- Keep role projections derived, not authoritative lifecycle storage

4. **Runtime access correction (should do)**

- Migrate high-churn callsites from `assignees_data` as primary source toward user-first helpers
- Preserve explicit role-filter helper APIs for assignment/approval workflows

5. **Test contract correction (should do)**

- Shift fixtures and assertions to user-first baseline
- Keep role-projection assertions where role behavior is the feature under test

### What should remain as-is (correct usage)

1. **Role semantics in domain behavior**

- Assignment fields and list names that describe who can perform chores
- Approval capability fields and approver-specific permission semantics

2. **Role-specific UX language**

- User-facing wording where “assignee” or “approver” is genuinely the role being configured or displayed

3. **Role projection helpers**

- Projection APIs are valid if they are read-only views over canonical users and not treated as lifecycle authorities

### What should not be done

1. Blind global replacement of all assignee/approver tokens
2. Introduce runtime compatibility aliases, bridges, or fallback logic for lifecycle contracts
3. Replacing valid role language with user-generic language where role meaning is essential

### Hard-fork boundary (non-negotiable)

- Runtime and test surfaces must not include legacy compatibility branches for lifecycle/event/API contracts.
- Any compatibility transformation from legacy KidsChores data is permitted only in migration modules.
- Migration modules may perform one-time key/signal/value normalization; normalized runtime state must be canonical user-first only.

### Practical endpoint definition for "100% correct"

- Canonical user lifecycle is the only authoritative lifecycle model in storage + manager authority + primary signals
- Assignee/approver remain role vocabulary and projection/permission concepts
- Compatibility wrappers/signals are not permitted in runtime; legacy normalization exists only in migration files
