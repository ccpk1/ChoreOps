# ntfy Integration Guide

## Setup

### 1. Deploy ntfy Server

```bash
docker run -d --name ntfy --restart=unless-stopped -p 8090:80 -v /var/lib/ntfy:/var/lib/ntfy binwiederhier/ntfy serve
```

### 2. Home Assistant Configuration

```yaml
notify:
  - platform: rest
    name: ntfy_notifications
    resource: https://your-ntfy-server/choreops
    method: POST
    message_param_name: message
    title_param_name: title
```

### 3. Automation Example

```yaml
automation:
  - alias: "Chore Due via ntfy"
    trigger:
      - platform: state
        entity_id: sensor.chore_due
        to: "due"
    action:
      - service: notify.ntfy_notifications
        data:
          title: "Chore Due"
          message: "{{ trigger.to_state.attributes.friendly_name }} is due!"
```

### Topics

| Topic | Purpose |
|-------|---------|
| choreops/due | Chores due now |
| choreops/reminders | Upcoming reminders |
| choreops/completed | Completion confirmations |
| choreops/alerts | Urgent alerts |

### Security

Enable auth on self-hosted instances:

```yaml
auth-file: /var/lib/ntfy/user.db
auth-default-access: deny-all
```

Then add auth header:

```yaml
headers:
  Authorization: "Basic <base64(user:pass)>"
```

## Compatibility

- Works with HA REST notify platform
- Supports HTTP and WebSocket
- Priority levels: min, low, default, high, urgent
- Actions: view, http, broadcast
