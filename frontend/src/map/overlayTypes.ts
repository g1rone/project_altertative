export type LngLat = [number, number]

export type CountryOverlayMetadata = {
  tag: string
  displayName: string
  color: string
  importance: number
}

export type OverlayRegionProperties = {
  regionId: string
  countryTag: string
  ownerTag: string
  defaultOwnerTag: string
  displayName: string
  isMainland: boolean
  isColony: boolean
  isDetachedTerritory: boolean
  isLabelEligible: boolean
  labelOwnerTag: string
  labelSize: number
  minZoom: number
}

export type OverlayRegionFeature = GeoJSON.Feature<
  GeoJSON.Polygon | GeoJSON.MultiPolygon,
  OverlayRegionProperties
>

export type OverlayRegionCollection = GeoJSON.FeatureCollection<
  GeoJSON.Polygon | GeoJSON.MultiPolygon,
  OverlayRegionProperties
>

export type OverlayData = {
  countries: Record<string, CountryOverlayMetadata>
  ownership: Record<string, string>
  regions: OverlayRegionCollection
}

export type DynamicCountryLabel = {
  tag: string
  text: string
  labelClass: 'major' | 'minor'
  kind: 'line' | 'point'
  anchorLine?: LngLat[]
  anchorPoint?: LngLat
  angle: number
  fontSize: number
  letterSpacing: number
  opacity: number
  priority: number
}
