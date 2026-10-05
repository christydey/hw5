import { AGENTS } from '../agents'
import type { AgentName } from '../types'

interface Props {
  agent: AgentName
  size?: number
  pulse?: boolean
  dim?: boolean
}

export function AgentAvatar({ agent, size = 36, pulse = false, dim = false }: Props) {
  const look = AGENTS[agent]
  const Icon = look.icon
  return (
    <span
      className={`avatar${pulse ? ' avatar--pulse' : ''}${dim ? ' avatar--dim' : ''}`}
      style={{ width: size, height: size, color: look.color, background: look.soft, borderColor: look.color }}
      title={look.title}
      aria-label={look.title}
    >
      <Icon size={Math.round(size * 0.5)} strokeWidth={2.2} />
    </span>
  )
}

export function AgentTag({ agent }: { agent: AgentName }) {
  const look = AGENTS[agent]
  return (
    <span className="agent-tag" style={{ color: look.color, background: look.soft }}>
      <look.icon size={12} strokeWidth={2.4} />
      {look.title}
    </span>
  )
}
