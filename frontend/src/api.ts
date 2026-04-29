import type { GameState } from './types'
import type { OverlayData } from './map/overlayTypes'

export const API_BASE = 'http://127.0.0.1:8000'

export type TileMetadata = {
  pmtilesUrl: string
  exists: boolean
  layers?: string[]
  error?: string
}

export async function fetchState(): Promise<GameState> {
  const res = await fetch(`${API_BASE}/api/state`)
  if (!res.ok) throw new Error('Failed to fetch state')
  return res.json()
}

export async function fetchMap1933(): Promise<GeoJSON.FeatureCollection> {
  const res = await fetch(`${API_BASE}/api/map/1933`)
  if (!res.ok) throw new Error('Failed to fetch map')
  return res.json()
}

export async function fetchMap1933TileMetadata(): Promise<TileMetadata> {
  return fetchJson('/api/map/1933/tile-metadata')
}

export async function fetchMap1933Provinces(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/provinces')
}

export async function fetchMap1933CurrentCountries(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/current-countries')
}

export async function fetchMap1933CurrentLabels(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/current-labels')
}

export async function fetchMap1933OverlayData(): Promise<OverlayData> {
  return fetchJson('/api/map/1933/overlay-data')
}

export async function fetchMap1933RegionsGeojson(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/regions-geojson')
}

export async function fetchMap1933RegionLabels(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/region-labels')
}

export async function fetchMap1933Microstates(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/microstates')
}

export async function fetchMap1933Regions() {
  return fetchJson('/api/map/1933/regions')
}

export async function fetchProvinceAdjacency() {
  return fetchJson('/api/map/1933/province-adjacency')
}

export async function fetchVisualOrders(): Promise<GeoJSON.FeatureCollection> {
  return fetchJson('/api/map/1933/visual-orders')
}

export async function debugTransferProvinces(provinceIds: string[], newOwner: string) {
  return postJson('/api/debug/transfer-provinces', { provinceIds, newOwner })
}

export async function debugTransferRegions(regionIds: string[], newOwner: string) {
  return postJson('/api/debug/transfer-regions', { regionIds, newOwner })
}

export async function debugMoveDivision(divisionId: string, toProvinceId: string) {
  return postJson('/api/debug/move-division', { divisionId, toProvinceId })
}

export async function parseOrder(actorTag: string, text: string) {
  return postJson('/api/orders/parse', { actorTag, text })
}

export async function executeOrder(parsedOrder: unknown) {
  return postJson('/api/orders/execute', parsedOrder)
}

export async function makeTurn(actor: string, action: string) {
  const res = await fetch(`${API_BASE}/api/turn`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ actor, action }),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text)
  }

  return res.json()
}

export async function resetState(): Promise<GameState> {
  const res = await fetch(`${API_BASE}/api/reset`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to reset state')
  return res.json()
}

async function fetchJson(path: string) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`Failed to fetch ${path}`)
  return res.json()
}

async function postJson(path: string, body: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text)
  }

  return res.json()
}
