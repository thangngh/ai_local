# Phase 4B — Daemon Loop Contract

## Phase scope

Formalize and test the daemon loop behavior: heartbeat, lock MVP, graceful
stop via `--max-iterations`, JSONL logging, and runtime visibility of daemon
state.

## Commands completed

| Command | Purpose |
|---|---|
| `daemon run --workspace <tmp> --once` | Single-shot worker run (Phase 4A, preserved) |
| `daemon run --workspace <tmp> --loop --poll-interval <s> --max-iterations <n>` | Bounded loop worker |
| `runtime status --workspace <tmp>` | Print control-plane snapshot incl. daemon fields |
| `runtime snapshot --workspace <tmp>` | Same as status + write `runtime-snapshot.json` |

## Daemon loop stdout contract

```
DAEMON run mode=loop poll_interval=0.1 max_iterations=3
WORKER loop iteration=1 status=pass processed=1 job_id=<id>
WORKER loop iteration=2 status=skipped processed=0 reason="no pending job"
WORKER loop iteration=3 status=skipped processed=0 reason="no pending job"
LOG <workspace>/.ai-local/logs/daemon.log
```

- `status=skipped`, never `status=skip`.
- `processed` is always an integer.
- When a job is processed, `job_id` is included.
- When no job is pending, `reason="no pending job"` is included.
- Exit code is `0` when stopping because of `--max-iterations`.

### Once-mode (preserved)

```
DAEMON run mode=once
WORKER once PASS processed=1 job_id=<id>
LOG <workspace>/.ai-local/logs/daemon.log
```

```
DAEMON run mode=once
WORKER once SKIP processed=0 reason="no pending job"
LOG <workspace>/.ai-local/logs/daemon.log
```

## Heartbeat JSON schema

Written to `<workspace>/.ai-local/reports/daemon-heartbeat.json`.

### During loop (running)

```json
{"status":"running","mode":"loop","pid":12345,"started_at":"...","last_seen_at":"...","iterations":2}
```

### After max-iterations stop (stopped)

```json
{"status":"stopped","mode":"loop","pid":12345,"started_at":"...","last_seen_at":"...","iterations":3,"stop_reason":"max_iterations"}
```

### Fields

| Field | Type | Always present | Description |
|---|---|---|---|
| `status` | string | yes | `running` or `stopped` |
| `mode` | string | yes | `loop` or `once` |
| `pid` | int | yes | Process ID of the daemon |
| `started_at` | string (ISO-8601) | yes | First-seen timestamp (preserved across writes) |
| `last_seen_at` | string (ISO-8601) | yes | Updated each iteration |
| `iterations` | int | no | Iteration count (present during and after loop) |
| `stop_reason` | string | no | `max_iterations` or `keyboard_interrupt` (present after stop) |

## daemon.log JSONL schema

Written to `<workspace>/.ai-local/logs/daemon.log`. Each line is a single JSON
object.

### Iteration event

```json
{
  "timestamp": "2026-06-08T09:53:32.359951+00:00",
  "component": "daemon",
  "mode": "loop",
  "iteration": 1,
  "worker": {
    "status": "pass",
    "processed": 1,
    "job_id": "task-23",
    "reason": null
  }
}
```

| Field | Type | Always present | Description |
|---|---|---|---|
| `timestamp` | string | yes | UTC ISO-8601 |
| `component` | string | yes | Always `"daemon"` |
| `mode` | string | yes | `loop` or `once` |
| `iteration` | int | yes (loop) | Current iteration (1-based) |
| `event` | string | no | `stopped` for stop events |
| `stop_reason` | string | no | `max_iterations` / `keyboard_interrupt` |
| `iterations` | int | no | Final iteration count (stop events) |
| `worker` | object | yes (iteration) | Worker result sub-object |

### Stop event

```json
{
  "timestamp": "2026-06-08T09:53:32.572421+00:00",
  "component": "daemon",
  "event": "stopped",
  "mode": "loop",
  "stop_reason": "max_iterations",
  "iterations": 3
}
```

## Lock MVP behavior

Lock file at `<workspace>/.ai-local/reports/daemon.lock`.

| Scenario | Behavior |
|---|---|
| No lock file exists | Daemon starts normally, creates lock. |
| Lock exists, heartbeat says `status=running` | Daemon refuses: prints "Daemon already running" and exits code 1, unless `--force` is passed. |
| Lock exists, heartbeat says `status=stopped` | Stale lock — cleaned up, daemon starts. |
| `--force` is passed | Overrides running-status check, daemon starts. |
| Normal exit (max-iterations, once) | Lock is removed. |
| KeyboardInterrupt | Lock is removed. |

No OS-level file locking is implemented in this phase.

## Runtime status/snapshot daemon fields

### `runtime status` output

When a heartbeat file exists, the status output includes a DAEMON line:

```
DAEMON status=stopped pid=22352 last_seen_at=... iterations=3 stop_reason=max_iterations
```

The full line is on one line. Fields are omitted when `null` in the snapshot.

### `runtime-snapshot.json` daemon fields

```json
{
  "tasks_total": 23,
  "tasks_pending": 0,
  "tasks_done": 23,
  "tasks_cancelled": 0,
  "last_worker_result": { ... },
  "logs_dir": "...",
  "reports_dir": "...",
  "daemon_status": "stopped",
  "daemon_pid": 22352,
  "daemon_last_seen_at": "2026-06-08T09:53:32.571688+00:00",
  "daemon_iterations": 3,
  "daemon_stop_reason": "max_iterations"
}
```

Daemon fields are only present in the JSON when the corresponding value in the
snapshot is non-null.

## Validation commands and results

### 16 tests passed

```
python -m pytest tests/test_demo_cli.py tests/test_worker_daemon_runtime.py -q
................                                                         [100%]
16 passed in 2.32s
```

### Daemon loop output (3 iterations)

```text
DAEMON run mode=loop poll_interval=0.1 max_iterations=3
WORKER loop iteration=1 status=pass processed=1 job_id=task-23
WORKER loop iteration=2 status=skipped processed=0 reason="no pending job"
WORKER loop iteration=3 status=skipped processed=0 reason="no pending job"
LOG .tmp-demo/.ai-local/logs/daemon.log
```

### Heartbeat ends with `status=stopped`, `stop_reason=max_iterations`

```json
{"status":"stopped","mode":"loop","pid":22352,"started_at":"...","last_seen_at":"...","iterations":3,"stop_reason":"max_iterations"}
```

### Runtime snapshot includes daemon fields

```json
{
  "daemon_status": "stopped",
  "daemon_pid": 22352,
  "daemon_last_seen_at": "2026-06-08T09:53:32.571688+00:00",
  "daemon_iterations": 3,
  "daemon_stop_reason": "max_iterations"
}
```

### Runtime status includes DAEMON line

```
DAEMON status=stopped pid=22352 last_seen_at=... iterations=3 stop_reason=max_iterations
```

## Known limitations

- The lock file advisory only — no OS-level `flock` / `LockFileEx`.
- No PID-staleness detection beyond the `status=stopped` heartbeat check.
- `KeyboardInterrupt` handling is present but not exercised in automated tests;
  manual or integration-only.
- `daemon.log` grows unboundedly (no log rotation in this phase).
- Heartbeat `started_at` is preserved across writes but is set from the clock
  of the first write — if the system clock is adjusted it may appear
  inconsistent.

## Explicit non-goals

- ❌ No Windows Service implementation.
- ❌ No service install/start/stop hardening.
- ❌ No cloud dependencies.
- ❌ No LLM calls.
- ❌ No unbounded `--loop` without `--max-iterations` testing (liveness assumed).
- ❌ No daemon auto-restart or supervision.
- ❌ No log rotation.
- ❌ No OS-level file locking.
