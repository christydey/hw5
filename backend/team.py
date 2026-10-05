"""Run the agent team on one ticket.

Opens (or reuses) one MCP connection, confirms the ticket exists (before
spending any model tokens), then starts the entry agent (the Boss by
default). Every step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass

from pydantic_ai.usage import RunUsage

from .agents import SPECS, run_agent
from .audit import AuditTrail
from .config import (
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MAX_LOOP_STEPS_PER_AGENT,
    MODEL_NAME,
    TEAM_USAGE_LIMITS,
)
from .mcp_bridge import ShopMCP
from .models import AgentName, AgentReport, RunBudget, TeamDeps


@dataclass
class TeamRun:
    run_id: str
    ticket_id: int
    entry_agent: AgentName
    report: AgentReport  # the entry agent's final report
    delegate_reports: list[AgentReport]  # every teammate report produced during the run
    delegations_used: int
    usage: dict[str, int]


def default_task(ticket_id: int) -> str:
    return (
        f"Work ticket {ticket_id}. Read it, decide which specialists are needed, delegate to them, "
        "combine what they find, and give a final operational recommendation. Do not execute any "
        "payment or send any message; anything that spends money or contacts a customer goes to a human."
    )


def _usage(usage: RunUsage) -> dict[str, int]:
    return {k: getattr(usage, k, 0) or 0 for k in ("requests", "input_tokens", "output_tokens", "tool_calls")}


async def run_ticket_detailed(
    ticket_id: int,
    task: str | None = None,
    entry_agent: AgentName = "boss",
    *,
    shop: ShopMCP | None = None,
    run_id: str | None = None,
) -> TeamRun:
    """Run the team. Pass `shop` to reuse an open MCP connection (the API
    does); otherwise one is opened for this run."""
    if not isinstance(ticket_id, int) or ticket_id < 1:
        raise ValueError(f"ticket_id must be a positive integer, got {ticket_id!r}.")
    if entry_agent not in SPECS:
        raise ValueError(f"Unknown agent {entry_agent!r}.")
    task = (task or default_task(ticket_id)).strip()

    run_id = run_id or uuid.uuid4().hex[:12]
    audit = AuditTrail(run_id)
    async with AsyncExitStack() as stack:
        if shop is None:
            shop = await stack.enter_async_context(ShopMCP())
        found = await shop.call("get_ticket", {"ticket_id": ticket_id})
        if "error" in found:
            audit.append(event="run_rejected", ticket_id=ticket_id, agent=entry_agent, error=found["error"],
                         guardrail="ticket must exist in the database before any model call")
            raise ValueError(found["error"])

        audit.append(
            event="run_start", ticket_id=ticket_id, agent=entry_agent, task=task,
            result={
                "model": MODEL_NAME,
                "limits": {
                    "max_delegation_depth": MAX_DELEGATION_DEPTH,
                    "max_delegations_per_run": MAX_DELEGATIONS_PER_RUN,
                    "max_loop_steps_per_agent": MAX_LOOP_STEPS_PER_AGENT,
                    "request_limit": TEAM_USAGE_LIMITS.request_limit,
                    "tool_calls_limit": TEAM_USAGE_LIMITS.tool_calls_limit,
                    "total_tokens_limit": TEAM_USAGE_LIMITS.total_tokens_limit,
                },
            },
        )
        deps = TeamDeps(
            run_id=run_id, ticket_id=ticket_id, agent=entry_agent, chain=(entry_agent,),
            budget=RunBudget(), audit=audit, shop=shop,
        )
        usage = RunUsage()
        try:
            report = await run_agent(entry_agent, task, deps, usage)
        except Exception as exc:
            audit.append(event="run_failed", ticket_id=ticket_id, agent=entry_agent,
                         error=f"{type(exc).__name__}: {exc}", usage=_usage(usage))
            raise

        audit.append(
            event="run_end", ticket_id=ticket_id, agent=entry_agent,
            result={"summary": report.summary, "delegations_used": deps.budget.delegations_used},
            requires_human_approval=report.needs_human_approval,
            usage=_usage(usage),
        )
        return TeamRun(
            run_id=run_id,
            ticket_id=ticket_id,
            entry_agent=entry_agent,
            report=report,
            delegate_reports=list(deps.budget.delegation_cache.values()),
            delegations_used=deps.budget.delegations_used,
            usage=_usage(usage),
        )


async def run_ticket(ticket_id: int, task: str | None = None, entry_agent: AgentName = "boss") -> AgentReport:
    return (await run_ticket_detailed(ticket_id, task, entry_agent)).report
