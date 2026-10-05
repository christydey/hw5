// Display formatting only. Values come from the API as-is.
import type { Approval, Ticket } from './types'

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export const money = (n: number | null | undefined) => (n === null || n === undefined ? '—' : usd.format(n))

export const time = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export const TICKET_TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

/** One line describing what the ticket is about, from its stored fields. */
export function ticketLine(t: Ticket): string {
  if (t.sku) return `${t.qty ?? '?'} × ${t.sku}${t.size ? ` · size ${t.size}` : ''}`
  if (t.lease_id) return `Lease #${t.lease_id}`
  return t.subject
}

export function approvalTitle(a: Approval): string {
  switch (a.kind) {
    case 'invoice':
      return `Pay invoice #${a.ref_id}`
    case 'lease_rent':
      return `Pay rent · lease #${a.ref_id}${a.expected_next_due ? ` (due ${a.expected_next_due})` : ''}`
    case 'purchase_order':
      return `Buy ${a.qty} × ${a.sku}${a.vendor_id ? ` from vendor #${a.vendor_id}` : ''}`
  }
}

export const prettyTool = (tool: string) => tool.replace(/_/g, ' ')
