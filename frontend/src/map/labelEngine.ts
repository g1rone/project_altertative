import {
  boundsSize,
  componentsFromRegion,
  intersectsBounds,
  makeInteriorishLine,
  pointCloudFromComponents,
  principalAxis,
  type PolygonComponent,
} from './labelGeometry'
import type {
  CountryOverlayMetadata,
  DynamicCountryLabel,
  LngLat,
  OverlayRegionCollection,
} from './overlayTypes'

const DISPLAY_NAMES: Record<string, string> = {
  GER: 'GERMANY',
  SOV: 'SOVIET UNION',
  GBR: 'UNITED KINGDOM',
  FRA: 'FRANCE',
  ITA: 'ITALY',
  POL: 'POLAND',
  ESP: 'SPAIN',
  TUR: 'TURKEY',
  USA: 'UNITED STATES',
  UNI: 'UNITED STATES',
  CHN: 'CHINA',
  CHI: 'CHINA',
  JAP: 'JAPAN',
  CAN: 'CANADA',
  BRA: 'BRAZIL',
  IND: 'INDIA',
  MNG: 'MONGOLIA',
}

const MAJOR_TAGS = new Set(['GER', 'SOV', 'GBR', 'FRA', 'ITA', 'POL', 'ESP', 'TUR', 'UNI', 'USA', 'CHI', 'CHN', 'JAP', 'CAN', 'BRA', 'IND', 'MNG'])
const SKIP_TAGS = new Set(['AND', 'MCO', 'LIE', 'SMR', 'VAT', 'LUX', 'DAN', 'DNZ', 'MLT'])
const MAINLAND_BOUNDS: Record<string, [number, number, number, number]> = {
  UNI: [-126, 24, -66, 50.5],
  USA: [-126, 24, -66, 50.5],
  GBR: [-9.5, 49, 2.5, 61.5],
  FRA: [-6, 41, 10.5, 52],
  ITA: [6, 36, 19, 48],
  GER: [5, 46, 22, 56],
  POL: [13, 48, 29, 56],
  ESP: [-10, 35, 5, 44.5],
  TUR: [25, 35, 46, 42.5],
  SOV: [25, 35, 180, 78],
  JAP: [129, 30, 146.5, 46],
  IND: [60, 5, 102, 38],
  CHI: [73, 18, 135, 54],
  CHN: [73, 18, 135, 54],
}

export function buildDynamicCountryLabels(
  regions: OverlayRegionCollection,
  ownership: Record<string, string>,
  countries: Record<string, CountryOverlayMetadata>,
  zoom: number,
): DynamicCountryLabel[] {
  const grouped = new Map<string, PolygonComponent[]>()

  for (const feature of regions.features) {
    const regionId = feature.properties.regionId
    const ownerTag = ownership[regionId] ?? feature.properties.ownerTag
    if (!ownerTag || SKIP_TAGS.has(ownerTag)) continue
    const components = componentsFromRegion(feature, ownerTag).filter((component) => component.isLabelEligible)
    if (!components.length) continue
    grouped.set(ownerTag, [...(grouped.get(ownerTag) ?? []), ...components])
  }

  const labels: DynamicCountryLabel[] = []
  for (const [tag, components] of grouped) {
    const label = buildLabelForOwner(tag, components, countries[tag], zoom)
    if (label) labels.push(label)
  }

  return labels.sort((a, b) => a.priority - b.priority)
}

function buildLabelForOwner(
  tag: string,
  components: PolygonComponent[],
  metadata: CountryOverlayMetadata | undefined,
  zoom: number,
): DynamicCountryLabel | null {
  const selectedComponents = selectMainLabelComponents(tag, components)
  const cloud = pointCloudFromComponents(selectedComponents)
  if (!cloud) return null

  const { width, height } = boundsSize(cloud.bounds)
  if (!MAJOR_TAGS.has(tag) && cloud.area < 5) return null
  if (width > 220 || height > 80) return null

  const text = labelText(tag, metadata)
  const labelClass = MAJOR_TAGS.has(tag) || cloud.area > 40 ? 'major' : 'minor'
  const opacity = labelOpacity(zoom)
  if (opacity <= 0.01) return null

  const axis = principalAxis(cloud.points)
  const canUseLine = labelClass === 'major' && axis && width >= 3 && height >= 1.4 && axis.span >= Math.max(2.5, text.length * 0.28)
  const fontSize = labelFontSize(tag, cloud.area, labelClass)
  const priority = (metadata?.importance ?? (labelClass === 'major' ? 2 : 1)) * 100000 + Math.min(99999, Math.round(cloud.area * 20))

  if (canUseLine) {
    const line = makeInteriorishLine(cloud, text.length)
    if (line) {
      return {
        tag,
        text,
        labelClass,
        kind: 'line',
        anchorLine: line,
        angle: axis.angle,
        fontSize,
        letterSpacing: labelClass === 'major' ? 3.2 : 1.7,
        opacity,
        priority,
      }
    }
  }

  return {
    tag,
    text,
    labelClass,
    kind: 'point',
    anchorPoint: cloud.centroid as LngLat,
    angle: 0,
    fontSize: Math.max(13, fontSize * 0.86),
    letterSpacing: labelClass === 'major' ? 2.4 : 1.2,
    opacity: opacity * 0.9,
    priority,
  }
}

function selectMainLabelComponents(tag: string, components: PolygonComponent[]) {
  const mainlandBounds = MAINLAND_BOUNDS[tag]
  if (mainlandBounds) {
    const anchored = components.filter((component) => intersectsBounds(component.bounds, mainlandBounds))
    if (anchored.length) return anchored
  }

  const sorted = [...components].sort((a, b) => b.area - a.area)
  const largest = sorted[0]
  if (!largest) return components
  return sorted.filter((component) => component.area >= largest.area * 0.18 || distance(component.centroid, largest.centroid) < 12)
}

function labelText(tag: string, metadata: CountryOverlayMetadata | undefined) {
  return DISPLAY_NAMES[tag] ?? metadata?.displayName?.toUpperCase() ?? tag
}

function labelFontSize(tag: string, area: number, labelClass: 'major' | 'minor') {
  if (tag === 'SOV') return 34
  if (['UNI', 'USA', 'CAN', 'BRA', 'IND', 'CHI', 'CHN'].includes(tag)) return Math.min(32, 24 + Math.sqrt(area) * 0.18)
  if (labelClass === 'major') return Math.min(30, 22 + Math.sqrt(area) * 0.7)
  return Math.min(19, 12 + Math.sqrt(area) * 0.45)
}

function labelOpacity(zoom: number) {
  if (zoom < 2) return 0
  if (zoom <= 3) return lerp(0.65, 1, (zoom - 2) / 1)
  if (zoom <= 5.8) return 1
  if (zoom <= 7.2) return lerp(1, 0, (zoom - 5.8) / 1.4)
  return 0
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * Math.max(0, Math.min(1, t))
}

function distance(a: LngLat, b: LngLat) {
  return Math.hypot(a[0] - b[0], a[1] - b[1])
}
