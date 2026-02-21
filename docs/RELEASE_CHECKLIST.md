# ChoreOps Release Checklist

Quick reference checklist for preparing and validating releases. Complete ALL items before tagging a release.

## Pre-Release Validation

### Version & Schema Updates

- [ ] **manifest.json version**: Updated to match release (e.g., `"version": "0.5.0"`)
- [ ] **Schema version (const.py)**: Incremented if data structure or migration changes
  - Location: `SCHEMA_VERSION_STORAGE_ONLY` constant
  - Rule: Increment for ANY storage data changes or new migrations
  - Example: v0.5.0 should use schema 50 (aligns version with schema, but beta verions would be in the 40s)
- [ ] **Migration file**: If schema changed, verify migration logic exists
  - File: `migration_pre_v{VERSION}.py`
  - Verify: All schema versions from previous → current have migration paths
  - Cumulative: Each version should run ALL previous migrations (defensive)
- [ ] **Migration observability log review**: Verify structured schema migration summary is present in startup logs
  - Required fields: users migrated, linked merges, standalone parent creations, collisions, remap totals, remap additions
  - Verify summary persisted in metadata when applicable (`meta.schema45_last_summary`)

### Code Quality

- [ ] **Linting passes**: `./utils/quick_lint.sh --fix` (9.5+ score required)
- [ ] **All tests pass**: `python -m pytest tests/ -v --tb=line` (100% pass rate)
- [ ] **Type checking**: No mypy errors if type checking enabled
- [ ] **No debug code**: Remove print statements, debug flags, test-only paths

### Documentation

- [ ] **README.md**: Version number updated, new features documented
- [ ] **CHANGELOG.md**: All changes since last release documented
- [ ] **ARCHITECTURE.md**: Updated if data structures or patterns changed
- [ ] **Translation files**: English master files current, Crowdin synced
  - Verify `en.json`, `en_notifications.json`, `en_dashboard.json` complete
  - Trigger Crowdin sync via `l10n-staging` branch if needed

### Constants & Standards

- [ ] **New constants added**: All hardcoded strings moved to const.py
- [ ] **Naming patterns**: Follow `DATA_*`, `CFOF_*`, `TRANS_KEY_*` conventions
- [ ] **Legacy constants**: Old constants marked with `_LEGACY` or `_DEPRECATED` suffix
- [ ] **STANDARDS.md compliance**: Constants organized per lifecycle suffixes

## Schema Version Change Process

**When to increment schema version:**

- Storage data structure changes (new fields, renamed keys, deleted fields)
- Data format changes (datetime parsing, enum values, list→dict conversions)
- New migration logic required for existing installations
- Breaking changes to how data is stored or accessed

**How to increment schema version:**

1. **Update const.py**: Increment `SCHEMA_VERSION_STORAGE_ONLY`
2. **Add migration method**: Create `_migrate_to_v{NEW_VERSION}()` in migration file
3. **Test migration path**: Verify upgrade from previous version works
4. **Update docs**: Document schema change in ARCHITECTURE.md
5. **Add to meta.migrations_applied**: Include migration name in tracking

**Example schema version alignment:**

- v0.5.0 release → schema 50
- v0.6.0 release → schema 60
- Minor releases (v0.5.1) typically don't change schema

## Release Branch Strategy

### Standard Release Flow

1. **Feature branch** → Complete all work, tests passing
2. **Merge to l10n-staging** → Trigger Crowdin translation sync
3. **Pull translations back** → Merge l10n-staging updates to feature branch
4. **Final validation** → Run full checklist above
5. **Merge to main** → Tag release with `vX.Y.Z`

### Critical Paths

- **Never commit** non-English translation files manually (Crowdin manages these)
- **Always sync** l10n-staging before final merge (translations must be current)
- **Test migration** from previous release schema version

## Post-Release Validation

- [ ] **Integration loads** in Home Assistant (no startup errors)
- [ ] **Entities created**: All expected sensors/buttons/selects appear
- [ ] **Config flow works**: Fresh setup creates correct entities
- [ ] **Options flow works**: Editing entities persists changes
- [ ] **Migration tested**: Upgrade from previous version succeeds
- [ ] **Backup/restore validation completed**
  - Create pre-upgrade backup artifact
  - Execute upgrade and confirm migration summary counts
  - Restore backup and confirm prior state is recoverable
- [ ] **Dashboard compatible**: Kid Dashboard renders correctly with new schema

## Migration go/no-go gate

- [ ] **Go/no-go decision recorded**
  - GO only when migration-path suites pass:
    - `python -m pytest tests/test_migration_hardening.py tests/test_config_flow_use_existing.py -v --tb=line`
  - GO only when rollback validation (backup + restore) has been executed
  - NO-GO if migration summary logs show unresolved collisions/remaps without documented acceptance

## Common Release Issues

**Problem: Schema version not incremented**

- Symptom: Storage data changes but old installations break
- Fix: Increment schema, add migration, re-release as patch version

**Problem: Translation files not synced**

- Symptom: Missing or outdated UI text in non-English languages
- Fix: Push to l10n-staging, wait for Crowdin action, pull updates

**Problem: Migration not running**

- Symptom: Old data format causes errors on upgrade
- Fix: Verify schema version check in coordinator `__init__()`, ensure migration method exists

**Problem: Tests fail after version bump**

- Symptom: Test fixtures reference old schema version
- Fix: Update `testdata_scenario_*.yaml` files with new schema version

## Emergency Rollback

If critical bug discovered post-release:

1. **Document the issue**: Log in GitHub issue with reproduction steps
2. **Revert or hotfix**: Quick patch or revert problematic commit
3. **Test thoroughly**: Verify fix doesn't introduce new bugs
4. **Bump patch version**: e.g., v0.5.0 → v0.5.1
5. **Fast-track release**: Skip full checklist if only critical fix

---

**Last Updated**: January 9, 2026
**Applies to**: ChoreOps v0.5.0+
