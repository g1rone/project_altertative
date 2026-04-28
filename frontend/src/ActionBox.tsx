import { useState } from 'react'
import type { CountryState } from './types'

type Props = {
  selectedCountry: CountryState | null
  onSubmit: (action: string) => Promise<void>
}

export default function ActionBox({ selectedCountry, onSubmit }: Props) {
  const [action, setAction] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit() {
    const clean = action.trim()
    if (!clean || !selectedCountry || busy) return

    setBusy(true)
    await onSubmit(clean)
    setAction('')
    setBusy(false)
  }

  return (
    <section className="card">
      <h2>Action</h2>
      <p className="muted">
        Selected: {selectedCountry ? selectedCountry.name : 'none'}
      </p>

      <textarea
        value={action}
        onChange={(e) => setAction(e.target.value)}
        placeholder="Например: Германия начинает тайную программу перевооружения..."
      />

      <button
        className="primary-button"
        disabled={!selectedCountry || !action.trim() || busy}
        onClick={handleSubmit}
      >
        {busy ? 'Processing...' : 'Make turn'}
      </button>
    </section>
  )
}
