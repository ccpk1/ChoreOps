# Quality reference and compliance mapping

This document maps ChoreOps standards to Home Assistant quality expectations.

Use this as a stable reference for reviewers and maintainers. Keep it focused on enduring contracts, not temporary metrics.

## Scope and intent

- Defines what quality means for ChoreOps.
- Maps architectural contracts to quality outcomes.
- Points to evidence locations and validation commands.

## Source documents

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md)
- [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md)
- [AGENTS.md](../AGENTS.md)
- [core/AGENTS.md](../../core/AGENTS.md)

## Quality mapping

| Home Assistant quality area    | ChoreOps contract                                                         | Primary evidence                                           |
| ------------------------------ | ------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Strict typing                  | Public APIs and internal workflows are type-annotated, validated by MyPy. | `pyproject.toml`, `custom_components/choreops/`, CI config |
| Decoupled architecture         | Pure logic is isolated from Home Assistant framework code.                | `engines/`, `utils/`, `helpers/`, `managers/`              |
| Config flow quality            | Setup and reconfiguration are UI-first and validated.                     | `config_flow.py`, `options_flow.py`, translations          |
| Service robustness             | Services validate inputs and raise translatable exceptions.               | `services.py`, `translations/en.json`                      |
| Entity reliability             | Entities have stable IDs, translation keys, and availability handling.    | platform files, `entity.py`, `icons.json`                  |
| Data integrity                 | Storage writes follow manager-owned single write path.                    | `managers/`, `coordinator.py`, `data_builders.py`          |
| Event-driven orchestration     | Cross-domain writes are signal-driven, not direct manager coupling.       | `managers/`, dispatcher patterns                           |
| Entry scope safety             | Runtime behavior remains scoped to the active config entry.               | coordinator and manager routing paths                      |
| Diagnostics and supportability | Diagnostics are available and redact sensitive content.                   | `diagnostics.py`                                           |
| Documentation quality          | User and developer docs remain aligned with implementation.               | `README.md`, `docs/`, wiki                                 |

## Architecture quality contracts

### Layer boundaries

- `engines/`, `utils/`, and `data_builders.py` stay framework-independent.
- Home Assistant registry and runtime helpers live in `helpers/`.
- State changes and persistence live in `managers/`.
- Coordinator provides infrastructure orchestration, not domain business rules.

### Terminology contract

- Storage objects are Items/Records.
- Home Assistant objects are Entities.
- User lifecycle terminology uses User and Approver role capability language.

### Data write contract

- Only managers write to `coordinator._data` and call persistence methods.
- UI flows and services delegate writes through manager APIs.

### Signal-first contract

- Managers do not directly invoke other managers for writes.
- Cross-domain state transitions use dispatcher signals.
- Signals are emitted after successful persistence.

### Translation contract

- User-facing strings are constants plus translation keys.
- English master translation files are the source of truth for content keys.

## Validation model

### Automated gates

Run:

```bash
./utils/quick_lint.sh --fix
mypy custom_components/choreops/
python -m pytest tests/ -v --tb=line
```

### Review gates

Use [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md) to validate:

- Purity and architecture boundaries
- Lexicon and terminology correctness
- CRUD ownership and signal-first orchestration
- Translation/constant usage
- Entry-scope and migration safety

## Non-goals for this document

Do not store in this file:

- Test counts, line counts, or method counts
- Dated certification claims
- Temporary migration phases
- File line references that require frequent updates

## How to keep this current

Update this document only when:

- A quality contract changes
- A new required gate is introduced
- A source-of-truth document moves or is replaced
