# Utils Directory

Development utilities and helper scripts for KidsChores integration development.

## Scripts

### `load_test_scenario_to_live_ha.py`

**Purpose**: Manually load test data into a running Home Assistant instance

**Type**: Development tool (NOT part of automated test suite)

**Usage**:

```bash
# Load test data
python utils/load_test_scenario_to_live_ha.py

# Reset all data first, then load
python utils/load_test_scenario_to_live_ha.py --reset
```

**Requirements**:

- Home Assistant running at http://localhost:8123
- KidsChores integration already installed
- Long-lived access token from Profile → Security

**What it does**:

1. Connects to HA REST API
2. Uses options flow to add kids, parents, chores, rewards, bonuses, penalties
3. Loads data from `tests/testdata_scenario_full.yaml`
4. Optionally resets all data first (creates backup)

**Use cases**:

- Quickly populate dev instance with test data
- Test dashboard UI with realistic entities
- Verify options flow works end-to-end
- Manual integration testing

**Not for**:

- Automated testing (use pytest instead)
- Production deployments
- CI/CD pipelines
