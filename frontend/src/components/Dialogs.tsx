import { useEffect, useState, type ReactNode } from 'react'
import { LoaderCircle, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { approvalTitle, money } from '../format'
import type { Approval } from '../types'
import { AgentTag } from './AgentAvatar'

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal__head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

const NAME_KEY = 'campus-customs-approver'

interface DecisionProps {
  approval: Approval
  mode: 'approve' | 'reject'
  balance: number | null
  onConfirm: (name: string) => Promise<void>
  onClose: () => void
}

export function DecisionDialog({ approval, mode, balance, onConfirm, onClose }: DecisionProps) {
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const approve = mode === 'approve'

  const submit = async () => {
    if (!name.trim()) return setError('Enter your name. Every approval records who made it.')
    setBusy(true)
    setError(null)
    try {
      localStorage.setItem(NAME_KEY, name.trim())
      await onConfirm(name.trim())
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <Modal title={approve ? 'Approve payment' : 'Reject payment'} onClose={onClose}>
      <div className="decision">
        <div className="decision__what">{approvalTitle(approval)}</div>
        <div className={`decision__amount${approve ? '' : ' decision__amount--muted'}`}>{money(approval.amount)}</div>
        <div className="decision__meta">
          Prepared by <AgentTag agent={approval.prepared_by} /> · paid from <strong>{approval.account}</strong>
          {balance !== null && <> · currently {money(balance)}</>}
        </div>
        <p className="decision__reason">{approval.reason}</p>
        {approve && (
          <div className="decision__safety">
            <ShieldCheck size={15} />
            <span>The backend re-checks the amount, the invoice or lease, the vendor and the cash balance before anything is paid. If any check fails, nothing changes.</span>
          </div>
        )}
        <label className="field">
          <span>Your name</span>
          <input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()} placeholder="e.g. Christy" maxLength={80} />
        </label>
        {error && <div className="decision__error">{error}</div>}
        <div className="modal__actions">
          <button className="btn btn--ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className={approve ? 'btn btn--approve' : 'btn btn--danger'} onClick={submit} disabled={busy}>
            {busy && <LoaderCircle size={15} className="spin" />}
            {approve ? `Approve & pay ${money(approval.amount)}` : 'Reject'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

export function ResetDialog({ onConfirm, onClose }: { onConfirm: () => Promise<void>; onClose: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }
  return (
    <Modal title="Reset the shop?" onClose={onClose}>
      <div className="decision">
        <p>
          This restores <code>data/campus_customs_new.db</code> from the original <code>campus_customs.db</code>: all three
          tickets reopen, payments are cleared and checking returns to its starting balance. Pending approvals are voided.
          The audit trail keeps its history.
        </p>
        {error && <div className="decision__error">{error}</div>}
        <div className="modal__actions">
          <button className="btn btn--ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn--danger" onClick={submit} disabled={busy}>
            {busy ? <LoaderCircle size={15} className="spin" /> : <RotateCcw size={15} />} Reset shop
          </button>
        </div>
      </div>
    </Modal>
  )
}
