# Hướng dẫn vận hành AI Local

## Tổng quan

AI Local là một hệ thống AI local-first để chạy agent pipeline với khả năng chạy dưới dạng Windows service hoặc daemon.

## Cấu trúc workspace

Ở mỗi workspace, hệ thống tạo các thư mục và database sau:

```
.<workspace>/
├── .ai-local/
│   ├── base/           # Thư mục base
│   ├── logs/           # Logs
│   ├── reports/        # Reports
│   ├── backups/        # Backups
│   ├── config.yaml     # Config file
│   ├── knowledge.db    # Database knowledge
│   ├── runtime.db      # Database runtime
│   ├── tasks.db        # Database tasks
│   └── audit.db        # Database audit
```

## Khởi tạo

```bash
# Khởi tạo workspace mới
ai-local init

# Hoặc chỉ định workspace khác
ai-local init --workspace /path/to/workspace
```

## Các lệnh CLI

### 1. Cấu hình (Config)

```bash
# Hiện công cấu hình
ai-local config show

# Kiểm tra tính hợp lệ của config
ai-local config validate
```

### 2. Kiến thức (Knowledge)

#### Command `knowledge`
```bash
# Thêm file vào knowledge base
ai-local knowledge add /path/to/file --tag "tag1,tag2"

# Thêm note mới
ai-local knowledge add-note "Nội dung note" --tag "tag"

# Liệt kê tất cả knowledge
ai-local knowledge list

# Tìm kiếm trong knowledge
ai-local knowledge search "query"
```

#### Command nhóm tương tự (command level)
- `ai-local knowledge add <path> --workspace . --tag "tags"`
- `ai-local knowledge add-note <text> --workspace . --tag "tags"`
- `ai-local knowledge list --workspace .`
- `ai-local knowledge search <query> --workspace .`

### 3. Index (Project Index)

#### Command `index cơ bản`
```bash
# Scan project và build index
ai-local index scan

# Rebuild index từ đầu
ai-local index rebuild

# Hiện thống kê index (files, chunks, symbols)
ai-local index stats

# Search trong index
ai-local index search "query"
```

#### Command groups (command level)
- `ai-local index scan --root . --workspace .`
- `ai-local index rebuild --root . --workspace .`
- `ai-local index stats --workspace .`
- `ai-local index search "query" --workspace .`

### 4. Hỏi đáp (Ask)

```bash
# Trả lời câu hỏi dựa trên knowledge và project index
ai-local ask "Câu hỏi của bạn"

# Hiện nguồn evidence
ai-local ask "Câu hỏi" --show-evidence

# Hoặc với workspace khác
ai-local ask "Câu hỏi" --workspace /path/to/workspace
```

### 5. Task Management

#### Command `task cơ bản`
```bash
# Submit task vào queue
ai-local task submit "Nội dung task"

# Liệt kê tất cả tasks
ai-local task list

# Đọc task chi tiết
ai-local task read <task_id>

# Hủy task
ai-local task cancel <task_id>
```

#### Command groups (command level)
- `ai-local task submit "task" --workspace .`
- `ai-local task list --workspace .`
- `ai-local task read <task_id> --workspace .`
- `ai-local task cancel <task_id> --workspace .`

### 6. Runtime Control

#### Command `runtime cơ bản`
```bash
# Xem status của runtime control plane
ai-local runtime status

# Take snapshot của runtime state
ai-local runtime snapshot

# Xem daemon logs
ai-local runtime logs

# Create backup toàn bộ database
ai-local runtime backup create

# Restore từ backup
ai-local runtime backup restore /path/to/backup
```

### 7. Worker

```bash
# Chạy worker một lần (process một job và exit)
ai-local worker run --once

# Chạy worker liên tục (cleanup với Ctrl+C)
ai-local worker run --loop

# Với workspace khác
ai-local worker run --workspace /path/to/workspace --loop
```

### 8. Daemon

```bash
# Chạy daemon (background process)
ai-local daemon run

# Chạy daemon một lần
ai-local daemon run --once
```

#### Daemon options:
- `--workspace /path/to/workspace` - Workspace để sử dụng
- `--loop` - Chạy liên tục
- `--once` - Chạy một lần và exit
- `--poll-interval <seconds>` - Tần suất poll (mặc định: 0.1)
- `--max-iterations <count>` - Số iteration tối đa
- `--force` - Bypass stale lock

### 9. Service (Windows only)

Tính năng **Windows Service** hỗ trợ 2 chiến lược:

#### NSSM strategy (mặc định)
- Sử dụng NSSM (Non-Sucking Service Manager) để cài Windows service

### pywin32 strategy
```bash
# Cài service
ai-local service install --strategy pywin32

# Gỡ service
ai-local service uninstall --strategy pywin32

# Start service
ai-local service start --strategy pywin32

# Stop service
ai-local service stop --strategy pywin32

# Xem status service
ai-local service status --strategy pywin32

# Xem logs
ai-local service logs --strategy pywin32

# Dry run (không thực sự cài/gỡ/start/stop)
ai-local service status --strategy pywin32 --dry-run
```

#### Daemon log commands (chung cho cả 2 strategy)
```bash
# Xem daemon logs
ai-local service logs --tail 100

# Xem logs với số dòng cuối
ai-local service logs --tail 50
```

#### Precondition cho Windows Service:
1. Chạy trên Windows
2. Cài **NSSM** nếu使用 NSSM strategy
3. Cài **pywin32**: `python -m pip install pywin32`

### 10. Demo

Chạy demo cơ bản để test tất cả các thành phần.

#### Command `demo cơ bản`
```bash
# Chạy demo basic
ai-local demo run basic

# Chạy demo daemon
ai-local demo run daemon
```

### 11. Gate (Testing & Validation)

Chạy gate tests để validate các thành phần của hệ thống.

#### Command `run`
```bash
# Chạy gate với level xác định
ai-local gate run level1

# Xem tất cả commands support:
ai-local gate --help
```

Note: Các commands dưới đây được định nghĩa trong file `ai_local/cli.py` nhưng không có implementation riêng:
- `gate`, `promote`, `noise`, `memory_regression`, `memory_layers`
- `composite`, `decision`, `retrieval`, `project_retrieval`
- `skill_registry_refresh`, `skill_registry_cleanup`, `skill_registry_rebuild`
- `agent_loop`, `big_harness`, `small_patch`, `patch_pipeline`
- ... và nhiều commands khác

### 12. Doctor (Health Check)

Kiểm tra sức khỏe của hệ thống.

```bash
# Chạy doctor checks
ai-local doctor

# Tùy chọn
ai-local doctor --ollama-model qwen2.5:0.5b
ai-local doctor --ollama-base-url http://127.0.0.1:11434
ai-local doctor --skip-ollama
ai-local doctor --skip-ripgrep
```

### 13. Backup & Restore

#### Runtime Backup
Backup database của runtime (tasks, audit, runtime):

```bash
# Tạo backup
ai-local runtime backup create

# Restore từ backup
ai-local runtime backup restore /path/to/backup-dir
```

Backup files:
- `tasks.db` - Task database
- `audit.db` - Audit database
- `runtime.db` - Runtime database
- `backup-manifest.json` - Manifest của backup

## Workflow Common

### Workflow cơ bản:

```bash
# 1. Khởi tạo workspace
ai-local init

# 2. Scan project và build index
ai-local index scan

# 3. Add kiến thức vào database
ai-local knowledge add /path/to/file --tag "docs"

# 4. Search để kiểm tra
ai-local knowledge search "từ khóa"

# 5. Submit task
ai-local task submit "Nhiệm vụ của bạn"

# 6. Chạy worker để process task
ai-local worker run --loop
```

### Workflow với Daemon:

```bash
# 1. Khởi tạo workspace
ai-local init

# 2. Cài Windows Service (nếu sử dụng)s
ai-local service install

# 3. Start service
ai-local service start

# 4. Monitor logs
ai-local service logs --tail 100

# 5. Stop service khi không cần
ai-local service stop
```

## Monitoring

### Monitor Runtime Status

```bash
# Xem runtime status realtime
ai-local runtime status
```

### Xem Logs

```bash
# Hiện daemon logs
ai-local service logs

# Hiện last N dòng logs
ai-local service logs --tail 100

# Hiện logs từ file daemon.log
ai-local runtime logs
```

### Take Snapshots

```bash
# Take snapshot runtime state
ai-local runtime snapshot

# Output: runtime-snapshot.json
```

## Troubleshooting

### Daemon Already Running

```bash
# Đóng cổng (lên procímmon hoặc services.msc)
# Hoặc kill process daemon

# Sau đó run với --force
ai-local daemon run --force
```

### Windows Service Issues

1. **Verify NSSM is installed**:
   ```bash
   nssm --version
   ```

2. **Verify pywin32 is installed**:
   ```bash
   python -m pip show pywin32
   ```

3. **Check service status**:
   ```bash
   ai-local service status
   ```

4. **Check logs**:
   ```bash
   ai-local service logs --tail 50
   ```

### Workspace Issues

```bash
# Xóa thư mục .ai-local của workspace
rm -rf /path/to/workspace/.ai-local

# Khởi tạo lại
ai-local init --workspace /path/to/workspace
```

## Development

### Setup environment

```bash
# Install dependencies
python -m pip install -e .

# Install dev dependencies
python -m pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_xxx.py

# Run with specific coverage
pytest --cov=ai_local
```

## Tips & Best Practices

1. **Workspace isolation**: Mỗi project nên có workspace riêng để tránh conflict
2. **Indexing**: Scan/Rebuild index thường xuyên để keep database updated
3. **Backup**: Thường xuyên backup database trước khi modify
4. **Monitoring**: Monitor logs để detect issues early
5. **Service vs Daemon**:
   - Service: Được cài như Windows service, khởi động tự động
   - Daemon: Chạy như process bình thường, kiểm soát thủ công
6. **Strategy choice**:
   - NSSM strategy: Chuẩn hơn, ít known issues
   - pywin32 strategy: Code native Windows, có thể tốt hơn performance

## Tìm hiểu thêm

- Xem file README.md cho introduction
- Xem docs/cheatsheet-pywin32-service-vietnamese.md cho tips pywin32 service
- Xem pytest tests để hiểu cách hoạt động của mỗi thành phần