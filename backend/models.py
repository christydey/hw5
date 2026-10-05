"""Shared data types for the Campus Customs agent team.

- AgentReport (and its parts) is what every agent returns.
- TeamDeps / RunBudget are the per-run state passed down each delegation.
- AuditRecord is one line of output/audit_trail.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .audit import AuditTrail
    from .mcp_bridge import ShopMCP

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

PaymentKind = Literal["invoice", "lease_rent", "purchase_order"]


# --- What an agent returns ----------------------------------------------------

class Fact(BaseModel):
    """One shop fact the agent relied on, with where it came from."""

    statement: str = Field(max_length=400)
    source: str = Field(
        description="The MCP tool name that returned this fact (e.g. 'get_ticket'), "
        "or 'agent:<name>' if a teammate you delegated to reported it.",
        max_length=80,
    )


class PaymentProposal(BaseModel):
    """A payment the team suggests. It is never executed by an agent.

    amount, balance_after, status and refusal_reasons are overwritten by the
    payment guardrail with what the MCP check_payment tool reports, so a
    model cannot invent an amount or wave through an overdraft.
    """

    kind: PaymentKind
    ref_id: int | None = Field(default=None, ge=1, description="invoices.id or leases.id")
    sku: str | None = Field(default=None, max_length=40, description="purchase_order only")
    qty: int | None = Field(default=None, ge=1, le=1000, description="purchase_order only")
    vendor_id: int | None = Field(default=None, ge=1, description="purchase_order only")
    account: str = Field(default="checking", max_length=40)
    reason: str = Field(max_length=600)
    amount: float | None = None
    balance_after: float | None = None
    status: Literal["awaiting_human_approval", "refused"] = "awaiting_human_approval"
    refusal_reasons: list[str] = Field(default_factory=list)
    requires_human_approval: Literal[True] = True


class DraftMessage(BaseModel):
    """A customer- or vendor-facing message. Always a draft; nothing is sent."""

    recipient: str = Field(max_length=120)
    channel: Literal["email", "phone_script", "in_store_note"] = "email"
    subject: str = Field(max_length=200)
    body: str = Field(max_length=3000)
    status: Literal["draft_pending_human_review"] = "draft_pending_human_review"


class Recommendation(BaseModel):
    action: str = Field(max_length=400)
    rationale: str = Field(max_length=800)
    owner: AgentName
    requires_human_approval: bool


class AgentReport(BaseModel):
    """The structured result of one agent run (Boss and specialists alike)."""

    agent: AgentName
    ticket_id: int | None
    summary: str = Field(max_length=2000)
    facts: list[Fact] = Field(default_factory=list, max_length=30)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=12)
    payment_proposals: list[PaymentProposal] = Field(default_factory=list, max_length=6)
    draft_messages: list[DraftMessage] = Field(default_factory=list, max_length=4)
    open_questions: list[str] = Field(default_factory=list, max_length=8)
    needs_human_approval: bool = False


# --- Delegation and tool-call records ----------------------------------------

class ToolCallRecord(BaseModel):
    tool: str
    args: dict[str, Any]
    ok: bool
    cached: bool = False
    result_excerpt: str | None = None


class DelegationRecord(BaseModel):
    from_agent: AgentName
    to_agent: AgentName
    task: str
    depth: int
    status: Literal["completed", "refused", "failed", "cached"]
    reason: str | None = None


class AuditRecord(BaseModel):
    seq: int
    timestamp: str
    run_id: str
    ticket_id: int | None
    agent: AgentName | None
    depth: int = 0
    step: int | None = None
    event: str
    task: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    delegation: DelegationRecord | None = None
    result: Any = None
    requires_human_approval: bool | None = None
    guardrail: str | None = None
    error: str | None = None
    usage: dict[str, int] | None = None


# --- Human approvals (Problem 7) ----------------------------------------------

ApprovalStatus = Literal["pending", "executed", "rejected", "refused", "void"]


class Approval(BaseModel):
    """A payment or purchase an agent prepared, waiting for a human.

    pending  -> a human may approve (executes via MCP) or reject it
    refused  -> failed the DB checks when prepared (overdraft, blocked vendor); cannot be approved
    executed -> a human approved it and the MCP write succeeded
    rejected -> a human declined it
    void     -> cancelled by a database reset before anyone decided
    """

    id: str
    run_id: str
    ticket_id: int
    created_at: str
    prepared_by: AgentName
    kind: PaymentKind
    ref_id: int | None = None
    sku: str | None = None
    qty: int | None = None
    vendor_id: int | None = None
    account: str = "checking"
    reason: str
    amount: float | None  # from the database (check_payment), never from the model
    expected_next_due: str | None = None  # lease_rent: the due date being paid, to block double payment
    status: ApprovalStatus
    refusal_reasons: list[str] = Field(default_factory=list)
    decided_by: str | None = None
    decided_at: str | None = None
    note: str | None = None
    last_error: str | None = None
    execution: dict[str, Any] | None = None


# --- API request / response bodies (backend/main.py) --------------------------

class TicketOut(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None
    size: str | None
    qty: int | None
    lease_id: int | None
    invoice_id: int | None
    status: str
    notes: str | None
    created_at: str
    is_open: bool
    active_run_id: str | None = None
    pending_approvals: int = 0


class TicketsResponse(BaseModel):
    date_today: str | None
    tickets: list[TicketOut]


class RunRequest(BaseModel):
    task: str | None = Field(default=None, min_length=10, max_length=1500,
                             description="Optional override of the Boss's default task.")


class RunOut(BaseModel):
    run_id: str
    ticket_id: int
    status: Literal["running", "completed", "failed"]
    started_at: str
    finished_at: str | None = None
    report: AgentReport | None = None
    delegate_reports: list[AgentReport] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    delegations_used: int | None = None
    usage: dict[str, int] | None = None
    error: str | None = None


class AgentEvent(BaseModel):
    seq: int
    timestamp: str
    run_id: str
    ticket_id: int | None
    agent: str | None
    depth: int = 0
    event: str
    summary: str
    mcp_tools: list[str] = Field(default_factory=list)
    delegation: dict[str, Any] | None = None
    requires_human_approval: bool | None = None
    guardrail: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


class EventsResponse(BaseModel):
    total_records: int
    returned: int
    events: list[AgentEvent]


class ApproveRequest(BaseModel):
    approved_by: str = Field(min_length=1, max_length=80, description="The human approving.")
    confirm_amount: float = Field(gt=0, description="Must equal the approval's amount, as a deliberate confirmation.")
    note: str | None = Field(default=None, max_length=500)


class RejectRequest(BaseModel):
    rejected_by: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class ResolveRequest(BaseModel):
    resolved_by: str = Field(min_length=1, max_length=80)


class ResetRequest(BaseModel):
    confirm: Literal["RESET"] = Field(description='Must be the literal string "RESET".')


class CashResponse(BaseModel):
    account: str
    balance: float
    as_of: str
    date_today: str | None
    accounts: list[dict[str, Any]]


# --- Per-run state passed down each delegation --------------------------------

@dataclass
class RunBudget:
    """Shared by every agent in one ticket run."""

    delegations_used: int = 0
    # (to_agent, normalised task) -> report, so the same question is never asked twice
    delegation_cache: dict[tuple[str, str], AgentReport] = field(default_factory=dict)
    # (tool, sorted args) -> result; the database does not change during a run
    mcp_cache: dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamDeps:
    run_id: str
    ticket_id: int | None
    agent: AgentName
    chain: tuple[AgentName, ...]  # who is currently waiting on whom, root first
    budget: RunBudget
    audit: AuditTrail
    shop: ShopMCP
    # Filled during this agent's run; used to check that cited facts are real.
    tools_called: set[str] = field(default_factory=set)
    delegated_to: set[str] = field(default_factory=set)

    @property
    def depth(self) -> int:
        return len(self.chain) - 1

    def for_delegate(self, to_agent: AgentName) -> TeamDeps:
        return TeamDeps(
            run_id=self.run_id,
            ticket_id=self.ticket_id,
            agent=to_agent,
            chain=(*self.chain, to_agent),
            budget=self.budget,
            audit=self.audit,
            shop=self.shop,
        )
