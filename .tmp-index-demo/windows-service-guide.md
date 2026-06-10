# Windows Service Installation Guide

## Installing the pywin32 Windows Service

To install the AI Local Windows service using pywin32 strategy:

1. **Prerequisites:**
   - Windows operating system
   - Python 3.10+
   - pywin32 package installed: `pip install pywin32`
   - Administrator privileges

2. **Installation Steps:**
   - Run PowerShell as Administrator
   - Navigate to the project directory
   - Execute: `python -m ai_local.cli service install --strategy pywin32 --workspace <workspace_path>`

3. **Verify Installation:**
   - Check service status: `ai-local service status --strategy pywin32`
   - View in Services: `Get-Service ai-local-agent-runtime-pywin32`

4. **Start the Service:**
   - `python -m ai_local.cli service start --strategy pywin32 --workspace <workspace_path>`

5. **Stop the Service:**
   - `python -m ai_local.cli service stop --strategy pywin32 --workspace <workspace_path>`

6. **Uninstall:**
   - `python -m ai_local.cli service uninstall --strategy pywin32 --workspace <workspace_path>`

## Registry Configuration

The service stores configuration in the Windows registry at:
`HKLM\SYSTEM\CurrentControlSet\Services\ai-local-agent-runtime-pywin32\Parameters`

Key parameters:
- `workspace`: The workspace directory path
- `poll_interval`: Polling interval in seconds (default: 1.0)

## Troubleshooting

If the service fails to start:
1. Check Windows Event Log: `Get-WinEvent -LogName Application | Where-Object {$_.ProviderName -like '*ai-local*'}`
2. Verify the package is installed: `pip list | grep ai-local`
3. Ensure workspace is initialized: `ai-local init --workspace <path>`
