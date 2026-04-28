import type { GameEvent } from './types'

type Props = {
  events: GameEvent[]
}

export default function EventLog({ events }: Props) {
  return (
    <section className="card event-card">
      <h2>Event Log</h2>

      {events.length === 0 && (
        <p className="muted">No events yet. Make your first turn.</p>
      )}

      <div className="events-list">
        {events.map((event, index) => (
          <article className="event-item" key={`${event.turn}-${index}`}>
            <div className="event-meta">
              Turn {event.turn} · {event.actor} · {event.action_class}
            </div>
            <div className="event-summary">{event.summary}</div>
            <div className="event-effects">
              {Object.entries(event.effects).map(([key, value]) => (
                <span key={key}>
                  {key}: {value > 0 ? `+${value}` : value}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
