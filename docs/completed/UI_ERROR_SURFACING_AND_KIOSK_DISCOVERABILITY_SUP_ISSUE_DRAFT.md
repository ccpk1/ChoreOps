# Proposed GitHub feature request

- **Title**: `[REQ] Surface helpful backend errors in the UI and warn when unlinked users are used without kiosk mode`
- **Suggested labels**: `enhancement`, `enh: feature`
- **Feature area**: `Integration logic/state`

## Form-ready draft

### Problem or use case

ChoreOps already does a good job logging failures, but many of those failures never make it back to the user in the Home Assistant UI.

The immediate example is button-driven actions such as chore claim buttons. If the backend catches a meaningful authorization or validation error, logs it, and then returns cleanly, the frontend sees the action as successful and the user gets no toast or inline feedback. The log contains the explanation, but the person using the dashboard does not.

This is especially confusing around kiosk mode and HA user linking. A common family setup is a shared or wall-mounted tablet. If a ChoreOps user has no linked Home Assistant user and kiosk mode is disabled, claim buttons can fail in a way that is easy to diagnose from logs but not obvious to the user.

That combination created a long troubleshooting loop even though the underlying feature already exists and works well once it is discovered.

### Proposed solution

Improve user-facing error surfacing for actionable backend failures, with the first focus on buttons and service calls.

Requested scope:

1. When button actions fail with a meaningful backend exception, let that failure reach Home Assistant so the native frontend can show the user-facing error toast.
2. Review service-call entry points and ensure user-actionable failures return helpful, translatable errors instead of log-only outcomes or overly technical wording.
3. Keep the existing strong logging, but treat logs as support evidence rather than the only place a user can learn why an action failed.
4. Improve kiosk-mode/user-link discoverability:
   - Add an inline hint on the HA User field explaining that kiosk mode may be appropriate for shared or wall-mounted tablets.
   - Add a soft warning when a user profile has no linked HA account and kiosk mode is disabled.
   - Add a dashboard generator warning/check when the user selects an assignee who is not linked to an HA user while kiosk mode is disabled.

I do **not** think this needs to include every possible onboarding or setup improvement right now. The highest-impact, lowest-effort piece appears to be the warning for `no linked HA user + kiosk mode disabled`, plus the dashboard generator check.

### Expected outcome

- Users see helpful feedback in the UI at the moment an action fails instead of having to inspect system logs.
- Shared-tablet and wall-mounted dashboard setups become much easier to configure correctly.
- Support burden drops because the most common kiosk-mode/user-linking mistake is explained proactively.
- The existing backend logging remains useful for maintainers, while the UI becomes more self-explanatory for families using the system.

### Alternatives considered

- Relying on logs only: good for maintainers, but not for the person pressing the button.
- Expanding onboarding/setup flow immediately: useful, but larger in scope than necessary for the main pain point.
- Document-only solution: helpful, but weaker than showing the user the problem at the moment it happens.

### Additional context

- A recent claim-button proof of concept confirmed that simply allowing the existing translated auth exception to propagate causes the native frontend error toast to appear as expected.
- This suggests there may be a broader opportunity across other buttons and service calls wherever ChoreOps already knows the action failed and already has meaningful error text.
- Related kiosk-mode discoverability suggestions from user feedback:
  - Inline hint in the user edit form
  - Warning when HA user is `none` and kiosk mode is disabled
  - Onboarding question during first-time setup
- Of those, the second option appears to have the best impact-to-effort ratio.

## Notes for triage

- Primary value: better user-facing UX with minimal backend behavior change.
- Secondary value: reduce kiosk-mode and HA-user-linking confusion before users hit broken claim-button behavior.
- Good first implementation slices:
  1. Audit and re-raise existing actionable button exceptions.
  2. Normalize user-facing service-call errors.
  3. Add the non-kiosk unlinked-user warning plus dashboard generator check.
