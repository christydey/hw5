"""The five Campus Customs agents and how they talk to each other.

Each agent is a PydanticAI Agent with its own prompt file, its own allow-list
of MCP tools, and the same `delegate` tool, so any agent can hand work to any
other. Delegation is bounded (no self-delegation, no delegating back up the
chain, max depth, max hand-offs per run, identical requests answered from
cache) and every step is written to output/audit_trail.json.

Every agent's output goes through `_guard_output`, which re-checks payments
against the MCP check_payment tool, keeps drafts as drafts, and rejects facts
that do not trace to an MCP call or a teammate's report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage

from .config import (
    AGENT_RETRIES,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MAX_LOOP_STEPS_PER_AGENT,
    MAX_TASK_CHARS,
    MODEL_SETTINGS,
    PROMPTS_DIR,
    TEAM_USAGE_LIMITS,
    build_model,
)
from .models import AGENT_NAMES, AgentName, AgentReport, DelegationRecord, TeamDeps, ToolCallRecord


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    title: str
    prompt_file: str
    mcp_tools: tuple[str, ...]
    expertise: str  # shown to teammates so they know when to delegate here


SPECS: dict[AgentName, AgentSpec] = {
    "boss": AgentSpec(
        "boss", "Boss", "boss.md",
        ("list_open_tickets", "get_ticket"),
        "coordinates tickets, combines specialist findings, makes the final recommendation",
    ),
    "inventory": AgentSpec(
        "inventory", "Inventory", "inventory.md",
        ("get_ticket", "get_backorder_and_vendor_block_status", "get_bulk_order_stock_and_pricing",
         "list_vendors", "get_vendor_ship_status"),
        "stock by SKU/size, shortages, restock options, vendor lead times, vendor shipping blocks",
    ),
    "accounting": AgentSpec(
        "accounting", "Accounting", "accounting.md",
        ("get_ticket", "get_cash_and_obligations", "check_payment", "get_vendor_ship_status",
         "get_bulk_order_stock_and_pricing"),
        "cash balances, invoices, margins and discounts, payment and purchase-order checks",
    ),
    "facilities": AgentSpec(
        "facilities", "Facilities", "facilities.md",
        ("get_ticket", "get_rent_due_and_cash_position"),
        "leases, rent amounts and due dates, other shop-space obligations",
    ),
    "customer_service": AgentSpec(
        "customer_service", "Customer Service", "customer_service.md",
        ("get_ticket",),
        "customer-facing draft messages (never sent) for human review",
    ),
}

# Only these agents may put payment proposals / message drafts in a report.
PAYMENT_AUTHORS = {"accounting", "boss"}  # boss may relay what accounting proposed
DRAFT_AUTHORS = {"customer_service", "boss"}  # boss may relay what customer service drafted


class AgentLoopLimit(RuntimeError):
    pass


# --- Delegation policy (pure, so it can be checked without a model) -----------

def delegation_refusal(deps: TeamDeps, to_agent: str, task: str) -> str | None:
    """Why this delegation is not allowed, or None if it is."""
    if to_agent not in AGENT_NAMES:
        return f"Unknown agent {to_agent!r}. Choose one of {list(AGENT_NAMES)}."
    if to_agent == deps.agent:
        return "An agent cannot delegate to itself."
    if to_agent in deps.chain:
        return (
            f"{to_agent} is already waiting on you (chain: {' -> '.join(deps.chain)}). "
            "Delegating back would loop; answer with what you have or ask a different teammate."
        )
    if deps.depth + 1 > MAX_DELEGATION_DEPTH:
        return f"Maximum delegation depth ({MAX_DELEGATION_DEPTH}) reached; answer with what you have."
    if not 10 <= len(task) <= MAX_TASK_CHARS:
        return f"Task must be 10-{MAX_TASK_CHARS} characters; send one focused question."
    return None


def _task_key(to_agent: str, task: str) -> tuple[str, str]:
    return to_agent, " ".join(task.lower().split())


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict[str, Any]:
    """Ask a teammate to do part of this ticket and get their structured report back.

    Use it when the answer needs another agent's MCP tools or expertise. Send one
    focused question with the context they need (ticket id, SKU, amounts you
    already know). Returns {"status": "completed" | "cached", "report": {...}} or
    {"status": "refused" | "failed", "reason": ...}. A refusal is final for that
    request: do not retry it; work with what you have.

    Args:
        to_agent: boss, inventory, accounting, facilities or customer_service.
        task: The question or job for that agent.
    """
    deps = ctx.deps
    task = task.strip()

    def record(status: str, reason: str | None = None) -> DelegationRecord:
        return DelegationRecord(
            from_agent=deps.agent, to_agent=to_agent, task=task, depth=deps.depth + 1, status=status, reason=reason
        )

    refusal = delegation_refusal(deps, to_agent, task)
    key = _task_key(to_agent, task)
    if refusal is None and key in deps.budget.delegation_cache:
        report = deps.budget.delegation_cache[key]
        deps.delegated_to.add(to_agent)
        deps.audit.append(
            event="delegation_cached", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
            delegation=record("cached", "Same request already answered this run."),
            guardrail="duplicate delegation served from cache",
        )
        return {"status": "cached", "report": report.model_dump(exclude_defaults=True)}
    if refusal is None and deps.budget.delegations_used >= MAX_DELEGATIONS_PER_RUN:
        refusal = f"Team delegation budget ({MAX_DELEGATIONS_PER_RUN}) used up; answer with what you have."
    if refusal is not None:
        deps.audit.append(
            event="delegation_refused", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
            delegation=record("refused", refusal), guardrail=refusal,
        )
        return {"status": "refused", "reason": refusal}

    deps.budget.delegations_used += 1
    deps.audit.append(
        event="delegation_start", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
        task=task, delegation=record("completed"),
    )
    try:
        report = await run_agent(
            to_agent, f"[Delegated by {SPECS[deps.agent].title}] {task}", deps.for_delegate(to_agent), ctx.usage
        )
    except UsageLimitExceeded:
        raise  # the whole team is out of budget; stop the run
    except (UnexpectedModelBehavior, ModelAPIError, AgentLoopLimit) as exc:
        reason = f"{type(exc).__name__}: {exc}"
        deps.audit.append(
            event="delegation_failed", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
            delegation=record("failed", reason), error=reason,
        )
        return {"status": "failed", "reason": reason}

    deps.budget.delegation_cache[key] = report
    deps.delegated_to.add(to_agent)
    deps.audit.append(
        event="delegation_end", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
        delegation=record("completed"), result={"summary": report.summary},
        requires_human_approval=report.needs_human_approval,
    )
    return {"status": "completed", "report": report.model_dump(exclude_defaults=True)}


# --- Instructions --------------------------------------------------------------

def _runtime_context(deps: TeamDeps) -> str:
    spec = SPECS[deps.agent]
    left = MAX_DELEGATIONS_PER_RUN - deps.budget.delegations_used
    can_go_deeper = deps.depth + 1 <= MAX_DELEGATION_DEPTH and left > 0
    teammates = [
        f"- {n} ({SPECS[n].title}): {SPECS[n].expertise}"
        + (" [waiting on you; do not delegate back]" if n in deps.chain else "")
        for n in AGENT_NAMES
        if n != deps.agent
    ]
    return "\n".join([
        "## Run context (set by the system, not the user)",
        f"- You are the {spec.title} agent ({deps.agent}).",
        f"- Ticket: {deps.ticket_id}.",
        f"- Delegation chain so far: {' -> '.join(deps.chain)} (depth {deps.depth} of max {MAX_DELEGATION_DEPTH}).",
        f"- Team delegations left this run: {left}."
        + ("" if can_go_deeper else " You cannot delegate further; answer with what you have."),
        f"- Your MCP tools: {', '.join(spec.mcp_tools)}.",
        "- Teammates:",
        *teammates,
        "- In `facts`, set `source` to the MCP tool you called or `agent:<name>` for a teammate's report. "
        "Facts with any other source are rejected.",
    ])


def _instructions_for(spec: AgentSpec):
    base = (PROMPTS_DIR / spec.prompt_file).read_text(encoding="utf-8")

    def instructions(ctx: RunContext[TeamDeps]) -> str:
        return f"{base}\n\n{_runtime_context(ctx.deps)}"

    return instructions


# --- Output guardrails ---------------------------------------------------------

async def _cached_mcp(deps: TeamDeps, name: str, args: dict[str, Any]) -> dict[str, Any]:
    key = f"{name}:{json.dumps(args, sort_keys=True)}"
    if key not in deps.budget.mcp_cache:
        result = await deps.shop.call(name, args)
        if "error" in result:
            return result
        deps.budget.mcp_cache[key] = result
    return deps.budget.mcp_cache[key]


async def _guard_output(ctx: RunContext[TeamDeps], output: AgentReport) -> AgentReport:
    deps = ctx.deps
    output.agent = deps.agent
    output.ticket_id = deps.ticket_id

    def reject(reason: str) -> ModelRetry:
        deps.audit.append(
            event="guardrail_rejected_output", ticket_id=deps.ticket_id, agent=deps.agent,
            depth=deps.depth, guardrail=reason,
        )
        return ModelRetry(reason)

    # 1. Facts must trace to a successful MCP call or a teammate's report in this run.
    allowed_sources = deps.tools_called | {f"agent:{a}" for a in deps.delegated_to}
    unsourced = [f.source for f in output.facts if f.source not in allowed_sources]
    if unsourced:
        raise reject(
            f"Facts cite sources you did not use in this run: {sorted(set(unsourced))}. "
            f"Allowed sources: {sorted(allowed_sources) or 'none yet; call an MCP tool or delegate first'}."
        )

    # 2. Only the right agents may author payments and drafts.
    if output.payment_proposals and deps.agent not in PAYMENT_AUTHORS:
        raise reject("Only Accounting prepares payment proposals. Delegate the payment question to accounting.")
    if output.draft_messages and deps.agent not in DRAFT_AUTHORS:
        raise reject("Only Customer Service writes customer/vendor drafts. Delegate the draft to customer_service.")

    # 3. Re-check every payment through MCP, in the order listed, reserving cash as we go.
    reserved: dict[str, float] = {}
    checks: list[ToolCallRecord] = []
    for p in output.payment_proposals:
        args: dict[str, Any] = {"kind": p.kind, "account": p.account, "reserved_amount": reserved.get(p.account, 0.0)}
        if p.kind == "purchase_order":
            args.update({k: v for k, v in {"sku": p.sku, "qty": p.qty, "vendor_id": p.vendor_id}.items() if v is not None})
        else:
            args["ref_id"] = p.ref_id
        res = await _cached_mcp(deps, "check_payment", args)
        claimed = (p.amount, p.status)
        if "error" in res:
            p.status, p.refusal_reasons, p.amount, p.balance_after = "refused", [res["error"]], None, None
        else:
            p.amount = res["amount"]
            p.balance_after = res["derived"]["balance_after_payment"]
            p.refusal_reasons = res["refusal_reasons"]
            p.status = "refused" if res["decision"] == "refuse" else "awaiting_human_approval"
            if p.status == "awaiting_human_approval":
                reserved[p.account] = reserved.get(p.account, 0.0) + p.amount
        checks.append(ToolCallRecord(tool="check_payment", args=args, ok="error" not in res,
                                     result_excerpt=json.dumps(res, default=str)[:600]))
        if claimed != (p.amount, p.status):
            deps.audit.append(
                event="guardrail_payment_corrected", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
                guardrail=f"Model said amount={claimed[0]} status={claimed[1]}; MCP says amount={p.amount} status={p.status}.",
            )
    if checks:
        deps.audit.append(
            event="guardrail_payment_check", ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
            tool_calls=checks, requires_human_approval=True,
            guardrail="Every payment re-checked via MCP check_payment; none executed; all need human approval.",
        )

    # 4. Anything that spends money or talks to a customer needs a human.
    output.needs_human_approval = (
        output.needs_human_approval
        or any(p.status == "awaiting_human_approval" for p in output.payment_proposals)
        or bool(output.draft_messages)
        or any(r.requires_human_approval for r in output.recommendations)
    )
    return output


# --- Building and running agents ----------------------------------------------

@lru_cache(maxsize=1)
def get_agents() -> dict[AgentName, Agent[TeamDeps, AgentReport]]:
    model = build_model()  # the single gpt-6-luna-via-Portkey model, shared by all five
    agents = {}
    for name, spec in SPECS.items():
        agent = Agent(
            model=model,
            name=name,
            instructions=_instructions_for(spec),
            deps_type=TeamDeps,
            output_type=AgentReport,
            model_settings=MODEL_SETTINGS,
            retries=AGENT_RETRIES,
            tools=[Tool(delegate)],
        )
        agent.output_validator(_guard_output)
        agents[name] = agent
    return agents


def _usage_dict(usage: Any) -> dict[str, int]:
    return {k: getattr(usage, k, 0) or 0 for k in ("requests", "input_tokens", "output_tokens", "tool_calls")}


def _audit_node(deps: TeamDeps, step: int, node: Any) -> None:
    common = dict(ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth, step=step)
    if Agent.is_user_prompt_node(node):
        deps.audit.append(event="loop_step_user_prompt", **common)
    elif Agent.is_model_request_node(node):
        sent = []
        for part in node.request.parts:
            if isinstance(part, ToolReturnPart):
                sent.append({"tool_return": part.tool_name, "content": str(part.content)[:300]})
            elif isinstance(part, RetryPromptPart):
                sent.append({"retry": part.tool_name, "content": str(part.content)[:500]})
        deps.audit.append(event="loop_step_model_request", result=sent or None, **common)
    elif Agent.is_call_tools_node(node):
        resp = node.model_response
        calls = [{"tool": p.tool_name, "args": p.args_as_dict()} for p in resp.parts if isinstance(p, ToolCallPart)]
        text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
        deps.audit.append(
            event="loop_step_model_response",
            result={"requested_tool_calls": calls, "text": text[:500] or None},
            usage=_usage_dict(resp.usage),
            **common,
        )
    elif Agent.is_end_node(node):
        deps.audit.append(event="loop_step_end", **common)


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage) -> AgentReport:
    """One agent's loop: model -> tools/delegations -> model ... -> AgentReport.

    `usage` is shared with every other agent in the run, so TEAM_USAGE_LIMITS
    caps the whole team, not just this agent."""
    agent = get_agents()[name]
    toolset = deps.shop.toolset_for(name, SPECS[name].mcp_tools)
    deps.audit.append(event="agent_loop_start", ticket_id=deps.ticket_id, agent=name, depth=deps.depth, task=task)

    step = 0
    async with agent.iter(
        task, deps=deps, usage=usage, usage_limits=TEAM_USAGE_LIMITS, toolsets=[toolset]
    ) as run:
        async for node in run:
            step += 1
            if step > MAX_LOOP_STEPS_PER_AGENT:
                msg = f"{name} exceeded {MAX_LOOP_STEPS_PER_AGENT} loop steps; stopped."
                deps.audit.append(event="guardrail_loop_limit", ticket_id=deps.ticket_id, agent=name,
                                  depth=deps.depth, step=step, guardrail=msg)
                raise AgentLoopLimit(msg)
            _audit_node(deps, step, node)

    report = run.result.output
    deps.audit.append(
        event="agent_loop_end", ticket_id=deps.ticket_id, agent=name, depth=deps.depth, step=step,
        result=report.model_dump(mode="json", exclude_defaults=True),
        requires_human_approval=report.needs_human_approval,
        usage=_usage_dict(usage),
    )
    return report
