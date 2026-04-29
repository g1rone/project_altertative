import type { LngLat, OverlayRegionFeature } from './overlayTypes'

export type PolygonComponent = {
  regionId: string
  ownerTag: string
  countryTag: string
  isLabelEligible: boolean
  ring: LngLat[]
  area: number
  centroid: LngLat
  bounds: [number, number, number, number]
}

export type PointCloud = {
  points: LngLat[]
  area: number
  centroid: LngLat
  bounds: [number, number, number, number]
}

export function componentsFromRegion(feature: OverlayRegionFeature, ownerTag: string): PolygonComponent[] {
  const geometry = feature.geometry
  if (!geometry) return []

  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  return polygons
    .map((polygon) => polygon[0] ?? [])
    .filter((ring): ring is number[][] => ring.length >= 4)
    .map((ring) => {
      const normalized = ring.map((point) => [Number(point[0]), Number(point[1])] as LngLat)
      const area = Math.abs(ringArea(normalized))
      return {
        regionId: feature.properties.regionId,
        ownerTag,
        countryTag: feature.properties.countryTag,
        isLabelEligible: feature.properties.isLabelEligible,
        ring: normalized,
        area,
        centroid: ringCentroid(normalized),
        bounds: ringBounds(normalized),
      }
    })
    .filter((component) => component.area > 0.0001)
}

export function pointCloudFromComponents(components: PolygonComponent[]): PointCloud | null {
  if (!components.length) return null
  const points = components.flatMap((component) => decimateRing(component.ring, 3))
  if (points.length < 3) return null

  const area = components.reduce((sum, component) => sum + component.area, 0)
  const centroid = weightedCentroid(components)
  const bounds = mergeBounds(components.map((component) => component.bounds))
  return { points, area, centroid, bounds }
}

export function principalAxis(points: LngLat[]): { axis: [number, number]; angle: number; span: number } | null {
  if (points.length < 3) return null
  const meanX = points.reduce((sum, point) => sum + point[0], 0) / points.length
  const meanY = points.reduce((sum, point) => sum + point[1], 0) / points.length
  const centered = points.map((point) => [point[0] - meanX, point[1] - meanY] as [number, number])
  const xx = centered.reduce((sum, point) => sum + point[0] * point[0], 0) / centered.length
  const xy = centered.reduce((sum, point) => sum + point[0] * point[1], 0) / centered.length
  const yy = centered.reduce((sum, point) => sum + point[1] * point[1], 0) / centered.length
  const angle = 0.5 * Math.atan2(2 * xy, xx - yy)
  let axis: [number, number] = [Math.cos(angle), Math.sin(angle)]
  if (axis[0] < 0) axis = [-axis[0], -axis[1]]
  const projections = centered.map((point) => point[0] * axis[0] + point[1] * axis[1])
  return {
    axis,
    angle: Math.atan2(axis[1], axis[0]),
    span: Math.max(...projections) - Math.min(...projections),
  }
}

export function makeInteriorishLine(cloud: PointCloud, labelLength: number): LngLat[] | null {
  const axis = principalAxis(cloud.points)
  if (!axis || axis.span < 2) return null
  const safeFactor = labelLength > 11 ? 0.62 : 0.68
  const halfLength = Math.max(1.2, Math.min(axis.span * safeFactor * 0.5, 45))
  const [cx, cy] = cloud.centroid
  return [
    [cx - axis.axis[0] * halfLength, cy - axis.axis[1] * halfLength],
    [cx + axis.axis[0] * halfLength, cy + axis.axis[1] * halfLength],
  ]
}

export function boundsSize(bounds: [number, number, number, number]) {
  return {
    width: bounds[2] - bounds[0],
    height: bounds[3] - bounds[1],
  }
}

export function intersectsBounds(a: [number, number, number, number], b: [number, number, number, number]) {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]
}

function ringArea(ring: LngLat[]) {
  let total = 0
  for (let index = 0; index < ring.length; index++) {
    const point = ring[index]
    const next = ring[(index + 1) % ring.length]
    total += point[0] * next[1] - next[0] * point[1]
  }
  return total / 2
}

function ringCentroid(ring: LngLat[]): LngLat {
  const signedArea = ringArea(ring)
  if (Math.abs(signedArea) < 0.000001) return averagePoint(ring)
  let cx = 0
  let cy = 0
  for (let index = 0; index < ring.length; index++) {
    const point = ring[index]
    const next = ring[(index + 1) % ring.length]
    const factor = point[0] * next[1] - next[0] * point[1]
    cx += (point[0] + next[0]) * factor
    cy += (point[1] + next[1]) * factor
  }
  return [cx / (6 * signedArea), cy / (6 * signedArea)]
}

function averagePoint(points: LngLat[]): LngLat {
  return [
    points.reduce((sum, point) => sum + point[0], 0) / points.length,
    points.reduce((sum, point) => sum + point[1], 0) / points.length,
  ]
}

function ringBounds(ring: LngLat[]): [number, number, number, number] {
  return [
    Math.min(...ring.map((point) => point[0])),
    Math.min(...ring.map((point) => point[1])),
    Math.max(...ring.map((point) => point[0])),
    Math.max(...ring.map((point) => point[1])),
  ]
}

function mergeBounds(boundsList: [number, number, number, number][]): [number, number, number, number] {
  return [
    Math.min(...boundsList.map((bounds) => bounds[0])),
    Math.min(...boundsList.map((bounds) => bounds[1])),
    Math.max(...boundsList.map((bounds) => bounds[2])),
    Math.max(...boundsList.map((bounds) => bounds[3])),
  ]
}

function weightedCentroid(components: PolygonComponent[]): LngLat {
  const area = components.reduce((sum, component) => sum + component.area, 0)
  if (area <= 0) return averagePoint(components.map((component) => component.centroid))
  return [
    components.reduce((sum, component) => sum + component.centroid[0] * component.area, 0) / area,
    components.reduce((sum, component) => sum + component.centroid[1] * component.area, 0) / area,
  ]
}

function decimateRing(ring: LngLat[], step: number) {
  return ring.filter((_, index) => index % step === 0)
}
