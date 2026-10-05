import { useMemo, useState } from 'react'
import { Plug, TriangleAlert, X } from 'lucide-react'
import { agentActivity } from './activity'
import { API_BASE } from './api'
import { AgentSummaries } from './components/AgentSummaries'
import { ApprovalsPanel } from './components/ApprovalsPanel'
import { DecisionDialog, ResetDialog } from './components/Dialogs'
import { Header } from './components/Header'
import { TicketDetail } from './components/TicketDetail'
import { TicketList } from './components/TicketList'
import type { Approval } from './types'
import { useDesk } from './useDesk'

export default function App() {
  const desk = useDesk()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [decision, setDecision] = useState<{ approval: Approval; mode: 'approve' | 'reject' } | null>(null)
  const [resetOpen, setResetOpen] = useState(false)

  const tickets = desk.tickets
  const selected = tickets?.find((t) => t.id === selectedId) ?? tickets?.find((t) => t.is_open) ?? tickets?.[0] ?? null
  const running = !!selected && (!!selected.active_run_id || !!desk.starting[selected.id])
  const events = useMemo(() => (selected ? desk.ticketEvents(selected.id) : []), [selected, desk])
  const activity = useMemo(() => agentActivity(events, running), [events, running])
  const pendingTotal = desk.approvals.filter((a) => a.status === 'pending').length
  const pendingHere = selected ? desk.approvals.filter((a) => a.ticket_id === selected.id && a.status === 'pending').length : 0

  return (
    <div className="app">
      <Header
        dateToday={desk.dateToday}
        cash={desk.cash}
        cashChange={desk.cashChange}
        online={!desk.connectionError}
        pendingApprovals={pendingTotal}
        resetDisabled={desk.anyRunning || !!desk.connectionError}
        onReset={() => setResetOpen(true)}
      />

      {desk.connectionError && (
        <div className="banner banner--error banner--page">
          <Plug size={16} />
          <span>
            {desk.connectionError} Start it with <code>cd backend && uvicorn main:app --reload --port 8000</code>. Retrying…
          </span>
        </div>
      )}
      {desk.actionError && (
        <div className="banner banner--error banner--page">
          <TriangleAlert size={16} />
          <span>{desk.actionError}</span>
          <button className="icon-btn" onClick={desk.clearActionError} aria-label="Dismiss"><X size={16} /></button>
        </div>
      )}

      <main className="layout">
        <TicketList tickets={tickets} selectedId={selected?.id ?? null} starting={desk.starting} onSelect={setSelectedId} />

        {selected ? (
          <TicketDetail
            ticket={selected}
            events={events}
            activity={activity}
            running={running}
            starting={!!desk.starting[selected.id]}
            pendingApprovals={pendingHere}
            onRun={() => desk.startRun(selected.id)}
          />
        ) : (
          <section className="panel detail detail--empty">
            {tickets === null ? (
              desk.connectionError ? <p className="empty">Can't load tickets from {API_BASE}.</p> : <div className="loader">Loading the desk…</div>
            ) : (
              <p className="empty">No tickets to show.</p>
            )}
          </section>
        )}

        <aside className="rail">
          {selected && (
            <ApprovalsPanel
              approvals={desk.approvals}
              ticketId={selected.id}
              runId={events[0]?.run_id ?? null}
              onApprove={(a) => setDecision({ approval: a, mode: 'approve' })}
              onReject={(a) => setDecision({ approval: a, mode: 'reject' })}
            />
          )}
          <AgentSummaries activity={activity} running={running} />
        </aside>
      </main>

      <footer className="footer">
        Agents prepare · humans approve · every step is logged to <code>output/audit_trail.json</code> · API {API_BASE}
      </footer>

      {decision && (
        <DecisionDialog
          approval={decision.approval}
          mode={decision.mode}
          balance={desk.cash?.balance ?? null}
          onConfirm={(name) => (decision.mode === 'approve' ? desk.approve(decision.approval, name) : desk.reject(decision.approval, name))}
          onClose={() => setDecision(null)}
        />
      )}
      {resetOpen && <ResetDialog onConfirm={desk.reset} onClose={() => setResetOpen(false)} />}
    </div>
  )
}
