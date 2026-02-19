# Supporting artifact: Translation/runtime mismatch inventory

## Scope

- Runtime sources audited:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
- Translation source audited:
  - `custom_components/choreops/translations/en.json`
- Custom translation source audited:
  - `custom_components/choreops/translations_custom/en_notifications.json`
  - `custom_components/choreops/translations_custom/en_dashboard.json`
  - `custom_components/choreops/translations_custom/en_report.json`

## Runtime key inventory (priority lockstep set)

The following runtime-consumed legacy key IDs were confirmed in `const.py` and flow/runtime call sites:

- `kid_count`
- `kids`
- `add_kid`
- `edit_kid`
- `delete_kid`
- `invalid_kid`
- `invalid_parent`
- `kid_not_found_by_name`
- `parent_not_found_by_name`
- `notif_message_data_reset_kid`
- `dashboard_kid_selection`
- `per_kid`

## Parity verification result

All priority runtime-consumed keys above are present in `translations/en.json`.

### Evidence snippets

- Config/Options step IDs in runtime:
  - `CONFIG_FLOW_STEP_KID_COUNT = "kid_count"`
  - `CONFIG_FLOW_STEP_KIDS = "kids"`
  - `OPTIONS_FLOW_STEP_ADD_KID = "add_kid"`
  - `OPTIONS_FLOW_STEP_EDIT_KID = "edit_kid"`
  - `OPTIONS_FLOW_STEP_DELETE_KID = "delete_kid"`
- Error/notification keys in runtime:
  - `TRANS_KEY_CFOF_INVALID_KID = "invalid_kid"`
  - `TRANS_KEY_CFOF_INVALID_PARENT = "invalid_parent"`
  - `TRANS_KEY_ERROR_KID_NOT_FOUND_BY_NAME = "kid_not_found_by_name"`
  - `TRANS_KEY_ERROR_PARENT_NOT_FOUND_BY_NAME = "parent_not_found_by_name"`
  - `TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_KID = "notif_message_data_reset_kid"`
  - `TRANS_KEY_CFOF_DASHBOARD_KID_SELECTION = "dashboard_kid_selection"`

## Mismatch summary

- Missing runtime key IDs in `en.json`: **0**
- Runtime key IDs present with canonical wording values: **yes**
- Translation key-only renames without runtime lockstep in this wave: **none introduced**

## Terminology cleanup summary (custom English translations)

- `en_notifications.json` comment wording updated:
  - `KID NOTIFICATIONS` → `ASSIGNEE NOTIFICATIONS`
  - `PARENT NOTIFICATIONS` → `APPROVER NOTIFICATIONS`
- `en_dashboard.json`: no `kid|parent|KidsChores` findings
- `en_report.json`: no `kid|parent|KidsChores` findings

## Sequence 4 conclusion

For the current wave, runtime/translation parity is intact and non-exception English custom translation wording is aligned with terminal terminology policy while preserving compatibility key IDs.
