// All dashboard state, loaded from the Problem 7 API. Polls quickly while an
// agent run is in progress and slowly otherwise. Nothing here decides shop
// outcomes; it only fetches, groups for display, and calls routes on request.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from './api'
import type { AgentEvent, Approval, CashResponse, Ticket } from './types'

const FAST_MS = 1500
const SLOW_MS = 5000

export interface CashChange {
  from: number
  to: number
  at: number
}

export function useDesk() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [dateToday, setDateToday] = useState<string | null>(null)
  const [cash, setCash] = useState<CashResponse | null>(null)
  const [cashChange, setCashChange] = useState<CashChange | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [starting, setStarting] = useState<Record<number, boolean>>({})
  const [actionError, setActionError] = useState<string | null>(null)

  const lastSeq = useRef(0)
  const lastBalance = useRef<number | null>(null)
  const inFlight = useRef(false)

  const refresh = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const [t, a, c, ev] = await Promise.all([
        api.tickets(),
        api.approvals(),
        api.cash(),
        api.events({ steps: false, limit: 1000, after_seq: lastSeq.current || undefined }),
      ])
      setTickets(t.tickets)
      setDateToday(t.date_today)
      setApprovals(a)
      if (lastBalance.current !== null && lastBalance.current !== c.balance) {
        setCashChange({ from: lastBalance.current, to: c.balance, at: Date.now() })
      }
      lastBalance.current = c.balance
      setCash(c)
      if (ev.events.length) {
        lastSeq.current = ev.events[ev.events.length - 1].seq
        setEvents((prev) => [...prev, ...ev.events])
      }
      setConnectionError(null)
    } catch (e) {
      setConnectionError(e instanceof ApiError ? e.message : String(e))
    } finally {
      inFlight.current = false
    }
  }, [])

  const anyRunning = !!tickets?.some((t) => t.active_run_id) || Object.values(starting).some(Boolean)

  useEffect(() => {
    refresh()
    const id = window.setInterval(refresh, anyRunning ? FAST_MS : SLOW_MS)
    return () => window.clearInterval(id)
  }, [refresh, anyRunning])

  // --- grouping for display ---------------------------------------------------
  const resetSeq = useMemo(
    () => events.reduce((s, e) => (e.event === 'database_reset' ? e.seq : s), 0),
    [events],
  )

  /** Events for a ticket from its most recent run since the last database reset. */
  const ticketEvents = useCallback(
    (ticketId: number): AgentEvent[] => {
      const start = events.reduce(
        (s, e) => (e.event === 'run_start' && e.ticket_id === ticketId && e.seq > resetSeq ? e.seq : s),
        0,
      )
      return start ? events.filter((e) => e.ticket_id === ticketId && e.seq >= start) : []
    },
    [events, resetSeq],
  )

  // --- actions (each is one API call) --------------------------------------------
  const startRun = useCallback(
    async (ticketId: number) => {
      setActionError(null)
      setStarting((s) => ({ ...s, [ticketId]: true }))
      try {
        await api.runTeam(ticketId)
        await refresh()
      } catch (e) {
        setActionError(e instanceof Error ? e.message : String(e))
      } finally {
        setStarting((s) => ({ ...s, [ticketId]: false }))
      }
    },
    [refresh],
  )

  const approve = useCallback(
    async (a: Approval, approvedBy: string) => {
      await api.approve(a.id, approvedBy, a.amount ?? 0)
      await refresh()
    },
    [refresh],
  )

  const reject = useCallback(
    async (a: Approval, rejectedBy: string) => {
      await api.reject(a.id, rejectedBy)
      await refresh()
    },
    [refresh],
  )

  const reset = useCallback(async () => {
    await api.reset()
    setCashChange(null)
    await refresh()
  }, [refresh])

  return {
    tickets,
    dateToday,
    cash,
    cashChange,
    approvals,
    connectionError,
    actionError,
    clearActionError: () => setActionError(null),
    starting,
    anyRunning,
    ticketEvents,
    startRun,
    approve,
    reject,
    reset,
  }
}

export type Desk = ReturnType<typeof useDesk>
