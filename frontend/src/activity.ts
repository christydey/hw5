// Groups a ticket's audit events by agent for the roster and summary cards.
// Reads only what the backend recorded.
import { AGENT_ORDER } from './agents'
import type { AgentEvent, AgentName } from './types'

export type AgentState = 'idle' | 'working' | 'waiting' | 'done'

export interface AgentActivity {
  agent: AgentName
  state: AgentState
  involved: boolean
  firstSeq: number
  waitingOn: AgentName | null
  lastLine: string | null
  summaries: string[] // one per finished task (an agent can be asked more than once)
  tools: string[] // distinct MCP tools it called
  toolCalls: number
  delegatedTo: AgentName[]
  guardrails: number
}

export function agentActivity(events: AgentEvent[], runActive: boolean): AgentActivity[] {
  const by = new Map<AgentName, AgentActivity>()
  for (const name of AGENT_ORDER) {
    by.set(name, {
      agent: name, state: 'idle', involved: false, firstSeq: Infinity, waitingOn: null, lastLine: null,
      summaries: [], tools: [], toolCalls: 0, delegatedTo: [], guardrails: 0,
    })
  }
  const open = new Map<AgentName, number>() // agent -> unfinished loops
  const depthOf = new Map<AgentName, number>()
  const pendingDelegation = new Map<AgentName, AgentName>()

  for (const e of events) {
    if (!e.agent || !by.has(e.agent)) continue
    const a = by.get(e.agent)!
    a.involved = true
    a.firstSeq = Math.min(a.firstSeq, e.seq)
    switch (e.event) {
      case 'agent_loop_start':
        open.set(e.agent, (open.get(e.agent) ?? 0) + 1)
        depthOf.set(e.agent, e.depth)
        break
      case 'agent_loop_end':
        open.set(e.agent, Math.max((open.get(e.agent) ?? 1) - 1, 0))
        a.summaries.push(e.summary)
        break
      case 'mcp_tool_call':
        a.toolCalls += 1
        e.mcp_tools.forEach((t) => !a.tools.includes(t) && a.tools.push(t))
        break
      case 'delegation_start':
        if (e.delegation) {
          pendingDelegation.set(e.agent, e.delegation.to_agent)
          if (!a.delegatedTo.includes(e.delegation.to_agent)) a.delegatedTo.push(e.delegation.to_agent)
        }
        break
      case 'delegation_end':
      case 'delegation_failed':
        pendingDelegation.delete(e.agent)
        break
    }
    if (e.event.startsWith('guardrail')) a.guardrails += 1
    if (e.event !== 'run_start' && e.event !== 'run_end') a.lastLine = e.summary
  }

  for (const a of by.values()) {
    const unfinished = (open.get(a.agent) ?? 0) > 0
    if (unfinished && runActive) {
      const waitingOn = pendingDelegation.get(a.agent) ?? null
      a.state = waitingOn ? 'waiting' : 'working'
      a.waitingOn = waitingOn
    } else {
      a.state = a.involved ? 'done' : 'idle'
    }
  }
  return [...by.values()]
}
