---
name: pwr-db-contention
description: "Diagnose and work around PWR MCP SQLite3 busy locks."
version: 1.0.0
author: workspace-profile
license: MIT
metadata:
  hermes:
    tags: [pwr, mcp, sqlite, troubleshooting]
    related_skills: [mention, company-overview, topic-management]
---

# PWR database lock contention

## When to Use

Any PWR MCP tool call (read-mcp, action-mcp, knowledge-mcp, task-mcp) fails with `SQLite3::BusyException: database is locked`, or the tool layer reports a PWR MCP server unreachable after consecutive failures while processing an event or task.

## What it means

The database is healthy — a process holds an uncommitted write transaction and the MCP server's sqlite connections use no busy_timeout. This procedure restores correct event processing without ever writing outside MCP.

## Procedure

1. Retry 1–2 times with 60–120 s waits. The tool layer opens a circuit breaker after ~5 consecutive failures ("unreachable ... auto-retry available in ~Ns") — respect the stated window; hammering does nothing.
2. Identify the holder (plain shell, read-only):
   - `lsof <repo>/storage/db/development.sqlite3` — ruby/puma holding fds is normal; a stray python3 scratch runner is the suspect.
   - Sample WAL size twice ~20 s apart: `ls -la ...sqlite3-wal`. A STATIC WAL with a persistent lock means a leaked uncommitted transaction (someone did `sqlite3.connect(db).execute(UPDATE)` without commit/close and is now sleeping), not active contention. A GROWING WAL is a live writer — just wait it out.
   - `ps -o pid,etime,cmd -p <pid>` and read the holder's script to estimate release time (look for `time.sleep(...)` stages, log/ledger files it writes).
3. Get required reads done via the fallback while MCP is locked: `sqlite3 -readonly <db> "select ..."` works even under the lock. Use it for read-before-write checks, dedupe queries, and item verification.
4. Decide per the rules below, then report the root cause to the user — the holder is usually their own test harness and they may want it fixed (leaked connections / no busy_timeout on the MCP server's sqlite connections).

## Rules

- NEVER write to the database file directly, even to "fix" the lock, even when MCP is blocked — all state changes go through MCP tools so they land in `tool_cal_logs`. Killing another session's process is also off-limits.
- While the lock persists, expect every state-changing MCP call to fail the same way — do not attempt writes to "check".
- If the correct verdict is **no action** (non-actionable event), the lock must not block completion: verify the state with `-readonly` reads, close with the verdict, no log needed.
- If real routed work is pending, wait for the holder to release (retest MCP reads every ~2 min), and only report to the user after several failed rounds — say plainly that the event is still unprocessed, never claim completion.
- A running test harness fires synthetic events (probe items, null `content_payload`, no `event_id`, titles like "<phase> <case> probe"). The holder's script is legitimate evidence of item provenance; processing such events still goes through the normal read → dedupe → verdict flow.
