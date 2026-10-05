import { useEffect, useRef, type ReactNode } from 'react'
import {
  ArrowRight, Ban, CircleCheck, CornerDownRight, Database, HandCoins, Inbox, Repeat, ShieldAlert, Sparkles,
  TriangleAlert, User,
} from 'lucide-react'
import { AGENTS, isAgent } from '../agents'
import { prettyTool, time } from '../format'
import type { AgentEvent } from '../types'
import { AgentAvatar, AgentTag } from './AgentAvatar'

function ToolChips({ tools }: { tools: string[] }) {
  if (!tools.length) return null
  return (
    <span className="tool-chips">
      {tools.map((t, i) => (
        <span key={`${t}-${i}`} className="tool-chip"><Database size={11} /> {prettyTool(t)}</span>
      ))}
    </span>
  )
}

function SystemLine({ icon, tone, children, at }: { icon: ReactNode; tone: string; children: ReactNode; at: string }) {
  return (
    <li className={`feed-system feed-system--${tone}`}>
      {icon}
      <span className="feed-system__text">{children}</span>
      <time>{time(at)}</time>
    </li>
  )
}

function FeedItem({ e }: { e: AgentEvent }) {
  const agent = isAgent(e.agent) ? e.agent : null
  const look = agent ? AGENTS[agent] : null
  const indent = { marginLeft: `${Math.min(e.depth, 3) * 18}px` }

  switch (e.event) {
    case 'run_start':
      return <SystemLine icon={<Sparkles size={14} />} tone="start" at={e.timestamp}>{e.summary}</SystemLine>
    case 'run_end':
      return <SystemLine icon={<CircleCheck size={14} />} tone="done" at={e.timestamp}>Team run finished.</SystemLine>
    case 'run_failed':
    case 'run_rejected':
      return <SystemLine icon={<TriangleAlert size={14} />} tone="error" at={e.timestamp}>Run failed: {e.error ?? e.summary}</SystemLine>
    case 'ticket_resolved':
      return <SystemLine icon={<CircleCheck size={14} />} tone="resolved" at={e.timestamp}>{e.summary}</SystemLine>
    case 'approvals_prepared':
      return <SystemLine icon={<HandCoins size={14} />} tone="approval" at={e.timestamp}>{e.summary}</SystemLine>
    case 'human_approval_executed':
    case 'human_approval_rejected':
      return <SystemLine icon={<User size={14} />} tone="human" at={e.timestamp}>{e.summary}</SystemLine>
    case 'human_approval_refused':
      return <SystemLine icon={<Ban size={14} />} tone="error" at={e.timestamp}>Approval refused by the database: {e.summary}</SystemLine>
  }
  if (!agent || !look) {
    return <SystemLine icon={<Inbox size={14} />} tone="muted" at={e.timestamp}>{e.summary}</SystemLine>
  }

  if (e.event === 'mcp_tool_call') {
    return (
      <li className={`feed-tool${e.error ? ' feed-tool--error' : ''}`} style={indent}>
        <CornerDownRight size={13} style={{ color: look.color }} />
        <Database size={12} />
        <span className="feed-tool__text">{e.summary.replace(/^Called MCP /, '')}</span>
        <time>{time(e.timestamp)}</time>
      </li>
    )
  }

  if (e.event.startsWith('delegation_') && e.delegation) {
    const to = e.delegation.to_agent
    const variant = e.event.replace('delegation_', '')
    const label = { start: 'hands off to', end: 'got the report from', refused: 'was refused handing off to',
      cached: 'reused an earlier answer from', failed: 'could not get an answer from' }[variant] ?? variant
    return (
      <li className={`feed-handoff feed-handoff--${variant}`} style={indent}>
        <AgentAvatar agent={agent} size={24} />
        {variant === 'start' ? <ArrowRight size={14} /> : <Repeat size={14} />}
        {isAgent(to) && <AgentAvatar agent={to} size={24} />}
        <div className="feed-handoff__body">
          <div><strong style={{ color: look.color }}>{look.title}</strong> {label} {isAgent(to) && <AgentTag agent={to} />}</div>
          {variant === 'start' && <div className="feed-quote">“{e.delegation.task}”</div>}
          {(variant === 'refused' || variant === 'failed') && e.delegation.reason && <div className="feed-note">{e.delegation.reason}</div>}
        </div>
        <time>{time(e.timestamp)}</time>
      </li>
    )
  }

  if (e.event.startsWith('guardrail')) {
    return (
      <li className="feed-guard" style={indent}>
        <ShieldAlert size={15} />
        <span><strong>Guardrail</strong> on {look.title}: {e.summary}</span>
        <time>{time(e.timestamp)}</time>
      </li>
    )
  }

  const isFinal = e.event === 'agent_loop_end'
  const isStart = e.event === 'agent_loop_start'
  return (
    <li className={`feed-msg${isFinal ? ' feed-msg--final' : ''}`} style={{ ...indent, ['--agent' as string]: look.color, ['--agent-soft' as string]: look.soft }}>
      <AgentAvatar agent={agent} size={30} />
      <div className="feed-msg__bubble">
        <div className="feed-msg__head">
          <strong style={{ color: look.color }}>{look.title}</strong>
          <span className="feed-msg__kind">{isFinal ? 'final report' : isStart ? 'picked up a task' : 'thinking'}</span>
          <time>{time(e.timestamp)}</time>
        </div>
        <div className={isStart ? 'feed-quote' : 'feed-msg__text'}>
          {isStart ? e.summary.replace(/^Started on task: /, '') : e.summary}
        </div>
        <ToolChips tools={e.mcp_tools} />
      </div>
    </li>
  )
}

interface Props {
  events: AgentEvent[]
  running: boolean
}

export function ActivityFeed({ events, running }: Props) {
  const listRef = useRef<HTMLOListElement>(null)
  const stick = useRef(true)

  useEffect(() => {
    const el = listRef.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [events.length])

  if (!events.length) {
    return (
      <div className="feed-empty">
        <Inbox size={28} />
        <p>{running ? 'Waiting for the first agent to speak…' : 'No agent activity yet for this ticket.'}</p>
        {!running && <p className="muted">Start the agent team to watch the Boss and specialists work it live.</p>}
      </div>
    )
  }
  return (
    <ol
      className="feed"
      ref={listRef}
      onScroll={(ev) => {
        const el = ev.currentTarget
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
      }}
    >
      {events.map((e) => <FeedItem key={e.seq} e={e} />)}
      {running && (
        <li className="feed-typing"><span /><span /><span /> agents working</li>
      )}
    </ol>
  )
}
