import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  fetchMap1933,
  fetchMap1933CurrentCountries,
  fetchMap1933CurrentLabels,
  fetchMap1933Microstates,
  fetchMap1933Provinces,
  fetchMap1933RegionLabels,
  fetchMap1933RegionsGeojson,
  fetchVisualOrders,
} from './api'
import type { GameState } from './types'
import type { FilterSpecification } from 'maplibre-gl'

const WORLD_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-180, -60],
  [180, 85],
]
const EUROPE_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-15, 33],
  [65, 72],
]
const START_BOUNDS = WORLD_BOUNDS
const EMPTY_GEOJSON: GeoJSON.FeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

type Props = {
  state: GameState | null
  selectedTag: string
  onSelectCountry: (tag: string) => void
}

type MapData = {
  provinces: GeoJSON.FeatureCollection
  countries: GeoJSON.FeatureCollection
  countryLabels: GeoJSON.FeatureCollection
  regions: GeoJSON.FeatureCollection
  regionLabels: GeoJSON.FeatureCollection
  microstates: GeoJSON.FeatureCollection
  visualOrders: GeoJSON.FeatureCollection
}

export default function MapView({ state, selectedTag, onSelectCountry }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const mapDataRef = useRef<MapData | null>(null)
  const [showProvinces, setShowProvinces] = useState(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const rect = containerRef.current.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) {
      console.error('Map container has zero size:', { width: rect.width, height: rect.height })
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: {
              'background-color': '#020617',
            },
          },
        ],
      },
      center: [18, 49],
      zoom: 2,
      attributionControl: false,
    })

    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl(), 'top-left')

    map.on('load', async () => {
      try {
        map.resize()
        setTimeout(() => map.resize(), 0)

        const data = await fetchAllMapData()
        mapDataRef.current = data
        console.log('Grand strategy map data loaded', {
          provinces: data.provinces.features.length,
          countries: data.countries.features.length,
          regions: data.regions.features.length,
        })

        addSources(map, data)
        addLayers(map, selectedTag)
        addInteractions(map, onSelectCountry)

        map.fitBounds(START_BOUNDS, { padding: 24, duration: 0 })
        map.resize()
        setTimeout(() => map.resize(), 0)
      } catch (error) {
        console.error('Failed to load grand strategy map:', error)
      }
    })

    map.on('error', (event) => {
      console.error('MapLibre error:', event)
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (map.getLayer('selected-country-border')) {
      map.setFilter('selected-country-border', selectedCountryFilter(selectedTag))
    }
  }, [selectedTag])

  useEffect(() => {
    const map = mapRef.current
    const data = mapDataRef.current
    if (!map || !data) return

    updateSource(map, 'provinces-1933', colorProvinces(data.provinces, state))
    updateSource(map, 'current-countries-1933', colorCountries(data.countries, state))
  }, [state])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (map.getLayer('province-fill')) {
      map.setLayoutProperty('province-fill', 'visibility', 'none')
    }
    if (map.getLayer('province-border')) {
      map.setLayoutProperty('province-border', 'visibility', showProvinces ? 'visible' : 'none')
    }
  }, [showProvinces])

  return (
    <>
      <div ref={containerRef} className="map-container" />
      <button className="map-debug-toggle" onClick={() => setShowProvinces((value) => !value)}>
        {showProvinces ? 'Hide provinces' : 'Show provinces'}
      </button>
    </>
  )
}

async function fetchAllMapData(): Promise<MapData> {
  const [
    provinces,
    currentCountries,
    fallbackCountries,
    countryLabels,
    regions,
    regionLabels,
    microstates,
    visualOrders,
  ] = await Promise.all([
    fetchMap1933Provinces(),
    fetchMap1933CurrentCountries(),
    fetchMap1933(),
    fetchMap1933CurrentLabels(),
    fetchMap1933RegionsGeojson(),
    fetchMap1933RegionLabels(),
    fetchMap1933Microstates(),
    fetchVisualOrders(),
  ])

  if (regions.features.length === 0) {
    console.warn('Region layer is empty. Run prepare_admin1_regions.py.')
  }

  return {
    provinces,
    countries: shouldUseCountryFallback(currentCountries) ? fallbackCountries : currentCountries,
    countryLabels,
    regions,
    regionLabels,
    microstates,
    visualOrders,
  }
}

function addSources(map: maplibregl.Map, data: MapData) {
  map.addSource('provinces-1933', {
    type: 'geojson',
    data: data.provinces,
  })
  map.addSource('current-countries-1933', {
    type: 'geojson',
    data: data.countries,
  })
  map.addSource('country-labels-1933', {
    type: 'geojson',
    data: data.countryLabels,
  })
  map.addSource('regions-1933', {
    type: 'geojson',
    data: data.regions,
  })
  map.addSource('region-labels-1933', {
    type: 'geojson',
    data: data.regionLabels,
  })
  map.addSource('microstates-1933', {
    type: 'geojson',
    data: data.microstates,
  })
  map.addSource('visual-orders-1933', {
    type: 'geojson',
    data: data.visualOrders,
  })
}

function addLayers(map: maplibregl.Map, selectedTag: string) {
  map.addLayer({
    id: 'province-fill',
    type: 'fill',
    source: 'provinces-1933',
    layout: {
      visibility: 'none',
    },
    paint: {
      'fill-color': ['get', 'color'],
      'fill-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0, 5, 0.12, 7, 0.35],
    },
  } as any)

  map.addLayer({
    id: 'province-border',
    type: 'line',
    source: 'provinces-1933',
    layout: {
      visibility: 'none',
    },
    paint: {
      'line-color': '#0f172a',
      'line-width': ['interpolate', ['linear'], ['zoom'], 3, 0.4, 7, 0.8],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 3, 0.35, 7, 0.55],
    },
  } as any)

  map.addLayer({
    id: 'current-country-fill',
    type: 'fill',
    source: 'current-countries-1933',
    paint: {
      'fill-color': ['get', 'color'],
      'fill-opacity': 0.72,
    },
  } as any)

  map.addLayer({
    id: 'region-border',
    type: 'line',
    source: 'regions-1933',
    minzoom: 4.5,
    paint: {
      'line-color': '#e5e7eb',
      'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0, 5, 0.7, 7, 1.4],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0, 5, 0.45, 7, 0.75],
    },
  } as any)

  map.addLayer({
    id: 'country-border',
    type: 'line',
    source: 'current-countries-1933',
    paint: {
      'line-color': '#020617',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 1, 5, 1.6],
    },
  } as any)

  map.addLayer({
    id: 'selected-country-border',
    type: 'line',
    source: 'current-countries-1933',
    filter: selectedCountryFilter(selectedTag),
    paint: {
      'line-color': '#facc15',
      'line-width': 3,
    },
  } as any)

  map.addLayer({
    id: 'country-label-lines',
    type: 'symbol',
    source: 'country-labels-1933',
    filter: ['==', ['get', 'labelKind'], 'line'],
    layout: {
      'symbol-placement': 'line',
      'text-field': ['get', 'label'],
      'text-size': ['get', 'labelSize'],
      'text-letter-spacing': ['get', 'labelSpacing'],
      'text-font': ['Open Sans Regular'],
      'text-keep-upright': true,
      'text-allow-overlap': false,
      'text-ignore-placement': false,
      'text-max-angle': 45,
    },
    paint: {
      'text-color': '#f8fafc',
      'text-halo-color': '#111827',
      'text-halo-width': 2,
      'text-halo-blur': 0.5,
      'text-opacity': ['interpolate', ['linear'], ['zoom'], 2, 0.95, 4, 0.9, 5.5, 0.55, 6.7, 0],
    },
  } as any)

  map.addLayer({
    id: 'country-label-points',
    type: 'symbol',
    source: 'country-labels-1933',
    filter: ['==', ['get', 'labelKind'], 'point'],
    layout: {
      'symbol-placement': 'point',
      'text-field': ['get', 'label'],
      'text-size': ['get', 'labelSize'],
      'text-font': ['Open Sans Regular'],
      'text-allow-overlap': false,
      'text-ignore-placement': false,
    },
    paint: {
      'text-color': '#f8fafc',
      'text-halo-color': '#111827',
      'text-halo-width': 2,
      'text-halo-blur': 0.5,
      'text-opacity': ['interpolate', ['linear'], ['zoom'], 2, 0.8, 4, 0.75, 5.5, 0.4, 6.7, 0],
    },
  } as any)

  map.addLayer({
    id: 'region-labels',
    type: 'symbol',
    source: 'region-labels-1933',
    minzoom: 5,
    layout: {
      'text-field': ['get', 'label'],
      'text-size': [
        'interpolate',
        ['linear'],
        ['zoom'],
        5,
        ['get', 'labelSize'],
        7,
        ['+', ['get', 'labelSize'], 2],
      ],
      'text-font': ['Open Sans Regular'],
      'text-allow-overlap': false,
      'text-ignore-placement': false,
      'text-variable-anchor': ['top', 'bottom', 'left', 'right'],
      'text-radial-offset': 0.4,
    },
    paint: {
      'text-color': '#f8fafc',
      'text-halo-color': '#020617',
      'text-halo-width': 1.5,
      'text-opacity': ['interpolate', ['linear'], ['zoom'], 4.5, 0, 5, 0.75, 7, 1],
    },
  } as any)

  map.addLayer({
    id: 'microstate-marker',
    type: 'circle',
    source: 'microstates-1933',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4.5, 0, 5, 4, 8, 6],
      'circle-color': ['get', 'color'],
      'circle-stroke-color': '#f8fafc',
      'circle-stroke-width': 1,
    },
  } as any)

  map.addLayer({
    id: 'microstate-label',
    type: 'symbol',
    source: 'microstates-1933',
    layout: {
      'text-field': ['get', 'label'],
      'text-font': ['Open Sans Regular'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 4.5, 0, 5, 10, 8, 12],
      'text-offset': [0, 0.8],
      'text-allow-overlap': true,
    },
    paint: {
      'text-color': '#f8fafc',
      'text-halo-color': '#020617',
      'text-halo-width': 1.5,
    },
  } as any)

  map.addLayer({
    id: 'visual-order-arrows',
    type: 'line',
    source: 'visual-orders-1933',
    paint: {
      'line-color': ['coalesce', ['get', 'color'], '#facc15'],
      'line-width': 2,
      'line-opacity': 0.9,
    },
  } as any)
}

function addInteractions(map: maplibregl.Map, onSelectCountry: (tag: string) => void) {
  map.on('click', 'current-country-fill', (event) => {
    const tag = event.features?.[0]?.properties?.tag
    if (typeof tag === 'string') onSelectCountry(tag)
  })

  map.on('click', 'province-fill', (event) => {
    const tag = event.features?.[0]?.properties?.ownerTag
    if (typeof tag === 'string') onSelectCountry(tag)
  })

  map.on('click', 'microstate-marker', (event) => {
    const tag = event.features?.[0]?.properties?.tag
    if (typeof tag === 'string') onSelectCountry(tag)
  })

  map.on('click', 'microstate-label', (event) => {
    const tag = event.features?.[0]?.properties?.tag
    if (typeof tag === 'string') onSelectCountry(tag)
  })

  for (const layer of ['current-country-fill', 'province-fill', 'microstate-marker', 'microstate-label']) {
    map.on('mousemove', layer, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', layer, () => {
      map.getCanvas().style.cursor = ''
    })
  }
}

function shouldUseCountryFallback(geojson: GeoJSON.FeatureCollection) {
  if (!geojson.features.length) return true

  const rectangular = geojson.features.filter((feature: any) => {
    const geometry = feature.geometry
    const coordinates = geometry?.type === 'Polygon' ? geometry.coordinates : null
    const ring = coordinates?.[0]
    return Array.isArray(ring) && ring.length === 5
  })

  return rectangular.length / geojson.features.length > 0.5
}

function updateSource(map: maplibregl.Map, sourceId: string, data: GeoJSON.FeatureCollection) {
  const source = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined
  source?.setData(data)
}

function colorProvinces(geojson: GeoJSON.FeatureCollection, state: GameState | null) {
  return {
    ...geojson,
    features: geojson.features.map((feature: any) => ({
      ...feature,
      properties: {
        ...feature.properties,
        color: state?.countries?.[feature.properties?.ownerTag]?.color ?? feature.properties?.color ?? '#64748b',
      },
    })),
  }
}

function colorCountries(geojson: GeoJSON.FeatureCollection, state: GameState | null) {
  return {
    ...geojson,
    features: geojson.features.map((feature: any) => ({
      ...feature,
      properties: {
        ...feature.properties,
        color: state?.countries?.[feature.properties?.tag]?.color ?? feature.properties?.color ?? '#64748b',
      },
    })),
  }
}

function selectedCountryFilter(selectedTag: string): FilterSpecification {
  return ['==', ['get', 'tag'], selectedTag]
}

export { EUROPE_BOUNDS, WORLD_BOUNDS }
