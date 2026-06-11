# 🎭 Demo: AI Local Agent - Pet Store Project

> **Mục đích**: Thể hiện toàn bộ capabilities của AI Local với một project thực tế: Next.js Pet Store
>
> **Project**: `D:\2026\viber-coding\pet-store`
>
> **Demo executed**: 2026-06-10 — full evidence from real run included below
>
> **Workflow bao gồm**:
> - Knowledge indexing (build index trước/current index sau)
> - Ask question (trả lời trước/after knowledge)
> - Task submission (submit task cho agent)
> - Task checking (kiểm tra task)
> - Worker execution (process task)
> - Gate validation (validate với gates) — **⚠️ known gap: gates only stub in main CLI**
> - User approval workflow (workflow approval dùng/approve)
> - System validation (hệ thống kiểm tra qua gates)

---

## 📊 Actual Results Summary (from real run)

### ✅ Worked
| Feature | Status | Detail |
|---------|--------|--------|
| Init workspace | ✅ | `.ai-local` created |
| Index scan | ✅ | 143 files, 3169 chunks |
| Index stats | ✅ | files=143 chunks=3169 |
| Knowledge add-note | ✅ | Adds with tags |
| Knowledge search | ✅ | Search by keyword works |
| Ask (after knowledge) | ✅ | `DECISION: enough_context`, returns notes |
| Task submit | ✅ | Enqueues to SQLite |
| Task list / read | ✅ | Full JSON payload |
| Worker once | ✅ | Marks task `succeeded` |
| Daemon loop | ✅ | 1100 iterations, process 2 tasks |
| Runtime status | ✅ | Shows queue + daemon state |

### ❌ Issues Found
| # | Issue | Root Cause |
|---|-------|------------|
| 1 | **Ask answer_draft sai priority** | Returns README.md instead of cart note — no relevance ranking |
| 2 | **Knowledge dedup** | Same auth note added twice (id=3, id=4) — no duplicate check |
| 3 | **Index includes `.next/`** | Search returns build artifacts — missing `.gitignore` rules |
| 4 | **Gate commands missing** | `gate promote`, `project_retrieval`, `patch_levels` → "No such command" |
| 5 | **Worker không execute code thật** | `WORKER once PASS` nhưng code không thay đổi |
| 6 | **PowerShell `\` không hoạt động** | Backtick `` ` `` required instead of backslash |

---

## 📋 Overview - Pet Store Project

### Stack
- **Framework**: Next.js 14+ (App Router)
- **State Management**: Zustand with persistence
- **E-commerce Features**:
  - Cart management
  - Checkout flow
  - Orders tracking
  - Product & Shop browsing
- **Key Files**:
  ```
  src/
  ├── store/
  │   ├── cart.store.ts    # Cart state (61 lines)
  │   └── auth.store.ts    # Auth state (60 lines)
  ├── types/
  │   └── index.ts         # All TypeScript types (134 lines)
  ├── services/
  │   ├── mock/
  │   │   ├── api.ts       # Mock API
  │   │   ├── data.ts      # Mock data
  │   │   └── index.ts     # Export
  │   └── index.ts         # Re-exports
  ├── components/
  │   ├── domain/          # Domain-specific components
  │   │   ├── CartItem
  │   │   ├── ProductCard
  │   │   └── ShopCard
  │   └── layout/          # Layout components (Header, Footer)
  └── app/                  # Next.js app router pages
      ├── cart/
      ├── checkout/
      ├── orders/
      ├── product/[id]/
      └── shop/[slug]/
  ```

---

## 📊 Real Execution Evidence (Full session log)

> **Workspace used**: `D:\2026\viber-coding\pet-store` (no separate temp dir)
> **Index build**: `ai-local index scan --root D:\2026\viber-coding\pet-store --workspace D:\2026\viber-coding\pet-store`

---

### **Bước 0: Workspace Init**

```powershell
# Trước khi chạy init — chưa có .ai-local
PS D:\2026\viber-coding\pet-store> ai-local config show
# → {}
```

```powershell
# Init workspace
ai-local init --workspace D:\2026\viber-coding\pet-store
# → INIT workspace=D:\2026\viber-coding\pet-store dir=D:\2026\viber-coding\pet-store\.ai-local
```

### **Bước 1: Index Scan + Stats**

```powershell
ai-local index scan --root D:\2026\viber-coding\pet-store --workspace D:\2026\viber-coding\pet-store
# → INDEX_SCAN indexed=143 unchanged=0

ai-local index stats --workspace D:\2026\viber-coding\pet-store
# → INDEX_STATS files=143 chunks=3169 symbols=0

# Note: includes .next/ files in index (should ignore build dirs)
ai-local index search "app" --workspace D:\2026\viber-coding\pet-store
# → .next\dev\server\chunks\ssr\[root-of-the-server]__1368f39f._.js:41-58
# → .next\dev\server\chunks\ssr\node_modules_next_dist_3e1f69b5._.js:1-40
# → .next\...
```

### **Bước 2: Knowledge Notes (with tag classification)**

```powershell
# Add notes với tags
ai-local knowledge add-note "CartStore xử lý logic add item với validation shopId:
- Nếu thêm item từ shop khác → clear cart và add mới item
- Nếu item đã tồn tại → increment quantity
- persist vào localStorage và zustand integration" --tag "cart,logic,validation" --workspace D:\2026\viber-coding\pet-store
# → KNOWLEDGE note added id=1 tags=cart,logic,validation

ai-local knowledge add-note "Price calculation trong CartStore cần fix:
- getSubtotal() chỉ hiển thị, final price phải từ server
- thiếu logic apply discount/promotion
- thiếu validation tax calculation" --tag "cart,price,bug" --workspace D:\2026\viber-coding\pet-store
# → KNOWLEDGE note added id=2 tags=cart,price,bug

ai-local knowledge add-note "Zustand auth store với persistence:
- persist với localStorage
- partialize chỉ lưu user và isAuthenticated
- onRehydrateStorage helper" --tag "auth,zustand,persistence" --workspace D:\2026\viber-coding\pet-store
# → KNOWLEDGE note added id=3 tags=auth,zustand,persistence

# ❌ BUG: Same note added twice — no duplicate detection
ai-local knowledge add-note "Zustand auth store với persistence:
- persist với localStorage
- partialize chỉ lưu user và isAuthenticated
- onRehydrateStorage helper" --tag "auth,zustand,persistence" --workspace D:\2026\viber-coding\pet-store
# → KNOWLEDGE note added id=4 tags=auth,zustand,persistence

# List all
ai-local knowledge list --workspace D:\2026\viber-coding\pet-store
# → 1 note note tags=cart,logic,validation
# → 2 note note tags=cart,price,bug
# → 3 note note tags=auth,zustand,persistence
# → 4 note note tags=auth,zustand,persistence
```

### **Bước 3: Ask (Before Knowledge → After Knowledge)**

#### **BEFORE** (chỉ có index, chưa có knowledge notes):

```powershell
ai-local ask "Tôi cần hiểu logic của Cart store, đặc biệt là validate shopId khi add item" --workspace D:\2026\viber-coding\pet-store
# → DECISION: low_context
# → QUESTION: Tôi cần hiểu logic của Cart store...
# → REPORT: C:\temp\pet-store\.ai-local\reports\ask-XXX.json
# → (không có ANSWER_DRAFT vì low_context)
```

#### **AFTER** (có knowledge notes với tags cart,logic,validation + cart,price,bug):

```powershell
ai-local ask "Tôi cần hiểu logic của Cart store, đặc biệt là validate shopId khi add item" --workspace D:\2026\viber-coding\pet-store --show-evidence
# → DECISION: enough_context
# → QUESTION: Tôi cần hiểu logic của Cart store...
# → ANSWER_DRAFT: Based on knowledge note: CartStore xử lý logic add item với validation shopId:
# →   - Nếu thêm item từ shop khác → clear cart và add mới item
# →   - Nếu item đã tồn tại → increment quantity
# →   - persist vào localStorage và zustand integration
# → EVIDENCE: knowledge_id=1 title=note
# → EVIDENCE: knowledge_id=2 title=note
# → REPORT: D:\2026\viber-coding\pet-store\.ai-local\reports\ask-XXX.json
```

**✅ Knowledge retrieval works**: AFTER returns knowledge_id=1,2 (cart notes).

### **Bước 4: In-depth Ask (phát hiện ranking bug)**

```powershell
ai-local ask "Trong cart store, tại sao getSubtotal() chỉ hiển thị và không fetch từ server?
Nêu các case bug tiềm ẩn và đề xuất fix" --workspace D:\2026\viber-coding\pet-store --show-evidence
# → DECISION: enough_context
# → QUESTION: Trong cart store, tại sao getSubtotal()...
# → ANSWER_DRAFT: Based on knowledge note: This is a Next.js project bootstrapped with create-next-app...
# → EVIDENCE: knowledge_id=1 title=README.md      ← ❌ Should be cart note!
# → EVIDENCE: knowledge_id=3 title=note
# → EVIDENCE: knowledge_id=4 title=note
```

**❌ Issue #1**: `answer_draft` trả về README.md content (file) thay vì cart note (knowledge).  
**Root cause**: Code `knowledge_hits[0]` không ranking theo relevance — lấy first result từ SQLite.

### **Bước 5: Task Submit (2 variants)**

```powershell
# Task 1 — simple fix
ai-local task submit "Upgrade CartStore price calculations:
1. getSubtotal() phải fetch final prices from mock API instead of using local product.price
2. Add discount logic (5% discount cho orders > $100)
3. Add tax calculation (10% VAT)
4. Update CartItem component để hiển thị calculated values
5. Test với edge cases: empty cart, mixed currency, etc." --workspace D:\2026\viber-coding\pet-store
# → TASK submitted

# Task 2 — full pipeline with PROBLEM/REQUIREMENTS/DELIVERABLES
ai-local task submit "Phát hiện và fix bugs trong CartStore:
PROBLEM:
- getSubtotal() dùng local product.price thay vì server price → giá sai
- Thiếu validation: quantity > stock của product
- Thiếu validation: shopId phải tồn tại trước khi add item
- Cart không reset khi checkout failed
REQUIREMENTS:
1. Complete endpoint integration: prices phải fetch từ mock API
2. Validation layer với reusable validation function
3. Error handling với user-friendly messages
4. Saga/transaction pattern cho multi-step flow
5. Unit tests cho từng fix
6. Update knowledge notes về issue và fix
DELIVERABLES:
- code fixes trong src/store/cart.store.ts
- unit tests trong tests/
- kèm changelog.md
- kèm knowledge notes về learned pattern" --workspace D:\2026\viber-coding\pet-store
# → TASK submitted
```

### **Bước 6: Task Check**

```powershell
ai-local task list --workspace D:\2026\viber-coding\pet-store
# → task-1 pending demo
# → task-2 pending demo

ai-local task read task-1 --workspace D:\2026\viber-coding\pet-store
# → {
# →   "id": "task-1",
# →   "type": "demo",
# →   "status": "pending",
# →   "priority": 100,
# →   "payload": {
# →     "task": "Upgrade CartStore price calculations:\n1. getSubtotal() phải fetch..."
# →   },
# →   "attempts": 0,
# →   "max_attempts": 3,
# →   "last_error": null
# → }

ai-local task read task-2 --workspace D:\2026\viber-coding\pet-store
# → { "payload": { "task": "Phát hiện và fix bugs trong CartStore:\n\nPROBLEM:\n..."} }
```

### **Bước 7: Worker Execution**

```powershell
# Worker once
ai-local worker run --once --workspace D:\2026\viber-coding\pet-store
# → WORKER once PASS processed=1 job_id=task-1

ai-local worker run --once --workspace D:\2026\viber-coding\pet-store
# → WORKER once PASS processed=1 job_id=task-2

# Verify tasks completed
ai-local task list --workspace D:\2026\viber-coding\pet-store
# → task-1 succeeded demo
# → task-2 succeeded demo
```

**⚠️ Issue #6**: Worker marks succeeded nhưng **không modify code** — chỉ enqueue → claim → succeeded. Chưa có logic thực sự execute task.

### **Bước 8: Daemon Loop**

```powershell
# Run daemon (background loop)
ai-local daemon run --loop --poll-interval 0.5 --workspace D:\2026\viber-coding\pet-store
# → DAEMON run mode=loop poll_interval=0.5 max_iterations=None
# → WORKER loop iteration=1 status=skipped processed=0 reason="no pending job"
# → WORKER loop iteration=2 status=skipped processed=0 reason="no pending job"
# → ... (1100 iterations total until Ctrl+C)
```

### **Bước 9: Runtime Status**

```powershell
ai-local runtime status --workspace D:\2026\viber-coding\pet-store
# → RUNTIME status=ok
# → TASKS total=2 pending=0 done=2 cancelled=0
# → WORKER last_status=pass processed=1 job_id=task-2
# → DAEMON status=stopped stale=none pid=32516 iterations=1100 stop_reason=keyboard_interrupt
# → PATHS logs_dir=D:\2026\viber-coding\pet-store\.ai-local\logs
```

### **Bước 10: Gates (❌ Only `run` available)**

```powershell
# All these fail — commands không tồn tại trong main CLI:
ai-local gate promote --max-level level3 --tools-config ... --gates-config ...
# → No such command 'promote'.

ai-local gate project_retrieval --query "cart store validation patterns" ...
# → No such command 'project_retrieval'.

ai-local gate patch_levels --config ...
# → No such command 'patch_levels'.

ai-local gate memory_regression --max-level level2 --config ...
# → No such command 'memory_regression'.

# Only this works:
ai-local gate run level1 --workspace D:\2026\viber-coding\pet-store
# → GATE run level=level1 workspace=D:\2026\viber-coding\pet-store
ai-local gate run level2 --workspace D:\2026\viber-coding\pet-store
# → GATE run level=level2 workspace=D:\2026\viber-coding\pet-store
```

**❌ Issue #5**: Gates advanced (`promote`, `project_retrieval`, `patch_levels`, v.v.) chỉ nằm trong old CLI `ai_local/cli.py` không được expose qua `ai-local` command.

### **Bước 11: Knowledge not updated after worker run**

```powershell
ai-local knowledge search "cart store fix proposal" --workspace D:\2026\viber-coding\pet-store
# → 1 note note CartStore xử lý logic add item với validation shopId: ...
# → 2 note note Price calculation trong CartStore cần fix: ...
# → 3 note note Zustand auth store với persistence: ...
# → 4 note note Zustand auth store với persistence: ...

ai-local knowledge search "cart store" --workspace D:\2026\viber-coding\pet-store
# → Same 4 notes (no change after worker)
```

### **Bước 12: Runtime Snapshot**

```powershell
ai-local runtime snapshot --workspace D:\2026\viber-coding\pet-store
# → RUNTIME status=ok
# → TASKS total=2 pending=0 done=2 cancelled=0
# → WORKER last_status=none processed=0 job_id=none
# → DAEMON status=stopped stale=none pid=32516 iterations=1100 stop_reason=keyboard_interrupt
# → PATHS logs_dir=D:\2026\viber-coding\pet-store\.ai-local\logs reports_dir=D:\2026\viber-coding\pet-store\.ai-local\reports
```

---

## 🚀 Revised: Corrected PowerShell Syntax

**⚠️ Important**: PowerShell không dùng `\` cho line continuation — dùng backtick `` ` ``:

```powershell
# ❌ Sai — Will cause parse error
ai-local ask "Some question" \
  --workspace D:\...

# ✅ Đúng
ai-local ask "Some question" `
  --workspace D:\..
```

---

### **Bước 1: Context Preparation (Quan trọng nhất!)**

Bất kỳ agent sẽ hỏi/sửa gì trong project, agent cần "hiểu" project trước.

```powershell
# 1. Init workspace cho pet-store
ai-local init --workspace D:\2026\viber-coding\pet-store

# 2. Scan project và build index
ai-local index scan --root D:\2026\viber-coding\pet-store --workspace D:\2026\viber-coding\pet-store

# 3. Check results
ai-local index stats --workspace D:\2026\viber-coding\pet-store
```

**Mong đợi kết quả**:
```
INDEX_STATS files=XX chunks=XXX symbols=XXXX
```

---

### **Bước 2: Add Knowledge Notes (Context enriching)**

Thêm các knowledge notes về project architecture để agent hiểu rõ hơn:

```bash
# Add note về cart store logic
ai-local knowledge add-note "CartStore xử lý logic add item với validation shopId:
- Nếu thêm item từ shop khác → clear cart và add mới item
- Nếu item đã tồn tại → increment quantity
- persist vào localStorage và zustand integration" --tag "cart,logic,validation"

# Add note về price calculation
ai-local knowledge add-note "Price calculation trong CartStore cần fix:
- getSubtotal() chỉ hiển thị, final price phải từ server
- thiếu logic apply discount/promotion
- thiếu validation tax calculation" --tag "cart,price,bug"

# Add note về auth store
ai-local knowledge add-note "Zustand auth store với persistence:
- persist với localStorage
- partialize chỉ lưu user và isAuthenticated
- onRehydrateStorage helper" --tag "auth,zustand,persistence"

# Hiện số lượng knowledge
ai-local knowledge list
```

---

### **Bước 3: Ask - Verify Knowledge Retrieval (Before/After)**

Test xem index và knowledge retrieval có hoạt động không:

#### **Scenario 1: Viết câu hỏi trước khi có knowledge**

```bash
ai-local ask "Tôi cần hiểu logic của Cart store, đặc biệt là validate shopId khi add item" \
  --workspace D:\2026\viber-coding\pet-store \
  --show-evidence
```

**Kết quả mong đợi**:
```
DECISION: enough_context
QUESTION: Tôi cần hiểu logic của Cart store, đặc biệt là validate shopId khi add item
ANSWER_DRAFT: Based on knowledge note: [văn bản từ knowledge note bạn vừa add]
EVIDENCE: knowledge_id=XXX title="cart,logic,validation"

REPORT: D:\2026\viber-coding\pet-store\.ai-local\reports\ask-XXXXX.json
```

#### **Scenario 2: Viết câu hỏi nâng cao (phải đọc code)**

```bash
ai-local ask "Trong cart store, tại sao getSubtotal() chỉ hiển thị và không fetch từ server?
Nêu các case bug tiềm ẩn và đề xuất fix" \
  --workspace D:\2026\viber-coding\pet-store \
  --show-evidence
```

**Kết quả mong đợi**:
- Agent sẽ search trong index để tìm file `cart.store.ts`
- Agent sẽ search trong knowledge để tìm notes
- Agent sẽ read code và trả lời chi tiết

---

### **Bước 4: Task Submission - Đưa request cho Agent**

#### **Lựa chọn 1: Task đơn giản (quick fix)**

```bash
ai-local task submit "Upgrade CartStore price calculations:
1. getSubtotal() phải fetch final prices from mock API instead of using local product.price
2. Add discount logic (5% discount cho orders > $100)
3. Add tax calculation (10% VAT)
4. Update CartItem component để hiển thị calculated values
5. Test với edge cases: empty cart, mixed currency, etc." --workspace D:\2026\viber-coding\pet-store
```

#### **Lựa chọn 2: Task phức tạp (full pipeline)**

```bash
ai-local task submit "Phát hiện và fix bugs trong CartStore:

PROBLEM:
- getSubtotal() dùng local product.price thay vì server price → giá sai
- Thiếu validation: quantity > stock của product
- Thiếu validation: shopId phải tồn tại trước khi add item
- Cart không reset khi checkout failed

REQUIREMENTS:
1. Complete endpoint integration: prices phải fetch từ mock API
2. Validation layer với reusable validation function
3. Error handling với user-friendly messages
4. Saga/transaction pattern cho multi-step flow
5. Unit tests cho từng fix
6. Update knowledge notes về issue và fix

DELIVERABLES:
- code fixes trong src/store/cart.store.ts
- unit tests trong tests/
- kèm changelog.md
- kèm knowledge notes về learned pattern
"  --workspace D:\2026\viber-coding\pet-store
```

---

### **Bước 5: Task Checking - Kiểm tra task trong queue**

```bash
# Liệt kê tất cả tasks
ai-local task list --workspace D:\2026\viber-coding\pet-store

# Đọc detail task
ai-local task read <task_id> --workspace D:\2026\viber-coding\pet-store
```

**Task sau khi submit**:
```
task-1 PENDING demo "Upgrade CartStore price calculations..."
```

---

### **Bước 6: Run Pipeline Agent Execution**

> **NOTE**: Tính năng này cần agent worker được cấu hình đúng rồi chạy.

#### **Lựa chọn 1: Chạy worker một lần**

```bash
ai-local worker run --once --workspace D:\2026\viber-coding\pet-store
```

**Mong đợi output**:
```
WORKER once PASS processed=1 job_id=task-1
```

#### **Lựa chọn 2: Chạy daemon loop (background)**

```bash
# Start daemon
ai-local daemon run --loop --poll-interval 0.5 \
  --workspace D:\2026\viber-coding\pet-store

# Chờ 30-60s, rồi kill với Ctrl+C
```

**Dưới daemon, agent sẽ**:
1. Read task từ queue
2. Understand task (Ask with index + knowledge)
3. Plan execution (Chain of thought)
4. Execute fix (Read code, modify files)
5. Run tests (pytest)
6. Generate knowledge notes (learn patterns)
7. Submit artifacts (changelog, added files)
8. Update task status
9. Log everything trong `ai-local/.ai-local/logs/daemon.log`

---

### **Bước 7: Validate với Gates**

Sau khi agent hoàn thành task, hãy validate với gates:

#### **Scenario 1: Venture Gate (ước tính, không chạy đầy đủ)**

```bash
# Dry-run để xem đường đi
ai-local gate promote --max-level level3 \
  --tools-config D:\2026\viber-coding\pet-store\.ai-local\.ai-local\configs\tools.yaml \
  --gates-config D:\2026\viber-coding\pet-store\.ai-local\.ai-local\configs\gates.yaml \
  --workspace D:\2026\viber-coding\pet-store
```

#### **Scenario 2: Semantic Clone Gate (Verify mutation)**

```bash
# Check xem code có bị change sai pattern
ai-local gate project_retrieval --query "cart store validation patterns" \
  --root D:\2026\viber-coding\pet-store \
  --workspace D:\2026\viber-coding\pet-store
```

**Mong đợi output**:
```
INDEX indexed=XX unchanged=XX
RETRIEVE decision=PASS hits=3
EVIDENCE cart.store.ts:line32 [validation logic snapshot]
```

---

### **Bước 8: User Approval Workflow**

#### **Lựa chọn 1: Auto-approved workflow (demo mode)**

Trong demo, nếu không cần human-in-the-loop, bỏ qua bước này.

#### **Lựa chọn 2: Human-in-the-loop workflow (production)**

Agent nên:
1. Generate proposal (draft fix suggestions)
2. Ask user approval: "Fields có modify được không?"
3. User confirm → Agent commit changes
4. System validate qua gates
5. User final sign-off

**Command để user review**:
```bash
# Xem runtime status
ai-local runtime status --workspace D:\2026\viber-coding\pet-store

# Xem last worker result
# (file: .ai-local/.ai-local/reports/last-worker-result.json)

# Xem artifact mà agent submit
ai-local knowledge search "cart store fix proposal" --workspace D:\2026\viber-coding\pet-store

# Review diff
git -C D:\2026\viber-coding\pet-store diff
```

**User approval flow**:
```bash
# User check diff
git -C D:\2026\viber-coding\pet-store diff --cached
git -C D:\2026\viber-coding\pet-store diff

# User approve (theo prompt của agent)
# Agent commit tự động hoặc user phải manually commit

# User sign-off
ai-local knowledge add-note "Task cart-store-price-upgrade approved by user.
Fixes: price calculation, tax, discount.
Gates: passed level2.
Status: production-ready." --tag "approval,signed-off"
```

---

### **Bước 9: System Validation (Gates & Quality Checks)**

#### **Git-based Gates**

```bash
# Check diff size
ai-local gate patch_levels \
  --config D:\2026\viber-coding\pet-store\.ai-local\.ai-local\configs\patch_levels.yaml \
  --workspace D:\2026\viber-coding\pet-store

# Mong đợi:
# PASS level1 files=5 lines=50 hop=3 risk=C
# PASS level2 files=3 lines=40 hop=2 risk=B
# PASS level3 files=1 lines=30 hop=1 risk=A
```

#### **Functional Gates**

```bash
# Check memory regression (no regression trong knowledge store)
ai-local gate memory_regression --max-level level2 \
  --config D:\2026\viber-coding\pet-store\.ai-local\.ai-local\configs\memory_regression_gates.yaml

# Check knowledge gates (knowledge changes hợp lệ không)
ai-local gate knowledge --max-level level2 \
  --config D:\2026\viber-coding\pet-store\.ai-local\.ai-local\configs\knowledge_gates.yaml
```

---

### **Bước 10: Knowledge Clean-up & Reporting**

#### **Clean-up knowledge duplicates**

```bash
ai-local knowledge search "cart store" --workspace D:\2026\viber-coding\pet-store

# Nếu có nhiều notes giống nhau, remove rác
ai-local knowledge cleanup
```

#### **Xem report cuối**

```bash
# Take snapshot final
ai-local runtime snapshot --workspace D:\2026\viber-coding\pet-store

# Xem summary
cat D:\2026\viber-coding\pet-store\.ai-local\.ai-local\reports\runtime-snapshot.json
```

---

## 📊 End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CONTEXT PREP (Bước 1-2)                                    │
│    • Init workspace                                          │
│    • Build index                                             │
│    • Add knowledge notes                                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 2. KNOWLEDGE RETRIEVAL (Bước 3)                              │
│    • Ask question → retrieve index + knowledge               │
│    • Verify retrieval quality                               │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 3. TASK SUBMISSION (Bước 4)                                  │
│    • Submit task với detail problem + requirements          │
│    • Task enqueued ke trong system                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 4. WORKER EXECUTION (Bước 6)                                 │
│    • Worker reads task                                      │
│    • Agent plans execution (CoT)                            │
│    • Agent reads code + searches index                      │
│    • Agent writes fixes                                      │
│    • Agent runs tests                                        │
│    • Agent adds knowledge notes (learn patterns)            │
│    • Agent submits artifacts (changelog, tests)             │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 5. KERNEL/GATE VALIDATION (Bước 7-9)                         │
│    • Semantic Clone Gate → verify mutations                 │
│    • Patch Levels Gate → check diff size                    │
│    • Memory Regression Gate → verify no regression          │
│    • Knowledge Gates → verify knowledge changes              │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 6. USER APPROVAL & SIGN-OFF (Bước 8)                         │
│    • Review artifacts                                        │
│    • Review diff                                            │
│    • Verify gateway results                                  │
│    • User approve                                            │
│    • User sign-off (knowledge note)                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 7. FINAL REPORT & CLEANUP (Bước 10)                          │
│    • Take final snapshot                                     │
│    • Generate summary                                         │
│    • Clean knowledge duplicates                              │
│    • Verify full pipeline success                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Example Output - Quan sát được gì?

Sau khi chạy xong Bước 6-10 với pet store workflow, bạn sẽ thấy:

### **1. Knowledge artifacts**
```
knowledge_id=cart-price-upgrade-2025-06-10
title="Cart Store Price Calculation Upgrade"
kind="note"
tags="cart,price,fix,approved"
```

### **2. Runtime snapshot**
```json
{
  "tasks_total": 1,
  "tasks_pending": 0,
  "tasks_done": 1,
  "tasks_cancelled": 0,
  "last_worker_result": {
    "job_id": "task-1",
    "status": "succeeded",
    "artifact_path": "C:\\reports\\agent-cart-fix.md"
  },
  "daemon_status": "running",
  "daemon_iterations": 3
}
```

### **3. Gate validation results**
```
PASS level1 files=5 lines=50 hop=3 risk=C
PASS level2 files=3 lines=40 hop=2 risk=B
PASS memory_regression level2 checks=30
PASS knowledge level2 checks=25
```

### **4. Knowledge note (user sign-off)**
```
knowledge added id=cart-fix-signed-off
title="Cart Store Price Upgrade - Production Ready"
tags="approved,signed-off,gate-passed,deployed"
```

### **5. Git commit log**
```
commit 7a3f4e2 "feat(cart): Complete price calculation upgrade with tax & discount"
Author: AI Local Agent
Date: 2026-06-10 14:23:45
```

---

## ⚠️ Common Pitfalls & Solutions

### **Issue 1: Index regeneration loops**

**Symptom**:
```bash
ai-local index scan
# → INDEX indexed=50 unchanged=5
# → Sau đó git clean → lại scan 50 files
```

**Solution**:
```bash
# Remove changed files trước khi scan để khỏi redo indexing
git -C <workspace> clean -fd

# Scan lagi
ai-local index scan

# Chỉ scan khi có chưa indexed files
```

### **Issue 2: Worker không chạy được**

**Symptom**:
```bash
ai-local worker run --once
# → WORKER once SKIP processed=0 reason="no valid tasks found"
```

**Solution**:
```bash
# Tạo task test
ai-local task submit "Test task: Print 'Hello AI Local'" --workspace <workspace>

# Run worker lại
ai-local worker run --once --workspace <workspace>
```

### **Issue 3: Knowledge search trả về kết quả sai**

**Symptom**:
Ask hỏi về cart store nhưng trả về shop store.

**Solution**:
```bash
# Check knowledge với tag filter
ai-local knowledge list

# Nếu knowledge sai, remove
# ai-local knowledge remove <knowledge_id> --workspace <workspace>
```

### **Issue 4: Gate validation too strict**

**Symptom**:
Patch levels gate fail mặc dù changes nhỏ.

**Solution**:
```bash
# Test với dry-run để xem threshold
ai-local gate patch_levels --config <path> --workspace <workspace>

# Nếu fail, adjust patch_levels.yaml:
# - Increase max_files_changed
# - Increase max_changed_lines
# - Increase max_hop_depth (hop = number of levels of nesting)
```

---

## 📈 Success Criteria - Khi nào coi demo thành công?

✅ **Tất cả conversion points đạt được**:

1. ✅ **Knowledge indexing**: Index với ≥50 files và ≥300 chunks
2. ✅ **Knowledge retrieval**: Ask question trả về knowledge từ index + notes
3. ✅ **Task submission**: Task enqueued và visible trong queue
4. ✅ **Worker execution**: Worker chạy và process task successfully
5. ✅ **Artifact submission**: Agent submit changelog, tests, knowledge notes
6. ✅ **Gate validation**: Tất cả gates pass check
7. ✅ **User approval**: User review artifacts và approve (theo workflow bạn chọn)
8. ✅ **Final report**: Runtime snapshot show final state

---

## 🎓 Takeaways - Happy Path vs Sad Path

### **Happy Path (Production-ready)**

```
Step 1-2: Context ✓
Step 3: Knowledge retrieval ✓
Step 4: Task submit ✓
Step 6: Worker execution ✓
Step 7-9: Gate validation ✓
Step 10: Final report ✓

Total time: ~5-10 phút (cho task nhỏ)
```

### **Sad Path (Troubleshooting)**

```
Step 1: Init fails
→ Solution: Create workspace directory manually first

Step 2: Index scan fails ( permission denied )
→ Solution: Run AI Local với admin/same user

Step 3: Knowledge retrieval returns empty
→ Solution: Rebuild index với index rebuild --root

Step 4: Task not enqueued
→ Solution: Check SQLite tasks.db exists
→ Solution: Restart daemon

Step 6: Worker SKIP always
→ Solution: Validate task payload vs Job schema
→ Solution: Enable debug mode trong worker
```

---

## 🔮 Future Improvements - Tăng cường tính năng

1. **Live indexing**: Index auto-regenerate khi file được tạo
2. **Task templates**: Task submission template cho common tasks
3. **Approval middleware**: Approval flow với role-based access control
4. **Pipeline orchestration**: Multi-step pipeline với dependency graph
5. **Artifact registry**: Registry của agent-generated artifacts
6. **Traceability**: Git commit link từ knowledge notes
7. **Diff visualization**: Visual diff của knowledge changes
8. **Rollback**: Rollback to previous state nếu lỗi

---

## 📞 Troubleshooting Quick Reference

| Issue | Command | Expected |
|-------|---------|----------|
| Index kor | `ai-local index rebuild --root` | `INDEX_REBUILD indexed=XX deleted=XX` |
| Knowledge not found | `ai-local knowledge list` | List tất cả knowledge |
| Task not executing | `ai-local task list` | Task visible trong queue |
| Worker stuck | `ai-local runtime status` | Daemon status="running", iterations>0 |
| Gate validation fail | `ai-local gate run level1` | Detailed error output |
| Agent change wrong file | `git -C` check diff | Wrong file trong git diff |

---

**📌 Lưu ý quan trọng**: Demo này hướng dẫn workflow lý tưởng. Trong production, bạn có thể skip các bước (ví dụ: skip gates, skip approval). Việc xác định "approved by user and system" tùy thuộc vào security level của app bạn.

---

**👋 End of Demo Guide**

Nhớ follow theo thứ tự: Bước 1 → 2 → ... → 10 để trải nghiệm full end-to-end workflow của AI Local với project pet store thực tế! 🚀
