import { Building2, CircleCheck, HandCoins, LoaderCircle, ShoppingBag, Tag } from 'lucide-react'
import { TICKET_TYPE_LABEL, ticketLine } from '../format'
import type { Ticket } from '../types'

const TYPE_ICON: Record<string, typeof Tag> = {
  customer_order: ShoppingBag,
  rent_notice: Building2,
  price_override: Tag,
}

export function StatusPill({ ticket, running }: { ticket: Ticket; running: boolean }) {
  if (running)
    return <span className="pill pill--running"><LoaderCircle size={12} className="spin" /> Running</span>
  if (ticket.is_open) return <span className="pill pill--open"><span className="dot" /> Open</span>
  return <span className="pill pill--resolved"><CircleCheck size={12} /> Resolved</span>
}

interface Props {
  tickets: Ticket[] | null
  selectedId: number | null
  starting: Record<number, boolean>
  onSelect: (id: number) => void
}

export function TicketList({ tickets, selectedId, starting, onSelect }: Props) {
  const open = tickets?.filter((t) => t.is_open).length ?? 0
  return (
    <section className="panel ticket-list" aria-label="Tickets">
      <div className="panel__head">
        <h2>Tickets</h2>
        {tickets && <span className="panel__count">{open} open · {tickets.length - open} resolved</span>}
      </div>

      {tickets === null && [0, 1, 2].map((i) => <div key={i} className="ticket-card skeleton" />)}
      {tickets?.length === 0 && <p className="empty">No tickets in the database.</p>}

      {tickets?.map((t) => {
        const Icon = TYPE_ICON[t.type] ?? Tag
        const running = !!t.active_run_id || !!starting[t.id]
        const state = running ? 'running' : t.is_open ? 'open' : 'resolved'
        return (
          <button
            key={t.id}
            className={`ticket-card ticket-card--${state}${selectedId === t.id ? ' is-selected' : ''}`}
            onClick={() => onSelect(t.id)}
            aria-pressed={selectedId === t.id}
          >
            <div className="ticket-card__top">
              <span className="ticket-card__type"><Icon size={15} /> {TICKET_TYPE_LABEL[t.type] ?? t.type}</span>
              <StatusPill ticket={t} running={running} />
            </div>
            <div className="ticket-card__title">
              <span className="ticket-card__id">#{t.id}</span> {t.subject}
            </div>
            <div className="ticket-card__meta">{t.requester}</div>
            <div className="ticket-card__meta ticket-card__mono">{ticketLine(t)}</div>
            {t.pending_approvals > 0 && (
              <div className="ticket-card__flag"><HandCoins size={13} /> {t.pending_approvals} awaiting your approval</div>
            )}
            {state === 'resolved' && <span className="stamp" aria-hidden>Resolved</span>}
          </button>
        )
      })}
    </section>
  )
}
