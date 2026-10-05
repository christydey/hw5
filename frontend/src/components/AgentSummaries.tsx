import { useState } from 'react'
import { ArrowRight, Database, ShieldAlert } from 'lucide-react'
import type { AgentActivity } from '../activity'
import { AGENTS } from '../agents'
import { prettyTool } from '../format'
import { AgentAvatar, AgentTag } from './AgentAvatar'

export function AgentSummaries({ activity, running }: { activity: AgentActivity[]; running: boolean }) {
  const involved = activity.filter((a) => a.involved).sort((a, b) => a.firstSeq - b.firstSeq)
  return (
    <section className="panel" aria-label="What each agent did">
      <div className="panel__head">
        <h2>Who did what</h2>
        {involved.length > 0 && <span className="panel__count">{involved.length} of 5 agents</span>}
      </div>
      {involved.length === 0 && <p className="empty">Agent summaries appear here once the team runs.</p>}
      <div className="summaries">
        {involved.map((a) => {
          const look = AGENTS[a.agent]
          return (
            <article key={a.agent} className="summary-card" style={{ ['--agent' as string]: look.color, ['--agent-soft' as string]: look.soft }}>
              <header>
                <AgentAvatar agent={a.agent} size={30} pulse={a.state === 'working'} />
                <div>
                  <div className="summary-card__name">{look.title}</div>
                  <div className="summary-card__role">{look.role}</div>
                </div>
              </header>
              {a.summaries.length ? (
                <LatestReport reports={a.summaries} />
              ) : (
                <p className="summary-card__text muted">{running ? 'Still working…' : 'No final report recorded.'}</p>
              )}
              <div className="summary-card__stats">
                {a.toolCalls > 0 && (
                  <span title={a.tools.join(', ')}><Database size={12} /> {a.toolCalls} MCP call{a.toolCalls > 1 ? 's' : ''}: {a.tools.map(prettyTool).join(', ')}</span>
                )}
                {a.delegatedTo.length > 0 && (
                  <span className="summary-card__handoffs"><ArrowRight size={12} /> {a.delegatedTo.map((d) => <AgentTag key={d} agent={d} />)}</span>
                )}
                {a.guardrails > 0 && <span className="summary-card__guard"><ShieldAlert size={12} /> {a.guardrails} guardrail check{a.guardrails > 1 ? 's' : ''}</span>}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

/** The agent's most recent final report, clamped so the card stays a summary. */
function LatestReport({ reports }: { reports: string[] }) {
  const [open, setOpen] = useState(false)
  const latest = reports[reports.length - 1]
  const long = latest.length > 260
  return (
    <>
      {reports.length > 1 && <span className="summary-card__n">Asked {reports.length}× · latest report</span>}
      <p className={`summary-card__text${long && !open ? ' clamp' : ''}`}>{latest}</p>
      {long && (
        <button className="link-btn" onClick={() => setOpen((o) => !o)}>{open ? 'Show less' : 'Show more'}</button>
      )}
    </>
  )
}
