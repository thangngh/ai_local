# Demo CLI Contract

AI Local exposes a demo-oriented local CLI. The intended public surface is listed below.

This is an MVP contract. It preserves local-first, harness-first, evidence-driven behavior and avoids cloud dependencies or service-hardening claims.

## Commands

### `ai-local doctor`

Purpose: validate the local environment and repo prerequisites.

Inputs: repo root and optional check flags.

Outputs: pass/fail report with check details.

Exit codes: `0` when required checks pass, non-zero on critical failure.

Storage touched: temporary probe files under `.reports`.

Demo role: first-run health gate.

MVP limitation: environment validation only, not runtime assurance.

### `ai-local init`

Purpose: create demo-ready local folders and default config.

Inputs: target root and overwrite flags.

Outputs: created files and initialization summary.

Exit codes: `0` on success.

Storage touched: local project config and demo directories.

Demo role: bootstrap a workspace.

MVP limitation: no provisioning or remote sync.

### `ai-local config show`

Purpose: display resolved config.

Inputs: config paths and environment overrides.

Outputs: resolved config data.

Exit codes: `0` on success.

Storage touched: read-only config files.

Demo role: inspect what the runtime will use.

MVP limitation: no secret backend.

### `ai-local config validate`

Purpose: validate config schema and required fields.

Inputs: config files.

Outputs: validation result.

Exit codes: `0` when valid.

Storage touched: read-only config files.

Demo role: catch broken config before a demo.

MVP limitation: local schema only.

### `ai-local index scan`

Purpose: scan and update the project index.

Inputs: project root, knowledge DB, chunk size.

Outputs: indexing summary and optional report.

Exit codes: `0` on success.

Storage touched: knowledge DB and source tree.

Demo role: prepare retrieval context.

MVP limitation: local text/code indexing only.

### `ai-local index rebuild`

Purpose: rebuild the index from scratch.

Inputs: project root and knowledge DB.

Outputs: rebuild summary.

Exit codes: `0` on success.

Storage touched: knowledge DB.

Demo role: recover from stale index state.

MVP limitation: single-node rebuild only.

### `ai-local index stats`

Purpose: show indexed file/chunk/symbol counts.

Inputs: knowledge DB.

Outputs: counts.

Exit codes: `0` on success.

Storage touched: knowledge DB read-only.

Demo role: verify index coverage.

MVP limitation: no scoring or latency analytics.

### `ai-local index search`

Purpose: search the index for a query.

Inputs: query string and knowledge DB.

Outputs: ranked evidence and refs.

Exit codes: `0` on success.

Storage touched: knowledge DB read-only.

Demo role: prove retrieval works.

MVP limitation: local FTS and heuristic matching only.

### `ai-local knowledge add`

Purpose: add durable knowledge.

Inputs: text, source, tags.

Outputs: created record.

Exit codes: `0` on success.

Storage touched: knowledge store.

Demo role: capture confirmed facts.

MVP limitation: no collaboration or replication.

### `ai-local knowledge add-note`

Purpose: add a note to an existing item.

Inputs: knowledge id and note text.

Outputs: updated record.

Exit codes: `0` on success.

Storage touched: knowledge store.

Demo role: annotate facts with context.

MVP limitation: local-only editing.

### `ai-local knowledge list`

Purpose: list stored knowledge.

Inputs: filters and pagination.

Outputs: item list.

Exit codes: `0` on success.

Storage touched: knowledge store read-only.

Demo role: inspect memory contents.

MVP limitation: basic listing only.

### `ai-local knowledge search`

Purpose: search stored knowledge.

Inputs: query and filters.

Outputs: ranked matches.

Exit codes: `0` on success.

Storage touched: knowledge store read-only.

Demo role: query local memory.

MVP limitation: no vector service required.

### `ai-local ask`

Purpose: answer a question from project context.

Inputs: query, project root, knowledge DB.

Outputs: answer decision and evidence refs.

Exit codes: `0` on success.

Storage touched: knowledge DB and optionally the source tree when refresh is requested.

Demo role: analysis endpoint for the demo.

MVP limitation: quality depends on local index coverage.

### `ai-local task submit`

Purpose: create a task in the local queue.

Inputs: goal, project id, metadata.

Outputs: task id and state.

Exit codes: `0` on enqueue success.

Storage touched: task queue and task store.

Demo role: start work through the queue.

MVP limitation: no distributed job guarantees.

### `ai-local task list`

Purpose: list active tasks.

Inputs: filters and status.

Outputs: task list.

Exit codes: `0` on success.

Storage touched: task store read-only.

Demo role: inspect work in progress.

MVP limitation: local visibility only.

### `ai-local task read`

Purpose: read a task state.

Inputs: task id.

Outputs: one task record.

Exit codes: `0` on success, non-zero if missing.

Storage touched: task store read-only.

Demo role: inspect a task in detail.

MVP limitation: no access control layer.

### `ai-local task cancel`

Purpose: cancel a task.

Inputs: task id.

Outputs: cancellation result.

Exit codes: `0` on success, non-zero if denied.

Storage touched: task store and audit store.

Demo role: manual control point.

MVP limitation: cancellation is local state only.

### `ai-local worker run --once`

Purpose: process one queued job.

Inputs: queue store and worker config.

Outputs: job result and audit event.

Exit codes: `0` on success.

Storage touched: queue store and audit store.

Demo role: show one-step execution.

MVP limitation: not a scalable worker fleet.

### `ai-local worker run --loop`

Purpose: keep processing jobs until stopped.

Inputs: queue store and runtime config.

Outputs: continuous job status.

Exit codes: `0` on stop, non-zero on failure.

Storage touched: queue store and audit store.

Demo role: demonstrate the daemon loop.

MVP limitation: no production watchdog or HA.

### `ai-local runtime status`

Purpose: show runtime health.

Inputs: task DB and audit DB paths.

Outputs: status snapshot.

Exit codes: `0` on success, non-zero when critical and requested.

Storage touched: runtime DBs read-only.

Demo role: check queue and run health.

MVP limitation: local snapshot only.

### `ai-local runtime snapshot`

Purpose: capture a structured runtime snapshot.

Inputs: runtime DBs.

Outputs: JSON/text snapshot.

Exit codes: `0` on success.

Storage touched: runtime DBs read-only.

Demo role: produce evidence for a demo run.

MVP limitation: no external observability backend.

### `ai-local runtime backup create`

Purpose: create a runtime backup.

Inputs: backup location and DB paths.

Outputs: backup manifest and copied files.

Exit codes: `0` on success.

Storage touched: backup path and runtime DBs.

Demo role: snapshot the system state.

MVP limitation: file-copy backup only.

### `ai-local runtime backup restore`

Purpose: restore runtime data from backup.

Inputs: backup location and DB paths.

Outputs: restore result.

Exit codes: `0` on success.

Storage touched: backup path and runtime DBs.

Demo role: recover a demo state.

MVP limitation: no transactional recovery guarantee.

### `ai-local gate run`

Purpose: run a harness or gate.

Inputs: gate name, config, max level.

Outputs: pass/fail results and reasons.

Exit codes: `0` when passed.

Storage touched: config files and report outputs.

Demo role: preserve harness-first workflow.

MVP limitation: bounded by local fixtures.

### `ai-local demo run basic`

Purpose: run the standard demo flow.

Inputs: project root and demo config.

Outputs: combined demo report.

Exit codes: `0` on complete success.

Storage touched: index, runtime, report outputs.

Demo role: one-command demo path.

MVP limitation: narrow demo scope.

### `ai-local daemon run`

Purpose: run the long-lived local daemon.

Inputs: runtime configuration.

Outputs: background process state.

Exit codes: `0` on start success.

Storage touched: runtime DBs and logs.

Demo role: keep local services active.

MVP limitation: no service recovery guarantees.

### `ai-local service install`

Purpose: install the experimental Windows Service wrapper.

Inputs: service name, executable path, log path.

Outputs: installed service metadata.

Exit codes: `0` on install success.

Storage touched: Windows Service Manager and logs.

Demo role: start the daemon automatically on Windows.

MVP limitation: experimental wrapper only.

### `ai-local service uninstall`

Purpose: remove the service wrapper.

Inputs: service name.

Outputs: uninstall result.

Exit codes: `0` on success.

Storage touched: Windows Service Manager.

Demo role: cleanly remove the service.

MVP limitation: data is not deleted.

### `ai-local service start`

Purpose: start the installed service.

Inputs: service name.

Outputs: service state transition.

Exit codes: `0` on success.

Storage touched: Windows service runtime.

Demo role: run the daemon without a console window.

MVP limitation: service may still fail if the environment is broken.

### `ai-local service stop`

Purpose: stop the installed service.

Inputs: service name.

Outputs: stop status.

Exit codes: `0` on success.

Storage touched: Windows service runtime.

Demo role: stop the daemon safely.

MVP limitation: no force-kill guarantee.

### `ai-local service status`

Purpose: inspect installed service state.

Inputs: service name.

Outputs: status text.

Exit codes: `0` on success.

Storage touched: Windows service runtime.

Demo role: verify the service is available.

MVP limitation: local OS query only.

### `ai-local service logs`

Purpose: locate or tail service logs.

Inputs: service name and log path.

Outputs: log pointers or tail text.

Exit codes: `0` on success.

Storage touched: local log files.

Demo role: inspect service output after a run.

MVP limitation: no centralized log aggregation.
