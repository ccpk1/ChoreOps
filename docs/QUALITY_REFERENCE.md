# 📊 Quality Reference & Compliance Tracking

**Purpose**: This document maps the KidsChores codebase to the Home Assistant Platinum Quality Scale. It serves as our 'Compliance Constitution.'

**Maintenance**: Update this file only when new quality tiers are reached or when mapping internal logic to HA requirements changes.

**Last Updated**: January 27, 2026
**Integration Version**: 0.5.0+
**Quality Level**: Platinum (Certified)

**Audience**: Code reviewers, maintainers, auditors verifying Platinum compliance.

**See Also**:

- [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) – How we code (prescriptive standards with examples)
- [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md) – Boundary checks and review procedures
- [ARCHITECTURE.md](ARCHITECTURE.md) – Data model and layered architecture
- [AGENTS.md](../../core/AGENTS.md) – Home Assistant's authoritative quality guidance

---

## 🎯 Platinum Requirement Map

**How KidsChores Architecture Satisfies Home Assistant Platinum Standards**

| HA Platinum Requirement    | KidsChores Implementation Statement                                                                                                    | Evidence Location                             | Standards Reference                                                            |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------ |
| **Strict Typing**          | 100% MyPy coverage enforced in CI/CD via `quick_lint.sh`. Zero type errors across all modules.                                         | `pyproject.toml` (mypy config), CI workflow   | [DEV_STDS § 4](DEVELOPMENT_STANDARDS.md#4-type-hints-mandatory)                |
| **Decoupling**             | Logic (Engines) physically isolated from Framework (Managers) via `utils/` and `engines/` split. No `homeassistant.*` imports allowed. | `utils/`, `engines/` directories              | [DEV_STDS § 5](DEVELOPMENT_STANDARDS.md#5-utils-vs-helpers-boundary)           |
| **Zero Hardcoded Strings** | All user-facing text routed through `const.py` → `translations/en.json`. Enforced via Phase 0 Audit Step C.                            | `const.py`, `translations/` | [DEV_STDS § 1](DEVELOPMENT_STANDARDS.md#1-no-hardcoded-strings)                |
| **Scalability**            | Storage-Only architecture removes Config Entry size limits. Reload 8x faster (2.5s → 0.3s).                                            | `.storage/kidschores_data`                    | [ARCHITECTURE § Data](ARCHITECTURE.md#storage-only-mode-advantages)            |
| **Async Dependencies**     | All I/O operations use async patterns. No blocking calls. Data coordinator pattern for efficient updates.                              | `coordinator.py`, all entity platforms        | [AGENTS.md § Async](../../core/AGENTS.md)                                      |
| **Config Flow**            | UI-based setup required. Reauthentication and reconfiguration supported.                                                               | `config_flow.py`, `options_flow.py`           | [DEV_STDS § Config Flow](DEVELOPMENT_STANDARDS.md#config-flow)                 |
| **Entity Unique IDs**      | Every entity has persistent UUID-based unique ID.                                                                                      | All entity platforms (`sensor.py`, etc.)      | [AGENTS.md § Unique IDs](../../core/AGENTS.md)                                 |
| **Service Actions**        | Registered in `async_setup()`. Validation checks entry state. Exception translations used.                                             | `services.py`                                 | [DEV_STDS § Services](DEVELOPMENT_STANDARDS.md#service-actions)                |
| **Entity Translations**    | Full i18n support via `translations/en.json` with Crowdin automation.                                                                  | `translations/` (14 languages)                | [DEV_STDS § 2](DEVELOPMENT_STANDARDS.md#2-localization--translation-standards) |
| **Test Coverage**          | 95%+ coverage enforced. 1000+ passing tests across workflow scenarios.                                                                 | `tests/` directory                            | [Test Reports](../tests/)                                                      |
| **Documentation**          | Comprehensive docs covering architecture, standards, review process.                                                                   | `docs/` directory                             | This file                                                                      |
| **Terminology Clarity**    | Strict lexicon: "Items" (storage) vs "Entities" (HA platform). Enforced via Phase 0 Audit Step B.                                      | All code and docs                             | [ARCHITECTURE § Lexicon](ARCHITECTURE.md#-lexicon-standards-critical)          |

**Platinum Certification Date**: January 2026

**Quality Scale File**: [quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml) - All 64 rules marked "done" or "exempt" with justification for each.

---

## 🏛️ Architecture as Quality

**Why Layered Architecture IS Quality Assurance**

KidsChores achieves Platinum quality not through manual review, but through architectural constraints that make defects unlikely.

### Reliability Through Persistence

**Challenge**: Gamification state (badge progress, streaks) must survive HA restarts.

**Solution**: Persisted Evaluation Queues store all badge conditions in `.storage/kidschores_data`. On coordinator init, badges are re-evaluated from storage, not recalculated from scratch.

**Quality Impact**: Zero "lost progress" bugs. State is always recoverable.

**Reference**: [ARCHITECTURE.md § Badge Lifecycle](ARCHITECTURE.md#badge-lifecycle)

### Auditability Through Automatic Timestamps

**Challenge**: Debugging state changes requires knowing "who changed what, when."

**Solution**: `data_builders.py` automatically sets `updated_at` timestamps on every Item modification. Managers never manually set timestamps.

**Quality Impact**: Built-in audit trail. Every change is traceable.

**Code Pattern**:

```python
# data_builders.py
def build_kid_data(...) -> KidData:
    return {
        "name": name.strip(),
        "updated_at": dt_now_iso(),  # ✅ Automatic
        ...
    }
```

**Reference**: [DEV_STDS § 4. Data Write Standards](DEVELOPMENT_STANDARDS.md#4-data-write-standards-crud-ownership)

### Decoupling Through Event-Driven Design

**Challenge**: When one domain (badges) needs another domain (points) to act, traditional architectures create tight coupling.

**Solution**: Managers never call each other directly. All cross-domain workflows use `async_dispatcher_send` with typed event payloads.

**Quality Impact**:

- **Testability**: Each Manager can be tested in isolation without mocking all dependencies
- **Maintainability**: Changing one Manager doesn't require changes in unrelated Managers
- **Reliability**: Eliminates circular dependency risks and "phantom state" bugs

**Code Pattern**:

```python
# GamificationManager (badge logic)
async def _evaluate_badge(self, kid_id: str) -> None:
    if self._badge_condition_met(kid_id):
        self._data[DATA_BADGES][badge_id] = badge_data
        self.coordinator._persist()
        # Emit signal - EconomyManager listens independently
        self.emit(SIGNAL_SUFFIX_BADGE_EARNED, kid_id=kid_id, points=50)

# EconomyManager (points logic) - separate file
async def _on_badge_earned(self, event: BadgeEarnedEvent) -> None:
    """Listener registered in __init__."""
    kid_id = event["kid_id"]
    points = event["points"]
    self._deposit(kid_id, points)
```

**Architectural Validation**: [CODE_REVIEW_GUIDE.md § Audit Step E](CODE_REVIEW_GUIDE.md#audit-step-e-manager-coupling-check-signal-first-logic)

**Reference**: [ARCHITECTURE.md § Event-Driven Orchestration](ARCHITECTURE.md#architectural-rules)

### Predictability Through Single Write Path

**Challenge**: Multiple code paths writing to storage cause race conditions and data corruption.

**Solution**: ONLY Manager methods can call `coordinator._persist()`. UI flows and services MUST delegate.

**Quality Impact**: Eliminates "dirty write" bugs. Data integrity is architecturally guaranteed.

**Enforcement**: Phase 0 Audit Step C verifies this boundary.

**Reference**: [ARCHITECTURE.md § Layered Architecture](ARCHITECTURE.md#layered-architecture)

---

## 🔡 Lexicon Requirement for Platinum Status

**Quality Rule**: Terminology Clarity (Platinum-Specific)

**Requirement**: Documents and code MUST distinguish between:

- **Items** / **Records**: Data in `.storage/kidschores_data` (JSON with UUIDs)
- **Entities**: Home Assistant platform objects (Sensors, Buttons, Selects)

**Rationale**: Ambiguous use of "Entity" causes:

1. **Developer confusion**: Is this a JSON dict or an HA class?
2. **Incorrect refactoring**: Moving storage logic into entity classes
3. **Documentation errors**: Users don't understand what "entity" means

**Anti-Pattern** (❌ Gold-Level Mistake):

```python
def update_chore_entity(self, chore_id: str) -> None:
    """Update the chore entity in storage."""  # ❌ Ambiguous
    self._data[DATA_CHORES][chore_id]["state"] = "claimed"
```

**Correct Pattern** (✅ Platinum-Compliant):

```python
def update_chore_item(self, chore_id: str) -> None:
    """Update the Chore Item (storage record) for the given UUID."""
    self._data[DATA_CHORES][chore_id]["state"] = "claimed"
```

**Enforcement**:

- Phase 0 Audit Step B: Lexicon Check
- Automated: `grep -rn "Chore Entity" custom_components/kidschores/`
- Manual: Code reviewer rejects PRs with ambiguous terminology

**Consequence of Violation**: PR blocked until terminology corrected. Platinum status requires this discipline.

**Reference**: [ARCHITECTURE.md § Lexicon Standards](ARCHITECTURE.md#-lexicon-standards-critical)

---

## ✅ Quality Compliance Checklist

### Automated Quality Gates (Enforced in CI/CD)

**Command**: `./utils/quick_lint.sh --fix`

This single command runs all quality checks in sequence:

1. **Ruff Check** - Code quality (unused imports, complexity, style)
2. **Ruff Format** - Code formatting (line length, indentation)
3. **MyPy** - Type checking (100% coverage required)
4. **Boundary Checker** - Architectural rules (NEW: January 2026)

**Exit Code**: Must be 0 before committing. All checks must pass.

#### Boundary Checker (`utils/check_boundaries.py`)

Automated enforcement of architectural standards from CODE_REVIEW_GUIDE.md Phase 0:

| Check Category            | Rule                                                   | Auto-Detected |
| ------------------------- | ------------------------------------------------------ | ------------- |
| **Purity Boundary**       | No `homeassistant.*` imports in `utils/` or `engines/` | ✅ Yes        |
| **Lexicon Standards**     | Use "Item"/"Record", not "Entity" for storage data     | ✅ Yes        |
| **CRUD Ownership**        | Only Managers can call `coordinator._persist()`        | ✅ Yes        |
| **Translation Constants** | Use `const.TRANS_KEY_*`, not hardcoded strings         | ✅ Yes        |
| **Logging Quality**       | Use lazy logging (`%s`), not f-strings                 | ✅ Yes        |
| **Type Syntax**           | Use `str \| None`, not `Optional[str]`                 | ✅ Yes        |
| **Exception Handling**    | Use specific exceptions, not bare `Exception:`         | ✅ Yes        |

**Current Baseline**: 11 known violations as of v0.5.0-beta3 (architectural migration in progress).

**Target**: Zero violations before Platinum recertification.

**Reference**: [CODE_REVIEW_GUIDE.md § Phase 0: Boundary Check](CODE_REVIEW_GUIDE.md#phase-0-boundary-check-mandatory)

---

### Manual Code Review Standards

**Wrong Pattern** (Never use):

```python
_LOGGER.debug(f"Processing {kid_name}")  # ❌ f-string evaluated even if log skipped
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Lazy Logging](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Constants for User-Facing Strings (100% Required)

**HA Guidance**: [AGENTS.md § Code Quality Standards](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ All user-facing strings stored in `const.py`
- ✅ Constants follow strict naming patterns:
  - `DATA_*` - Storage data keys
  - `CONF_*` - Config entry options (9 system settings only, never in schemas)
  - `CFOF_*` - Config/Options flow input fields (use in schemas)
  - `TRANS_KEY_*` - Translation keys
  - `CFOP_ERROR_*` - Config flow error keys
  - etc. (see const.py for complete patterns)
- ✅ No hardcoded strings in error messages, labels, or notifications

**Correct Pattern**:

```python
# In const.py
TRANS_KEY_ERROR_KID_NOT_FOUND = "error_kid_not_found"

# In code
raise HomeAssistantError(
    translation_domain=const.DOMAIN,
    translation_key=const.TRANS_KEY_ERROR_KID_NOT_FOUND,
    translation_placeholders={"kid_name": kid_name},
)
```

**Wrong Pattern** (Never use):

```python
raise HomeAssistantError(f"Kid {kid_name} not found")  # ❌ Hardcoded, not translatable
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Constants](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Exception Handling (Specific Exceptions Required)

**HA Guidance**: [AGENTS.md § Error Handling](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ Use most specific exception type available:
  - `ServiceValidationError` for user input errors
  - `HomeAssistantError` with translation_key for runtime errors
  - `UpdateFailed` for coordinator errors
  - `ConfigEntryAuthFailed` for auth issues
- ✅ Never use bare `except Exception:`
- ✅ Always chain exceptions with `from err`

**Correct Pattern**:

```python
try:
    data = await client.fetch_data()
except ApiConnectionError as err:
    raise HomeAssistantError("Connection failed") from err
except ApiAuthError as err:
    raise ConfigEntryAuthFailed("Auth expired") from err
```

**Wrong Pattern** (Never use):

```python
try:
    value = await sensor.read_value()
except Exception:  # ❌ Too broad
    _LOGGER.error("Failed")
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Exception Handling](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

### Docstrings (Required for All Public Functions)

**HA Guidance**: [AGENTS.md § Documentation Standards](../../core/AGENTS.md)

**KidsChores Implementation**:

- ✅ All public methods have docstrings
- ✅ Module docstrings describe purpose and entity types
- ✅ Class docstrings explain when entities update
- ✅ Clear, descriptive language

**Example**:

```python
"""Platform for KidsChores sensor entities.

Provides 26 sensor types across 3 scopes:
- Kid Scope: Per-kid sensors (points, chores completed, badges)
- Parent Scope: Parent-specific sensors (N/A for sensors)
- System Scope: Global aggregation sensors (pending approvals)
"""

class KidPointsSensor(CoordinatorEntity, SensorEntity):
    """Sensor tracking a kid's current point balance.

    Updates whenever points change via:
    - Chore approvals (adds default_points)
    - Reward redemptions (subtracts cost)
    - Bonus applications (adds bonus_points)
    - Penalty applications (subtracts penalty_points)
    """
```

**Reference**: [ARCHITECTURE.md § Code Quality Standards - Docstrings](ARCHITECTURE.md#code-quality-standards-all-implemented-)

---

## 🧪 Testing Standards Mapping

### Test Coverage (95%+ Required)

**HA Guidance**: [AGENTS.md § Testing Requirements](../../core/AGENTS.md)

**KidsChores Status**:

- ✅ All tests/\*.py passing without warnings (100% baseline)
- ✅ Small group of intentionally skipped acceptable (not counted)
- ✅ 95%+ code coverage across all modules
- ✅ All test categories covered:
  - Config flow tests (test_config_flow.py)
  - Options flow tests (test*options_flow*\*.py)
  - Coordinator tests (test_coordinator.py)
  - Service tests (test_services.py)
  - Workflow tests (test*workflow*\*.py)

**Test Validation Command**:

```bash
./utils/quick_lint.sh --fix    # Must pass with 9.5+/10
python -m pytest tests/ -v     # Must pass 560/560
```

**Reference**: [ARCHITECTURE.md § Testing Requirements](ARCHITECTURE.md#testing-requirements-95-coverage-required)

---

### Linting Standards (9.5+/10 Required)

**HA Guidance**: [AGENTS.md § Code Quality Standards](../../core/AGENTS.md)

**KidsChores Status**:

- ✅ Current score: 9.64/10
- ✅ Zero critical errors (Severity 4+)
- ✅ All files pass validation

**Linting Command**:

```bash
./utils/quick_lint.sh --fix
```

**Output Example**:

```
Your code has been rated at 9.64/10
All 50 files meet quality standards
✅ Ready to commit!
```

**Reference**: [ARCHITECTURE.md § Code Review Checklist - Testing Checks](ARCHITECTURE.md#code-review-checklist-before-committing)

---

## 📚 Section-by-Section Reference

### Configuration Flow

**HA Source**: [AGENTS.md § Configuration Flow](../../core/AGENTS.md)
**KidsChores**: [config_flow.py](../custom_components/kidschores/config_flow.py)
**Standards in ARCHITECTURE.md**: [Quality Standards § 1 - Configuration Flow](ARCHITECTURE.md#1-configuration-flow-)

**Key Points**:

- ✅ Multi-step dynamic flow
- ✅ User input validation
- ✅ Translation keys for errors
- ✅ Duplicate detection via unique IDs
- ✅ Storage separation (data vs options)

---

### Entity Development

**HA Source**: [AGENTS.md § Entity Development](../../core/AGENTS.md)
**KidsChores**: [sensor.py](../custom_components/kidschores/sensor.py), [button.py](../custom_components/kidschores/button.py)
**Standards in ARCHITECTURE.md**: [Entity Class Naming Standards](ARCHITECTURE.md#entity-class-naming-standards)

**Key Points**:

- ✅ Every entity has unique ID
- ✅ Has entity name enabled
- ✅ Device info properly set
- ✅ Translation keys for names
- ✅ State handling with None for unknown

---

### Services & Actions

**HA Source**: [AGENTS.md § Service Actions](../../core/AGENTS.md)
**KidsChores**: [services.py](../custom_components/kidschores/services.py)
**Standards in ARCHITECTURE.md**: [Quality Standards § 3 - Service Actions](ARCHITECTURE.md#3-service-actions-with-validation-)

**Key Points**:

- ✅ 17 services with validation
- ✅ ServiceValidationError for input
- ✅ HomeAssistantError with translation_key for runtime
- ✅ Config entry existence checks
- ✅ Proper exception chaining

---

### Coordinator Pattern

**HA Source**: [AGENTS.md § Data Update Coordinator](../../core/AGENTS.md)
**KidsChores**: [coordinator.py](../custom_components/kidschores/coordinator.py)
**Standards in ARCHITECTURE.md**: [Data Separation & Storage Architecture](ARCHITECTURE.md#data-separation)

**Key Pattern**:

```python
class KidsChoresDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        super().__init__(
            hass,
            logger=const.LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,  # ✅ Always pass config_entry
        )
```

---

## 🔗 Quick Links to Quality References

**Official HA Guidance**:

- [AGENTS.md](../../core/AGENTS.md) - Authoritative source for all quality standards

**KidsChores Documentation**:

- [ARCHITECTURE.md](ARCHITECTURE.md) - Complete architecture + quality standards (NEW)
- [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md) - Phase 0 audit framework + review checklists
- [quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml) - Rule implementation status

**Implementation Files**:

- [const.py](../custom_components/kidschores/const.py) - All constants and translation keys
- [config_flow.py](../custom_components/kidschores/config_flow.py) - Configuration flow
- [services.py](../custom_components/kidschores/services.py) - Service definitions
- [coordinator.py](../custom_components/kidschores/coordinator.py) - Core business logic

**Test References**:

- [tests/](../tests/) - Comprehensive test suite covering all functionality
- [TESTING_AGENT_INSTRUCTIONS.md](../tests/TESTING_AGENT_INSTRUCTIONS.md) - Testing guidance

---

## ✅ Quality Checklist for Developers

Before submitting code, verify all items:

### Pre-Commit Checklist

- [ ] Read [ARCHITECTURE.md § Quality Standards & Maintenance Guide](ARCHITECTURE.md#quality-standards--maintenance-guide)
- [ ] Run `./utils/quick_lint.sh --fix` (must pass 9.5+/10)
- [ ] Run `python -m pytest tests/ -v --tb=line` (must pass)
- [ ] No f-strings in logging (lazy logging only)
- [ ] All user-facing strings in const.py (no hardcoded strings)
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] All exceptions are specific (no bare Exception)

### Code Review Checklist

- [ ] Exception handling uses proper types (ServiceValidationError, HomeAssistantError)
- [ ] Entity unique IDs follow pattern: `entry_id_{scope_id}{SUFFIX}`
- [ ] All entities implement `available` property
- [ ] Services have proper validation and error handling
- [ ] Translation keys reference entries in en.json (master file)
- [ ] Config flow validation uses CFOF*\* and CFOP_ERROR*\* constants

### Translation Maintenance Checklist

**When updating user-facing strings**:

- [ ] **For English translations only**: Edit `translations/en.json`, `translations_custom/en_dashboard.json`, or `translations_custom/en_notifications.json` as appropriate
- [ ] **Never edit other language files** - They are automatically sourced from Crowdin project
- [ ] **Verify translation keys exist** in English master file before using in code
- [ ] **Use constants for all translation keys** (e.g., `const.TRANS_KEY_ERROR_*`)
- [ ] **Document new translation keys** if adding new notification types or error messages

**Translation Workflow**:

1. **Edit English Master**: Update translation file(s) in repository
2. **Push to l10n-staging**: Workflow automatically triggers on changes
3. **Crowdin Sync**: Automated workflow uploads English sources and triggers machine translation
4. **Alternative**: Manual download from Crowdin project available if needed

**Reference**: [ARCHITECTURE.md § Translation Architecture](ARCHITECTURE.md#translation-architecture-complete-reference)

### Language Support Maintenance Checklist ⭐ NEW

**When adding a new language to KidsChores**:

- [ ] **Add dashboard translations**: Create `translations_custom/{lang_code}_dashboard.json` with all UI strings
- [ ] **Add notification translations**: Create `translations_custom/{lang_code}_notifications.json` with all notification text
- [ ] **Valid language code**: Ensure code is in Home Assistant's `LANGUAGES` set (HA will validate automatically)
- [ ] **Submit to Crowdin**: Upload to project for professional translation
- [ ] **No metadata sections**: Ensure JSON files contain ONLY translations (no `_metadata` or version info)
- [ ] **File format**: Use standard JSON format with key-value pairs (strings only, no nested structures except notifications)
- [ ] **Testing**: Run tests after adding language to ensure `get_available_dashboard_languages()` detects it
- [ ] **Fallback handling**: English fallback works if new language file is missing or corrupted

**Language Detection (Automatic)**:

- System automatically detects new language files via filename scanning
- No code changes required to register new languages
- Crowdin-managed: Add translations to Crowdin, download files automatically synced

**Common Language Support Patterns to Verify**:

```bash
# Verify language file exists and is valid JSON
python -m json.tool translations_custom/es_dashboard.json > /dev/null && echo "Valid"

# Test language detection (admin task, for verification)
# Should show new language in available languages list

# Ensure no hardcoded language lists anywhere
grep -r "LANGUAGES = \[" custom_components/kidschores/ | grep -v "homeassistant.generated"
# Should return 0 results (no hardcoded lists)
```

**Why Dynamic Language Detection Matters**:

- ✅ Add language file = auto-detected (no code changes)
- ✅ Remove language file = auto-removed (no code cleanup)
- ✅ Crowdin-proof: No metadata to translate and corrupt
- ✅ Single source of truth: HA's LANGUAGES set for validation
- ✅ Zero maintenance: No constant updates or registrations needed

**Reference**: [ARCHITECTURE.md § Language Selection Architecture](ARCHITECTURE.md#language-selection-architecture) for full design details.

---

## ✅ Quality Compliance Checklist

**For code reviewers and maintainers: Verify these items before approving PRs.**

### Platinum Boundary Enforcement

- [ ] **Purity Check**: No `homeassistant.*` imports in `utils/`, `engines/`, `data_builders.py`
- [ ] **Lexicon Check**: No "Chore Entity" or "Kid Entity" in docstrings/comments (use "Item"/"Record")
- [ ] **CRUD Ownership**: No `_data[` or `_persist()` in `options_flow.py` or `services.py`
- [ ] **Type Checking**: `mypy custom_components/kidschores/` returns zero errors
- [ ] **Test Coverage**: New code has 95%+ test coverage

### Code Quality Standards

- [ ] All functions have complete type hints (args + return)
- [ ] Modern syntax used (`str | None` not `Optional[str]`)
- [ ] All logging uses lazy evaluation (no f-strings)
- [ ] No hardcoded user-facing strings (all via `const.py` → `translations/`)
- [ ] Specific exceptions used (not bare `except Exception:`)
- [ ] All public methods have docstrings

### Architecture Compliance

- [ ] Pure logic in `engines/` or `utils/` (no HA imports)
- [ ] HA-dependent code in `managers/` or `helpers/` (entity_helpers.py, auth_helpers.py, etc.)
- [ ] Data writes ONLY through Manager methods
- [ ] `data_builders.py` sets all timestamps automatically
- [ ] Event-driven: Managers use Dispatcher, not direct calls

**Reference**: [CODE_REVIEW_GUIDE.md § Phase 0 Boundary Check](CODE_REVIEW_GUIDE.md#phase-0-boundary-check-required-first-step)

---

## 📚 Standards Reference Links

**For detailed syntax patterns and code examples, consult:**

- **[DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md)** - Complete coding standards with examples:
  - § 1: No Hardcoded Strings - Translation patterns
  - § 3: Constant Naming Standards - Prefix patterns and usage
  - § 4: Data Write Standards - CRUD ownership rules
  - § 5: Utils vs Helpers Boundary - Import restrictions
  - § 6: DateTime & Scheduling - Always use `dt_*` helpers

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and quality rationale:
  - § Lexicon Standards - Item vs Entity terminology
  - § Layered Architecture - Component responsibilities
  - § Type System Architecture - TypedDict vs dict[str, Any] strategy

- **[CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md)** - Review procedures:
  - § Phase 0: Boundary Check - Audit steps with grep commands
  - § Boundary Validation Table - File placement rules

**Note**: This document focuses on COMPLIANCE MAPPING, not coding HOW-TO. For implementation patterns, always refer to the standards documents above.

---

### Before Marking "Ready for Review"

- [ ] All linting passes (`./utils/quick_lint.sh --fix`)
- [ ] All tests pass (`python -m pytest tests/ -v`)
- [ ] Coverage maintained at 95%+
- [ ] No regressions in existing tests
- [ ] Commit message documents what changed and why

---

## 🎯 Relationship to Certification Levels

### Bronze ✅ (Complete)

All Bronze requirements satisfied as foundation for higher tiers.

### Silver ✅ (Complete)

All Silver requirements satisfied.

### Gold ✅ (Complete)

All Gold requirements satisfied.

### Platinum ✅ (Certified)

**All requirements implemented and verified**:

- ✅ Configuration Flow
- ✅ Entity Unique IDs
- ✅ Service Actions with Validation
- ✅ Entity Unavailability Handling
- ✅ Parallel Updates
- ✅ Logging When Unavailable
- ✅ Strict Typing (100% type hints, zero mypy errors)
- ✅ runtime_data pattern
- ✅ All 64 quality scale rules (done or legitimately exempt)
- ✅ Terminology Clarity (Item vs Entity lexicon enforced)

See [quality_scale.yaml](../custom_components/kidschores/quality_scale.yaml) for complete rule status.

---

## 📝 Document Maintenance

This guide is maintained alongside the ARCHITECTURE.md document. When updating:

1. **Update both documents** if quality standards change
2. **Keep links current** (especially to AGENTS.md sections)
3. **Update Platinum Requirement Map** when new mappings established
4. **Mark completion date** when new standards are implemented

**Last Updated**: January 27, 2026
**Maintained By**: KidsChores Development Team
