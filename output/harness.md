# Campus Customs Database Harness

Source: `data/campus_customs.db` (original, read-only reset copy).
Working copy: `data/campus_customs_new.db` (later problems may modify this one only).

Everything below comes from inspecting the database schema and rows directly. Where a link between tables is inferred rather than stored as a foreign key, it is marked **(inferred)**.

---

## Tables

### `desk`

| Field | Type |
|---|---|
| `date_today` | TEXT, not null |
| `notes` | TEXT |

One row: `date_today = 2026-08-31`, `notes` empty. This is the shop's official "today", so every agent should use it (not the system clock) to judge due dates, overdue invoices and delivery timing.

### `tickets`

| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `type` | TEXT, not null |
| `requester` | TEXT, not null |
| `subject` | TEXT, not null |
| `sku` | TEXT |
| `size` | TEXT |
| `qty` | INTEGER |
| `lease_id` | INTEGER, FK → `leases.id` |
| `invoice_id` | INTEGER, FK → `invoices.id` |
| `status` | TEXT, not null |
| `notes` | TEXT |
| `created_at` | TEXT, not null (ISO timestamp, −04:00) |

The work queue: 3 rows, all `open`. Each ticket names who is asking and what they want. Its `sku`/`size`/`lease_id`/`invoice_id` fields tell the Boss agent which specialist agents and tables are needed to resolve it.

### `inventory`

| Field | Type |
|---|---|
| `sku` | TEXT, not null, part of primary key |
| `name` | TEXT, not null |
| `size` | TEXT, not null, part of primary key |
| `qty` | INTEGER, not null |
| `location` | TEXT, not null |

10 rows: stock on hand for each product and size (`OS` = one size). The Inventory agent uses it to check whether an order can be filled now or needs a restock. Two items are at 0: `CC-TEE-WHITE` size S and `CC-MUG-CREST` OS.

### `pricing`

| Field | Type |
|---|---|
| `sku` | TEXT, primary key |
| `unit_cost` | REAL, not null |
| `list_price` | REAL, not null |

4 rows: cost to the shop and normal selling price for each SKU, not broken down by size. The Accounting agent needs it to judge discounts (how far below `list_price` the shop can go before falling below `unit_cost`) and to estimate restock costs.

### `vendors`

| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `name` | TEXT, not null |
| `specialty` | TEXT, not null |
| `lead_days` | INTEGER, not null |

3 rows: suppliers and how many days each takes to deliver. This is the only source of vendor lead times. The `specialty` field tells agents which vendor fits a product (for example, apparel goes to Bulldog Print Co).

### `leases`

| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `space_name` | TEXT, not null |
| `landlord` | TEXT, not null |
| `monthly_rent` | REAL, not null |
| `next_due` | TEXT, not null |
| `notes` | TEXT |

1 row: the Chapel Street shop lease ($2,400/month, next due 2026-09-02). The Facilities agent uses it to confirm rent notices. Paying rent is a cash outflow, so it needs human approval and a cash balance check.

### `cash_accounts`

| Field | Type |
|---|---|
| `name` | TEXT, primary key |
| `balance` | REAL, not null |
| `date` | TEXT, not null |

1 row: `checking` holds $3,400.00 as of 2026-08-31. This is the only cash the shop has, and there is no revenue table, so it only goes down. Every payment must check it first so the balance can never go negative.

### `payments`

| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `kind` | TEXT, not null |
| `ref_id` | INTEGER |
| `amount` | REAL, not null |
| `account` | TEXT, not null |
| `paid_at` | TEXT, not null |
| `approved_by` | TEXT, not null |

Empty (0 rows). This is the record of approved payments. **(inferred)** `kind` plus `ref_id` say what was paid (for example, an invoice or a lease), and `account` names the `cash_accounts` row debited. `approved_by` is required, which matches the rule that a human must approve every payment.

### `invoices`

| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `vendor_id` | INTEGER, not null, FK → `vendors.id` |
| `amount` | REAL, not null |
| `due_date` | TEXT, not null |
| `status` | TEXT, not null |
| `description` | TEXT |

1 row: invoice 501 from Bulldog Print Co, $840.00, due 2026-08-28, status `open`. That's 3 days overdue as of `desk.date_today`. An open invoice blocks the vendor from shipping new product, so the Accounting agent must track this table.

---

## Table relationships

```
tickets.invoice_id ──► invoices.id
tickets.lease_id   ──► leases.id
invoices.vendor_id ──► vendors.id
tickets.sku        ──► inventory.sku / pricing.sku      (inferred, no FK)
payments.ref_id    ──► invoices.id or leases.id         (inferred, depends on kind)
payments.account   ──► cash_accounts.name               (inferred, no FK)
```

---

## The three open tickets

### Ticket 101: Customer order (Tauhid Zaman)

- **Request:** 1 × `CC-TEE-WHITE` (Classic Bulldog Tee), size S. Linked to `invoice_id = 501`.
- **What the data shows:**
  - `inventory`: `CC-TEE-WHITE` size S has `qty = 0`, so the order can't be filled from stock.
  - `invoices`: invoice 501 is a $840.00 "Rush reprint CC-TEE-WHITE S" from vendor 1. It's `open`, and its due date (2026-08-28) has passed.
  - `vendors`: vendor 1 is Bulldog Print Co (apparel reprint, `lead_days = 5`). Because invoice 501 is open, Bulldog can't ship until it's paid.
  - `pricing`: the tee's `list_price` is $28.00 and `unit_cost` is $8.00.
- **Relevant tables:** `tickets`, `inventory`, `invoices`, `vendors`, `pricing`, `cash_accounts`, `payments`, `desk`.

### Ticket 102: Rent notice (Elm City Properties)

- **Request:** "Email: shop rent due in 2 days." Linked to `lease_id = 1`.
- **What the data shows:**
  - `leases`: lease 1 is the Chapel Street shop, landlord Elm City Properties, $2,400.00/month, `next_due = 2026-09-02`. That's 2 days after `desk.date_today`, which matches the email.
  - `cash_accounts`: checking holds $3,400.00, enough to cover the rent.
- **Relevant tables:** `tickets`, `leases`, `cash_accounts`, `payments`, `desk`.

### Ticket 103: Price override (Yale AI Club)

- **Request:** 20 × `CC-HOOD-NAVY` (Basic Hoodie Big Yale), size M, with a bulk discount.
- **What the data shows:**
  - `inventory`: size M has `qty = 8`, which is 12 short of 20.
  - `pricing`: `list_price` is $58.00 and `unit_cost` is $22.00, so any discount has to stay above $22.00/unit to avoid selling at a loss.
  - `vendors` **(inferred)**: a restock of the remaining 12 would most likely come from Bulldog Print Co (apparel reprint, 5 lead days). That vendor is the same one blocked by open invoice 501.
- **Relevant tables:** `tickets`, `inventory`, `pricing`, `vendors`, `invoices`, `cash_accounts`, `desk`.

### Cross-ticket observations

- **Cash is tight.** Paying invoice 501 ($840) and the rent ($2,400) together uses $3,240 of the $3,400 in checking, leaving $160. **(inferred)** If restocking 12 hoodies costs `unit_cost` × 12 = $264, all three outflows together ($3,504) would exceed the balance. Agents will need to prioritize.
- **Tickets 101 and 103 share a dependency.** Both likely need Bulldog Print Co, which can't ship until invoice 501 is paid.
- **The `payments` table is empty.** No payment has been made yet, so invoice 501 and the 2026-09-02 rent are both still outstanding.

---

## MCP tools

Server: `mcp_server/server.py` (FastMCP). It opens only `data/campus_customs_new.db`, read-only. Each tool takes a `ticket_id`, so the SKU, size, quantity, lease or invoice always comes from the ticket itself rather than from the agent.

### `get_backorder_and_vendor_block_status`

- **Reads:** `tickets`, `inventory`, `invoices`, `vendors`, `desk`
- **Unlocks:** Ticket 101
- **Why:** Tauhid's size S tee has `qty = 0`, and the ticket's own `invoice_id = 501` is an open $840 reprint invoice from Bulldog Print Co. That invoice is 3 days past due, so this tool shows in one call both that the tee is out of stock and that Bulldog (5 lead days) can't ship it until invoice 501 is paid.

### `get_rent_due_and_cash_position`

- **Reads:** `tickets`, `leases`, `cash_accounts`, `desk`
- **Unlocks:** Ticket 102
- **Why:** The landlord's email says rent is due "in 2 days," and this tool confirms it against lease 1 ($2,400.00 due 2026-09-02, exactly 2 days after `desk.date_today`). It also shows that checking ($3,400.00) would drop to $1,000.00, which is the non-negative cash check a human needs before approving the payment.

### `get_bulk_order_stock_and_pricing`

- **Reads:** `tickets`, `inventory`, `pricing`
- **Unlocks:** Ticket 103
- **Why:** The Yale AI Club wants 20 navy hoodies in size M, and this tool shows only 8 are in stock (12 short, with other sizes listed in case they're acceptable). It also returns the $22.00 unit cost against the $58.00 list price, so any bulk discount can be kept above cost (at most $36.00 off per hoodie).

### Design notes

- **No vendor is guessed for ticket 103.** The database has no stored link between a SKU and a vendor, so the third tool doesn't name one. The restock vendor is only known for ticket 101, through its invoice.
- **Stored and computed values are kept apart.** Anything computed from stored values (days overdue, shortfall, totals, `vendor_can_ship`) appears under a `derived` key, separate from the stored rows.
- **The tools are read-only.** Payments, which need human approval, are left for later problems.

---

## Problem 5: The agent team

Code: `backend/` (PydanticAI). Prompts: `backend/prompts/`. Shared types: `backend/models.py`.

Run a ticket with `python -m backend.run --ticket 101`. Run the offline checks (no model calls) with `python -m backend.check_setup`.

Every agent is a PydanticAI `Agent` running `gpt-6-luna` through Portkey (see *Model* below). Each agent returns a structured `AgentReport` and has three things: its own prompt file, an allow-list of MCP tools, and the same `delegate` tool. The agent loop is PydanticAI's model → tool → model cycle, stepped with `Agent.iter()` so every step is written to the audit trail.

### The five agents

| Agent | Role | Responsibilities | MCP tools | Delegates when |
|---|---|---|---|---|
| **Boss** (`boss.md`) | Coordinator and final decision-maker | Reads the ticket, picks the specialists it needs, delegates focused questions, reconciles their reports, writes the final recommendation, and sends anything involving money or customer contact to a human. | `list_open_tickets`, `get_ticket` | On every ticket. It has no specialist tools, so it must delegate stock to Inventory, money to Accounting, the space to Facilities and messages to Customer Service. |
| **Inventory** (`inventory.md`) | Stock and restocking | Checks stock for the exact SKU and size, works out shortfalls, finds restock vendors and `lead_days`, and flags vendors blocked by open invoices. | `get_ticket`, `get_backorder_and_vendor_block_status`, `get_bulk_order_stock_and_pricing`, `list_vendors`, `get_vendor_ship_status` | Asks Accounting whether a restock or the blocking invoice is affordable. Rarely asks Customer Service or Facilities. |
| **Accounting** (`accounting.md`) | Cash, invoices, margins, payments | Reviews balances and open invoices, checks discounts against `unit_cost`, and dry-runs payments and purchase orders. It is the only specialist that writes payment proposals. It refuses anything that would overdraw an account, and every proposal needs human approval. | `get_ticket`, `get_cash_and_obligations`, `check_payment`, `get_vendor_ship_status`, `get_bulk_order_stock_and_pricing` | Asks Inventory for shortfalls, vendors and lead times, and Facilities for lease details. |
| **Facilities** (`facilities.md`) | Lease and shop-space obligations | Confirms the lease behind a rent notice, checks the notice against the stored lease, and counts days until due from `desk.date_today` (never the system clock). Checks that cash covers the rent. | `get_ticket`, `get_rent_due_and_cash_position` | Asks Accounting to prepare the rent payment proposal alongside the shop's other obligations. Asks Customer Service for a landlord acknowledgement draft. |
| **Customer Service** (`customer_service.md`) | Customer-facing drafts | Writes messages for human review only, using confirmed facts only. It never promises unapproved discounts or dates, and keeps internal matters (unpaid invoices, cash) out of messages. | `get_ticket` | Asks Inventory for stock and arrival dates, and Accounting for what price can be offered. |

### How delegation works

- **Full connectivity.** Every agent has the same `delegate(to_agent, task)` tool and can call any of the other four, giving all 20 directed edges. `check_setup` verifies all 20. Specialists can delegate to each other directly, not only through the Boss.
- **Bounded, so loops can't happen:**
  - No self-delegation.
  - No delegating to an agent that is already waiting in the current chain (so A → B → A is impossible).
  - Maximum chain depth is 3.
  - At most 8 hand-offs per ticket run, across the whole team.
  - An identical `(agent, task)` request is answered from cache instead of re-running.
- **Refusals don't crash the run.** A refused or failed delegation comes back to the caller as `{"status": "refused" | "failed", "reason": ...}`, so the agent can carry on with what it has.
- **Every delegation is audited.** The trail records `delegation_start`, `delegation_end`, `delegation_refused`, `delegation_cached` and `delegation_failed`, each with from, to, task and depth.

### Model

- **One model.** `backend/config.py` sets `MODEL_NAME = "gpt-6-luna"`. It is the only model in the backend: there is no env override, no fallback and no second model. All five agents share one model object.
- **Portkey.** The `AsyncOpenAI` client points at `https://api.portkey.ai/v1` with `x-portkey-provider: openai`. `PORTKEY_API_KEY` is read from the environment (after loading `AI-Foundation/.env`) and never hard-coded or logged.
- **Responses API.** The model uses PydanticAI's `OpenAIResponsesModel`. Portkey's `gpt-6-luna` deployment rejects function tools on `/v1/chat/completions` while reasoning is on.

### MCP tools (all 9, after Problem 5)

The server is `mcp_server/server.py`. Every tool is read-only against `data/campus_customs_new.db`. The agents reach it through `backend/mcp_bridge.py`, an MCP client that launches the server exactly as `.mcp.json` defines it. The backend never opens the database.

| Tool | Tables | Need / ticket | Added in |
|---|---|---|---|
| `get_backorder_and_vendor_block_status(ticket_id)` | tickets, inventory, invoices, vendors, desk | 101: tee out of stock; vendor blocked by invoice 501 | Problem 3 |
| `get_rent_due_and_cash_position(ticket_id)` | tickets, leases, cash_accounts, desk | 102: confirm rent amount and due date; cash after rent | Problem 3 |
| `get_bulk_order_stock_and_pricing(ticket_id)` | tickets, inventory, pricing | 103: stock in every size, shortfall, cost vs. list price | Problem 3 |
| `list_open_tickets()` | tickets, desk | Boss reads the work queue (all tickets) | **Problem 5** |
| `get_ticket(ticket_id)` | tickets, desk | Any agent reads the ticket it was handed. Customer Service needs the requester and notes (all tickets). | **Problem 5** |
| `list_vendors()` | vendors, desk | 103: no invoice links a vendor, and no table maps SKU to vendor, so Inventory chooses by `specialty` and `lead_days` | **Problem 5** |
| `get_vendor_ship_status(vendor_id)` | vendors, invoices, desk | 103 (and 101): is the restock vendor blocked by open invoices, and when could stock arrive once unblocked | **Problem 5** |
| `get_cash_and_obligations()` | cash_accounts, invoices, vendors, leases, payments, desk | 101 + 102 + 103 together: $3,400 cash vs. $840 overdue invoice + $2,400 rent + any restock. Accounting has to rank them. | **Problem 5** |
| `check_payment(kind, ref_id \| sku+qty+vendor_id, account, reserved_amount)` | invoices, leases, pricing, vendors, cash_accounts, payments, desk | Dry-run of paying invoice 501 (101), lease 1 rent (102) or a 12-hoodie purchase order (103). Takes the amount from the DB, refuses an overdraft or a blocked vendor, never writes, and always requires human approval. | **Problem 5** |

**Why no write tool yet:** nothing in Problem 5 authorizes executing a payment. `check_payment` reports `executed: false`. When a human-approved payment is executed later, it must insert into `payments` and update `cash_accounts` and the invoice status or lease `next_due`.

### Audit trail: `output/audit_trail.json`

- **Format.** The file is one JSON object, `{"schema", "note", "records": [...]}`.
- **Safe appends.** Each append takes a file lock, re-reads the file, adds one record and atomically replaces the file. History is never truncated, and the file stays valid JSON even if a run crashes. If the file is ever corrupt, the team refuses to run rather than overwrite it.
- **What each record holds.** A record has `seq`, `timestamp`, `run_id`, `ticket_id`, `agent`, `depth`, `step` and `event`, plus whichever of these apply: `task`, `tool_calls` (MCP tool, args, ok, cached, result excerpt), `delegation`, `result`, `requires_human_approval`, `guardrail`, `error` and `usage` (token counts).
- **Events:**
  - Run lifecycle: `run_start`, `run_end`, `run_failed`, `run_rejected`
  - Agent loop: `agent_loop_start`, `loop_step_user_prompt`, `loop_step_model_request`, `loop_step_model_response`, `loop_step_end`, `agent_loop_end`
  - MCP: `mcp_tool_call`
  - Delegation: `delegation_*`
  - Guardrails: `guardrail_rejected_output`, `guardrail_payment_check`, `guardrail_payment_corrected`, `guardrail_loop_limit`
- **Redaction.** The `PORTKEY_API_KEY` value, and any field named like a key, token or secret, is redacted before writing. Long strings are truncated.

### Safety

A real shop letting agents near real customers and real money would want the guardrails below. Each one is enforced in code (file in brackets), not just stated in a prompt.

**Human approval**
- No agent can execute a payment, change a balance, mark an invoice paid or move a lease date. There is no write tool on the MCP server.
- `PaymentProposal.requires_human_approval` is fixed to `True`.
- Any report with a payment, a draft or an approval-required recommendation is forced to `needs_human_approval = true` (`agents._guard_output`).

**Financial safeguards**
- **Amounts come from the database.** Every payment proposal is re-checked through MCP `check_payment` after the model answers. The amount always comes from `invoices`, `leases` or `pricing × qty`, so a model-supplied amount is overwritten and the correction is logged.
- **No overdrafts.** Proposals are checked in priority order with cash reserved cumulatively. Any proposal that would take an account below zero is marked `refused` with reasons. For example: pay invoice 501 ($840), then rent ($2,400), leaves $160, so a 12-hoodie restock ($264) is refused.
- **Blocked vendors.** A purchase order to a vendor with open invoices is refused.
- **Only Accounting** (and the Boss relaying it) may put payments in a report.

**Communication safeguards**
- No tool sends email or contacts anyone.
- `DraftMessage.status` can only be `draft_pending_human_review`.
- Only Customer Service (and the Boss relaying it) may author drafts.
- The Customer Service prompt forbids promising unapproved discounts or dates and forbids exposing internal finances.

**Data integrity**
- **Read-only database.** All shop facts come from `campus_customs_new.db` through MCP, which opens it read-only. The backend has no database code. `campus_customs.db` is never opened.
- **Validated tool inputs.** Inputs are validated by the MCP server (positive ids, enum `kind`, bounded `qty` and strings). A bad call returns an error the agent can correct.
- **Traceable facts.** Every `Fact` must cite an MCP tool the agent actually called successfully in this run, or a teammate it actually delegated to. Otherwise the output is bounced back to the model.
- **Real tickets only.** The ticket must exist in the DB before any model call.
- **Shop date.** `desk.date_today` is returned by every date-related tool and is the only "today" agents are told to use.

**Token and runaway limits**
- **Team-wide usage cap.** One `RunUsage` is shared down every delegation, with `UsageLimits` of 40 model requests, 60 tool calls and 250k total tokens per ticket run.
- **Per-response cap.** `max_tokens` is 4,000 per model response.
- **Loop step cap.** Each agent may take at most 30 loop steps.
- **Delegation caps.** Delegation depth is capped at 3, with at most 8 hand-offs per run.
- **Bounded retries.** Agents get 2 retries for output and argument validation. The client makes 2 HTTP retries with a 90 s timeout. MCP calls time out after 30 s.
- **Caching.** Identical MCP calls and identical delegations within a run are served from cache.
- **Short tasks.** Delegated tasks are capped at 1,500 characters.

**Failures**
- **Errors as data.** MCP errors and timeouts come back to the agent as `{"error": ...}` instead of crashing it.
- **Failed delegations.** A delegation that fails (model error, loop limit) is reported to the caller as `failed`.
- **Usage limits stop the run.** Exceeding a usage limit stops the whole run. Every failure is written to the audit trail before the error surfaces.

**Secrets**
- The key is only read from the environment.
- The MCP server process is launched with a minimal environment (no API keys).
- The audit writer redacts the key value and key-like fields.

---

## Problem 7: Backend routes

Code: `backend/main.py` (FastAPI). Start it with `cd backend && uvicorn main:app --reload --port 8000` (or `uvicorn backend.main:app --port 8000` from `hwv5/`). Interactive docs are at `http://localhost:8000/docs`. CORS allows the React dev servers on `localhost:5173` and `localhost:3000`.

### Routes

GET /api/health — Backend status: the model name (`gpt-6-luna`), the MCP tools available, and any agent runs in progress.
GET /api/tickets — All three tickets from `data/campus_customs_new.db` (via MCP `list_tickets`). Each has its stored status, an `is_open` flag (open vs. resolved), any active run, and its count of pending approvals.
GET /api/tickets/{ticket_id} — One ticket with the same fields (404 if it doesn't exist).
POST /api/tickets/{ticket_id}/run — Runs the Problem 5 Boss + specialist team on one open ticket. Returns 202 with a `run_id` right away (`?wait=true` blocks until the run finishes). Rejects missing tickets (404), resolved tickets (409), a second run on the same ticket (409) and more than 3 runs at once (429). When the run finishes, its payment and purchase proposals become approvals.
GET /api/runs — Runs started by this backend process, newest first, with their status and results (optional `?ticket_id=`).
GET /api/runs/{run_id} — One run: status, the Boss's final report, every specialist report, delegations used, token usage, and the approvals it produced.
GET /api/events — Recent agent events read from `output/audit_trail.json`: which agent acted, what it said or did, which MCP tools it used, delegations, guardrail decisions and errors. Filters: `limit`, `ticket_id`, `run_id`, `agent`, `after_seq` (for polling), `steps=false` (hide low-level loop steps), `raw=true` (include the full record).
GET /api/approvals — The human-approval queue (optional `?status=pending|executed|rejected|refused|void` and `?ticket_id=`).
GET /api/approvals/{approval_id} — One approval (404 if it doesn't exist).
POST /api/approvals/{approval_id}/approve — A human approves a prepared payment or purchase. Body: `approved_by` (a name) and `confirm_amount` (must equal the amount). This is the only route that moves cash: it calls the signed MCP write tool `execute_approved_payment`, which re-checks everything and then updates `payments`, `cash_accounts` and the invoice or lease in one transaction. Returns 409 if the approval isn't pending or the database refuses (overdraft, already paid, vendor blocked), and 422 for a bad body or amount mismatch.
POST /api/approvals/{approval_id}/reject — A human declines a pending approval. Body: `rejected_by`. Nothing in the database changes.
POST /api/tickets/{ticket_id}/resolve — A human marks an open ticket resolved, via the signed MCP write tool `resolve_ticket`. Body: `resolved_by`. Returns 409 if the ticket isn't open or has a run in progress.
GET /api/cash — The current checking balance read live from `cash_accounts` (via MCP `get_cash_and_obligations`), plus every account and `desk.date_today`.
POST /api/reset — Restores `data/campus_customs_new.db` as a byte-for-byte copy of the read-only `data/campus_customs.db`, via the signed MCP write tool `reset_working_database`. It then verifies both the SHA-256 and the SQL dump match and voids any pending approvals. Body: `{"confirm": "RESET"}`. Returns 409 while agent runs are in progress.

FastAPI also serves its built-in docs at GET /docs, GET /redoc and GET /openapi.json.

### How the human-in-the-loop works

- **Agents prepare, humans execute.** Agents can only produce `PaymentProposal`s. After a run, the backend turns each one into an approval in `output/approvals.json`, re-reading the amount (and, for rent, the due date being paid) from the database through MCP `check_payment`. If the same payment is proposed twice, it becomes one approval, and one already pending from an earlier run isn't duplicated. Proposals that fail the check (overdraft, blocked vendor) are stored as `refused` and can't be approved.
- **Only the backend can write.** Four MCP tools were added:
  - `list_tickets` (read)
  - `execute_approved_payment`, `resolve_ticket` and `reset_working_database` (write)

  The write tools only work on the server instance the backend starts. The backend gives that process a random per-run secret and signs every write call with HMAC-SHA256 over the tool name and arguments. No agent's allow-list contains a write tool, and the bridge refuses to hand one out. The server Claude Code starts from `.mcp.json` has no secret, so its write tools always refuse. All database access still happens only inside `mcp_server/server.py`.
- **Duplicates and stale approvals are blocked.** An approval must be `pending`, and approvals are processed one at a time under a lock. Execution checks that:
  - the invoice is still `open`
  - the lease's `next_due` still equals the approved due date
  - the amount still matches what the human confirmed
  - the vendor isn't blocked
  - cash stays ≥ 0

  If any check fails, nothing changes.
- **What a payment changes.**
  - Invoice: a `payments` row, `cash_accounts` debited, and `invoices.status = 'paid'`.
  - Rent: a `payments` row, `cash_accounts` debited, and `leases.next_due` moved forward one month.
  - Purchase order: a `payments` row (`ref_id` = vendor) and `cash_accounts` debited. Inventory isn't increased, because the stock hasn't arrived.

  `paid_at` is `desk.date_today`.
- **Audit.** Every approve, reject, refusal, resolve and reset is appended to `output/audit_trail.json`, never the signature.

### Test record (2026-10-04)

All routes were tested against a live `uvicorn main:app --reload --port 8000`:
- **Reads.** Health, tickets and cash returned live DB values (3 tickets open, checking $3,400). Bad ids returned 404/422.
- **Run route.** It ran the real team on ticket 102: Boss → Facilities → Accounting, then Boss → Accounting, with 15 model requests, ~48k tokens, and the guardrails firing in the audit trail. A duplicate run and a reset during the run both returned 409. The DB was unchanged after the run.
- **Approvals.** The run's two approvals (invoice 501 $840, lease 1 rent $2,400) were approved and rejected through the routes:
  - Paying 501 took checking from $3,400 to $2,560 and set the invoice to `paid`. A second approve returned 409.
  - A test rent approval took checking from $2,560 to $160 and moved `next_due` to 2026-10-02.
  - A $264 purchase order with $160 left was refused at execution (409, nothing changed).
- **Resolve and reset.** Resolve worked once, then returned 409. Reset restored the working DB to the same checksum as the original. The original was never modified.

---

## Problem 8: Backend changes for the dashboard

The dashboard lives in `frontend/` (React + Vite + TypeScript); its design is described in `output/design.md`. It uses only the Problem 7 routes. Two small backend changes were made for it:

- **A finished run resolves its ticket.** When a team run completes successfully, `POST /api/tickets/{ticket_id}/run` (in `_execute_run`) now marks the ticket `resolved` through the signed MCP write tool `resolve_ticket`, with `resolved_by = "agent team (run <id>)"`, and logs a `ticket_resolved` audit event. The backend does this, never an agent. A failed run leaves the ticket `open`, and any payments the team proposed still wait for a human in the approval queue.
- **CORS** now also allows the `vite preview` origins (`localhost:4173`, `127.0.0.1:4173`), alongside the existing dev origins (`5173`, `3000`).

---

## Problem 9: Resolving the tickets end to end

### The run, step by step (2026-10-04, times in UTC)

1. **Reset (audit seq 440, 01:30:32).** `POST /api/reset` restored `data/campus_customs_new.db` byte-for-byte from the original (SHA-256 verified). Checking was **$3,400.00**, tickets 101–103 were `open`, there were no payments, invoice 501 was `open`, and lease 1 was due 2026-09-02.
2. **Discarded attempt (run `70669b1d5296`).** Ticket 101's first run came back with every model reply in a median 0.41 s (vs ~4 s live). Its final report was identical to a Problem 8 test run: Portkey was replaying cached responses for the identical prompts. One fix was made: `backend/config.py` now sends `x-portkey-cache-force-refresh: true` on every model call. The database was reset again (seq 556, 01:33:53; this voided that run's pending approval) and nothing had been paid. Both the discarded run and the reset remain in the audit trail.
3. **Ticket 101 (run `85124044c167`, 01:34:09–01:35:39).** Started from the dashboard's **Start agent team** button.
   - **Agents:** Boss → Inventory and Accounting (same step); Inventory → Accounting; Accounting → Inventory; Boss → Customer Service; Customer Service → Inventory.
   - **MCP calls (16):** `get_ticket`, `get_backorder_and_vendor_block_status`, `get_vendor_ship_status`, `get_cash_and_obligations`, `check_payment`.
   - **Outcome:** resolved, with an $840 invoice-501 payment pending approval.
   - **Approval:** **christy** approved it in the dashboard (seq 672, 01:45:12). Checking went **$3,400.00 → $2,560.00**, and invoice 501 is now `paid`.
4. **Ticket 102 (run `5e8b62537b56`, 01:46:28–01:47:16).**
   - **Agents:** Boss → Facilities; Facilities → Accounting; Boss → Accounting.
   - **MCP calls (9):** `get_ticket`, `get_rent_due_and_cash_position`, `get_cash_and_obligations`, `check_payment`.
   - **Outcome:** resolved, with the $2,400 lease 1 rent pending approval.
   - **Approval:** **christy** approved it (seq 742, 01:49:41). Checking went **$2,560.00 → $160.00**, and lease 1's next_due is now 2026-10-02.
5. **Ticket 103 (run `883a2c0cd609`, 01:53:30–01:54:37).**
   - **Agents:** Boss → Inventory and Accounting (same step); Boss → Customer Service; Customer Service → Inventory and Accounting.
   - **MCP calls (13):** `get_ticket`, `get_bulk_order_stock_and_pricing`, `list_vendors`, `get_vendor_ship_status`, `get_cash_and_obligations`.
   - **Outcome:** resolved, with **no payment or purchase proposed**. The team recommended a manager-approved bulk discount above the $22 unit cost and confirming sourcing for the remaining 12 hoodies. The Boss flagged that Customer Service's draft (10%) conflicts with Accounting's suggestion to the Boss (15%).

### Cash

| | Change | Checking |
|---|---|---|
| Start (after reset) | | $3,400.00 |
| Ticket 101: payment #1, Bulldog Print Co invoice #501 | −$840.00 | $2,560.00 |
| Ticket 102: payment #2, lease #1 rent due 2026-09-02 | −$2,400.00 | $160.00 |
| Ticket 103: no payment or purchase | $0.00 | $160.00 |
| **End: `cash_accounts.checking` in `data/campus_customs_new.db`** | | **$160.00** |

Both payments were approved by a human in the dashboard. No agent executed or approved any payment.

### Deliverables

- `output/desk_tickets.html`: Expected sections unchanged (verified by hash); Actual sections and the Cash tab filled from the run evidence.
- `output/resolved_tickets.json`: per ticket, the status, outcome, each agent's contribution, MCP tools, approvals and cash effect.
- `output/resolved_board.html`: labelled dashboard screenshots for tickets 101, 102 and 103, embedded so it opens by double-click. The source PNGs are in `output/problem9_screenshots/`.
- `output/problem9_evidence/`: the raw API records for each run (run report, events, approvals), saved as each ticket finished.
- `output/audit_trail.json`: 833 records, contiguous sequence numbers, with all 439 earlier records kept.

---

## Harness summary: where each component is documented

| Component | What exists now | Documented in |
|---|---|---|
| **Database** | 9 tables (`desk`, `tickets`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments`, `invoices`). The original `data/campus_customs.db` is never written. All work happens in `data/campus_customs_new.db`. | "Tables", "Table relationships" (top of this file) |
| **MCP server** | `mcp_server/server.py`, 13 tools. **Read:** `get_backorder_and_vendor_block_status`, `get_rent_due_and_cash_position`, `get_bulk_order_stock_and_pricing`, `list_open_tickets`, `get_ticket`, `list_vendors`, `get_vendor_ship_status`, `get_cash_and_obligations`, `check_payment` (dry run), `list_tickets`. **Backend-only signed writes:** `execute_approved_payment`, `resolve_ticket`, `reset_working_database`. | "MCP tools" (Problems 3–4), "MCP tools (all 9, after Problem 5)", Problem 7 "How the human-in-the-loop works", `mcp_server/README.md` |
| **Five agents** | Boss, Inventory, Accounting, Facilities, Customer Service. They are PydanticAI agents on `gpt-6-luna` via Portkey (Responses API, cache force-refresh), with a prompt each in `backend/prompts/`. Any agent can delegate to any other, with bounds (no self-delegation or loops back up the chain, depth ≤ 3, ≤ 8 hand-offs per run). | "Problem 5: The agent team" |
| **API routes** | `backend/main.py`, 14 routes. Tickets, run the team, runs, events, approvals (list, approve, reject), resolve, cash and reset. A finished run marks its ticket resolved. | "Problem 7: Backend routes", "Problem 8: Backend changes for the dashboard" |
| **React dashboard** | `frontend/` (React + Vite + TypeScript) on http://localhost:5173. It shows tickets, the live agent roster and feed, approvals with an Approve button, and the cash card. | "Problem 8", `output/design.md` |
| **Safety and human approval** | Agents can only propose payments. Every proposal is re-checked against the DB through `check_payment`. Only the human Approve route executes a payment, as a signed MCP write that re-checks everything and refuses overdrafts, stale or duplicate approvals, and blocked vendors. Messages stay drafts. Facts must trace to MCP calls. Token, loop and retry limits apply, and nothing secret is logged. | "Safety" (Problem 5), Problem 7 human-in-the-loop, Problem 9 cash above |
| **End-to-end run** | Reset, then 101, 102 and 103, with two human approvals. $3,400.00 → $160.00, all three tickets resolved. | "Problem 9" (above) |
