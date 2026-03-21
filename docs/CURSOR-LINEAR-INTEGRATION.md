# Cursor + Linear Integration (MCP)

## Purpose

Document how Linear was connected to Cursor so issues can be created/updated directly from Cursor workflows.

---

## Integration model

This setup uses **MCP (Model Context Protocol)** in Cursor:

- Cursor loads a Linear MCP server configuration.
- Cursor reads tool schemas from local MCP descriptor files.
- Cursor calls Linear actions (for example, create issue) through MCP tools.

In this project, the Linear MCP server used was:

- `project-0-Cursor_test_project-linear`

---

## Where configuration lives

Cursor stores MCP descriptors in the project-level MCP directory:

- `.../mcps/project-0-Cursor_test_project-linear/tools/*.json`

Key tool descriptors used:

- `list_teams.json`
- `save_issue.json`
- (optional) `list_issue_labels.json`, `list_issue_statuses.json`

These files define parameters and schema for each Linear action.

---

## Authentication flow

1. Enable/add Linear MCP in Cursor.
2. Authenticate the Linear MCP server (OAuth/token flow prompted by Cursor).
3. Confirm access by listing teams.

Validation check (conceptual):

- Call `list_teams` and confirm your team appears (for example `Ai_testing_space`).

If auth fails, re-run MCP auth from Cursor and re-check `list_teams`.

---

## Minimal operational flow used in this project

1. Read `save_issue` tool schema (required fields: `title`, `team`).
2. Resolve target team via `list_teams`.
3. Create issue with `save_issue`:
   - `team`
   - `title`
   - `description` (Markdown)
   - `priority` (Linear numeric scale)
4. Capture returned issue URL and ID in docs/tracker.

---

## Priority mapping used by Linear tool

- `1` = Urgent
- `2` = High
- `3` = Normal
- `4` = Low

---

## Issues created during this project

- `AI-6` — v6 workflow hardening
- `AI-7` — Task 3 post-prompt baseline run + gate checks
- `AI-8` — Task 4 topK 10 -> 5 contamination experiment
- `AI-9` — Logger path hardening (`question/text`, undefined reply prevention)

---

## Troubleshooting

### Team not found

- Run `list_teams` and use exact team name/ID in `save_issue`.

### Tool call rejected

- Re-open tool descriptor and verify argument names/types match schema.

### Auth expired

- Re-authenticate Linear MCP in Cursor and retry.

---

## Security notes

- Do not hardcode API tokens in repo files.
- Use Cursor MCP auth/session handling.
- Treat issue descriptions as potentially sensitive; avoid pasting secrets/log tokens.

