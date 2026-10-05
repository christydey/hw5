# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that is the shop-data layer for the Campus Customs agents. Claude Code connects to it through `.mcp.json`, and the PydanticAI agent team in `backend/` connects to it as an MCP client using that same `.mcp.json` entry. Nothing else reads the shop database.

## Database

The server works only on the working copy, `data/campus_customs_new.db`. Read tools open it read-only; the three backend write tools below are the only code that changes it. The original, `data/campus_customs.db`, is never written: `reset_working_database` only reads it, to copy it over the working file.

Tools return values exactly as stored in the database. Any simple arithmetic on those values (days overdue, shortfall, totals, balance after a payment) appears under a separate `derived` key. If a row is missing, the tool returns `None` or an `error` message instead of guessing. Inputs are validated (positive ids, a fixed set of payment kinds, bounded quantities), and invalid calls return a validation error.

## Tools

The server has thirteen tools: ten read-only tools and three backend-only write tools.

### Ticket tools (Problems 3–4)

These take a `ticket_id` and read the SKU, size, quantity, lease or invoice from the ticket itself.

| Tool | Ticket | What it does |
|---|---|---|
| `get_backorder_and_vendor_block_status(ticket_id)` | 101 | Returns stock for the ticket's SKU/size, the linked invoice, that invoice's vendor and lead time, and all of the vendor's open invoices. Also reports whether the vendor can ship (it can't while any invoice is open). |
| `get_rent_due_and_cash_position(ticket_id)` | 102 | Returns the lease the ticket points to, days until rent is due (based on `desk.date_today`), each cash account's balance, and the balance left after paying the rent. |
| `get_bulk_order_stock_and_pricing(ticket_id)` | 103 | Returns stock for the SKU in every size, the shortfall for the requested size, and the stored unit cost and list price. Also reports totals and the largest per-unit discount before selling at a loss. |

### Team tools (Problem 5)

| Tool | What it does |
|---|---|
| `list_open_tickets()` | Returns every ticket with status `open` plus `desk.date_today`, so the Boss can see the queue. |
| `get_ticket(ticket_id)` | Returns one ticket exactly as stored plus `desk.date_today`, so any agent can read the ticket it was handed. |
| `list_vendors()` | Returns every vendor with its specialty and `lead_days`. The database has no SKU-to-vendor link, so this is how a restock vendor is chosen when no invoice names one (ticket 103). |
| `get_vendor_ship_status(vendor_id)` | Returns one vendor's open invoices, days overdue, whether it can ship, and the earliest arrival date if it could ship today. |
| `get_cash_and_obligations()` | Returns every cash account, every open invoice (with vendor and days overdue), every lease's next rent, recorded payments, and what cash would be left after paying all of them. |
| `check_payment(kind, ref_id?, sku?, qty?, vendor_id?, account="checking", reserved_amount=0)` | **Dry run, never writes.** Checks a proposed `invoice`, `lease_rent` or `purchase_order` payment. The amount always comes from the database (`invoices.amount`, `leases.monthly_rent`, or `pricing.unit_cost × qty`). It refuses if the account would go negative (after `reserved_amount` for other planned payments), if the invoice isn't open, or if the purchase-order vendor is blocked by open invoices. Always returns `requires_human_approval: true` and `executed: false`. |

### Backend tools (Problem 7)

| Tool | What it does |
|---|---|
| `list_tickets()` | Read-only. Returns every ticket, open and resolved, with its status, plus `desk.date_today`. Backs `GET /api/tickets`. |
| `execute_approved_payment(approval_id, approved_by, kind, expected_amount, account, ref_id?, sku?, qty?, vendor_id?, expected_next_due?, authorization)` | **Write.** Carries out a payment a human approved, in one transaction. It first re-checks that the amount still matches, the invoice is open, the lease's due date hasn't already been paid, the vendor isn't blocked, and cash stays ≥ 0. Then it inserts the `payments` row, debits `cash_accounts`, and marks the invoice `paid` or moves `leases.next_due` forward one month. If any check fails, nothing changes. |
| `resolve_ticket(ticket_id, resolved_by, authorization)` | **Write.** Sets an open ticket's status to `resolved`. |
| `reset_working_database(authorization)` | **Write.** Replaces the working database with a byte-for-byte copy of the original (temp file, then an atomic rename). Then confirms the SHA-256 and SQL dump match. |

**Who can call the write tools.** Only the FastAPI backend (`backend/main.py`), from its human-approval, resolve and reset routes.
- The backend starts this server with a random per-process secret in `CAMPUS_CUSTOMS_ADMIN_SECRET`, and signs each write call with HMAC-SHA256 over the tool name and arguments (the `authorization` argument).
- Without that secret, every write tool refuses. That covers the instance Claude Code starts from `.mcp.json` and any agent-only CLI run.
- No agent has a write tool on its allow-list, and `backend/mcp_bridge.py` refuses to give one out.

## Running

```bash
pip install -r mcp_server/requirements.txt
python mcp_server/server.py   # starts the server over stdio
```
