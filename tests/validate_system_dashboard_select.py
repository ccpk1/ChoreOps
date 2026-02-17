"""Validation script for SystemDashboardAdminKidSelect entity.

This script validates the new system-level select entity implementation.
Run from KidsChores integration workspace root.
"""

import json

from custom_components.choreops import const

# Verify all constants are defined
required_constants = [
    "SELECT_KC_UID_SUFFIX_SYSTEM_DASHBOARD_ADMIN_KID_SELECT",
    "TRANS_KEY_SELECT_SYSTEM_DASHBOARD_ADMIN_KID",
    "TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_KID",
    "ATTR_DASHBOARD_HELPER_EID",
    "ATTR_SELECTED_KID_SLUG",
    "ATTR_SELECTED_KID_NAME",
]

print("✅ SystemDashboardAdminKidSelect Validation")
print("=" * 50)
print("\n📋 Constant Verification:")
for constant_name in required_constants:
    value = getattr(const, constant_name, None)
    if value is None:
        print(f"  ❌ {constant_name}: NOT FOUND")
    else:
        print(f"  ✅ {constant_name}: {value}")

# Verify select module can be imported
print("\n📋 Module Import Check:")
try:
    from custom_components.choreops import select

    print("  ✅ select.py imports successfully")

    # Check if class exists
    if hasattr(select, "SystemDashboardAdminKidSelect"):
        print("  ✅ SystemDashboardAdminKidSelect class found")
    else:
        print("  ❌ SystemDashboardAdminKidSelect class NOT found")
except ImportError as e:
    print(f"  ❌ Import failed: {e}")

# Check translation file
print("\n📋 Translation Check:")

try:
    with open("custom_components/choreops/translations/en.json") as f:
        translations = json.load(f)

    # Check entity translation
    entity_trans = (
        translations.get("entity", {})
        .get("select", {})
        .get("system_dashboard_admin_kid_select")
    )
    if entity_trans:
        print(f"  ✅ Entity translation found: {entity_trans.get('name')}")
    else:
        print("  ❌ Entity translation NOT found")

    # Check purpose translation
    purpose_trans = (
        translations.get("entity", {})
        .get("select", {})
        .get("system_dashboard_admin_kid_select", {})
        .get("state_attributes", {})
        .get("purpose", {})
        .get("state", {})
        .get("purpose_system_dashboard_admin_kid")
    )
    if purpose_trans:
        print(f"  ✅ Purpose translation found: {purpose_trans}")
    else:
        print("  ❌ Purpose translation NOT found")

except FileNotFoundError:
    print("  ❌ Translation file not found")
except json.JSONDecodeError as e:
    print(f"  ❌ Translation file JSON error: {e}")

print("\n" + "=" * 50)
print("✅ Validation complete")
