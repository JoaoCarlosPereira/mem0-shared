---
name: remember
description: Stores a memory verbatim from user input with appropriate type classification and metadata. Use when the user says remember this, save this, store this, note that, or explicitly asks to record a decision, preference, convention, or learning.
---

# Mem0 Remember

Store a fact or learning directly into mem0.

## Execution

### Step 1: Extract the content

The user provides the content as an argument: `/mem0:remember <text>`

If no text was provided, ask: "What should I remember?"

### Step 2: Classify the memory

Based on the content, pick the best `metadata.type`:

| Content signal | Type |
|---|---|
| "we decided...", "always use...", "never..." | `decision` |
| "X doesn't work because...", "don't try..." | `anti_pattern` |
| "I prefer...", "use X instead of Y" | `user_preference` |
| "the convention is...", "we always..." | `convention` |
| "learned that...", "figured out..." | `task_learning` |
| setup, env, tooling, config | `environmental` |
| anything else | `task_learning` |

### Step 3: Store

Call `add_memories` (OpenMemory MCP) or `add_memory` (hosted) with the classified content and project/app scope.

**Rate limit (HTTP 429):** If the call fails with `error=rate_limit_exceeded` or status 429, read `retry_after_sec` from the JSON body (or the `Retry-After` header), wait that many seconds, and retry the **same text** 1–3 times with backoff. Do not discard the content. Reads (`search_memory`) are not rate-limited on OpenMemory.

Call `add_memory` / `add_memories` with:
- `text="<the user's text>"` (OpenMemory) or `messages=[...]` (hosted)
- `user_id=<active_user_id>` / hostname attribution as required by the server
- `app_id` / `project=<active_project_id>`
- `metadata={"type": "<classified_type>", "branch": "<active_branch>", "confidence": 1.0, "source": "remember_command"}`
- `infer=False` when the platform supports it

`infer=False` because the user stated the fact explicitly — no extraction needed.
`confidence=1.0` because the user explicitly asked to store this.

### Step 4: Confirm

OpenMemory `add_memories` returns `status=accepted` with `job_id`, `queue_depth`, and `estimated_wait_sec`. The memory is **not searchable yet**; do not poll. Hosted `add_memory` may return `event_id` — call `get_event_status` once if available.

```
Remembered as <type>: "<content, first 80 chars>"
Queued: job_id=<id> (searchable after ~estimated_wait_sec; depth=queue_depth)
```
