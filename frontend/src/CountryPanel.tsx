import type { CountryState } from './types'

type Props = {
  country: CountryState | null
  selectedTag: string
}

export default function CountryPanel({ country, selectedTag }: Props) {
  if (!country) {
    return (
      <section className="card">
        <h2>Country</h2>
        <p className="muted">
          {selectedTag ? `${selectedTag} В· No state data yet.` : 'Click a country on the map.'}
        </p>
      </section>
    )
  }

  return (
    <section className="card">
      <div className="country-header">
        <div>
          <h2>{country.name}</h2>
          <p className="muted">{country.tag} · {country.ideology}</p>
        </div>
        <div className="country-color" style={{ background: country.color }} />
      </div>

      <Stat label="Stability" value={country.stability} />
      <Stat label="Economy" value={country.economy} />
      <Stat label="Military" value={country.military} />
      <Stat label="Legitimacy" value={country.legitimacy} />
    </section>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-row">
      <div className="stat-label">{label}</div>
      <div className="stat-bar">
        <div className="stat-fill" style={{ width: `${value}%` }} />
      </div>
      <div className="stat-value">{value}</div>
    </div>
  )
}
