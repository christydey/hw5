"""Campus Customs MCP server.

The shop-data layer for the Campus Customs agent team. Every tool is
read-only and reads the working database (data/campus_customs_new.db).

Ticket tools (Problems 3-4):
- get_backorder_and_vendor_block_status -> ticket 101 (out-of-stock tee + open invoice)
- get_rent_due_and_cash_position        -> ticket 102 (rent notice)
- get_bulk_order_stock_and_pricing      -> ticket 103 (bulk hoodie discount)

Team tools (Problem 5):
- list_open_tickets        -> Boss reads the work queue
- get_ticket               -> any agent reads the ticket it was handed
- list_vendors             -> Inventory picks a restock vendor (103 has no linked vendor)
- get_vendor_ship_status   -> is a given vendor blocked by open invoices (101, 103)
- get_cash_and_obligations -> Accounting's cross-ticket view of cash vs. what is owed
- check_payment            -> dry-run of a proposed payment; never writes

Backend tools (Problem 7):
- list_tickets             -> every ticket with its open/resolved status
- execute_approved_payment -> WRITE: carry out a payment a human approved
- resolve_ticket           -> WRITE: a human marks a ticket resolved
- reset_working_database   -> WRITE: restore the working copy from the original

The three WRITE tools only work when this server was started by the
Campus Customs backend, which puts a per-process secret in
CAMPUS_CUSTOMS_ADMIN_SECRET and signs every write call with it (HMAC over
the tool name and arguments). No agent has these tools on its allow-list,
and the instance Claude Code starts from .mcp.json has no secret, so for
those callers the write tools always refuse.

Every value returned comes from the database. Simple arithmetic on those
values (days overdue, shortfall, totals) is kept under a separate "derived"
key so it is never confused with stored data. Missing rows come back as None
or an "error" message rather than a guess.
"""

import calendar
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

TicketId = Annotated[int, Field(ge=1, description="A tickets.id value, e.g. 101.")]
VendorId = Annotated[int, Field(ge=1, description="A vendors.id value.")]

# Always the working copy. The original campus_customs.db is the reset copy
# and must never be opened by this server.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"
# Only ever opened read-only, as the source for reset_working_database.
ORIGINAL_DB_PATH = DB_PATH.with_name("campus_customs.db")
ADMIN_SECRET_ENV = "CAMPUS_CUSTOMS_ADMIN_SECRET"

mcp = FastMCP("campus-customs")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    # mode=ro: these tools only read, and SQLite will not create an empty file
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _date_today(conn: sqlite3.Connection) -> str | None:
    desk = _row(conn, "SELECT date_today FROM desk LIMIT 1")
    return desk["date_today"] if desk else None


def _days_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


@mcp.tool
def get_backorder_and_vendor_block_status(ticket_id: int) -> dict:
    """For a customer order ticket (e.g. 101): check whether the requested
    SKU/size is in stock and whether the vendor on the ticket's linked invoice
    is blocked from shipping because it still has open (unpaid) invoices.

    Reads tickets, inventory, invoices, vendors and desk.
    """
    with closing(_connect()) as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id}."}
        if not ticket["sku"] or not ticket["size"]:
            return {"error": f"Ticket {ticket_id} has no sku/size, so it is not an order ticket."}

        date_today = _date_today(conn)
        stock = _row(
            conn,
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        )

        invoice = vendor = None
        vendor_open_invoices: list[dict] = []
        if ticket["invoice_id"] is not None:
            invoice = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
        if invoice is not None:
            vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],))
            vendor_open_invoices = _rows(
                conn,
                "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
                (invoice["vendor_id"],),
            )

    derived: dict = {}
    if stock is not None:
        derived["shortfall"] = max((ticket["qty"] or 0) - stock["qty"], 0)
    if invoice is not None:
        derived["linked_invoice_days_overdue"] = max(
            _days_between(invoice["due_date"], date_today) or 0, 0
        )
        derived["vendor_open_invoice_total"] = sum(i["amount"] for i in vendor_open_invoices)
        # A vendor cannot ship new product while it has an open unpaid invoice.
        derived["vendor_can_ship"] = len(vendor_open_invoices) == 0

    return {
        "date_today": date_today,
        "ticket": ticket,
        "stock": stock,  # None if this sku/size is not in inventory
        "linked_invoice": invoice,  # None if the ticket has no invoice_id
        "vendor": vendor,  # None if there is no linked invoice; never guessed from sku
        "vendor_open_invoices": vendor_open_invoices,
        "derived": derived,
    }


@mcp.tool
def get_rent_due_and_cash_position(ticket_id: int) -> dict:
    """For a rent notice ticket (e.g. 102): look up the lease the ticket points
    to, when rent is next due relative to the shop's date, and how much cash
    each account holds before and after paying that rent.

    Reads tickets, leases, cash_accounts and desk.
    """
    with closing(_connect()) as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id}."}
        if ticket["lease_id"] is None:
            return {"error": f"Ticket {ticket_id} has no lease_id, so it is not a rent ticket."}

        date_today = _date_today(conn)
        lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        if lease is None:
            return {"error": f"Lease {ticket['lease_id']} on ticket {ticket_id} does not exist."}
        accounts = _rows(conn, "SELECT name, balance, date FROM cash_accounts ORDER BY name")

    return {
        "date_today": date_today,
        "ticket": ticket,
        "lease": lease,
        "cash_accounts": accounts,
        "derived": {
            "days_until_due": _days_between(date_today, lease["next_due"]),
            # Cash only goes out, so a negative value here means the account cannot cover rent.
            "balance_after_rent": {
                a["name"]: a["balance"] - lease["monthly_rent"] for a in accounts
            },
        },
    }


@mcp.tool
def get_bulk_order_stock_and_pricing(ticket_id: int) -> dict:
    """For a bulk/price-override ticket (e.g. 103): compare the requested
    quantity with stock for that SKU (requested size and all other sizes) and
    return the stored unit cost and list price, so any discount can be checked
    against cost.

    Reads tickets, inventory and pricing.
    """
    with closing(_connect()) as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id}."}
        if not ticket["sku"] or not ticket["size"] or ticket["qty"] is None:
            return {"error": f"Ticket {ticket_id} is missing sku, size or qty."}

        stock_by_size = _rows(
            conn,
            "SELECT size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid",
            (ticket["sku"],),
        )
        pricing = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))

    requested_qty = ticket["qty"]
    on_hand = next((s["qty"] for s in stock_by_size if s["size"] == ticket["size"]), None)

    derived: dict = {}
    if on_hand is not None:
        derived["requested_size_on_hand"] = on_hand
        derived["shortfall"] = max(requested_qty - on_hand, 0)
    if pricing is not None:
        derived["list_total"] = pricing["list_price"] * requested_qty
        derived["cost_total"] = pricing["unit_cost"] * requested_qty
        # Any discounted unit price at or below unit_cost sells at a loss.
        derived["max_discount_per_unit_before_loss"] = pricing["list_price"] - pricing["unit_cost"]

    return {
        "ticket": ticket,
        "stock_by_size": stock_by_size,  # empty if the sku is not in inventory
        "pricing": pricing,  # None if the sku has no pricing row
        "derived": derived,
    }


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket whose status is 'open', plus the shop's date
    (desk.date_today). The Boss uses this to see the work queue.

    Reads tickets and desk.
    """
    with closing(_connect()) as conn:
        return {
            "date_today": _date_today(conn),
            "open_tickets": _rows(conn, "SELECT * FROM tickets WHERE status = 'open' ORDER BY id"),
        }


@mcp.tool
def get_ticket(ticket_id: TicketId) -> dict:
    """Return one ticket exactly as stored, plus the shop's date
    (desk.date_today). Any agent can use this to read the ticket it was
    handed (requester, sku/size/qty, lease_id, invoice_id, notes).

    Reads tickets and desk.
    """
    with closing(_connect()) as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id}."}
        return {"date_today": _date_today(conn), "ticket": ticket}


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty and lead time (lead_days), plus the
    shop's date. The database stores no SKU-to-vendor link, so a restock
    vendor for a ticket without an invoice (e.g. 103) has to be chosen from
    `specialty`; say so when you rely on it.

    Reads vendors and desk.
    """
    with closing(_connect()) as conn:
        return {
            "date_today": _date_today(conn),
            "vendors": _rows(conn, "SELECT * FROM vendors ORDER BY id"),
        }


@mcp.tool
def get_vendor_ship_status(vendor_id: VendorId) -> dict:
    """For one vendor: its lead time, every open (unpaid) invoice it has, and
    whether it can ship new product. A vendor will not ship while it has any
    open invoice. Also gives the earliest arrival date if an order were
    placed today and the vendor could ship.

    Reads vendors, invoices and desk.
    """
    with closing(_connect()) as conn:
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return {"error": f"No vendor with id {vendor_id}."}
        date_today = _date_today(conn)
        open_invoices = _rows(
            conn,
            "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
            (vendor_id,),
        )

    can_ship = len(open_invoices) == 0
    derived: dict = {
        "can_ship": can_ship,
        "open_invoice_total": sum(i["amount"] for i in open_invoices),
        "open_invoice_days_overdue": {
            str(i["id"]): max(_days_between(i["due_date"], date_today) or 0, 0)
            for i in open_invoices
        },
    }
    if date_today:
        arrival = date.fromordinal(date.fromisoformat(date_today).toordinal() + vendor["lead_days"])
        # Only meaningful once the vendor is unblocked; ordering today while blocked ships nothing.
        derived["arrival_if_ordered_today_and_unblocked"] = arrival.isoformat()

    return {
        "date_today": date_today,
        "vendor": vendor,
        "open_invoices": open_invoices,
        "derived": derived,
    }


@mcp.tool
def get_cash_and_obligations() -> dict:
    """The shop-wide money picture: every cash account, every open invoice
    (with vendor and days overdue), every lease's next rent, and the payments
    already recorded. Cash only goes out in this shop (no revenue is
    modelled), so this shows whether the shop can cover everything it owes.

    Reads cash_accounts, invoices, vendors, leases, payments and desk.
    """
    with closing(_connect()) as conn:
        date_today = _date_today(conn)
        accounts = _rows(conn, "SELECT name, balance, date FROM cash_accounts ORDER BY name")
        open_invoices = _rows(
            conn,
            "SELECT i.*, v.name AS vendor_name FROM invoices i "
            "JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open' ORDER BY i.due_date",
        )
        leases = _rows(conn, "SELECT * FROM leases ORDER BY next_due")
        payments = _rows(conn, "SELECT * FROM payments ORDER BY paid_at")

    cash_total = sum(a["balance"] for a in accounts)
    invoice_total = sum(i["amount"] for i in open_invoices)
    rent_total = sum(l["monthly_rent"] for l in leases)
    return {
        "date_today": date_today,
        "cash_accounts": accounts,
        "open_invoices": open_invoices,
        "leases": leases,
        "payments_recorded": payments,
        "derived": {
            "cash_total": cash_total,
            "open_invoice_total": invoice_total,
            "invoice_days_overdue": {
                str(i["id"]): max(_days_between(i["due_date"], date_today) or 0, 0)
                for i in open_invoices
            },
            "next_rent_total": rent_total,
            "days_until_rent_due": {
                str(l["id"]): _days_between(date_today, l["next_due"]) for l in leases
            },
            # Negative means the shop cannot pay every open invoice plus next rent.
            "cash_after_open_invoices_and_next_rent": cash_total - invoice_total - rent_total,
        },
    }


@mcp.tool
def check_payment(
    kind: Annotated[
        Literal["invoice", "lease_rent", "purchase_order"],
        Field(description="invoice = pay an invoices row; lease_rent = pay a lease's monthly rent; "
                          "purchase_order = buy stock at pricing.unit_cost."),
    ],
    ref_id: Annotated[int | None, Field(ge=1, description="invoices.id for 'invoice', leases.id for 'lease_rent'.")] = None,
    sku: Annotated[str | None, Field(max_length=40, description="SKU to buy, for 'purchase_order'.")] = None,
    qty: Annotated[int | None, Field(ge=1, le=1000, description="Units to buy, for 'purchase_order'.")] = None,
    vendor_id: Annotated[int | None, Field(ge=1, description="Vendor that would fill a 'purchase_order'.")] = None,
    account: Annotated[str, Field(max_length=40, description="cash_accounts.name to pay from.")] = "checking",
    reserved_amount: Annotated[
        float,
        Field(ge=0, description="Cash already earmarked for other payments in the same plan, "
                                "so several payments are checked together."),
    ] = 0,
) -> dict:
    """DRY RUN ONLY: check whether a proposed payment could be put in front of
    a human for approval. The amount always comes from the database
    (invoices.amount, leases.monthly_rent, or pricing.unit_cost x qty), never
    from the caller. This tool never records a payment or changes a balance.

    Refuses when the account would go negative, when an invoice is not open,
    or when a purchase order's vendor is blocked by open invoices. Every
    payment requires human approval, even when this check passes.

    Reads invoices, leases, pricing, vendors, cash_accounts, payments and desk.
    """
    with closing(_connect()) as conn:
        date_today = _date_today(conn)
        acct = _row(conn, "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,))
        if acct is None:
            return {"error": f"No cash account named {account!r}."}

        refusals: list[str] = []
        detail: dict = {}
        if kind == "invoice":
            if ref_id is None:
                return {"error": "kind='invoice' needs ref_id (an invoices.id)."}
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if inv is None:
                return {"error": f"No invoice with id {ref_id}."}
            amount, amount_source = inv["amount"], "invoices.amount"
            detail["invoice"] = inv
            if inv["status"] != "open":
                refusals.append(f"Invoice {ref_id} has status {inv['status']!r}, not 'open'.")
        elif kind == "lease_rent":
            if ref_id is None:
                return {"error": "kind='lease_rent' needs ref_id (a leases.id)."}
            lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
            if lease is None:
                return {"error": f"No lease with id {ref_id}."}
            amount, amount_source = lease["monthly_rent"], "leases.monthly_rent"
            detail["lease"] = lease
            detail["days_until_due"] = _days_between(date_today, lease["next_due"])
        else:
            if not sku or qty is None:
                return {"error": "kind='purchase_order' needs sku and qty."}
            price = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
            if price is None:
                return {"error": f"No pricing row for sku {sku!r}."}
            amount, amount_source = price["unit_cost"] * qty, "pricing.unit_cost x qty"
            detail["pricing"] = price
            if vendor_id is not None:
                vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
                if vendor is None:
                    return {"error": f"No vendor with id {vendor_id}."}
                blocking = _rows(
                    conn,
                    "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'",
                    (vendor_id,),
                )
                detail["vendor"] = vendor
                detail["vendor_open_invoices"] = blocking
                if blocking:
                    refusals.append(
                        f"Vendor {vendor_id} has open invoice(s) {[b['id'] for b in blocking]} "
                        "and will not ship until they are paid."
                    )

        prior = _rows(
            conn,
            "SELECT * FROM payments WHERE kind = ? AND ref_id IS ?",
            (kind, ref_id),
        )

    available = acct["balance"] - reserved_amount
    balance_after = available - amount
    if balance_after < 0:
        refusals.append(
            f"Insufficient cash: {account} has {acct['balance']:.2f}"
            + (f" ({reserved_amount:.2f} already reserved)" if reserved_amount else "")
            + f", payment is {amount:.2f}; balance would be {balance_after:.2f}."
        )

    return {
        "date_today": date_today,
        "kind": kind,
        "ref_id": ref_id,
        "amount": amount,
        "amount_source": amount_source,
        "account": acct,
        **detail,
        "prior_payments_same_ref": prior,
        "derived": {
            "available_after_reserved": available,
            "balance_after_payment": balance_after,
            "sufficient_funds": balance_after >= 0,
        },
        "decision": "refuse" if refusals else "eligible_for_human_approval",
        "refusal_reasons": refusals,
        "requires_human_approval": True,
        "executed": False,
    }


@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open and resolved) with its status, plus the shop's
    date. Used by the backend's ticket list.

    Reads tickets and desk.
    """
    with closing(_connect()) as conn:
        return {
            "date_today": _date_today(conn),
            "tickets": _rows(conn, "SELECT * FROM tickets ORDER BY id"),
        }


# --- Write tools (backend only; see module docstring) -------------------------

def signing_payload(tool: str, args: dict) -> str:
    """The exact string the backend signs. Must match backend/mcp_bridge.py."""
    return tool + ":" + json.dumps(args, sort_keys=True, separators=(",", ":"))


def _authorize(tool: str, args: dict, authorization: str) -> str | None:
    """None if the call is signed by the backend that started this server."""
    secret = os.environ.get(ADMIN_SECRET_ENV)
    if not secret:
        return ("Write tools are disabled in this server instance: it was not started by the "
                "Campus Customs backend, so no human approval can reach it.")
    expected = hmac.new(secret.encode(), signing_payload(tool, args).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, authorization or ""):
        return "Authorization check failed: this write was not signed by the backend."
    return None


def _connect_rw() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    # autocommit mode so the explicit BEGIN IMMEDIATE below controls the transaction
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _add_one_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day[:10])
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


Authorization = Annotated[str, Field(min_length=64, max_length=64, description="Backend signature.")]


@mcp.tool
def execute_approved_payment(
    approval_id: Annotated[str, Field(min_length=6, max_length=40)],
    approved_by: Annotated[str, Field(min_length=1, max_length=80)],
    kind: Literal["invoice", "lease_rent", "purchase_order"],
    expected_amount: Annotated[float, Field(gt=0)],
    authorization: Authorization,
    account: Annotated[str, Field(max_length=40)] = "checking",
    ref_id: Annotated[int | None, Field(ge=1)] = None,
    sku: Annotated[str | None, Field(max_length=40)] = None,
    qty: Annotated[int | None, Field(ge=1, le=1000)] = None,
    vendor_id: Annotated[int | None, Field(ge=1)] = None,
    expected_next_due: Annotated[str | None, Field(max_length=10)] = None,
) -> dict:
    """WRITE (backend only). Carry out a payment a human has approved, in one
    transaction: re-check everything check_payment checks, then insert the
    `payments` row, debit `cash_accounts`, and mark the invoice paid or move
    the lease's next_due forward one month. A purchase order is recorded
    against its vendor (payments.ref_id = vendor id); stock is not added,
    because it hasn't arrived.

    Refuses (and changes nothing) if the call isn't signed by the backend,
    the amount no longer matches what the human approved, the invoice is not
    open, the lease was already paid for that due date, the vendor is
    blocked, or the account would go negative.
    """
    # Sign over the non-None arguments; backend/mcp_bridge.py does the same.
    args = {k: v for k, v in locals().items() if k != "authorization" and v is not None}
    if (denied := _authorize("execute_approved_payment", args, authorization)):
        return {"error": denied, "executed": False}
    approved_by = approved_by.strip()
    if not approved_by:
        return {"error": "approved_by must name the human who approved this.", "executed": False}

    with closing(_connect_rw()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            date_today = _date_today(conn)
            acct = _row(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
            if acct is None:
                raise ValueError(f"No cash account named {account!r}.")

            updates: list[str] = []
            if kind == "invoice":
                inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,)) if ref_id else None
                if inv is None:
                    raise ValueError(f"No invoice with id {ref_id}.")
                if inv["status"] != "open":
                    raise ValueError(f"Invoice {ref_id} is {inv['status']!r}, not 'open'; it may already be paid.")
                amount, pay_ref = inv["amount"], ref_id
            elif kind == "lease_rent":
                lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,)) if ref_id else None
                if lease is None:
                    raise ValueError(f"No lease with id {ref_id}.")
                if not expected_next_due:
                    raise ValueError("lease_rent needs expected_next_due (the due date the human approved).")
                if lease["next_due"] != expected_next_due:
                    raise ValueError(
                        f"Lease {ref_id} is now due {lease['next_due']}, not {expected_next_due}; "
                        "that rent was already paid."
                    )
                amount, pay_ref = lease["monthly_rent"], ref_id
            else:
                if not sku or qty is None or vendor_id is None:
                    raise ValueError("purchase_order needs sku, qty and vendor_id.")
                price = _row(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
                if price is None:
                    raise ValueError(f"No pricing row for sku {sku!r}.")
                if _row(conn, "SELECT id FROM vendors WHERE id = ?", (vendor_id,)) is None:
                    raise ValueError(f"No vendor with id {vendor_id}.")
                blocking = _rows(conn, "SELECT id FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,))
                if blocking:
                    raise ValueError(f"Vendor {vendor_id} has open invoice(s) {[b['id'] for b in blocking]} and will not ship.")
                amount, pay_ref = price["unit_cost"] * qty, vendor_id

            if abs(amount - expected_amount) > 0.005:
                raise ValueError(f"Amount is now {amount:.2f}, but the human approved {expected_amount:.2f}.")
            balance_after = acct["balance"] - amount
            if balance_after < 0:
                raise ValueError(
                    f"Insufficient cash: {account} has {acct['balance']:.2f}, payment is {amount:.2f}."
                )

            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (kind, pay_ref, amount, account, date_today, approved_by),
            )
            payment_id = cur.lastrowid
            conn.execute(
                "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (balance_after, date_today, account)
            )
            updates += ["payments", "cash_accounts"]
            if kind == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
                updates.append(f"invoices[{ref_id}].status=paid")
            elif kind == "lease_rent":
                new_due = _add_one_month(expected_next_due)
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, ref_id))
                updates.append(f"leases[{ref_id}].next_due={new_due}")
            conn.execute("COMMIT")
        except (ValueError, sqlite3.Error) as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            return {"error": str(exc), "executed": False}

        payment = _row(conn, "SELECT * FROM payments WHERE id = ?", (payment_id,))
    return {
        "executed": True,
        "approval_id": approval_id,
        "payment": payment,
        "balance_before": acct["balance"],
        "balance_after": balance_after,
        "tables_updated": updates,
    }


@mcp.tool
def resolve_ticket(
    ticket_id: TicketId,
    resolved_by: Annotated[str, Field(min_length=1, max_length=80)],
    authorization: Authorization,
) -> dict:
    """WRITE (backend only). A human marks an open ticket 'resolved'. Changes
    only tickets.status; refuses if the ticket is missing or not open.
    """
    args = {"ticket_id": ticket_id, "resolved_by": resolved_by}
    if (denied := _authorize("resolve_ticket", args, authorization)):
        return {"error": denied}
    with closing(_connect_rw()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None or ticket["status"] != "open":
            conn.execute("ROLLBACK")
            return {"error": f"Ticket {ticket_id} does not exist." if ticket is None
                    else f"Ticket {ticket_id} is {ticket['status']!r}, not 'open'."}
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        conn.execute("COMMIT")
        return {"resolved": True, "ticket": _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))}


@mcp.tool
def reset_working_database(authorization: Authorization) -> dict:
    """WRITE (backend only). Replace the working copy with a byte-for-byte
    copy of the original data/campus_customs.db, which is only ever read.
    The copy goes to a temp file first and is then renamed over the working
    file, so the working database is never half-written. Confirms the result
    has the same SHA-256 as the original and dumps to identical SQL.
    """
    if (denied := _authorize("reset_working_database", {}, authorization)):
        return {"error": denied}
    if not ORIGINAL_DB_PATH.exists():
        return {"error": f"Original database not found: {ORIGINAL_DB_PATH}"}
    tmp = DB_PATH.with_name(f".{DB_PATH.name}.resetting")
    shutil.copyfile(ORIGINAL_DB_PATH, tmp)
    shutil.copymode(ORIGINAL_DB_PATH, tmp)
    os.replace(tmp, DB_PATH)
    DB_PATH.with_name(DB_PATH.name + "-journal").unlink(missing_ok=True)  # stale rollback journal, if any

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    with closing(sqlite3.connect(f"file:{ORIGINAL_DB_PATH}?mode=ro", uri=True)) as src, \
            closing(sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)) as dst:
        same_sql = list(src.iterdump()) == list(dst.iterdump())
        counts = {
            t: dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for (t,) in dst.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        }
    original_sha, working_sha = sha(ORIGINAL_DB_PATH), sha(DB_PATH)
    return {
        "reset": True,
        "verified_identical_to_original": same_sql and original_sha == working_sha,
        "sha256": {"original": original_sha, "working": working_sha},
        "row_counts": counts,
    }


if __name__ == "__main__":
    mcp.run()
