# Utils Directory

Development utilities and helper scripts for ChoreOps integration development.

## Scripts

### `load_test_scenario_to_live_ha.py`

**Purpose**: Manually load test data into a running Home Assistant instance

**Type**: Development tool (NOT part of automated test suite)

**Usage**:

```bash
# Validate scenario shape only (no API calls)
python utils/load_test_scenario_to_live_ha.py --dry-run

# Load default scenario test data
python utils/load_test_scenario_to_live_ha.py

# Load a specific scenario from tests/scenarios
python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_minimal.yaml

# Load UX state-driver scenario (coded names + rotation coverage)
python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml

# Target a non-default HA URL
python utils/load_test_scenario_to_live_ha.py --ha-url http://homeassistant.local:8123

# Use token from environment (recommended)
HASS_TOKEN="<token>" python utils/load_test_scenario_to_live_ha.py

# Reset transactional data first, then load
python utils/load_test_scenario_to_live_ha.py --reset

# Apply optional post-load state seeding actions from scenario
python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml --seed-states

# Recommended UX loop: reset + load + seed with state-driver scenario
HASS_TOKEN="<token>" python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml --ha-url http://localhost:8123 --reset --seed-states

# Use a one-off shell variable instead of exporting HASS_TOKEN
TOKEN="<token>" python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml --ha-url http://localhost:8123 --reset --seed-states --token "$TOKEN"
```

**Requirements**:

- Home Assistant running at http://localhost:8123
- ChoreOps integration already installed
- Long-lived access token from Profile → Security (`--token`, `--token-env`, or prompt)

**What it does**:

1. Connects to HA REST API
2. Uses ChoreOps options flow (`manage_user`, `manage_chore`, etc.) to add entities
3. Loads data from `tests/scenarios/scenario_full.yaml` by default
4. Optionally resets transactional data first via `choreops.reset_transactional_data`
5. Supports helper flow completion for advanced chore steps
6. Optionally applies scenario-defined post-load state seed actions (`--seed-states`)
7. Supports now-relative due dates in scenario files (`now`, `now+1m`, `now+3h`, `now+7d`, etc.)

**Use cases**:

- Quickly populate dev instance with test data
- Test dashboard UI with realistic entities
- Verify options flow works end-to-end
- Manual integration testing

**UI control verification tip**:

- After loading a scenario, inspect the dashboard helper entity attributes in Developer Tools → States.
- Confirm `ui_control` appears on the helper payload for the active user.
- For the current reviewed contract, verify the Rewards header toggle updates `ui_control.gamification.rewards.header_collapse` and returns to the default expanded state when the stored override is removed.

**Not for**:

- Automated testing (use pytest instead)
- Production deployments
- CI/CD pipelines
