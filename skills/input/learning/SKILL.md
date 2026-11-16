---
name: learning
description: "`learning_<action>` events on company-status `learnings` items."
---

# Learning (any action)

Type: input-processing skill
Apply when: `learning_<action>` events on company-status `learnings` items.

## Procedure

1. Read: `learnings(item_id: <event_id>)` — the event content is the lesson text. The real lesson may sit in `outcome` (or `desc`) while `title`/`text` are placeholder labels — read every text field and adopt the substantive one.
2. Learnings are perishable in status views but permanent in knowledge: adopt the lesson into project knowledge so it survives the period:
   - dedupe: `knowledge_summary_items(project_id)` / `project_knowledge_items(project_id)` — these list tools REQUIRE project scope (an unscoped call returns "Project not found"), so sweep each candidate project separately;
   - create: `add_knowledge_summary_item(title: "<short lesson>", description: "<full text> (learning item <id>, <date>)", project_id)` — pick the project from the item's scope; company-wide lessons (status items carry no project_id) go under project 2 "Receipts", the workspace's knowledge home for adopted lessons, else route a `knowledge` task;
   - `add_knowledge_activity_log(actor_name: "w-ai", action_text: "adopted learning <id> into summaries")`.
3. If the learning forbids something you (or a profile) currently automate, raise a `decisions_waiting` attention item ("revoke auto-X per learning <id>?") instead of silently changing behavior.
4. Rejected/deleted learning event → if you already adopted it, edit the summary item to mark "withdrawn (learning <id> deleted)" — delete only if it was created solely from that item.
5. Re-fire of an already-adopted learning (same `occurred_at`) → re-read the item AND the summary before judging: confirm the summary citing the item id still exists and the item gained no new content. Unchanged → one `noop-verification` cal-log citing the owning adoption log ids; no second summary, no activity re-log. If the author enriched `outcome`/`details` since adoption, `edit_knowledge_summary_item` to merge the fuller lesson — never create a second summary. A learning whose every text field (title/label/text) is one placeholder string with empty outcome/desc/details carries no lesson beyond its label: adopt verbatim with a "pending richer detail" note rather than inventing substance, and re-check on re-fire.

## Tools used

| Tool | Endpoint | Key arguments |
|---|---|---|
| `learnings` | read-mcp + action-mcp | list = read-only filters; get/edit/delete = `item_id`; create = `title` (+`details`, `owner_name`, `evidence`, `impact`, `badge`, `health`, `percent`, `status`) |
| `company_status_period` | read-mcp | find the current period via list + `current`; there is no dedicated "get current" arg |
| `add_company_status_period` / `edit_company_status_period` | action-mcp | create requires `name`; edit requires `period_id` |
| `tool_cal_logs` | knowledge-mcp | dedupe your own footprint — filters are topic/room/project/used_tool_name only (date filters are IGNORED); match `target_entity_id` inside returned rows and page backward (page: 2, 3, …) until older than the event's `occurred_at` before declaring no footprint |
| `add_knowledge_summary_item` / `knowledge_summary_items` | action/read-mcp | permanent adoption |
| `add_project_knowledge_item` | action-mcp | durable rule-shaped lessons |
| `add_knowledge_activity_log` | action-mcp | adoption trail |
| `add_decisions_waiting` | action-mcp | behavior changes needing sign-off |

## Example

```json
{"event_type": "learning_created", "event_id": 166,
 "event_data": {"actor": {"username": "bob"}, "target_type": "CompanyStatusItem",
   "content": "learning: never mark ai_confirm items resolved without owner visibility",
   "content_payload": {"company_status_item_id": 166, "category": "learnings", "status": "active"}}}
```

Run: `knowledge_summary_items(project_id: 2)` → none equivalent → `add_knowledge_summary_item(project_id: 2, title: "ai_confirm requires owner visibility before resolve", description: "Never mark ai_confirm items resolved without the artifact owner seeing it — learning 166, 2026-11-02")` → `add_knowledge_activity_log(project_id: 2, actor_name: "w-ai", action_text: "adopted learning 166")` → 2 logs.
## Logging rule

After **each** state-changing tool call, call `create_tool_cal_log` (knowledge-mcp):
`{"used_tool_name": "<tool>", "project_id": ..., "room_id": ..., "topic_id": ..., "target_entity_id": "<entity touched>", "why_was_it_required": "<event_type>", "change_log": "<one line>"}`.

## Guardrails

- Read-before-write: never `add_*` into a category without listing that category for the same scope first — PWR has no dedupe tool.
- Never overwrite existing text with `edit_*`: fetch, merge, write back.
- Attention statuses are exactly `pending` / `resolved` / `dismissed`.
- Event delivery is at-least-once: re-delivery has the same `group_id` / `event_type` / `event_id`. Check `tool_cal_logs` filtered by `target_entity_id` before acting a second time.
