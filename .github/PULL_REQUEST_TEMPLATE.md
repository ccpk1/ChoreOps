## Summary

- Describe what changed and why.

## Linked issue

- Closes #

## Main merge automation checks

- [ ] PR body uses a closing keyword when applicable (`Closes #...`)
- [ ] Correct release-note label is applied for `.github/release.yml` categorization
- [ ] Excluded triage or status labels have been removed before merge
- [ ] PR title is suitable for generated release notes

## Change type

- [ ] Bug fix
- [ ] Enhancement
- [ ] Refactor
- [ ] Documentation

## Scope

- [ ] Integration logic/state
- [ ] Dashboard/template behavior
- [ ] Services/automations
- [ ] Documentation/wiki

## Dashboard source boundary

- [ ] This PR does not introduce manual source edits under `custom_components/choreops/dashboards/`
- [ ] If dashboard source changes are needed, a corresponding PR is opened in `ccpk1/ChoreOps-Dashboards`

## Standards references

- [Architecture](../docs/ARCHITECTURE.md)
- [Development standards](../docs/DEVELOPMENT_STANDARDS.md)
- [Quality reference](../docs/QUALITY_REFERENCE.md)
- [Technical troubleshooting wiki](https://github.com/ccpk1/choreops/wiki/Technical:-Troubleshooting)

## Validation

- [ ] `./utils/quick_lint.sh --fix`
- [ ] `python -m pytest tests/ -v --tb=line` (or targeted suite with rationale)

## Documentation impact

- [ ] No documentation updates needed
- [ ] Documentation updated (README / wiki / inline docs)

## Release notes

- [ ] No release notes needed
- [ ] Release notes needed (summarize user-visible changes below)

- Release note summary:

## Breaking changes

- [ ] No breaking changes
- [ ] Breaking change (describe migration or compatibility impact below)
