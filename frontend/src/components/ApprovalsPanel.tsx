import { Ban, CircleCheck, Clock, HandCoins, ShieldAlert, Undo2 } from 'lucide-react'
import { approvalTitle, money } from '../format'
import type { Approval, ApprovalStatus } from '../types'
import { AgentTag } from './AgentAvatar'

const ORDER: Record<ApprovalStatus, number> = { pending: 0, refused: 1, executed: 2, rejected: 3, void: 4 }

const STATUS: Record<ApprovalStatus, { label: string; icon: typeof Clock }> = {
  pending: { label: 'Needs your approval', icon: Clock },
  executed: { label: 'Approved & paid', icon: CircleCheck },
  refused: { label: 'Blocked by safety check', icon: ShieldAlert },
  rejected: { label: 'Rejected', icon: Ban },
  void: { label: 'Voided by reset', icon: Undo2 },
}

interface Props {
  approvals: Approval[]
  ticketId: number
  runId: string | null // the ticket's latest run since the last reset
  onApprove: (a: Approval) => void
  onReject: (a: Approval) => void
}

export function ApprovalsPanel({ approvals, ticketId, runId, onApprove, onReject }: Props) {
  // Pending approvals are always current (a reset voids them). Decided or refused ones are
  // shown only for the latest run, so history from before a reset doesn't look like today's state.
  const mine = approvals
    .filter((a) => a.ticket_id === ticketId && (a.status === 'pending' || (a.status !== 'void' && a.run_id === runId)))
    .sort((a, b) => ORDER[a.status] - ORDER[b.status] || b.created_at.localeCompare(a.created_at))
  const pending = mine.filter((a) => a.status === 'pending').length

  return (
    <section className={`panel approvals${pending ? ' approvals--attention' : ''}`} aria-label="Approvals">
      <div className="panel__head">
        <h2><HandCoins size={16} /> Approvals</h2>
        {pending > 0 && <span className="badge">{pending} waiting</span>}
      </div>
      {mine.length === 0 && (
        <p className="empty">Nothing needs approval for this ticket. Payments the agents prepare land here, and only you can execute them.</p>
      )}
      {mine.map((a) => {
        const s = STATUS[a.status]
        return (
          <article key={a.id} className={`approval approval--${a.status}`}>
            <div className="approval__status"><s.icon size={13} /> {s.label}</div>
            <div className="approval__row">
              <div className="approval__title">{approvalTitle(a)}</div>
              <div className="approval__amount">{money(a.amount)}</div>
            </div>
            <div className="approval__meta">
              Prepared by <AgentTag agent={a.prepared_by} /> · from {a.account}
            </div>
            <p className="approval__reason">{a.reason}</p>
            {a.refusal_reasons.length > 0 && a.status !== 'executed' && (
              <ul className="approval__reasons">{a.refusal_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            )}
            {a.last_error && a.status === 'pending' && <div className="approval__error">Last attempt refused: {a.last_error}</div>}
            {a.status === 'executed' && a.execution && (
              <div className="approval__done">
                {a.decided_by} approved · checking {money(a.execution.balance_before)} → <strong>{money(a.execution.balance_after)}</strong>
              </div>
            )}
            {a.status === 'rejected' && <div className="approval__done">Rejected by {a.decided_by}</div>}
            {a.status === 'pending' && (
              <div className="approval__actions">
                <button className="btn btn--approve" onClick={() => onApprove(a)}>Approve {money(a.amount)}</button>
                <button className="btn btn--ghost" onClick={() => onReject(a)}>Reject</button>
              </div>
            )}
          </article>
        )
      })}
    </section>
  )
}
