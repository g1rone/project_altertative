export type CountryState = {
  tag: string
  name: string
  color: string
  ideology: string
  stability: number
  economy: number
  military: number
  legitimacy: number
}

export type GameEvent = {
  turn: number
  actor: string
  action: string
  action_class: string
  summary: string
  effects: Record<string, number>
}

export type GameState = {
  year: number
  turn: number
  countries: Record<string, CountryState>
  events: GameEvent[]
}
