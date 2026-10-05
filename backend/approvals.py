"""The human-approval queue at output/approvals.json.

After a team run, every payment or purchase the agents proposed becomes an
Approval. Its amount, and for rent the due date being paid, are re-read from
the database through MCP check_payment, never taken from the model. Only a
human, through the API, can move a pending approval to executed or rejected.
Executing it is a signed MCP write (execute_approved_payment), done by
backend/main.py.

This file holds workflow state (who approved what), not shop data. The shop
data itself only changes through MCP.
"""

from __future__ import annotations

import fcntl
import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .audit import atomic_write_json
from .config import PROJECT_ROOT
from .mcp_bridge import ShopMCP
from .models import AgentReport, Approval

APPROVALS_FILE = PROJECT_ROOT / "output" / "approvals.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _key(kind: str, ref_id, sku, qty, vendor_id, account: str) -> tuple:
    return (kind, ref_id, sku, qty, vendor_id, account)


class ApprovalStore:
    def __init__(self, path: Path = APPROVALS_FILE):
        self.path = path
        self._lock_path = path.parent / f".{path.name}.lock"

    @contextmanager
    def _locked(self) -> Iterator[list[Approval]]:
        """Load all approvals under an exclusive lock; changes are saved on exit."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            raw = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"approvals": []}
            items = [Approval.model_validate(a) for a in raw["approvals"]]
            yield items
            atomic_write_json(self.path, {"note": "Human-approval queue. Workflow state only.",
                                          "approvals": [a.model_dump(mode="json") for a in items]})

    def list(self, status: str | None = None, ticket_id: int | None = None) -> list[Approval]:
        if not self.path.exists():
            return []
        items = [Approval.model_validate(a) for a in json.loads(self.path.read_text(encoding="utf-8"))["approvals"]]
        return [a for a in items
                if (status is None or a.status == status) and (ticket_id is None or a.ticket_id == ticket_id)]

    def get(self, approval_id: str) -> Approval | None:
        return next((a for a in self.list() if a.id == approval_id), None)

    def update(self, approval_id: str, change: Callable[[Approval], None]) -> Approval | None:
        with self._locked() as items:
            for a in items:
                if a.id == approval_id:
                    change(a)
                    return a
        return None

    def void_pending(self, reason: str) -> int:
        with self._locked() as items:
            pending = [a for a in items if a.status == "pending"]
            for a in pending:
                a.status, a.note, a.decided_at = "void", reason, _now()
        return len(pending)

    async def prepare_from_run(
        self, shop: ShopMCP, run_id: str, ticket_id: int, reports: list[AgentReport]
    ) -> list[Approval]:
        """Turn the run's payment proposals into approvals. Duplicates (the
        same payment proposed by two agents, or already pending from an
        earlier run) are not added twice."""
        seen: dict[tuple, Approval] = {}
        existing = {_key(a.kind, a.ref_id, a.sku, a.qty, a.vendor_id, a.account): a
                    for a in self.list(status="pending")}
        # Accounting's own proposals first, so it is credited when the Boss relays the same one.
        ordered = sorted(reports, key=lambda r: r.agent != "accounting")
        for report in ordered:
            for p in report.payment_proposals:
                k = _key(p.kind, p.ref_id, p.sku, p.qty, p.vendor_id, p.account)
                if k in seen or k in existing:
                    continue
                args = {"kind": p.kind, "account": p.account}
                args.update({f: v for f, v in {"ref_id": p.ref_id, "sku": p.sku, "qty": p.qty,
                                                "vendor_id": p.vendor_id}.items() if v is not None})
                check = await shop.call("check_payment", args)
                if "error" in check:
                    status, reasons, amount, next_due = "refused", [check["error"]], None, None
                else:
                    eligible = check["decision"] == "eligible_for_human_approval" and p.status == "awaiting_human_approval"
                    status = "pending" if eligible else "refused"
                    reasons = list(dict.fromkeys(check["refusal_reasons"] + p.refusal_reasons))
                    amount = check["amount"]
                    next_due = check.get("lease", {}).get("next_due") if p.kind == "lease_rent" else None
                seen[k] = Approval(
                    id=uuid.uuid4().hex[:10], run_id=run_id, ticket_id=ticket_id, created_at=_now(),
                    prepared_by=report.agent, kind=p.kind, ref_id=p.ref_id, sku=p.sku, qty=p.qty,
                    vendor_id=p.vendor_id, account=p.account, reason=p.reason, amount=amount,
                    expected_next_due=next_due, status=status, refusal_reasons=reasons,
                )
        if seen:
            with self._locked() as items:
                items.extend(seen.values())
        return list(seen.values()) + [a for k, a in existing.items()
                                      if any(_key(p.kind, p.ref_id, p.sku, p.qty, p.vendor_id, p.account) == k
                                             for r in reports for p in r.payment_proposals)]
