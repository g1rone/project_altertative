import { useEffect, useState } from 'react'
import MapView from './MapView'
import CountryPanel from './CountryPanel'
import ActionBox from './ActionBox'
import EventLog from './EventLog'
import { fetchState, makeTurn, resetState } from './api'
import type { GameState } from './types'

export default function App() {
  const [state, setState] = useState<GameState | null>(null)
  const [selectedTag, setSelectedTag] = useState<string>('GER')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchState()
      .then(setState)
      .catch((err) => setError(String(err)))
  }, [])

  async function handleTurn(action: string) {
    if (!selectedTag) return

    try {
      const data = await makeTurn(selectedTag, action)
      setState(data.state)
      setError(null)
    } catch (err) {
      setError(String(err))
    }
  }

  async function handleReset() {
    try {
      const data = await resetState()
      setState(data)
      setError(null)
    } catch (err) {
      setError(String(err))
    }
  }

  const selectedCountry = state?.countries[selectedTag] ?? null

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="game-title">Pax 1933</div>
          <div className="game-subtitle">
            Year: {state?.year ?? '...'} · Turn: {state?.turn ?? '...'}
          </div>
        </div>

        <button className="reset-button" onClick={handleReset}>
          Reset
        </button>
      </header>

      <main className="layout">
        <section className="map-section">
          <MapView
            state={state}
            selectedTag={selectedTag}
            onSelectCountry={setSelectedTag}
          />
        </section>

        <aside className="side-panel">
          {error && <div className="error-box">{error}</div>}

          <CountryPanel country={selectedCountry} selectedTag={selectedTag} />

          <ActionBox selectedCountry={selectedCountry} onSubmit={handleTurn} />

          <EventLog events={state?.events ?? []} />
        </aside>
      </main>
    </div>
  )
}
