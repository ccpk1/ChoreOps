# Contributing to ChoreOps

Thanks for contributing to ChoreOps.

## Quick start

1. Fork and clone the repository
2. Create a feature branch from `main`
3. Make focused changes with tests when applicable
4. Run validation locally
5. Open a pull request

## Local validation requirements

Run these before opening a PR:

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- `python -m pytest tests/ -v --tb=line`

If your change only affects a narrow area, you may run a targeted test suite, but include rationale in your PR.

## Code quality expectations

- Follow `docs/DEVELOPMENT_STANDARDS.md`
- Follow `docs/ARCHITECTURE.md`
- Follow `docs/QUALITY_REFERENCE.md`
- Use constants instead of hardcoded user-facing strings
- Use lazy logging (for example, `LOGGER.debug("value: %s", value)`)
- Keep changes minimal and scoped to the problem

## Pull request expectations

- Link the issue when applicable (`Closes #...`)
- Explain what changed and why
- Describe validation performed
- Note documentation impact (README/wiki/docs)
- Call out breaking changes and migration impact when relevant

## Dashboard source of truth policy

- Do not submit dashboard template source changes to this repository.
- Any PR that changes files under `custom_components/choreops/dashboards/` will be closed and redirected.
- Submit dashboard template, registry, and preference documentation changes to `ccpk1/ChoreOps-Dashboards`.
- Dashboard assets in this repository are synchronized from `ccpk1/ChoreOps-Dashboards`.

## Discussions vs issues

- Use GitHub Discussions for questions and early ideas
- Use GitHub Issues for actionable bugs and feature requests

## Need help?

- Support and usage questions: GitHub Discussions
- Bug reports: GitHub Issues templates
