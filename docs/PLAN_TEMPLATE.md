# Initiative Plan Template

## Initiative snapshot

- **Name / Code**: _Name the initiative or refactor_
- **Target release / milestone**: _Target release version or sprint_
- **Owner / driver(s)**: _Names or teams owning execution_
- **Status**: _Not started / In progress / Blocked / Complete_

## Summary & immediate steps

| Phase / Step     | Description                   | % complete | Quick notes                |
| ---------------- | ----------------------------- | ---------- | -------------------------- |
| Phase 1 – _Name_ | _Short description of intent_ | _0‑100%_   | _Key highlight or blocker_ |
| Phase 2 – _Name_ | _Short description of intent_ | _0‑100%_   | _Key highlight or blocker_ |
| Phase 3 – _Name_ | _Short description of intent_ | _0‑100%_   | _Key highlight or blocker_ |

1. **Key objective** – Briefly describe the primary goal for the initiative.
2. **Summary of recent work** – Bullet the most recent progress per phase.
3. **Next steps (short term)** – Outline the immediate actions.
4. **Risks / blockers** – Highlight dependencies, outstanding bugs, or required approvals.
5. **References** – Link to key resources:
   - Add document links that support the effort. Example ARCHITECHTURE.md
6. **Decisions & completion check**
   - **Decisions captured**: _List any key architectural or process decisions made for this initiative._
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – _Name_

- **Goal**: _Describe the scope/intent of phase 1._
- **Steps / detailed work items**
  1. _Detailed step or ticket reference + status/owner_
  2. _Detailed step or ticket reference + status/owner_
- **Key issues**
  - _Issue / blocker description (linked if applicable)_

### Phase 2 – _Name_

- **Goal**: _Describe the scope/intent of phase 2._
- **Steps / detailed work items**
  1. _Detailed step or ticket reference + status/owner_
  2. _Detailed step or ticket reference + status/owner_
- **Key issues**
  - _Issue / blocker description (linked if applicable)_

### Phase 3 – _Name_

- **Goal**: _Describe the scope/intent of phase 3._
- **Steps / detailed work items**
  1. _Detailed step or ticket reference + status/owner_
  2. _Detailed step or ticket reference + status/owner_
- **Key issues**
  - _Issue / blocker description (linked if applicable)_

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed (describe suites, commands, results).
- Outstanding tests (not run and why).
- Links to failing logs or CI runs if relevant.

## Notes & follow-up

- Additional context, architecture considerations, decisions made, or dependencies.
- Follow-up tasks for future initiative phases.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
