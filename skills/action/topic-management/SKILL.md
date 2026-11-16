---
name: topic-management
description: "owning topics, message analysis, room history topics, and — critically — the `tool_cal_logs` audit trail for every action you take."
---

# Topic management

Type: action skill
Purpose: owning topics, message analysis, room history topics, and — critically — the `tool_cal_logs` audit trail for every action you take.

Topics live on `/knowledge-mcp` (also reachable via `/mcp` and `/action-mcp`). The workspace profile creates topics sparingly: topics are the memory spine, so wrong topics are worse than no topics.

## Tools

| Tool | Endpoint | Required | Notes |
|---|---|---|---|
| `topics`, `get_topic`, `search_topics`, `room_topic_tree` | knowledge/read | — | list/get/search before creating anything |
| `create_topic` | knowledge+action | `name` | optional: `memory`, `state`, `importance_level`, `need_an_action`, `required_actions`, `parent_topic_id`, `related_topics`, `project_id`, `active` |
| `update_topic`, `delete_topic` | knowledge+action | — | merge semantics; delete only topics you created |
| `message_topics`, `get/create/update/delete_message_topic` | knowledge+action | create: message↔topic link | attach messages to topics when they extend a known thread |
| `message_analysis`, `get/create/update/delete_message_analysis` | knowledge+action | create: `message_id` | fields: `analysis`, `importance_level`, `message_content_summary`, `message_type`, `tags`, `is_a_response` |
| `room_history_topics`, `get/create/update/delete_room_history_topic` | knowledge+action | — | room-level historical clustering |
| `tool_cal_logs`, `get/create/update/delete_tool_cal_log` | knowledge+action | create: `used_tool_name` | your audit trail |

## Tool-call logging rules (binding for all skills)

After each successful state-changing call, `create_tool_cal_log`:
- `used_tool_name` = exactly the tool you called;
- scope: `project_id`, `room_id`, `topic_id` when applicable to the touched entity;
- `target_entity_id` = id string of the entity changed (dedupe anchor for event redelivery);
- `why_was_it_required` = triggering `event_type` or task id;
- `change_log` = one line, human-readable diff ("created milestone 12", "merged precondition into task 61").

Reads used purely for dedupe do not need logs; reads that drive a decision may be logged when the decision is non-obvious.

Redelivery rule: when a delivered event is already handled (your footprint exists in `tool_cal_logs` for the same `target_entity_id`), re-run nothing — but never silently drop it either: re-read the artifacts the original action produced (they may have been deleted or edited since), then write one verification log with `used_tool_name: "noop-verification"`, `why_was_it_required: "<event_type> — <n>th re-delivery dedup"` citing the prior cal-log ids covering the same signature (they chain, so the next re-delivery counts from them), and `target_entity_id` = the entity id, listing the fresh reads and standing verdicts. Cap the trail: once an entity id carries its first-delivery log plus at most one re-delivery verification log, every further *identical* re-delivery (same entity id, same `occurred_at`) STOPS with read-only confirmation only — no new log, no new verdict; re-logging every at-least-once duplicate turns the audit trail into spam. Note `tool_cal_logs` itself filters only by `project_id` / `room_id` / `topic_id` / `used_tool_name` / dates — there is no `target_entity_id` filter; results come newest-first. When scanning a captured dump client-side, match the full quoted field (`"target_entity_id": "<id>"`), never the bare number — ids collide as substrings (searching `5` matches log `1365`), and a false match manufactures a footprint or hides a real one. Scan the spillover archive rather than re-requesting pages from the API: oversized tool results are persisted to a local file whose path the result prints, so grep/read that file once per page (an archive re-request is redundant and the transcript says so). Verify a page's window coverage mechanically — `grep -o '"created_at": "[^"]*"' <dump> | sort | head -1` gives the page's oldest timestamp; compare it against the event's `occurred_at` to decide whether to page further, instead of eyeballing previews. "Absent from the newest window" is NOT proof of first delivery: a busy profile burns 100 log entries within hours, so a footprint can sit just past page 1 and a duplicate verdict gets logged or the event re-acted. Before declaring no footprint exists, keep paging (`page: 2, 3, …`) until the scanned entries reach timestamps older than the footprint's plausible creation (the event's `occurred_at` / your original handling); only then conclude absence. Do NOT rely on `start_date`/`end_date` to bound the scan — they are ignored: two disjoint windows returned the identical newest-first page, so narrowing by date silently re-answers with page 1 and paging is the only reliable bound.

## Topic discipline

1. Never create a near-duplicate topic: `search_topics(name)` + `room_topic_tree(room_id)` first.
2. `importance_level` (integer) and `need_an_action` gate downstream automation — set them deliberately, copy them from the analysis that justifies the topic.
3. When an event or task belongs to an existing topic, link the task (`ai_tasks.topic_id` — settable ONLY at creation, so route new child tasks with `topic_id` rather than editing old ones) and add a `message_topic` link for the driving message.

## Example — record the footprint for a routed task

```json
{"tool": "create_ai_task", "arguments": {"description": "Draft MCP topic taxonomy", "project_id": 2,
  "topic_id": 7, "adder_profile": "workspace", "assigneee_profile": "knowledge",
  "input_event_entity_id": 456, "proposed_task_context": "message 456 in room 9 asks for taxonomy under topic 7"}}

{"tool": "create_message_topic", "arguments": {"message_id": 456, "topic_id": 7}}

{"tool": "create_tool_cal_log", "arguments": {"used_tool_name": "create_message_topic",
  "project_id": 2, "room_id": 9, "topic_id": 7, "target_entity_id": "456",
  "why_was_it_required": "message_created -> routed taxonomy task",
  "change_log": "linked message 456 to topic 7; taxonomy task created under it"}}
```
