# 📋 Cheatsheet: pywin32 Windows Service - Tiếng Việt

> **Mục đích**: Hướng dẫn nhanh sử dụng tính năng **pywin32 Windows Service** trong dự án `ai_local` — chạy agent runtime như Windows Service gốc (native) thay vì dùng NSSM.

---

## 🎯 Tổng Quan

| Đặc điểm | NSSM (mặc định) | pywin32 (tùy chọn) |
|----------|-----------------|---------------------|
| **Binary ngoài** | Cần `nssm.exe` | Không cần binary ngoài |
| **Dependency** | Chỉ stdlib | Cần `pywin32` (`pip install pywin32`) |
| **Service ID** | `ai-local-agent-runtime` | `ai-local-agent-runtime-pywin32` |
| **Display Name** | AI Local Agent Runtime | AI Local Agent Runtime (pywin32) |
| **Config** | Registry NSSM | File JSON trong workspace |
| **Tích hợp daemon** | Chạy CLI qua shell | Gọi trực tiếp `run_daemon_loop()` |
| **Dừng service** | NSSM gửi SIGTERM | pywin32 event → `should_stop()` callback |
| **Logging** | File stdout/stderr | **Windows EventLog** |

---

## ⚙️ Cài Đặt Môi Trường

### 1. Cài pywin32
```powershell
python -m pip install pywin32
```

> ⚠️ **Quan trọng**: Python user-local install có thể **KHÔNG** hoạt động cho service `LocalSystem`.  
> → Cài Python system-wide **HOẶC** dùng virtual env accessible bởi service account.

### 2. Kiểm tra pywin32
```powershell
python -c "import win32serviceutil, win32service, win32event, servicemanager; print('pywin32 ok')"
```

### 3. Yêu cầu Administrator
Tất cả thao tác service thật cần **PowerShell elevated (Run as Administrator)**:
```powershell
# Kiểm tra admin
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
# Phải trả về: True
```

---

## 🚀 Lệnh CLI (Unified Interface)

Tất cả lệnh dùng flag `--strategy pywin32`:

```powershell
# === CÀI ĐẶT ===
# Dry-run (không tạo service thật)
python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace .tmp-demo

# Cài thật (CẦN ADMIN + pywin32)
python -m ai_local.cli service install --strategy pywin32 --workspace C:\temp\ai-local-smoke

# === KHỞI ĐỘNG ===
python -m ai_local.cli service start --dry-run --strategy pywin32
python -m ai_local.cli service start --strategy pywin32

# === DỪNG ===
python -m ai_local.cli service stop --dry-run --strategy pywin32
python -m ai_local.cli service stop --strategy pywin32

# === TRẠNG THÁI ===
python -m ai_local.cli service status --dry-run --strategy pywin32
python -m ai_local.cli service status --strategy pywin32

# === GỠ CÀI ĐẶT ===
python -m ai_local.cli service uninstall --dry-run --strategy pywin32
python -m ai_local.cli service uninstall --strategy pywin32

# === XEM LOG (chung cho cả 2 strategy) ===
python -m ai_local.cli service logs --workspace C:\temp\ai-local-smoke --tail 30
```

---

## 🔧 Gọi Module Trực Tiếp (Advanced)

Có thể bypass CLI và gọi module pywin32 service trực tiếp:

```powershell
# Cài đặt
python -m ai_local.runtime.pywin32_service install --workspace C:\temp\ai-local-smoke

# Khởi động
python -m ai_local.runtime.pywin32_service start

# Dừng
python -m ai_local.runtime.pywin32_service stop

# Trạng thái
python -m ai_local.runtime.pywin32_service status

# Gỡ cài đặt
python -m ai_local.runtime.pywin32_service remove

# Tự động khởi động với Windows
python -m ai_local.runtime.pywin32_service install --workspace C:\temp\ai-local-smoke --startup auto
```

---

## 📂 File Cấu Hình

Service pywin32 ghi config vào:
```
<workspace>/.ai-local/reports/pywin32-service.json
```

**Ví dụ nội dung:**
```json
{
  "workspace": "C:\\temp\\ai-local-smoke",
  "poll_interval": 1.0,
  "service_id": "ai-local-agent-runtime-pywin32"
}
```

> Config cũng được ghi vào **Windows Registry** tại:
> `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\ai-local-agent-runtime-pywin32\Parameters`

---

## ✅ Quy Trình Smoke Test Đầy Đủ (Full Validation)

### Bước 1: Chuẩn bị (từ PowerShell ADMIN)
```powershell
$Repo = "D:\2026\agent_new\ai_local"
$Workspace = "C:\temp\ai-local-pywin32-smoke"
$Python = "python"
cd $Repo

# 1. Init workspace
& $Python -m ai_local.cli init --workspace $Workspace

# 2. Kiểm tra pywin32
& $Python -c "import win32serviceutil, win32service, win32event, servicemanager; print('pywin32 ok')"
```

### Bước 2: Dry-run
```powershell
& $Python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace $Workspace
& $Python -m ai_local.cli service status --dry-run --strategy pywin32 --workspace $Workspace
```

### Bước 3: Cài & Chạy thật
```powershell
# Cài service
& $Python -m ai_local.cli service install --strategy pywin32 --workspace $Workspace

# Khởi động
& $Python -m ai_local.cli service start --strategy pywin32

# Kiểm tra trạng thái
& $Python -m ai_local.cli service status --strategy pywin32
# Kết quả mong đợi: STATE RUNNING
```

### Bước 4: Test xử lý task
```powershell
# Submit task
& $Python -m ai_local.cli task submit "pywin32 smoke task" --workspace $Workspace
Start-Sleep -Seconds 3

# Kiểm tra runtime
& $Python -m ai_local.cli runtime status --workspace $Workspace
# Task phải chuyển từ pending → done

# Xem log
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 50
```

### Bước 5: Dọn dẹp
```powershell
# Dừng service
& $Python -m ai_local.cli service stop --strategy pywin32

# Gỡ cài đặt
& $Python -m ai_local.cli service uninstall --strategy pywin32

# Verify workspace vẫn còn
Test-Path "$Workspace\.ai-local"
Get-ChildItem "$Workspace\.ai-local"
```

---

## 🛠️ Xử Lý Sự Cố (Troubleshooting)

| Triệu chứng | Nguyên nhân | Giải pháp |
|-------------|-------------|-----------|
| `pywin32 not found` | Chưa cài dependency | `python -m pip install pywin32` |
| `Windows only` | Không chạy trên Windows | Chỉ chạy trên Windows 10+/Server 2019+ |
| `Access denied` | Không phải Admin | Mở PowerShell **Run as Administrator** |
| `Workspace not initialised` | Chưa chạy `init` | `python -m ai_local.cli init --workspace <path>` |
| Service start rồi stop ngay | Sai Python path/workdir | Kiểm tra `service.stderr.log` hoặc EventLog |
| Task cứ pending | Daemon không chạy | `runtime status`, `service logs` |
| Uninstall fail | Service vẫn chạy | Dùng `stop` → `kill fallback` trước |

---

## 🔨 Kill Fallback (LAST RESORT)

Khi `service stop` không hoạt động:

```powershell
# Tìm process daemon
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*pywin32_service*" -or $_.CommandLine -like "*ai_local*" } |
  Select-Object ProcessId, CommandLine

# Kill process
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*pywin32_service*" -or $_.CommandLine -like "*ai_local*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Hoặc force stop service native
Stop-Service -Name "ai-local-agent-runtime-pywin32" -Force -ErrorAction SilentlyContinue
```

---

## 📋 Kiểm Tra Nhanh (Checklist)

Trước khi báo lỗi, hãy verify:

- [ ] Windows 10+ / Server 2019+
- [ ] PowerShell **Run as Administrator**
- [ ] `python -c "import win32serviceutil"` → **không lỗi**
- [ ] `python -m ai_local.cli init --workspace <path>` → **PASS**
- [ ] Dry-run install/status → **PASS**
- [ ] Real install → **PASS** (có output `SERVICE install PASS`)
- [ ] Start → **PASS**, status → `STATE RUNNING`
- [ ] Submit task → task **done** trong runtime status
- [ ] Stop → **PASS**, status → `STATE STOPPED`
- [ ] Uninstall → **PASS**, workspace `.ai-local` **vẫn tồn tại**

---

## 🧪 Chạy Tests

```powershell
# Chạy toàn bộ test liên quan
python -m pytest tests/test_worker_daemon_runtime.py -q

# Check code quality
python -m ruff check ai_local/cli/commands/service.py ai_local/runtime/pywin32_service.py ai_local/runtime/daemon_contract.py tests/test_worker_daemon_runtime.py
```

**Kết quả mong đợi**: `59 passed` (bao gồm 14 test pywin32-specific)

---

## ⚠️ Hạn Chế Biết (Known Limitations)

1. **pywin32 không phải hard dependency** — module import được trên mọi platform
2. **pywin32 phải cài trong env accessible cho service account** (user-local có thể fail cho LocalSystem)
3. **Không có recovery policy** — service dừng hẳn nếu daemon loop crash
4. **Không log rotation** — EventLog size bị giới hạn bởi OS
5. **1 workspace / 1 service instance**
6. **Không phải production-hardened** — MVP integration only
7. **NSSM vẫn là default** — pywin32 opt-in qua `--strategy pywin32`

---

## 📚 File Liên Quan

| File | Chức năng |
|------|-----------|
| `ai_local/runtime/pywin32_service.py` | Service host module (lazy imports) |
| `ai_local/cli/commands/service.py` | CLI commands với `--strategy` flag |
| `ai_local/runtime/daemon_contract.py` | `run_daemon_loop()` helper |
| `docs/demo/phase-6a-pywin32-service-host.md` | Spec chi tiết Phase 6A |
| `docs/demo/phase-6b-pywin32-real-service-smoke.md` | Smoke test evidence |
| `docs/demo/phase-6c-windows-service-powershell-runbook.md` | Runbook PowerShell đầy đủ |

---

## 🎓 Tóm Tắt Lệnh Hay Dùng

```powershell
# === DAILY WORKFLOW ===
# 1. Init workspace (lần đầu)
python -m ai_local.cli init --workspace .my-workspace

# 2. Dry-run kiểm tra
python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace .my-workspace

# 3. Cài service thật (Admin required)
python -m ai_local.cli service install --strategy pywin32 --workspace .my-workspace

# 4. Start service
python -m ai_local.cli service start --strategy pywin32

# 5. Submit task & check
python -m ai_local.cli task submit "my task" --workspace .my-workspace
python -m ai_local.cli runtime status --workspace .my-workspace

# 6. Xem log
python -m ai_local.cli service logs --workspace .my-workspace --tail 30

# 7. Cleanup
python -m ai_local.cli service stop --strategy pywin32
python -m ai_local.cli service uninstall --strategy pywin32
```

---

**📝 Lưu ý**: Cheatsheet này dựa trên implement Phase 6A/6B/6C hiện tại. Xem `docs/demo/phase-6*.md` để biết chi tiết thiết kế và test evidence.