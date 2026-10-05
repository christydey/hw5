"""Campus Customs backend API (FastAPI).

    cd backend && uvicorn main:app --port 8000          # or, from hwv5/:
    uvicorn backend.main:app --port 8000

One MCP connection is opened at startup and shared by every route and every
agent run. It is the only path to the shop database. That connection is
given a random per-process admin secret, which enables the MCP server's write
tools for this backend alone. Only three human-facing routes use them:
approve, resolve and reset. Agents run with read-only allow-lists and never
see the secret, so they can prepare payments but cannot execute one.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `uvicorn main:app` from inside backend/ as well as `backend.main:app`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Body, FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from backend.approvals import ApprovalStore  # noqa: E402
from backend.audit import AuditTrail  # noqa: E402
from backend.config import AUDIT_FILE, MODEL_NAME  # noqa: E402
from backend.mcp_bridge import WRITE_TOOLS, ShopMCP  # noqa: E402
from backend.models import (  # noqa: E402
    AgentEvent,
    Approval,
    ApprovalStatus,
    ApproveRequest,
    CashResponse,
    EventsResponse,
    RejectRequest,
    ResetRequest,
    ResolveRequest,
    RunOut,
    RunRequest,
    TicketOut,
    TicketsResponse,
)
from backend.team import run_ticket_detailed  # noqa: E402

MAX_CONCURRENT_RUNS = 3  # one per open ticket; each run is token-capped by TEAM_USAGE_LIMITS
NOT_MCP_TOOLS = {"delegate", "final_result"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    shop: ShopMCP
    approvals = ApprovalStore()
    runs: dict[str, RunOut] = {}
    tasks: dict[str, asyncio.Task] = {}
    write_lock = asyncio.Lock()  # approve / reject / resolve / reset happen one at a time


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.shop = ShopMCP(admin_secret=secrets.token_hex(32))
    await state.shop.__aenter__()
    missing = WRITE_TOOLS - set(state.shop.tools)
    if missing:
        raise RuntimeError(f"MCP server is missing write tools {sorted(missing)}.")
    try:
        yield
    finally:
        for task in state.tasks.values():
            task.cancel()
        await asyncio.gather(*state.tasks.values(), return_exceptions=True)
        await state.shop.__aexit__(None, None, None)


app = FastAPI(
    title="Campus Customs backend",
    description="Tickets, agent-team runs, agent events, human approvals, cash and reset.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",  # vite dev
        "http://localhost:4173", "http://127.0.0.1:4173",  # vite preview
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


async def mcp(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read through MCP. A tool-level error becomes a 502 unless the caller handles it."""
    result = await state.shop.call(name, args or {})
    if "error" in result:
        raise HTTPException(status_code=502, detail=f"MCP {name}: {result['error']}")
    return result


def api_audit(event: str, ticket_id: int | None = None, **fields: Any) -> None:
    AuditTrail(f"api-{uuid.uuid4().hex[:8]}").append(event=event, ticket_id=ticket_id, **fields)


def active_run_for(ticket_id: int) -> str | None:
    return next((r.run_id for r in state.runs.values() if r.ticket_id == ticket_id and r.status == "running"), None)


async def get_ticket_or_404(ticket_id: int) -> dict[str, Any]:
    result = await state.shop.call("get_ticket", {"ticket_id": ticket_id})
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result["ticket"]


# --- Health ---------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "model": MODEL_NAME, "mcp_tools": sorted(state.shop.tools),
            "active_runs": [r.run_id for r in state.runs.values() if r.status == "running"]}


# --- 1. Tickets -------------------------------------------------------------

def _ticket_out(t: dict[str, Any], pending: list[Approval]) -> TicketOut:
    return TicketOut(**t, is_open=t["status"] == "open", active_run_id=active_run_for(t["id"]),
                     pending_approvals=sum(a.ticket_id == t["id"] for a in pending))


@app.get("/api/tickets", response_model=TicketsResponse)
async def list_tickets() -> TicketsResponse:
    data = await mcp("list_tickets")
    pending = state.approvals.list(status="pending")
    return TicketsResponse(date_today=data["date_today"], tickets=[_ticket_out(t, pending) for t in data["tickets"]])


@app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: int) -> TicketOut:
    return _ticket_out(await get_ticket_or_404(ticket_id), state.approvals.list(status="pending"))


@app.post("/api/tickets/{ticket_id}/resolve", response_model=TicketOut)
async def resolve_ticket(ticket_id: int, body: ResolveRequest) -> TicketOut:
    """A human marks a ticket resolved (signed MCP write)."""
    await get_ticket_or_404(ticket_id)
    if active_run_for(ticket_id):
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} has an agent run in progress.")
    async with state.write_lock:
        result = await state.shop.admin_call("resolve_ticket", {"ticket_id": ticket_id,
                                                                "resolved_by": body.resolved_by.strip()})
    if "error" in result:
        api_audit("ticket_resolve_refused", ticket_id, error=result["error"])
        raise HTTPException(status_code=409, detail=result["error"])
    api_audit("ticket_resolved", ticket_id, result={"resolved_by": body.resolved_by.strip()})
    return _ticket_out(result["ticket"], state.approvals.list(status="pending"))


# --- 2. Run the agent team --------------------------------------------------

async def _execute_run(run: RunOut, task: str | None) -> None:
    try:
        team = await run_ticket_detailed(run.ticket_id, task, shop=state.shop, run_id=run.run_id)
        approvals = await state.approvals.prepare_from_run(
            state.shop, team.run_id, team.ticket_id, [team.report, *team.delegate_reports]
        )
        if approvals:
            api_audit("approvals_prepared", run.ticket_id,
                      result=[{"approval_id": a.id, "kind": a.kind, "amount": a.amount, "status": a.status,
                               "prepared_by": a.prepared_by} for a in approvals],
                      requires_human_approval=any(a.status == "pending" for a in approvals))
        run.report, run.delegate_reports, run.approvals = team.report, team.delegate_reports, approvals
        run.delegations_used, run.usage = team.delegations_used, team.usage
        # The team has finished its work on this ticket, so the backend (never an
        # agent) marks it resolved. Payments it proposed still wait for a human.
        async with state.write_lock:
            resolved = await state.shop.admin_call(
                "resolve_ticket", {"ticket_id": run.ticket_id, "resolved_by": f"agent team (run {run.run_id})"}
            )
        if "error" in resolved:
            api_audit("ticket_resolve_refused", run.ticket_id, error=resolved["error"])
        else:
            api_audit("ticket_resolved", run.ticket_id,
                      result={"resolved_by": f"agent team (run {run.run_id})", "run_id": run.run_id})
        run.status = "completed"
    except asyncio.CancelledError:
        run.status, run.error = "failed", "Cancelled (backend shut down)."
        raise
    except Exception as exc:  # recorded on the run; the audit trail already has run_failed
        run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        run.finished_at = _now()
        state.tasks.pop(run.run_id, None)


@app.post("/api/tickets/{ticket_id}/run", response_model=RunOut, status_code=202)
async def run_team(
    ticket_id: int,
    body: RunRequest | None = Body(default=None),
    wait: bool = Query(False, description="Block until the run finishes (default: return immediately)."),
) -> RunOut | JSONResponse:
    """Start the Boss + specialist team on one ticket."""
    ticket = await get_ticket_or_404(ticket_id)
    if ticket["status"] != "open":
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is {ticket['status']!r}; only open tickets are run.")
    if existing := active_run_for(ticket_id):
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} already has run {existing} in progress.")
    if len(state.tasks) >= MAX_CONCURRENT_RUNS:
        raise HTTPException(status_code=429, detail=f"At most {MAX_CONCURRENT_RUNS} agent runs at once.")

    run = RunOut(run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id, status="running", started_at=_now())
    state.runs[run.run_id] = run
    task = asyncio.create_task(_execute_run(run, body.task if body else None))
    state.tasks[run.run_id] = task
    if wait:
        await asyncio.shield(task)
        return JSONResponse(status_code=200, content=run.model_dump(mode="json"))
    return run


@app.get("/api/runs", response_model=list[RunOut])
async def list_runs(ticket_id: int | None = None) -> list[RunOut]:
    """Runs started by this backend process, newest first (full history is in /api/events)."""
    runs = [r for r in state.runs.values() if ticket_id is None or r.ticket_id == ticket_id]
    return sorted(runs, key=lambda r: r.started_at, reverse=True)


@app.get("/api/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: str) -> RunOut:
    if run_id not in state.runs:
        raise HTTPException(status_code=404, detail=f"No run {run_id} in this backend session.")
    return state.runs[run_id]


# --- 3. Agent events (from output/audit_trail.json) ---------------------------

def _summarize(r: dict[str, Any]) -> tuple[str, list[str]]:
    ev, res = r["event"], r.get("result")
    calls = r.get("tool_calls") or []
    tools = [c["tool"] for c in calls]
    deleg = r.get("delegation") or {}
    if ev == "loop_step_model_response" and isinstance(res, dict):
        requested = [c["tool"] for c in res.get("requested_tool_calls", [])]
        tools = [t for t in requested if t not in NOT_MCP_TOOLS]
        if res.get("text"):
            return res["text"], tools
        if "final_result" in requested:
            return "Wrote its final report.", tools
        return ("Decided to call " + ", ".join(requested)) if requested else "Model responded.", tools
    if ev == "mcp_tool_call" and calls:
        c = calls[0]
        args = ", ".join(f"{k}={v!r}" for k, v in c.get("args", {}).items())
        status = "error" if not c.get("ok") else ("cached" if c.get("cached") else "ok")
        return f"Called MCP {c['tool']}({args}) — {status}", tools
    if ev.startswith("delegation_"):
        verb = {"delegation_start": "Delegated to", "delegation_end": "Got report from",
                "delegation_refused": "Delegation refused to", "delegation_cached": "Reused earlier answer from",
                "delegation_failed": "Delegation failed to"}.get(ev, ev)
        extra = (res or {}).get("summary") if ev == "delegation_end" else (deleg.get("reason") or deleg.get("task"))
        return f"{verb} {deleg.get('to_agent')}: {extra or ''}".strip(), tools
    if ev == "agent_loop_start":
        return f"Started on task: {r.get('task', '')}", tools
    if ev in ("agent_loop_end", "run_end") and isinstance(res, dict):
        return res.get("summary", ev), tools
    if ev == "run_start":
        return f"Team run started (model {(res or {}).get('model')}).", tools
    if ev == "approvals_prepared" and isinstance(res, list):
        return "Prepared for human approval: " + "; ".join(
            f"{a['kind']} ${a['amount']:,.2f} ({a['status']})" if a.get("amount") is not None
            else f"{a['kind']} ({a['status']})" for a in res), tools
    if ev == "human_approval_executed" and isinstance(res, dict):
        p = res.get("payment", {})
        return (f"{res.get('approved_by')} approved {p.get('kind')} ${p.get('amount', 0):,.2f}; checking "
                f"${res.get('balance_before', 0):,.2f} → ${res.get('balance_after', 0):,.2f}."), tools
    if ev == "human_approval_rejected" and isinstance(res, dict):
        return f"{res.get('rejected_by')} rejected approval {res.get('approval_id')}.", tools
    if ev == "ticket_resolved" and isinstance(res, dict):
        return f"{res.get('resolved_by')} marked the ticket resolved.", tools
    if ev == "database_reset" and isinstance(res, dict):
        return (f"Working database reset from the original (identical: "
                f"{res.get('verified_identical_to_original')}; approvals voided: {res.get('approvals_voided')})."), tools
    if r.get("guardrail"):
        return r["guardrail"], tools
    if r.get("error"):
        return r["error"], tools
    labels = {"loop_step_user_prompt": "Received prompt.", "loop_step_model_request": "Sent results back to the model.",
              "loop_step_end": "Loop finished."}
    return labels.get(ev, ev.replace("_", " ").capitalize() + "."), tools


@app.get("/api/events", response_model=EventsResponse)
async def events(
    limit: int = Query(100, ge=1, le=1000),
    ticket_id: int | None = None,
    run_id: str | None = None,
    agent: str | None = None,
    after_seq: int | None = Query(None, ge=0, description="Only events newer than this seq (for polling)."),
    steps: bool = Query(True, description="Include low-level loop steps (prompt/request/end)."),
    raw: bool = Query(False, description="Include the full audit record."),
) -> EventsResponse:
    """Most recent agent/audit events, oldest first within the returned window."""
    records = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))["records"] if AUDIT_FILE.exists() else []
    noisy = {"loop_step_user_prompt", "loop_step_model_request", "loop_step_end"}
    picked = [
        r for r in records
        if (ticket_id is None or r.get("ticket_id") == ticket_id)
        and (run_id is None or r.get("run_id") == run_id)
        and (agent is None or r.get("agent") == agent)
        and (after_seq is None or r["seq"] > after_seq)
        and (steps or r["event"] not in noisy)
    ][-limit:]
    out = []
    for r in picked:
        summary, tools = _summarize(r)
        out.append(AgentEvent(
            seq=r["seq"], timestamp=r["timestamp"], run_id=r["run_id"], ticket_id=r.get("ticket_id"),
            agent=r.get("agent"), depth=r.get("depth", 0), event=r["event"], summary=summary,
            mcp_tools=tools, delegation=r.get("delegation"), requires_human_approval=r.get("requires_human_approval"),
            guardrail=r.get("guardrail"), error=r.get("error"), raw=r if raw else None,
        ))
    return EventsResponse(total_records=len(records), returned=len(out), events=out)


# --- 4. Human approval --------------------------------------------------------

@app.get("/api/approvals", response_model=list[Approval])
async def list_approvals(status: ApprovalStatus | None = None, ticket_id: int | None = None) -> list[Approval]:
    return state.approvals.list(status=status, ticket_id=ticket_id)


@app.get("/api/approvals/{approval_id}", response_model=Approval)
async def get_approval(approval_id: str) -> Approval:
    if (a := state.approvals.get(approval_id)) is None:
        raise HTTPException(status_code=404, detail=f"No approval {approval_id}.")
    return a


@app.post("/api/approvals/{approval_id}/approve", response_model=Approval)
async def approve(approval_id: str, body: ApproveRequest) -> Approval:
    """A human approves a prepared payment/purchase. This is the only place cash changes."""
    who = body.approved_by.strip()
    if not who:
        raise HTTPException(status_code=422, detail="approved_by must name a person.")
    async with state.write_lock:  # serialises approvals: no double execution from double clicks
        a = state.approvals.get(approval_id)
        if a is None:
            raise HTTPException(status_code=404, detail=f"No approval {approval_id}.")
        if a.status != "pending":
            raise HTTPException(status_code=409, detail=f"Approval {approval_id} is {a.status!r}, not 'pending'.")
        if a.amount is None or abs(body.confirm_amount - a.amount) > 0.005:
            raise HTTPException(status_code=422,
                                detail=f"confirm_amount {body.confirm_amount:.2f} does not match the approval amount {a.amount}.")

        args = {"approval_id": a.id, "approved_by": who, "kind": a.kind, "expected_amount": float(a.amount),
                "account": a.account, "ref_id": a.ref_id, "sku": a.sku, "qty": a.qty, "vendor_id": a.vendor_id,
                "expected_next_due": a.expected_next_due}
        result = await state.shop.admin_call("execute_approved_payment", args)
        logged_args = {k: v for k, v in args.items() if v is not None}

        if not result.get("executed"):
            err = result.get("error", "Payment was not executed.")
            state.approvals.update(a.id, lambda x: setattr(x, "last_error", err))
            api_audit("human_approval_refused", a.ticket_id, error=err, requires_human_approval=True,
                      tool_calls=[{"tool": "execute_approved_payment", "args": logged_args, "ok": False}])
            raise HTTPException(status_code=409, detail=err)

        def mark(x: Approval) -> None:
            x.status, x.decided_by, x.decided_at, x.note = "executed", who, _now(), body.note
            x.last_error = None
            x.execution = {k: result[k] for k in ("payment", "balance_before", "balance_after", "tables_updated")}

        updated = state.approvals.update(a.id, mark)
        api_audit("human_approval_executed", a.ticket_id, requires_human_approval=False,
                  result={"approval_id": a.id, "approved_by": who, **updated.execution},
                  tool_calls=[{"tool": "execute_approved_payment", "args": logged_args, "ok": True}])
        return updated


@app.post("/api/approvals/{approval_id}/reject", response_model=Approval)
async def reject(approval_id: str, body: RejectRequest) -> Approval:
    who = body.rejected_by.strip()
    if not who:
        raise HTTPException(status_code=422, detail="rejected_by must name a person.")
    async with state.write_lock:
        a = state.approvals.get(approval_id)
        if a is None:
            raise HTTPException(status_code=404, detail=f"No approval {approval_id}.")
        if a.status != "pending":
            raise HTTPException(status_code=409, detail=f"Approval {approval_id} is {a.status!r}, not 'pending'.")

        def mark(x: Approval) -> None:
            x.status, x.decided_by, x.decided_at, x.note = "rejected", who, _now(), body.note

        updated = state.approvals.update(a.id, mark)
    api_audit("human_approval_rejected", a.ticket_id, result={"approval_id": a.id, "rejected_by": who})
    return updated


# --- 5. Cash ------------------------------------------------------------------

@app.get("/api/cash", response_model=CashResponse)
async def cash() -> CashResponse:
    data = await mcp("get_cash_and_obligations")
    checking = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No 'checking' row in cash_accounts.")
    return CashResponse(account="checking", balance=checking["balance"], as_of=checking["date"],
                        date_today=data["date_today"], accounts=data["cash_accounts"])


# --- 6. Reset -----------------------------------------------------------------

@app.post("/api/reset")
async def reset(body: ResetRequest) -> dict[str, Any]:
    """Restore data/campus_customs_new.db from the read-only original."""
    if state.tasks:
        raise HTTPException(status_code=409, detail="Agent runs are in progress; wait for them before resetting.")
    async with state.write_lock:
        result = await state.shop.admin_call("reset_working_database", {})
        if "error" in result:
            api_audit("database_reset_failed", error=result["error"])
            raise HTTPException(status_code=500, detail=result["error"])
        voided = state.approvals.void_pending("Voided by database reset.")
    api_audit("database_reset", result={**result, "approvals_voided": voided})
    return {**result, "approvals_voided": voided}
