---
name: project-todo-completed
description: "a `project_todo_completed` event arrives (`event_id` = the todo id)."
---

# Project todo completed

Type: input-processing skill
Apply when: a `project_todo_completed` event arrives (`event_id` = the todo id).

## Procedure

1. Resolve, then verify: `project_todos(todo_id: <event_id>)` — `completed` is already true. Delivered envelopes may carry no `event_id` (null `content_payload`): identify the todo by exact match of `occurred_at` against `completed_at` in `project_todos(project_id:)` — the same-millisecond match is the signature — and state the match basis in the verification log so the identity is auditable.
2. Consequences in order:
   - tracked Hermes task (`ai_tasks(input_event_entity_id: <event_id>, finished=false)`) → cost then close it (`ai_task_cost`, `update_ai_task finished=true, actual_task_context=...`). Guard the hit: `input_event_entity_id` holds a raw number shared across projects and event types, so a match can be a collision — confirm the task's `project_id` and text actually reference this todo before treating it as tracked. When sweeping open-task bodies for the todo's title, regex-search the persisted (spillover) result file rather than re-requesting the API.
   - the todo was the last open item gating a milestone (`project_milestones(project_id, status...)`) → milestone state belongs to humans: route a task or raise `add_outcomes_review(title: "Milestone X: all todos complete, review outcome")` — do not mark milestones yourself.
3. Plain todos with nothing attached: verification log only.

## Tools used

| Tool | Endpoint | Key arguments |
|---|---|---|
| `project_todos` | read-mcp | `todo_id` or list with `project_id` |
| `project_milestones` | read-mcp | `project_id`, `milestone_id` |
| `ai_tasks` / `ai_task_cost` / `update_ai_task` | task-mcp | see `task management` skill |
| `add_outcomes_review` | action-mcp | required: `title` |

## Example

```json
{"event_type": "project_todo_completed", "event_id": 88,
 "event_data": {"actor": {"username": "alice"}, "content": "todo 'wire task-mcp into workspace profile' completed",
   "content_payload": {"id": 88, "project_id": 2}}}
```

Run: read todo → true → `ai_tasks(input_event_entity_id: 88)` → task 90 open → `ai_task_cost(task_id: 90, token_used: 18300, usd_used: 0.12)` → `update_ai_task(task_id: 90, finished: true, actual_task_context: "closed: todo 88 completed")` → 2 logs (task close needs none for reads).

## Logging rule

After **each** state-changing tool call, call `create_tool_cal_log` (knowledge-mcp):
`{"used_tool_name": "<tool>", "project_id": ..., "room_id": ..., "topic_id": ..., "target_entity_id": "<entity touched>", "why_was_it_required": "<event_type>", "change_log": "<one line>"}`.

## Guardrails

- Read-before-write: never `add_*` into a category without listing that category for the same scope first — PWR has no dedupe tool.
- Never overwrite existing text with `edit_*`: fetch, merge, write back.
- Attention statuses are exactly `pending` / `resolved` / `dismissed`; company-status item and approval flows add `approved` / `denied` / `canceled` via events.
- If the target profile or room is ambiguous, prefer minimal justified action or route a clarification task; never guess identities.
- Event delivery is at-least-once: re-delivery has the same `group_id` / `event_type` / `event_id`. Check `tool_cal_logs` filtered by `target_entity_id` before acting a second time.

## API-plane origin note (added 2026-11-13)

`project_todo_completed` / `project_todo_reopened` events may now come from the REST/MCP plane as well as the web toggle. The procedure above is unchanged: verify state first (`project_todos(todo_id:)`), close tracked tasks cost→finished, and never self-mark milestones — route `add_outcomes_review` instead.
