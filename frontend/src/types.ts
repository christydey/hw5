// Mirrors the Pydantic models in backend/models.py. Keep in sync.

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  is_open: boolean
  active_run_id: string | null
  pending_approvals: number
}

export interface TicketsResponse {
  date_today: string | null
  tickets: Ticket[]
}

export interface Fact {
  statement: string
  source: string
}

export interface Recommendation {
  action: string
  rationale: string
  owner: AgentName
  requires_human_approval: boolean
}

export interface PaymentProposal {
  kind: 'invoice' | 'lease_rent' | 'purchase_order'
  ref_id: number | null
  sku: string | null
  qty: number | null
  vendor_id: number | null
  account: string
  reason: string
  amount: number | null
  balance_after: number | null
  status: 'awaiting_human_approval' | 'refused'
  refusal_reasons: string[]
}

export interface DraftMessage {
  recipient: string
  channel: 'email' | 'phone_script' | 'in_store_note'
  subject: string
  body: string
  status: 'draft_pending_human_review'
}

export interface AgentReport {
  agent: AgentName
  ticket_id: number | null
  summary: string
  facts: Fact[]
  recommendations: Recommendation[]
  payment_proposals: PaymentProposal[]
  draft_messages: DraftMessage[]
  open_questions: string[]
  needs_human_approval: boolean
}

export type ApprovalStatus = 'pending' | 'executed' | 'rejected' | 'refused' | 'void'

export interface Approval {
  id: string
  run_id: string
  ticket_id: number
  created_at: string
  prepared_by: AgentName
  kind: PaymentProposal['kind']
  ref_id: number | null
  sku: string | null
  qty: number | null
  vendor_id: number | null
  account: string
  reason: string
  amount: number | null
  expected_next_due: string | null
  status: ApprovalStatus
  refusal_reasons: string[]
  decided_by: string | null
  decided_at: string | null
  note: string | null
  last_error: string | null
  execution: {
    payment: Record<string, unknown>
    balance_before: number
    balance_after: number
    tables_updated: string[]
  } | null
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'running' | 'completed' | 'failed'
  started_at: string
  finished_at: string | null
  report: AgentReport | null
  delegate_reports: AgentReport[]
  approvals: Approval[]
  delegations_used: number | null
  usage: Record<string, number> | null
  error: string | null
}

export interface AgentEvent {
  seq: number
  timestamp: string
  run_id: string
  ticket_id: number | null
  agent: AgentName | null
  depth: number
  event: string
  summary: string
  mcp_tools: string[]
  delegation: {
    from_agent: AgentName
    to_agent: AgentName
    task: string
    depth: number
    status: string
    reason?: string | null
  } | null
  requires_human_approval: boolean | null
  guardrail: string | null
  error: string | null
}

export interface EventsResponse {
  total_records: number
  returned: number
  events: AgentEvent[]
}

export interface CashResponse {
  account: string
  balance: number
  as_of: string
  date_today: string | null
  accounts: { name: string; balance: number; date: string }[]
}

export interface Health {
  status: string
  model: string
  mcp_tools: string[]
  active_runs: string[]
}
