---
name: risk
description: "events `risk_<action>` (`add`, `approved`, `denied`, `destroy`…) on `risks` company-status items."
---

# Risk (add / approved / denied / destroyed)

Type: input-processing skill
Apply when: any `risk_<action>` event on `risks` company-status items.

## Procedure

1. Gate on `target_type: "CompanyStatusItem"` + `category: "risks"`. Dedupe FIRST (see Guardrails), then read the item: `risks(item_id: <company_status_item_id>)`.
1b. `risk_add` and other non-approval lifecycle actions — informational: PWR's own flow already recorded the row. Verify the item is live and appears in the period's `status_payload` snapshot (`company_status_period(period_id)`), check it has no owner/project that would need routing for, then no-action — mitigation routing fires **only** on `risk_approved`. Record the no-action verdict as a one-line marker log when re-processing cost is non-trivial (see logging rule) so redeliveries become pure dedupe hits.
2. `risk_approved` — the risk is live company state:
   - link it to the work that carries it: if the risk references a project, find open tasks/todos on that thread and merge "risk <id> approved <date>: <evidence>" into their `description`;
   - if the risk has an owner (`owner_name`), route a mitigation task only when none exists: check `ai_tasks` and `add_blockers` footprint first.
3. `risk_denied` — the proposed risk was rejected. Close out the artifacts *the risk proposal created*: blockers you opened citing it (`edit_blockers(item_id, status: "dismissed")`), and correct any `progress` items that were hedged on it.
3b. `risk_destroy` — the deletion is already executed by PWR's own flow; there is nothing to undo. Verify: `risks(item_id: <company_status_item_id>)` must return not-found (the tool's `"Record not found: Couldn't find CompanyStatusItem with 'id'=N"` error IS the confirmation — do not retry). Then scan open `ai_tasks(finished=false)` and `attention_items(status: "pending")` for any citation of the destroyed risk. The unfiltered open-task list is usually huge: let it persist to the spillover file and grep THAT with a regex of the risk's id, title, and distinctive text phrases — never page through it manually or re-request it. An empty pending-attention list is a clean scan, not a query failure. No citations → no-action (raw event: no task close, no tool_cal_log needed). If one of your open artifacts cites it, strip/annotate the citation or close the artifact. Note: the period's `status_payload` snapshot may still list OTHER rows of the same category — check the ids, don't assume staleness; never delete company-status rows on your own initiative.
4. Never invent mitigation deadlines; `due_at` only when the event content states one.

## Tools used

| Tool | Endpoint | Key arguments |
|---|---|---|
| `risks` | read-mcp + action-mcp | list = read-only filters; get/edit/delete = `item_id`; create = `title` (+`details`, `owner_name`, `evidence`, `impact`, `badge`, `health`, `percent`, `status`) |
| `company_status_period` | read-mcp | find the current period via list + `current`; there is no dedicated "get current" arg |
| `add_company_status_period` / `edit_company_status_period` | action-mcp | create requires `name`; edit requires `period_id` |
| `tool_cal_logs` | knowledge-mcp | dedupe your own footprint: filter by `used_tool_name` (the category tool) — there is NO `target_entity_id` filter arg; match ids/timestamps client-side in the returned rows |
| `risks` | read+action-mcp | the risks category tool |
| `edit_blockers` | action-mcp | dismiss derived blockers |
| `ai_tasks` / `update_ai_task` / `create_ai_task` | task-mcp | carry risk context |

## Example

```json
{"event_type": "risk_approved", "event_id": 143,
 "event_data": {"actor": {"username": "bob"}, "target_type": "CompanyStatusItem",
   "content": "Risk: MCP bridge hangs on long-poll under load",
   "content_payload": {"company_status_item_id": 143, "category": "risks", "status": "approved", "company_status_period_id": 3}}}
```

Run: `risks(item_id: 143)` → approved, owner carol → `ai_tasks(finished=false)` → task 77 "stabilize bridge" exists, cite it: `update_ai_task(task_id: 77, description: "<existing>\n[2026-11-02] company risk 143 approved — this task is its mitigation")` → log. No new task: dedupe rule satisfied by reuse.
## Logging rule

After **each** state-changing tool call, call `create_tool_cal_log` (knowledge-mcp):
`{"used_tool_name": "<tool>", "project_id": ..., "room_id": ..., "topic_id": ..., "target_entity_id": "<entity touched>", "why_was_it_required": "<event_type>", "change_log": "<one line>"}`.

## Guardrails

- Read-before-write: never `add_*` into a category without listing that category for the same scope first — PWR has no dedupe tool.
- Never overwrite existing text with `edit_*`: fetch, merge, write back.
- Attention statuses are exactly `pending` / `resolved` / `dismissed`.
- Event delivery is at-least-once: re-delivery has the same `group_id` / `event_type` / `event_id`. Check `tool_cal_logs` before acting a second time: no `target_entity_id` filter exists — call with `used_tool_name: "risks"` (optionally `start_date`) and match each row's `target_entity_id` AND the event's `occurred_at` inside `change_log`. A prior row citing the same event timestamp means the event was already handled: take no action and write no new log — logging a handled event is itself a second action.
- Make verdicts matchable: start every `change_log` with `<event_type> <occurred_at> (item <company_status_item_id>)` so future redeliveries dedupe on one grep.
- When following this skill after a context compression, `skill_view` may answer "content unchanged since loaded earlier" while the content is no longer visible — read this skill's `SKILL.md` file path directly instead of trusting the dedup reply.
