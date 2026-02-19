# Local wiki workflow

Use this workflow when you want to edit the ChoreOps GitHub wiki in your IDE without mixing wiki changes into normal `choreops` repository commits.

## Why this is isolated

- The wiki is a separate Git repository: `https://github.com/ccpk1/ChoreOps.wiki.git`
- The local clone lives outside the app repo at `/workspaces/choreops-wiki`
- Commits from `/workspaces/choreops` and `/workspaces/choreops-wiki` are fully independent

## One-time setup

1. Run workspace task: `Sync ChoreOps Wiki`
2. Open `choreops-dev.code-workspace`
3. Edit wiki pages under the `choreops-wiki` folder in the Explorer

## Daily workflow

1. In `choreops-wiki`, pull latest changes:
   - `git pull --ff-only`
2. Edit wiki Markdown files in your IDE
3. Commit in the wiki repo:
   - `git add -A`
   - `git commit -m "docs(wiki): <summary>"`
4. Push wiki changes:
   - `git push origin master`

## Guardrails in this repo

- `.gitignore` includes `wiki/`, `wiki-local/`, and `.wiki/` to prevent accidental in-repo wiki clones
- Workspace includes `../choreops-wiki` as a dedicated folder so wiki work is visible but separate
- A `Sync ChoreOps Wiki` task refreshes or bootstraps the local wiki clone

## Quick sanity check before app commits

From `/workspaces/choreops`:

- `git status --short`

Expected: no wiki-file changes appear here. If wiki files appear, they were created inside the main repo by mistake and should be moved to `/workspaces/choreops-wiki`.
