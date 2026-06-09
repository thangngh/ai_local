# Phase 5A — Windows Service MVP Contract

## Phase goal

Define the Windows Service MVP contract, compare implementation strategies, and
select a recommended approach for Phase 5B.  No service mutations are written
in this phase — only the contract document.

Once approved, Phase 5B will implement the chosen strategy so that:

```powershell
python -m ai_local.cli service install --workspace <path>
python -m ai_local.cli service uninstall --workspace <path>
python -m ai_local.cli service start --workspace <path>
python -m ai_local.cli service stop --workspace <path>
python -m ai_local.cli service status --workspace <path>
python -m ai_local.cli service logs --workspace <path> --tail 20
```

behave correctly on Windows, and fail with a clear message on other platforms.

## MVP scope

| Capability | Included |
|---|---|
| Install the daemon as a Windows service | yes |
| Start / stop / query the service | yes |
| Uninstall (remove the service) | yes |
| Route daemon logs to `daemon.log` | yes (already works) |
| Auto-start on boot (via service SID) | yes (default for services) |
| Workspace resolution from install args | yes |
| Pre-flight check before install | yes |
| Safe dry-run that works everywhere | yes (Phase 4C) |
| Failure message when NSSM is missing | yes |
| NSSM binary bundled in repo | no |
| Recovery actions (restart on crash) | no (future) |
| Multiple workspace instances | no (future) |
| Service --user / --password | no (future) |
| Production hardening (ACLs, perf counters) | no |

## Non-goals

- No pywin32 dependency.
- No WinSW binary bundled.
- No service monitoring dashboard.
- No automatic crash recovery in MVP.
- No multi-service instance manager.
- No service uninstall that deletes workspace data.
- No service install on non-Windows.
- No network calls.
- No LLM calls.

## Service runner command

The service will ultimately execute:

```powershell
python -m ai_local.cli daemon run --workspace <workspace> --loop --poll-interval 1.0
```

- `python` resolution: use `sys.executable` at install time to capture the
  absolute path to the Python interpreter that ran the install command.
- `--workspace <workspace>`: the absolute workspace path provided at install
  time, resolved to an absolute path and stored in the service definition.
- `--loop --poll-interval 1.0`: continuous loop with a 1-second poll interval.

## Service identity

| Property | Value |
|---|---|
| Service name (SERVICE_NAME) | `ai-local-agent-runtime` |
| Display name | `AI Local Agent Runtime` |
| Description | "Runs the AI Local daemon loop to process tasks from a local queue." |
| Startup type | `Automatic` (boot start) |
| Run-as account | `LocalSystem` (default for `New-Service` / NSSM) |

## Workspace resolution

- The workspace path is supplied via `--workspace <path>` at install time.
- The path is resolved to an absolute path (`Path.resolve()`) and frozen into
  the service command line.
- The service does not re-resolve or auto-discover the workspace at runtime.
- The workspace directory must exist (or be initialisable via `init`) before
  the service starts.

## Environment assumptions

| Assumption | Notes |
|---|---|
| Python is installed | The same `python` used for install is used for the service |
| Python is on `PATH` for the `LocalSystem` account | Often **not** true — NSSM allows setting an explicit `AppEnvironment` |
| Workspace path is a stable absolute path | No network drives, no symlinks that could dissolve |
| User has admin privileges for install/uninstall | Required by Windows service APIs |
| No antivirus blocks NSSM or Python | Outside our control |
| System is Windows 10+ or Windows Server 2019+ | Not tested on earlier versions |

## Install strategy options

### Option A: PowerShell `New-Service`

The built-in PowerShell cmdlet.

```powershell
New-Service -Name "ai-local-agent-runtime" `
    -DisplayName "AI Local Agent Runtime" `
    -BinaryPathName '"C:\Python313\python.exe" -m ai_local.cli daemon run --workspace C:\workspace --loop --poll-interval 1.0' `
    -StartupType Automatic
```

**Pros:**
- Built into Windows — no external dependency.
- No binary to distribute.
- Straightforward for a single command.

**Cons:**
- Binary path quoting is fragile — spaces in Python path or workspace path
  require careful nested quoting.
- Python is rarely on `PATH` for `LocalSystem`; must use full path to
  `python.exe`, which may differ between machines or Python versions.
- No working-directory or environment-variable configuration without extra
  `sc.exe` calls after creation.
- Recovery options (restart on failure) require additional `sc.exe` commands.
- No stdout/stderr redirection to a log file without manual configuration.

### Option B: NSSM (Non-Sucking Service Manager)

A dedicated, well-known service wrapper.

```
nssm install ai-local-agent-runtime "C:\Python313\python.exe" "-m ai_local.cli daemon run --workspace C:\workspace --loop --poll-interval 1.0"
nssm set ai-local-agent-runtime AppDirectory "C:\Python313"
nssm set ai-local-agent-runtime AppStdout "C:\workspace\.ai-local\logs\daemon.log"
nssm set ai-local-agent-runtime AppStderr "C:\workspace\.ai-local\logs\daemon.log"
nssm start ai-local-agent-runtime
```

**Pros:**
- Purpose-built for wrapping arbitrary executables as Windows services.
- Explicit working directory, environment variables, stdout/stderr log files.
- Graceful shutdown via named-pipe IPC (sends Ctrl+C / WM_CLOSE).
- Recovery tab (restart on failure) configurable via CLI.
- Handles the `PATH` / working-directory problem cleanly.

**Cons:**
- External binary (~300 KB) — not part of Windows.
- Must be installed (or at least placed on disk) before use.
- Licensing: NSSM is released under a permissive 2-clause BSD license, but
  distribution terms must be respected (not bundled in repo without notice).
- Install precheck required — fail gracefully if NSSM is not available.

### Option C: Windows Task Scheduler

Run the daemon as a scheduled task rather than a true service.

```
schtasks /create /tn "AI Local Agent Runtime" /tr "python -m ai_local.cli daemon run --workspace C:\workspace --loop --poll-interval 1.0" /sc onstart /ru SYSTEM /rl highest
```

**Pros:**
- Built into Windows.
- No external binary.
- Can run as `SYSTEM` without Python on `PATH` (specify full path).

**Cons:**
- Not a real service — does not appear in `services.msc` under the expected
  name, does not support `sc.exe query` / `net start` semantics easily.
- Different lifecycle: "run whether user is logged on or not" can prompt for
  credentials.
- Logging/restart behaviour differs from a true service.
- Harder to stop/remove reliably from CLI without complex `schtasks` flags.
- Not a standard pattern for Python Windows services.

## Chosen strategy recommendation

**Recommend NSSM (Option B) for Phase 5B.**

Rationale:

1. **Environment control** — NSSM lets us set `AppDirectory` to the Python
   installation directory and `AppEnvironment` to include `PATH`, avoiding the
   common "Python not found for LocalSystem" failure.

2. **Log redirection** — NSSM can write stdout/stderr directly to
   `daemon.log`, eliminating the need for additional log-capture plumbing.

3. **Graceful shutdown** — NSSM's IPC sends a console event to the wrapped
   process, which `asyncio` / `signal` handlers can catch, enabling clean
   teardown.

4. **Recovery configuration** — A single `nssm set` command configures
   restart-on-failure, which would require multiple `sc.exe` calls otherwise.

5. **No bundling** — We will not bundle NSSM in the repository. The install
   command will:
   - Check if `nssm` is on `PATH` or at a well-known location.
   - If missing, print a clear error message with installation instructions.
   - Dry-run continues to work regardless.

### Fallback

If NSSM is not available and the user explicitly requests a no-dependency
approach, Option A (PowerShell `New-Service` + `sc.exe` recovery config) is
the secondary choice.  Phase 5B implements only the primary (NSSM) strategy.

## Command contract

### `python -m ai_local.cli service install --workspace <path>`

**Preconditions:**
- Platform is Windows (otherwise print error and exit 1).
- NSSM is available on `PATH` (otherwise print error with install link).
- Workspace path exists or is creatable.

**Behaviour:**
- Resolves workspace to absolute path.
- Resolves Python interpreter to absolute path (`sys.executable`).
- Runs:
  ```
  nssm install ai-local-agent-runtime <python> -m ai_local.cli daemon run --workspace <workspace> --loop --poll-interval 1.0
  nssm set ai-local-agent-runtime AppDirectory <python-home>
  nssm set ai-local-agent-runtime AppStdout <workspace>/.ai-local/logs/daemon.log
  nssm set ai-local-agent-runtime AppStderr <workspace>/.ai-local/logs/daemon.log
  nssm set ai-local-agent-runtime Description "Runs the AI Local daemon loop to process tasks from a local queue."
  nssm set ai-local-agent-runtime Start SERVICE_AUTO_START
  ```

**Postconditions:**
- Service `ai-local-agent-runtime` is registered and configured.
- Service is not started (start is a separate step).
- Exit code 0 on success, non-zero on failure.

**Dry-run output:**
```
SERVICE install dry-run
NAME AI Local Agent Runtime
COMMAND python -m ai_local.cli daemon run --workspace <path> --loop --poll-interval 1.0
NOTE dry-run only; no Windows service was created
```

### `python -m ai_local.cli service uninstall --workspace <path>`

**Preconditions:**
- Platform is Windows (otherwise print error and exit 1).
- NSSM is available (otherwise print error).

**Behaviour:**
- Stops the service if running.
- Runs `nssm remove ai-local-agent-runtime confirm`.
- Does not remove workspace files, logs, or reports.

**Postconditions:**
- Service is removed.
- Workspace data is preserved.
- Exit code 0 on success, non-zero on failure.

**Dry-run output:**
```
SERVICE uninstall dry-run
NAME AI Local Agent Runtime
NOTE dry-run only; no Windows service was removed
```

### `python -m ai_local.cli service start --workspace <path>`

**Preconditions:**
- Platform is Windows.
- Service exists.

**Behaviour:**
- Runs `nssm start ai-local-agent-runtime`.

**Postconditions:**
- Service transitions to `RUNNING`.
- Exit code 0 on success, non-zero on failure.

**Dry-run output:**
```
SERVICE start dry-run
NAME AI Local Agent Runtime
COMMAND <service-start-command-placeholder>
NOTE dry-run only; no Windows service was started
```

### `python -m ai_local.cli service stop --workspace <path>`

**Preconditions:**
- Platform is Windows.
- Service exists.

**Behaviour:**
- Runs `nssm stop ai-local-agent-runtime`.

**Postconditions:**
- Service transitions to `STOPPED`.
- Exit code 0 on success, non-zero on failure.

**Dry-run output:**
```
SERVICE stop dry-run
NAME AI Local Agent Runtime
NOTE dry-run only; no Windows service was stopped
```

### `python -m ai_local.cli service status --workspace <path>`

**Preconditions:**
- Platform is Windows.
- Service exists.

**Behaviour:**
- Runs `nssm status ai-local-agent-runtime` or `sc.exe query ai-local-agent-runtime`.
- Prints human-readable status:
  ```
  SERVICE status <running|stopped|not_found>
  NAME AI Local Agent Runtime
  PID <pid>
  ```

**Dry-run output:**
```
SERVICE status dry-run
NAME AI Local Agent Runtime
NOTE dry-run only; no Windows service was queried
```

### `python -m ai_local.cli service logs --workspace <path> --tail 20`

**No dry-run distinction.**  This command reads the local daemon log file
regardless of whether the service is installed.  Works on all platforms.

**Output:**
```
LOGS <workspace>/.ai-local/logs/daemon.log tail=20
<jsonl-line-1>
...
```

## Safety rules

1. **Real install/start/stop/uninstall must be Windows-only.**
   - `platform.system() != "Windows"` → print error, exit 1.
   - Exception: `logs`, `install --dry-run`, `uninstall --dry-run`,
     `start --dry-run`, `stop --dry-run`, `status --dry-run` work on any
     platform.

2. **Real install must require explicit non-dry-run command.**
   - `--dry-run` is the default for safety; omitting it is an affirmative
     action.

3. **Must not run if workspace path does not exist.**
   - Workspace existence is checked before any mutation.
   - If only `init` needs to be run, print guidance.

4. **Must not delete workspace data on uninstall.**
   - Uninstall removes only the Windows service registration.
   - `.ai-local/` contents (logs, reports, databases) are preserved.

5. **Must not delete logs/reports on uninstall.**
   - Handled by the same rule as workspace data.

6. **Must not require network.**
   - No downloads, no phone-home, no package installs during service
     operations.

7. **Must not call LLMs.**

8. **Must not claim production-grade service.**
   - Output text and documentation must qualify the service as
     "development/demo" grade.

9. **NSSM precheck must fail safely.**
   - If NSSM is not found, the install command prints a message with a link
     to https://nssm.cc/download and exits non-zero.

## Validation checklist

These commands will be used in Phase 5B to validate the implementation.  They
are listed here as a contract reference; they are **not** executed in Phase 5A.

```powershell
# 1. Dry-run (works everywhere, including non-Windows)
python -m ai_local.cli service install --dry-run --workspace .tmp-demo
python -m ai_local.cli service uninstall --dry-run --workspace .tmp-demo
python -m ai_local.cli service start --dry-run --workspace .tmp-demo
python -m ai_local.cli service stop --dry-run --workspace .tmp-demo
python -m ai_local.cli service status --dry-run --workspace .tmp-demo

# 2. Real install (Windows + NSSM only)
python -m ai_local.cli service install --workspace C:\full\path\to\workspace

# 3. Service lifecycle
python -m ai_local.cli service start --workspace C:\full\path\to\workspace
python -m ai_local.cli service status --workspace C:\full\path\to\workspace
python -m ai_local.cli service stop --workspace C:\full\path\to\workspace

# 4. Service runs daemon loop
# Submit a task, wait, check it was processed via status

# 5. Logs are accessible
python -m ai_local.cli service logs --workspace C:\full\path\to\workspace --tail 10

# 6. Uninstall preserves data
python -m ai_local.cli service uninstall --workspace C:\full\path\to\workspace
# Verify workspace .ai-local/ still exists

# 7. Non-Windows fails cleanly (test on Linux/macOS CI)
python -m ai_local.cli service install --workspace /tmp/workspace
# Expected: error message, exit 1

# 8. Missing NSSM fails cleanly
# Remove NSSM from PATH temporarily
python -m ai_local.cli service install --workspace C:\workspace
# Expected: "NSSM not found" message, exit 1
```

## Rollback/uninstall expectations

| Step | Action | Data loss? |
|---|---|---|
| Uninstall service | `nssm remove ai-local-agent-runtime confirm` | No — only service registration removed |
| Stop service (pre-uninstall) | `nssm stop ai-local-agent-runtime` | No — process terminated |
| Remove workspace | Manual (`rm -rf`) | Yes — all data, logs, DBs |
| Re-install after uninstall | Re-run `install` | Works as fresh install |
| Upgrade Python | Uninstall, install new Python, re-run `install` | Service binary path updated |

## Known limitations

- **Single workspace** — Only one workspace can be serviced per install.
  Multiple workspaces require multiple service instances (future work).

- **No crash recovery** — The MVP does not configure NSSM recovery actions
  (restart on crash).  The service stays stopped if the daemon exits
  unexpectedly.

- **No log rotation** — `daemon.log` grows unboundedly.  NSSM's
  `AppRotateFiles` can be configured later.

- **NSSM external dependency** — Users must install NSSM manually.  This is
  documented but adds a friction point.

- **No monitoring** — No health-check endpoint, no heartbeat failover.

- **No multi-user support** — Runs as `LocalSystem`; not designed for
  per-user service instances.

- **demo/development grade** — The service is intended for local development
  and demo workflows, not production deployments.
