import type { ReactNode } from 'react'
import { CircleCheck, HandCoins, LoaderCircle, Play, RotateCcw, TriangleAlert } from 'lucide-react'
import type { AgentActivity } from '../activity'
import { AGENTS } from '../agents'
import { TICKET_TYPE_LABEL, ticketLine } from '../format'
import type { AgentEvent, Ticket } from '../types'
import { ActivityFeed } from './ActivityFeed'
import { AgentAvatar } from './AgentAvatar'
import { StatusPill } from './TicketList'

interface Props {
  ticket: Ticket
  events: AgentEvent[]
  activity: AgentActivity[]
  running: boolean
  starting: boolean
  pendingApprovals: number
  onRun: () => void
}

function stateText(a: AgentActivity, running: boolean): string {
  if (a.state === 'working') return 'Working…'
  if (a.state === 'waiting') return `Waiting on ${a.waitingOn ? AGENTS[a.waitingOn].title : 'a teammate'}`
  if (a.state === 'done') return 'Done'
  return running ? 'Standing by' : 'Not called'
}

export function TicketDetail({ ticket, events, activity, running, starting, pendingApprovals, onRun }: Props) {
  const failed = events.some((e) => e.event === 'run_failed')
  const hasRun = events.length > 0
  // The agent actually doing the work right now (others in the chain are waiting on it).
  const speaking = activity.find((a) => a.state === 'working') ?? null

  let banner: { tone: string; icon: ReactNode; text: string } | null = null
  if (running) banner = { tone: 'running', icon: <LoaderCircle size={16} className="spin" />, text: 'The agent team is working this ticket. Activity streams in below.' }
  else if (failed) banner = { tone: 'error', icon: <TriangleAlert size={16} />, text: 'The last run failed before finishing. The ticket is still open; see the activity log for the error.' }
  else if (pendingApprovals > 0) banner = { tone: 'approval', icon: <HandCoins size={16} />, text: `${pendingApprovals} payment${pendingApprovals > 1 ? 's' : ''} prepared by the team need${pendingApprovals > 1 ? '' : 's'} your approval. Nothing has been paid yet.` }
  else if (!ticket.is_open) banner = { tone: 'resolved', icon: <CircleCheck size={16} />, text: 'Resolved. The team finished this ticket.' }

  return (
    <section className="panel detail" aria-label={`Ticket ${ticket.id}`}>
      <div className="detail__head">
        <div>
          <div className="detail__kicker">
            {TICKET_TYPE_LABEL[ticket.type] ?? ticket.type} · {ticket.requester}
          </div>
          <h1 className="detail__title"><span className="detail__id">#{ticket.id}</span> {ticket.subject}</h1>
          <div className="detail__meta">
            <span className="mono">{ticketLine(ticket)}</span>
            {ticket.invoice_id && <span className="mono">Invoice #{ticket.invoice_id}</span>}
            {ticket.notes && <span className="detail__note">“{ticket.notes}”</span>}
          </div>
        </div>
        <div className="detail__actions">
          <StatusPill ticket={ticket} running={running || starting} />
          {ticket.is_open ? (
            <button className="btn btn--primary" onClick={onRun} disabled={running || starting}>
              {running || starting ? <><LoaderCircle size={16} className="spin" /> Agents working…</> : <><Play size={16} /> {hasRun ? 'Run team again' : 'Start agent team'}</>}
            </button>
          ) : (
            <span className="detail__hint"><RotateCcw size={13} /> Reset the shop to run it again</span>
          )}
        </div>
      </div>

      {banner && <div className={`banner banner--${banner.tone}`}>{banner.icon}<span>{banner.text}</span></div>}

      <div className="roster" aria-label="Agent team">
        {activity.map((a) => {
          const look = AGENTS[a.agent]
          return (
            <div
              key={a.agent}
              className={`roster__agent roster__agent--${a.state}${!a.involved && hasRun && !running ? ' roster__agent--skipped' : ''}`}
              style={{ ['--agent' as string]: look.color, ['--agent-soft' as string]: look.soft }}
            >
              <AgentAvatar agent={a.agent} size={40} pulse={a.state === 'working'} dim={!a.involved && hasRun} />
              <div className="roster__text">
                <div className="roster__name">{look.title}</div>
                <div className="roster__state">{stateText(a, running)}</div>
              </div>
            </div>
          )
        })}
      </div>

      {running && speaking && (
        <div className="now" style={{ ['--agent' as string]: AGENTS[speaking.agent].color }}>
          <span className="now__label">Now</span>
          <AgentAvatar agent={speaking.agent} size={22} pulse />
          <strong>{AGENTS[speaking.agent].title}</strong>
          <span className="now__text">{speaking.lastLine ?? 'Working…'}</span>
        </div>
      )}

      <div className="detail__feed-head">
        <h2>Live activity</h2>
        <span className="muted">from output/audit_trail.json via /api/events</span>
      </div>
      <ActivityFeed events={events} running={running} />
    </section>
  )
}
