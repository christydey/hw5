// Thin client for the Problem 7 FastAPI backend. Every call maps to one route;
// no shop rules live here.
import type {
  Approval,
  CashResponse,
  EventsResponse,
  Health,
  Run,
  TicketsResponse,
} from './types'

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).join('; ')
          : `${res.status} ${res.statusText}`
    throw new ApiError(res.status, message)
  }
  return body as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/api/health'),
  tickets: () => request<TicketsResponse>('/api/tickets'),
  runTeam: (ticketId: number) => post<Run>(`/api/tickets/${ticketId}/run`),
  run: (runId: string) => request<Run>(`/api/runs/${runId}`),
  events: (params: { ticket_id?: number; run_id?: string; after_seq?: number; limit?: number; steps?: boolean }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => v !== undefined && q.set(k, String(v)))
    return request<EventsResponse>(`/api/events?${q}`)
  },
  approvals: (ticketId?: number) =>
    request<Approval[]>(`/api/approvals${ticketId !== undefined ? `?ticket_id=${ticketId}` : ''}`),
  approve: (id: string, approvedBy: string, confirmAmount: number) =>
    post<Approval>(`/api/approvals/${id}/approve`, { approved_by: approvedBy, confirm_amount: confirmAmount }),
  reject: (id: string, rejectedBy: string) => post<Approval>(`/api/approvals/${id}/reject`, { rejected_by: rejectedBy }),
  cash: () => request<CashResponse>('/api/cash'),
  reset: () => post<Record<string, unknown>>('/api/reset', { confirm: 'RESET' }),
}

