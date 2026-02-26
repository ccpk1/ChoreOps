# ChoreOps release checklist

Use this checklist before tagging any release.

The goal is predictable releases with safe migrations, stable translations, and clean quality gates.

## 1) Version and schema readiness

- [ ] Update integration version metadata (`manifest.json`, release notes, docs as needed).
- [ ] If storage shape changed, increment schema constant in `const.py`.
- [ ] Ensure migration logic exists for schema transitions.
- [ ] Confirm migration paths are idempotent and safe across upgrade paths.

## 2) Quality gates

Run and pass:

```bash
./utils/quick_lint.sh --fix
mypy custom_components/choreops/
python -m pytest tests/ -v --tb=line
```

Checklist:

- [ ] No unresolved lint errors in release scope.
- [ ] No unresolved type errors in release scope.
- [ ] No failing tests in release scope.
- [ ] No debug artifacts or temporary flags remain.

## 3) Boundary and architecture verification

- [ ] Run boundary checks from [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md).
- [ ] Confirm no direct storage writes outside managers.
- [ ] Confirm signal-first cross-manager write orchestration.
- [ ] Confirm pure modules remain Home Assistant import free.

## 4) Translation and constant verification

- [ ] New user-facing strings use constants and translation keys.
- [ ] English master translation files are updated.
- [ ] Non-English translations are managed through localization workflow.
- [ ] Release notes reflect user-visible changes in plain language.

## 5) Configuration and service verification

- [ ] Config flow setup path works.
- [ ] Options flow updates persist and reload behavior is correct.
- [ ] Service calls validate input and return translatable errors.
- [ ] Entity registration and IDs remain stable.

## 6) Storage and migration safety

- [ ] Create a backup before upgrade validation.
- [ ] Validate upgrade from prior supported schema.
- [ ] Validate restore path for rollback confidence.
- [ ] Confirm migration summary logs are actionable and clean.
- [ ] Record go/no-go decision with rationale.

## 7) Documentation sync

- [ ] Update `README.md` for user-visible changes.
- [ ] Update architecture or standards docs if contracts changed.
- [ ] Update wiki pages for new features or changed workflows.
- [ ] Ensure terminology is consistent: User/Approver roles and Item/Entity lexicon.

## 8) Release and post-release checks

- [ ] Tag and publish release artifacts.
- [ ] Confirm integration loads in Home Assistant.
- [ ] Confirm primary entities and services operate in a clean environment.
- [ ] Monitor for migration or configuration regressions.

## Rollback readiness

If a critical issue appears after release:

1. Document issue scope and reproduction.
2. Prepare a rollback or hotfix branch.
3. Re-run quality gates and migration checks.
4. Publish a patch release with clear upgrade guidance.
