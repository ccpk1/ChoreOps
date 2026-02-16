#!/bin/bash
# Quick notification testing script for KidsChores development

set -e

LOG_FILE="/workspaces/core/config/home-assistant.log"

echo "=================================================="
echo "KidsChores Notification Testing Utility"
echo "=================================================="
echo ""

# Check if HA is running
if ! pgrep -f "homeassistant" > /dev/null; then
    echo "❌ Home Assistant is not running!"
    echo "   Start it with: Run Home Assistant Core task"
    exit 1
fi

echo "✅ Home Assistant is running"
echo ""

# Function to show menu
show_menu() {
    echo "Choose a test option:"
    echo ""
    echo "  1) Watch notification logs (real-time)"
    echo "  2) View recent notification logs"
    echo "  3) Check notification service availability"
    echo "  4) Show current notify service settings"
    echo "  5) Test persistent notification"
    echo "  6) Exit"
    echo ""
    read -p "Enter option (1-6): " choice
    echo ""
}

# Function to watch logs
watch_logs() {
    echo "🔍 Watching notification logs (Ctrl+C to stop)..."
    echo "=================================================="
    tail -f "$LOG_FILE" | grep -i --line-buffered "notification\|notify\|_notify_kid"
}

# Function to view recent logs
recent_logs() {
    echo "📋 Recent notification logs (last 50):"
    echo "=================================================="
    grep -i "notification\|notify" "$LOG_FILE" | tail -50
    echo ""
    echo "Press Enter to continue..."
    read
}

# Function to check service availability
check_services() {
    echo "🔧 Checking available notification services..."
    echo "=================================================="
    echo ""
    echo "To check services manually:"
    echo "1. Go to Developer Tools → Services in HA UI"
    echo "2. Search for 'notify.'"
    echo "3. Available services:"
    echo "   - persistent_notification.create (always available)"
    echo "   - notify.mobile_app_* (if mobile app set up)"
    echo ""
    echo "Press Enter to continue..."
    read
}

# Function to show notify settings
show_notify_settings() {
    echo "⚙️  Current notification service settings:"
    echo "=================================================="
    echo ""
    echo "To view kid/parent notify services:"
    echo "1. Go to Developer Tools → States in HA UI"
    echo "2. Search for: sensor.kc_*_profile"
    echo "3. Look for 'mobile_notify_service' attribute"
    echo ""
    echo "Common values:"
    echo "  - persistent_notification (best for dev)"
    echo "  - notify.mobile_app_<device> (production)"
    echo ""
    echo "Press Enter to continue..."
    read
}

# Function to test persistent notification
test_notification() {
    echo "🔔 Sending test notification..."
    echo "=================================================="
    echo ""

    echo "To manually test a notification:"
    echo ""
    echo "1. Go to Developer Tools → Services in HA UI"
    echo "2. Select: persistent_notification.create"
    echo "3. Enter YAML:"
    echo ""
    echo "   title: 'KidsChores Test'"
    echo "   message: 'Notifications are working!'"
    echo "   notification_id: 'kidschores_test'"
    echo ""
    echo "4. Click 'CALL SERVICE'"
    echo "5. Check notification bell icon (top right)"
    echo ""
    echo "Press Enter to continue..."
    read
}

# Main loop
while true; do
    show_menu

    case $choice in
        1) watch_logs ;;
        2) recent_logs ;;
        3) check_services ;;
        4) show_notify_settings ;;
        5) test_notification ;;
        6)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid option. Please try again."
            echo ""
            ;;
    esac
done
