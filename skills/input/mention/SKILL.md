---
name: mention
description: "events `mention_resolved`, `mention_dismissed`, or `mention_created`."
---

# Mention / requested review (resolved / dismissed)

Type: input-processing skill
Apply when: events `mention_resolved`, `mention_dismissed`, or `mention_created`.

## Procedure

1. Read the item: `mentions(item_id: <event_id>)` — it carries `user_id` (who was mentioned) and often a room.
2. This family is usually **someone else's turn**, not yours:
   - if the mentioned user is represented by a profile you coordinate (check `get_ai_profile` / naming convention), route: `create_ai_task(description: "Respond to mention: <item title>", room_id: <item.room_id>, project_id: <item.project_id>, assigneee_profile: <profile>, input_event_entity_id: <event_id>, proposed_task_context: "<mention context>")`;
   - if the mention is resolved (the human already replied), verify nothing is left untracked: `search_messages_of_room(room_id: <item.room_id>)` recent messages for follow-up commitments; if a commitment exists that no todo/task carries, create the todo or task — not both.
3. `mention_dismissed` — nobody owed a response. Verification log only.
4. Never answer a mention by posting messages as the mentioned person.

## Tools used

| Tool | Endpoint | Key arguments |
|---|---|---|
| `mentions` (generic) | read-mcp + action-mcp | list = no args beyond filters; get/edit/delete = `item_id`; create = `title`. PITFALL: filtered list returns ONE item (latest for the filter), not the burst — sweep the whole set with `attention_items(category: "mentions", project_id)` instead |
| `add_mentions` | action-mcp | required: `title`; optional: `meta_text`, `action_label`, `due_at`, `overdue`, `project_id`/`project_name`, `room_id`/`room_name`, `user_id`/`user_name` |
| `edit_mentions` | action-mcp | required: `item_id`; writable: `title`, `meta_text`, `status`, `action_label`, `due_at`, `overdue` |
| `attention_items` | read-mcp | cross-category list: `category`, `status`, `project_id`, `user_id` |
| `delete_attention_item` | action-mcp | required: `item_id` — only for duplicate/erroneous items you created |
| `tool_cal_logs` | knowledge-mcp | dedupe: `target_entity_id`... |
| `get_ai_profile` | config-mcp | confirm the owning profile exists |
| `search_messages_of_room` | read-mcp | required: `room_id` |
| `create_ai_task` | task-mcp | required: `description` |
| `add_project_todo` | action-mcp | required: `title` |

## Example

```json
{"event_type": "mention_resolved", "event_id": 60,
 "event_data": {"actor": {"username": "dana"}, "target_type": "AttentionItem",
   "content": "mention of alice resolved",
   "content_payload": {"attention_item_id": 60, "room_id": 9, "project_id": 2}}}
```

Run: `mentions(item_id: 60)` → resolved → `search_messages_of_room(room_id: 9, from_message_id: <mention source>)` → alice's reply promises "docs by Friday", nothing tracks it → `add_project_todo(project_id: 2, title: "Ship integration docs by Friday (committed in room 9 reply)")` → log. If a matching open todo had existed: verification log only.

## Logging rule

After **each** state-changing tool call, call `create_tool_cal_log` (knowledge-mcp):
`{"used_tool_name": "<tool>", "project_id": ..., "room_id": ..., "topic_id": ..., "target_entity_id": "<entity touched>", "why_was_it_required": "<event_type>", "change_log": "<one line>"}`.

## Guardrails

- Read-before-write: never `add_*` into a category without listing that category for the same scope first — PWR has no dedupe tool.
- Never overwrite existing text with `edit_*`: fetch, merge, write back.
- Attention statuses are exactly `pending` / `resolved` / `dismissed`.
- Event delivery is at-least-once: re-delivery has the same `group_id` / `event_type` / `event_id`. Check `tool_cal_logs` filtered by `target_entity_id` before acting a second time.

## `mention_created` (added 2026-11-13)

Apply when: a `mention_created` event arrives (a person or profile was flagged).

1. Read the item: `mentions(item_id: <event_id>)`. Some deliveries omit `event_id` and carry `content_payload: null` (probe/harness-fired events) — then locate the item by listing `mentions` filtered on the event's `title` + `project_id`/`room_id` instead. In a same-title burst the filter returns many items; pin the exact one by the event's `occurred_at` equalling the item's `created_at`. `occurred_at` is second-truncated while `created_at` carries real ms — match on truncated-to-second equality, NEVER on nearest timestamp: harness bursts keep appending same-title items AFTER an event's time, so the newest item is usually not the anchored one. Corroborate the match on `room_id`/`project_id` when the event carries them (verified across two T2 bursts: exact second-matches held while later same-title items existed).
2. If the item has no `user_id`, nobody was actually mentioned: there is no routing target and no response owed — verdict **no action**, no log (raw-event non-actionable rule). Do not invent an assignee; a title containing "probe" or matching a live test harness is corroborating evidence, not the test itself.
3. Route it exactly once when a `user_id` is set and the mentioned user belongs to a profile you coordinate: `create_ai_task(description: "Respond to mention: <title>", room_id: <item.room_id>, project_id: <item.project_id>, assigneee_profile: <profile>, input_event_entity_id: <event_id>, proposed_task_context: "<context>")` — `input_event_entity_id` is what later lets `mention_resolved` find and close the task with cost (`ai_task_cost` then `update_ai_task(finished: true)`).
4. Dedupe first: `ai_tasks(input_event_entity_id: <event_id>)`; if a task already exists for the same event or same (title, room), do nothing.
5. Then `create_tool_cal_log` recording the created task id — no other writes.
6. Burst duplicates (multiple items with the same title, e.g. a "burst dedupe" harness run): the verdict is per-item — all `user_id: null` means each is individually non-actionable, and one no-action verdict covers the redeliveries. Do NOT mass-resolve/dismiss/delete the duplicate attention items; deletion is only for duplicates you created yourself.
