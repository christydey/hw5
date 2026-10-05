// Visual identity for the five agents. Purely presentational.
import { Building2, Calculator, Crown, MessagesSquare, Package, type LucideIcon } from 'lucide-react'
import type { AgentName } from './types'

export interface AgentLook {
  name: AgentName
  title: string
  role: string
  color: string // solid accent
  soft: string // tinted background
  icon: LucideIcon
  initials: string
}

export const AGENTS: Record<AgentName, AgentLook> = {
  boss: {
    name: 'boss', title: 'Boss', role: 'Coordinates the desk',
    color: '#ff4fa3', soft: 'rgba(255, 79, 163, 0.14)', icon: Crown, initials: 'BS',
  },
  inventory: {
    name: 'inventory', title: 'Inventory', role: 'Stock, vendors, lead times',
    color: '#2dd4bf', soft: 'rgba(45, 212, 191, 0.13)', icon: Package, initials: 'IN',
  },
  accounting: {
    name: 'accounting', title: 'Accounting', role: 'Cash, invoices, margins',
    color: '#fbbf24', soft: 'rgba(251, 191, 36, 0.13)', icon: Calculator, initials: 'AC',
  },
  facilities: {
    name: 'facilities', title: 'Facilities', role: 'Lease and rent',
    color: '#a78bfa', soft: 'rgba(167, 139, 250, 0.14)', icon: Building2, initials: 'FA',
  },
  customer_service: {
    name: 'customer_service', title: 'Customer Service', role: 'Drafts replies',
    color: '#38bdf8', soft: 'rgba(56, 189, 248, 0.13)', icon: MessagesSquare, initials: 'CS',
  },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const isAgent = (name: string | null | undefined): name is AgentName =>
  !!name && name in AGENTS
