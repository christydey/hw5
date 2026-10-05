import { HandCoins, RotateCcw, ShoppingBag, TrendingDown, TrendingUp, Wallet } from 'lucide-react'
import { money } from '../format'
import type { CashResponse } from '../types'
import type { CashChange } from '../useDesk'

interface Props {
  dateToday: string | null
  cash: CashResponse | null
  cashChange: CashChange | null
  online: boolean
  pendingApprovals: number
  resetDisabled: boolean
  onReset: () => void
}

function shopDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
  })
}

export function Header({ dateToday, cash, cashChange, online, pendingApprovals, resetDisabled, onReset }: Props) {
  const recent = cashChange && Date.now() - cashChange.at < 15000
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand__mark"><ShoppingBag size={22} strokeWidth={2.4} /></span>
        <div>
          <div className="brand__name">Campus Customs</div>
          <div className="brand__sub">Operations Desk · Chapel Street</div>
        </div>
      </div>

      <div className="topbar__meta">
        <div className="meta-chip">
          <span className="meta-chip__label">Shop date</span>
          <span className="meta-chip__value">{shopDate(dateToday)}</span>
        </div>
        <div className={`meta-chip ${online ? 'meta-chip--live' : 'meta-chip--down'}`}>
          <span className="dot" />
          <span className="meta-chip__value">{online ? 'Backend live' : 'Backend offline'}</span>
        </div>
        {pendingApprovals > 0 && (
          <div className="meta-chip meta-chip--alert">
            <HandCoins size={14} />
            <span className="meta-chip__value">
              {pendingApprovals} awaiting approval
            </span>
          </div>
        )}
      </div>

      <div className="topbar__right">
        <div className={`cash-card${recent ? ' cash-card--changed' : ''}`} key={cashChange?.at ?? 0}>
          <div className="cash-card__label"><Wallet size={14} /> Checking</div>
          <div className="cash-card__amount">{cash ? money(cash.balance) : '—'}</div>
          <div className="cash-card__foot">
            {recent && cashChange ? (
              <span className="cash-delta">
                {cashChange.to < cashChange.from ? <TrendingDown size={13} /> : <TrendingUp size={13} />}{' '}
                {cashChange.to > cashChange.from ? '+' : ''}{money(cashChange.to - cashChange.from)} · was {money(cashChange.from)}
              </span>
            ) : (
              <span>as of {cash?.as_of ?? '—'} · live from cash_accounts</span>
            )}
          </div>
        </div>
        <button className="btn btn--ghost" onClick={onReset} disabled={resetDisabled} title="Restore the working database from the original">
          <RotateCcw size={15} /> Reset shop
        </button>
      </div>
    </header>
  )
}
