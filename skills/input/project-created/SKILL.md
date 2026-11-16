---
name: project-created
description: "a `project_created` event arrives (`event_data.target_type: \"Project\"`)."
---

# Project created

Type: input-processing skill
Apply when: a `project_created` event arrives (`event_data.target_type: "Project"`).

## Procedure

1. Read the new project record: `get_single_project` by `project_id` (or `project_slug`) from `event_data.content_payload`. When `content_payload` is null, take the numeric id from the `- /company/<c>/projects/<id>/knowledge` line in `event_data.knowledge_path`; `get_single_project` with `project_slug` has returned "Project not found" for an existing slug — fall back to `project_id` / `get_projects`.
2. Decide what a brand-new project is missing that only structure requires:
   - `tree_based_project_directory_data` for this project — if empty, scaffold the knowledge root with `add_tree_based_project_directory_item(name: "knowledge", item_type: "directory", project_id: ...)`.
   - `add_knowledge_activity_log(actor_name: "w-ai", action_text: "project <slug> created", target_path: <line from event_data.knowledge_path>)`.
3. If the project needs first milestones/todos/status alignment, do **not** invent them — route: `create_ai_task(project_id: ..., adder_profile: "workspace", assigneee_profile: "project_manager", description: "Define initial milestones, todos, and status-period alignment for project <slug>", proposed_task_context: "<project payload summary>", input_event_entity_id: <event_id>, level: 0)`.
   - Pitfall (2026-11-16): `create_ai_task` validates the assignee against the live Hermes gateway and raises "Unknown assignee profile" for names the gateway 404s — `planner` is not valid in the current deployment. Probe gateway profiles read-only via `GET <HERMES_BASE_URI>/p/<profile>/v1/models` (path-based, not `?profile=`; 200 = exists) or list `~/.hermes/profiles/`, then route `project_manager` as the planner-equivalent. Valid names observed: workspace, w_ai, coder, project_manager, business_analyst, market_research, message_analyst. A profile that isn't a clean equivalent → create the task WITHOUT `assigneee_profile`; PWR then raises a "missing assignee profile" blockers attention item instead of guessing identities.
   - `assignee_profile` is validated against local Hermes profiles (`~/.hermes/profiles/`), NOT against PWR: PWR `list_ai_profiles` on both read-mcp and config-mcp returns `[]` even when gateway profiles exist, so it cannot confirm a profile. `planner` is not registered on this gateway; the planning-capable registered profiles are `project_manager`, `business_analyst`. Use `project_manager` and note the substitution in `proposed_task_context`.
   - Optional id fields (`input_event_entity_id`, `task_id`, `topic_id`) must be OMITTED, not sent as `null` — a null fails schema validation before the call reaches the server.
   - After 3 rejected calls the `pwr-task` server pauses ~45s; fix arguments and wait rather than retrying fast.
4. Never post a celebration message for this event; it is not a work signal.

## Tools used

| Tool | Endpoint | Key arguments |
|---|---|---|
| `get_single_project` | read-mcp | `project_id` / `project_name` / `project_slug` |
| `tree_based_project_directory_data` | read-mcp | `project_id` |
| `add_tree_based_project_directory_item` | action-mcp | required: `name`; optional: `item_type` (`directory`\|`knowledge_item`\|`adr`\|`note`), `parent_id`, `content`, `file_path` |
| `add_knowledge_activity_log` | action-mcp | required: `actor_name`, `action_text`; optional: `target_path`, `target_url`, `actor_color` |
| `create_ai_task` | task-mcp | required: `description`; see `task management` skill |

## Example

```json
{"event_type": "project_created", "event_id": 31,
 "event_data": {"actor": {"username": "alice"}, "target_type": "Project",
   "content_payload": {"project_id": 31, "slug": "atlas"},
   "knowledge_path": "<knowledge_path>\n- /company/1/projects/31/knowledge\n</knowledge_path>"}}
```

Run: directory check → empty → `add_tree_based_project_directory_item(project_id: 31, name: "knowledge", item_type: "directory")` → `add_knowledge_activity_log(project_id: 31, actor_name: "w-ai", action_text: "project atlas created", target_path: "/company/1/projects/31/knowledge")` → `create_ai_task(project_id: 31, adder_profile: "workspace", assigneee_profile: "project_manager", description: "Define initial milestones/todos/status alignment for atlas", proposed_task_context: "created 2026-11-02 by alice; no structure yet", input_event_entity_id: 31)` → one `create_tool_cal_log` per write (3 logs).

## Pitfalls

- `proposed_task_context` does not survive dispatch: PWR nulls it after the task is dispatched (verified 2026-11-16, task 68). Put every fact the assignee needs in `description` at create time (or append it via `update_ai_task` right after creating); the field is create-read-only.
- `assigneee_profile` is validated against the active Hermes gateway's profiles; unknown names (e.g. "planner") are rejected outright and repeated rejects trip the `pwr-task` circuit breaker (~46s pause). Gateway profiles (verified 2026-11-16): business_analyst, coder, market_research, message_analyzer, project_manager, w_ai, workspace, yogasina_seo. Milestone/todo structuring belongs to `project_manager`.
- A batched `tool_call` with one malformed entry rejects ALL entries client-side (nothing executes) — re-verify state before re-issuing.

## Logging rule

After **each** state-changing tool call, call `create_tool_cal_log` (knowledge-mcp):
`{"used_tool_name": "<tool>", "project_id": ..., "room_id": ..., "topic_id": ..., "target_entity_id": "<entity touched>", "why_was_it_required": "<event_type>", "change_log": "<one line>"}`.

## Guardrails

- Read-before-write: never `add_*` into a category without listing that category for the same scope first — PWR has no dedupe tool.
- Never overwrite existing text with `edit_*`: fetch, merge, write back.
- Attention statuses are exactly `pending` / `resolved` / `dismissed`; company-status item and approval flows add `approved` / `denied` / `canceled` via events.
- If the target profile or room is ambiguous, prefer minimal justified action or route a clarification task; never guess identities.
- Event delivery is at-least-once, and the delivered envelope may omit `event_id`/`group_id` — dedupe by footprint, not event id. Filter `tool_cal_logs` by `project_id` (not a single `target_entity_id`: one handled `project_created` leaves several entity footprints — directory item, activity log, routing task — so any one entity under-detects), and re-read the directory items to confirm live state. If the footprint already covers every planned write, stop completely: no re-run, and a no-action verdict on a raw event needs no log entry.
