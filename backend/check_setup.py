"""Offline checks for the agent team. Makes NO model calls and spends no tokens.

    python -m backend.check_setup

Checks the five agents, prompts, model/Portkey config, full delegation
connectivity and loop bounds, MCP tool allocation, and the guardrails. Then
it drives one scripted ticket run through the real agent loop and the real
MCP server, with a FunctionModel standing in for gpt-6-luna. That scripted
run writes to a scratch audit file, so output/audit_trail.json only ever
holds real runs.
"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from contextlib import ExitStack
from pathlib import Path

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart, RetryPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RunUsage

from . import agents as team_agents
from .audit import AuditTrail
from .config import AUDIT_FILE, MAX_DELEGATION_DEPTH, MODEL_NAME, PORTKEY_BASE_URL, PROMPTS_DIR, build_model
from .mcp_bridge import WRITE_TOOLS, ShopMCP, ShopMCPError
from .models import AGENT_NAMES, AgentReport, PaymentProposal, RunBudget, TeamDeps, Fact, DraftMessage

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def deps_for(chain: tuple, shop=None, audit=None) -> TeamDeps:
    return TeamDeps(run_id="check", ticket_id=103, agent=chain[-1], chain=chain, budget=RunBudget(),
                    audit=audit, shop=shop)


class _Ctx:  # just enough RunContext for calling the output validator directly
    def __init__(self, deps): self.deps = deps


# --- scripted stand-in model for the end-to-end loop check --------------------

def _agent_of(messages) -> str:
    text = " ".join(getattr(m, "instructions", "") or "" for m in messages)
    return re.search(r"You are the .+? agent \((\w+)\)", text).group(1)


def scripted(messages, info: AgentInfo) -> ModelResponse:
    me = _agent_of(messages)
    returns = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, ToolReturnPart)]
    retries = [p for m in messages for p in getattr(m, "parts", []) if isinstance(p, RetryPromptPart)]
    out = info.output_tools[0].name
    n = len(returns)
    if me == "boss":
        task = "How short are we on CC-HOOD-NAVY size M for 20 units, and can vendor 1 ship a restock?"
        steps = [
            ToolCallPart("get_ticket", {"ticket_id": 103}),
            ToolCallPart("delegate", {"to_agent": "inventory", "task": task}),
            ToolCallPart("delegate", {"to_agent": "inventory", "task": task}),  # duplicate -> cache
            ToolCallPart(out, {
                "agent": "boss", "ticket_id": 103, "summary": "scripted",
                "facts": [{"statement": "Ticket 103 wants 20 hoodies", "source": "get_ticket"},
                          {"statement": "Vendor 1 is blocked", "source": "agent:inventory"}],
                "payment_proposals": [{"kind": "purchase_order", "sku": "CC-HOOD-NAVY", "qty": 12,
                                       "vendor_id": 1, "reason": "restock", "amount": 1.0}],
            }),
        ]
        return ModelResponse(parts=[steps[min(n, 3)]])
    # inventory
    if n == 0:
        return ModelResponse(parts=[ToolCallPart("get_vendor_ship_status", {"vendor_id": 1})])
    if n == 1:
        return ModelResponse(parts=[ToolCallPart("delegate", {"to_agent": "boss", "task": "Should I ask you again?"})])
    bad = not retries  # first answer cites a fake source; the guardrail should bounce it
    return ModelResponse(parts=[ToolCallPart(out, {
        "agent": "inventory", "ticket_id": 103, "summary": "scripted",
        "facts": [{"statement": "Vendor 1 has open invoice 501",
                   "source": "made_up_source" if bad else "get_vendor_ship_status"}],
    })])


async def main() -> int:
    # 1. Five agents, five prompts, one model
    agents = team_agents.get_agents()
    check("five agents exist", set(agents) == set(AGENT_NAMES), ", ".join(agents))
    check("all are PydanticAI Agents", all(isinstance(a, Agent) for a in agents.values()))
    for name, spec in team_agents.SPECS.items():
        p = PROMPTS_DIR / spec.prompt_file
        check(f"prompt file for {name}", p.exists() and len(p.read_text()) > 1500, f"{p.name}, {p.stat().st_size} bytes")
    model = build_model()
    check("every agent uses the same model object", all(a.model is model for a in agents.values()))
    check(f"model is {MODEL_NAME}", model.model_name == "gpt-6-luna", model.model_name)
    base = str(model.client.base_url).rstrip("/")
    check("model goes through Portkey", base == PORTKEY_BASE_URL, base)
    check("every agent has the delegate tool",
          all("delegate" in a._function_toolset.tools for a in agents.values()))

    # 2. Delegation connectivity and bounds
    edges = [(a, b) for a in AGENT_NAMES for b in AGENT_NAMES if a != b]
    allowed = [e for e in edges if team_agents.delegation_refusal(deps_for((e[0],)), e[1], "a focused question") is None]
    check("full connectivity: all 20 directed edges allowed", len(allowed) == 20, f"{len(allowed)}/20")
    check("self-delegation refused", team_agents.delegation_refusal(deps_for(("boss",)), "boss", "x" * 20) is not None)
    check("delegating back up the chain refused",
          team_agents.delegation_refusal(deps_for(("boss", "inventory")), "boss", "x" * 20) is not None)
    check("specialist->specialist allowed mid-chain",
          team_agents.delegation_refusal(deps_for(("boss", "inventory")), "accounting", "x" * 20) is None)
    deep = ("boss", "inventory", "accounting", "facilities")
    check(f"depth > {MAX_DELEGATION_DEPTH} refused",
          team_agents.delegation_refusal(deps_for(deep), "customer_service", "x" * 20) is not None)

    scratch = Path(tempfile.mkdtemp()) / "audit_check.json"
    audit = AuditTrail("check", path=scratch)
    async with ShopMCP() as shop:
        # 3. MCP tools
        check("MCP server exposes 13 tools", len(shop.tools) == 13, ", ".join(shop.tools))
        for name, spec in team_agents.SPECS.items():
            shop.toolset_for(name, spec.mcp_tools)  # raises if any tool is missing
        check("every agent's MCP allow-list exists on the server", True)
        check("no agent is given a write tool",
              not any(WRITE_TOOLS & set(s.mcp_tools) for s in team_agents.SPECS.values()))
        try:
            shop.toolset_for("inventory", ("get_ticket", "execute_approved_payment"))
            check("bridge refuses to hand an agent a write tool", False)
        except ShopMCPError:
            check("bridge refuses to hand an agent a write tool", True)
        unsigned = await shop.call("reset_working_database", {"authorization": "0" * 64})
        check("write tools refuse on a server started without the backend secret",
              "disabled" in unsigned.get("error", ""), unsigned.get("error", "")[:70])
        orig = await shop.call("get_backorder_and_vendor_block_status", {"ticket_id": 101})
        check("Problem 4 tool still works", orig.get("derived", {}).get("vendor_can_ship") is False)

        # 4. Guardrails on agent output
        acct = deps_for(("boss", "accounting"), shop, audit)
        acct.tools_called.add("check_payment")
        rep = AgentReport(agent="accounting", ticket_id=103, summary="t", payment_proposals=[
            PaymentProposal(kind="invoice", ref_id=501, reason="unblock vendor", amount=5.0),
            PaymentProposal(kind="lease_rent", ref_id=1, reason="rent"),
            PaymentProposal(kind="purchase_order", sku="CC-HOOD-NAVY", qty=12, reason="restock"),
        ])
        out = await team_agents._guard_output(_Ctx(acct), rep)
        p = out.payment_proposals
        check("payment amount taken from DB, not the model", p[0].amount == 840.0, f"{p[0].amount}")
        check("payments within cash await human approval",
              [x.status for x in p[:2]] == ["awaiting_human_approval"] * 2, f"after rent: {p[1].balance_after}")
        check("payment that would overdraw is refused", p[2].status == "refused" and p[2].balance_after < 0,
              f"balance_after={p[2].balance_after}")
        check("report flagged for human approval", out.needs_human_approval)

        for label, chain, report in [
            ("unsourced fact rejected", ("boss", "inventory"),
             AgentReport(agent="inventory", ticket_id=103, summary="t", facts=[Fact(statement="x", source="guess")])),
            ("inventory cannot author payments", ("boss", "inventory"),
             AgentReport(agent="inventory", ticket_id=103, summary="t",
                         payment_proposals=[PaymentProposal(kind="invoice", ref_id=501, reason="r")])),
            ("accounting cannot author drafts", ("boss", "accounting"),
             AgentReport(agent="accounting", ticket_id=103, summary="t",
                         draft_messages=[DraftMessage(recipient="x", subject="s", body="b")])),
        ]:
            try:
                await team_agents._guard_output(_Ctx(deps_for(chain, shop, audit)), report)
                check(label, False)
            except ModelRetry:
                check(label, True)
        try:
            DraftMessage(recipient="x", subject="s", body="b", status="sent")
            check("draft status cannot be 'sent'", False)
        except Exception:
            check("draft status cannot be 'sent'", True)

        # 5. Scripted end-to-end loop: boss -> inventory, real MCP, no real model
        e2e_audit = AuditTrail("e2e-check", path=scratch)
        deps = TeamDeps(run_id="e2e-check", ticket_id=103, agent="boss", chain=("boss",), budget=RunBudget(),
                        audit=e2e_audit, shop=shop)
        with ExitStack() as stack:
            for a in agents.values():
                stack.enter_context(a.override(model=FunctionModel(scripted)))
            report = await team_agents.run_agent("boss", "Work ticket 103.", deps, RunUsage())
        events = [r["event"] for r in json.loads(scratch.read_text())["records"] if r["run_id"] == "e2e-check"]
        check("e2e: boss delegated to inventory", "delegation_start" in events)
        check("e2e: duplicate delegation served from cache", "delegation_cached" in events)
        check("e2e: inventory->boss loop refused", "delegation_refused" in events)
        check("e2e: fake fact source bounced, then accepted", "guardrail_rejected_output" in events)
        check("e2e: MCP calls audited", events.count("mcp_tool_call") >= 2)
        po = report.payment_proposals[0]
        check("e2e: blocked-vendor purchase order refused with DB amount",
              po.status == "refused" and po.amount == 264.0, f"amount={po.amount}, reasons={po.refusal_reasons}")
        check("e2e: every loop step audited", {"loop_step_model_request", "loop_step_model_response",
                                               "loop_step_end", "agent_loop_end"} <= set(events))

    # 6. Audit file is append-oriented
    before = len(json.loads(scratch.read_text())["records"])
    AuditTrail("append-check", path=scratch).append(event="append_check", ticket_id=None)
    after = len(json.loads(scratch.read_text())["records"])
    check("audit appends without losing history", after == before + 1, f"{before} -> {after}")
    if AUDIT_FILE.exists():
        data = json.loads(AUDIT_FILE.read_text())
        check("output/audit_trail.json is valid JSON with a records list", isinstance(data.get("records"), list),
              f"{len(data['records'])} records")

    width = max(len(n) for _, n, _ in results)
    for status, name, detail in results:
        print(f"[{status}] {name.ljust(width)}  {detail}")
    failed = sum(s == FAIL for s, _, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
