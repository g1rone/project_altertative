import { useEffect, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'
import maplibregl from 'maplibre-gl'
import type { FilterSpecification } from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  API_BASE,
  fetchMap1933Provinces,
  fetchMap1933TileMetadata,
  fetchVisualOrders,
} from './api'
import type { GameState } from './types'

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

let protocolRegistered = false

export default function MapView({ selectedTag, onSelectCountry }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const provincesLoadedRef = useRef(false)
  const [showProvinces, setShowProvinces] = useState(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    ensurePmtilesProtocol()

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

        const [metadata, visualOrders] = await Promise.all([
          fetchMap1933TileMetadata(),
          fetchVisualOrders(),
        ])

        if (!metadata.exists) {
          console.error('PMTiles missing, run backend/scripts/build_pmtiles.py')
          if (metadata.error) console.error(metadata.error)
          map.fitBounds(START_BOUNDS, { padding: 24, duration: 0 })
          return
        }

        const pmtilesUrl = new URL(metadata.pmtilesUrl, API_BASE).toString()
        addSources(map, pmtilesUrl, visualOrders)
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
    if (!map) return

    if (showProvinces) {
      ensureProvinceDebugData(map, provincesLoadedRef).catch((error) => {
        console.error('Failed to load province debug layer:', error)
      })
    }

    if (map.getLayer('province-border-debug')) {
      map.setLayoutProperty('province-border-debug', 'visibility', showProvinces ? 'visible' : 'none')
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

function ensurePmtilesProtocol() {
  if (protocolRegistered) return
  const protocol = new Protocol()
  try {
    maplibregl.addProtocol('pmtiles', protocol.tile)
  } catch (error) {
    console.warn('PMTiles protocol registration was skipped:', error)
  }
  protocolRegistered = true
}

function addSources(map: maplibregl.Map, pmtilesUrl: string, visualOrders: GeoJSON.FeatureCollection) {
  map.addSource('pax1933', {
    type: 'vector',
    url: `pmtiles://${pmtilesUrl}`,
  })
  map.addSource('provinces-debug-1933', {
    type: 'geojson',
    data: EMPTY_GEOJSON,
  })
  map.addSource('visual-orders-1933', {
    type: 'geojson',
    data: visualOrders,
  })
}

function addLayers(map: maplibregl.Map, selectedTag: string) {
  map.addLayer({
    id: 'country-fill',
    type: 'fill',
    source: 'pax1933',
    'source-layer': 'countries',
    paint: {
      'fill-color': ['coalesce', ['get', 'color'], '#64748b'],
      'fill-opacity': 0.74,
    },
  } as any)

  map.addLayer({
    id: 'microstate-fill',
    type: 'fill',
    source: 'pax1933',
    'source-layer': 'microstates',
    paint: {
      'fill-color': ['coalesce', ['get', 'color'], '#facc15'],
      'fill-opacity': ['interpolate', ['linear'], ['zoom'], 2, 0.82, 6, 0.92],
    },
  } as any)

  map.addLayer({
    id: 'rivers-line',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'rivers',
    minzoom: 3.5,
    paint: {
      'line-color': '#38bdf8',
      'line-width': ['interpolate', ['linear'], ['zoom'], 3.5, 0.45, 6, 0.9],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 3.5, 0.2, 6, 0.42],
    },
  } as any)

  map.addLayer({
    id: 'region-border',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'regions',
    minzoom: 4.6,
    paint: {
      'line-color': '#e5e7eb',
      'line-width': ['interpolate', ['linear'], ['zoom'], 4.6, 0.35, 7, 1.15],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 4.6, 0.22, 7, 0.66],
    },
  } as any)

  map.addLayer({
    id: 'province-border-debug',
    type: 'line',
    source: 'provinces-debug-1933',
    layout: {
      visibility: 'none',
    },
    paint: {
      'line-color': '#0f172a',
      'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.35, 7, 0.75],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 4, 0.22, 7, 0.52],
    },
  } as any)

  map.addLayer({
    id: 'country-border',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'countries',
    paint: {
      'line-color': '#020617',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 0.9, 5, 1.65],
      'line-opacity': 0.92,
    },
  } as any)

  map.addLayer({
    id: 'microstate-border',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'microstates',
    paint: {
      'line-color': '#f8fafc',
      'line-width': ['interpolate', ['linear'], ['zoom'], 3, 0.8, 7, 1.6],
      'line-opacity': 0.92,
    },
  } as any)

  map.addLayer({
    id: 'selected-country-border',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'countries',
    filter: selectedCountryFilter(selectedTag),
    paint: {
      'line-color': '#facc15',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 2.4, 6, 3.6],
    },
  } as any)

  map.addLayer({
    id: 'microstate-hitbox',
    type: 'circle',
    source: 'pax1933',
    'source-layer': 'microstate_label_points',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 8, 7, 15],
      'circle-color': '#ffffff',
      'circle-opacity': 0,
    },
  } as any)

  map.addLayer({
    id: 'country-label-lines',
    type: 'symbol',
    source: 'pax1933',
    'source-layer': 'country_label_lines',
    layout: {
      'symbol-placement': 'line',
      'text-field': ['get', 'label'],
      'text-size': ['coalesce', ['get', 'labelSize'], 18],
      'text-letter-spacing': ['coalesce', ['get', 'labelSpacing'], 0.16],
      'text-font': ['Open Sans Bold'],
      'text-keep-upright': true,
      'text-allow-overlap': false,
      'text-ignore-placement': false,
      'text-max-angle': 45,
    },
    paint: countryLabelPaint(0.95),
  } as any)

  map.addLayer({
    id: 'country-label-points',
    type: 'symbol',
    source: 'pax1933',
    'source-layer': 'country_label_points',
    layout: {
      'symbol-placement': 'point',
      'text-field': ['get', 'label'],
      'text-size': ['coalesce', ['get', 'labelSize'], 15],
      'text-letter-spacing': ['coalesce', ['get', 'labelSpacing'], 0.12],
      'text-font': ['Open Sans Bold'],
      'text-allow-overlap': false,
      'text-ignore-placement': false,
      'text-variable-anchor': ['center', 'top', 'bottom'],
      'text-radial-offset': 0.25,
    },
    paint: countryLabelPaint(0.85),
  } as any)

  map.addLayer({
    id: 'region-labels',
    type: 'symbol',
    source: 'pax1933',
    'source-layer': 'region_label_points',
    minzoom: 5.8,
    layout: {
      'text-field': ['get', 'label'],
      'text-size': [
        'interpolate',
        ['linear'],
        ['zoom'],
        5.8,
        ['coalesce', ['get', 'labelSize'], 10],
        7,
        ['+', ['coalesce', ['get', 'labelSize'], 10], 1.5],
      ],
      'text-font': ['Open Sans Regular'],
      'text-allow-overlap': false,
      'text-ignore-placement': false,
      'text-variable-anchor': ['top', 'bottom', 'left', 'right'],
      'text-radial-offset': 0.35,
    },
    paint: {
      'text-color': '#cbd5e1',
      'text-halo-color': '#020617',
      'text-halo-width': 1.7,
      'text-halo-blur': 0.4,
      'text-opacity': ['interpolate', ['linear'], ['zoom'], 5.6, 0, 5.8, 0.78, 7, 1],
    },
  } as any)

  map.addLayer({
    id: 'microstate-labels',
    type: 'symbol',
    source: 'pax1933',
    'source-layer': 'microstate_label_points',
    minzoom: 5.7,
    layout: {
      'text-field': ['get', 'label'],
      'text-font': ['Open Sans Bold'],
      'text-size': ['interpolate', ['linear'], ['zoom'], 5.7, 11, 8, ['coalesce', ['get', 'labelSize'], 13]],
      'text-offset': [0, 0.75],
      'text-allow-overlap': true,
    },
    paint: {
      'text-color': '#f8fafc',
      'text-halo-color': '#020617',
      'text-halo-width': 2,
      'text-halo-blur': 0.35,
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

function countryLabelPaint(baseOpacity: number) {
  return {
    'text-color': '#f8fafc',
    'text-halo-color': '#020617',
    'text-halo-width': 2.4,
    'text-halo-blur': 0.35,
    'text-opacity': ['interpolate', ['linear'], ['zoom'], 2, baseOpacity, 5.8, 0.55, 6.8, 0],
  }
}

function addInteractions(map: maplibregl.Map, onSelectCountry: (tag: string) => void) {
  const selectableLayers = [
    'country-fill',
    'country-border',
    'microstate-fill',
    'microstate-border',
    'microstate-labels',
    'microstate-hitbox',
  ]

  for (const layer of selectableLayers) {
    map.on('click', layer, (event) => {
      const properties = event.features?.[0]?.properties
      const tag = properties?.tag || properties?.ownerTag
      if (typeof tag === 'string') onSelectCountry(tag)
    })
    map.on('mousemove', layer, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', layer, () => {
      map.getCanvas().style.cursor = ''
    })
  }
}

async function ensureProvinceDebugData(
  map: maplibregl.Map,
  provincesLoadedRef: MutableRefObject<boolean>,
) {
  if (provincesLoadedRef.current) return
  const provinces = await fetchMap1933Provinces()
  const source = map.getSource('provinces-debug-1933') as maplibregl.GeoJSONSource | undefined
  source?.setData(provinces)
  provincesLoadedRef.current = true
}

function selectedCountryFilter(selectedTag: string): FilterSpecification {
  return ['==', ['get', 'tag'], selectedTag]
}

export { EUROPE_BOUNDS, WORLD_BOUNDS }
