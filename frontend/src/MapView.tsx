import { useEffect, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'
import maplibregl from 'maplibre-gl'
import type { FilterSpecification } from 'maplibre-gl'
import { Protocol } from 'pmtiles'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  API_BASE,
  fetchMap1933OverlayData,
  fetchMap1933Provinces,
  fetchMap1933TileMetadata,
  fetchVisualOrders,
} from './api'
import type { GameState } from './types'
import MapOverlay from './map/MapOverlay'
import type { OverlayData } from './map/overlayTypes'

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

export default function MapView({ state, selectedTag, onSelectCountry }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const provincesLoadedRef = useRef(false)
  const [mapInstance, setMapInstance] = useState<maplibregl.Map | null>(null)
  const [overlayData, setOverlayData] = useState<OverlayData | null>(null)
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
    setMapInstance(map)
    map.addControl(new maplibregl.NavigationControl(), 'top-left')

    map.on('load', async () => {
      try {
        map.resize()
        setTimeout(() => map.resize(), 0)

        const [metadata, visualOrders, nextOverlayData] = await Promise.all([
          fetchMap1933TileMetadata(),
          fetchVisualOrders(),
          fetchMap1933OverlayData(),
        ])
        setOverlayData(nextOverlayData)

        if (!metadata.exists) {
          console.error('PMTiles missing, run backend/scripts/build_pmtiles.py')
          if (metadata.error) console.error(metadata.error)
          map.fitBounds(START_BOUNDS, { padding: 24, duration: 0 })
          return
        }

        const pmtilesUrl = new URL(metadata.pmtilesUrl, API_BASE).toString()
        addSources(map, pmtilesUrl, visualOrders)
        addLayers(map, selectedTag)
        updateSelectedOwnedRegions(map, nextOverlayData, selectedTag)
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
      setMapInstance(null)
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    for (const layerId of [
      'selected-country-border-glow',
      'selected-country-border-main',
      'selected-microstate-border-glow',
      'selected-microstate-border-main',
    ]) {
      if (map.getLayer(layerId)) {
        map.setFilter(layerId, selectedCountryFilter(selectedTag))
      }
    }
    updateSelectedOwnedRegions(map, overlayData, selectedTag)
  }, [overlayData, selectedTag])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !state) return
    fetchMap1933OverlayData()
      .then((nextOverlayData) => {
        setOverlayData(nextOverlayData)
        updateSelectedOwnedRegions(map, nextOverlayData, selectedTag)
      })
      .catch((error) => console.error('Failed to refresh map overlay data:', error))
  }, [state?.turn])

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
      <div className="map-stack">
        <div ref={containerRef} className="map-container" />
        <MapOverlay map={mapInstance} overlayData={overlayData} selectedTag={selectedTag} />
      </div>
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
  map.addSource('selected-owned-regions', {
    type: 'geojson',
    data: EMPTY_GEOJSON,
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
    id: 'rivers-casing',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'rivers',
    minzoom: 3.5,
    paint: {
      'line-color': '#0f172a',
      'line-width': [
        'interpolate',
        ['linear'],
        ['zoom'],
        3.5,
        ['match', ['get', 'widthClass'], 3, 1.5, 2, 1.0, 0.55],
        7,
        ['match', ['get', 'widthClass'], 3, 2.8, 2, 1.8, 1.0],
      ],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 3.5, 0.06, 5, 0.14, 7, 0.22],
      'line-blur': 0.35,
    },
  } as any)

  map.addLayer({
    id: 'rivers-line',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'rivers',
    minzoom: 3.5,
    paint: {
      'line-color': '#60a5fa',
      'line-width': [
        'interpolate',
        ['linear'],
        ['zoom'],
        3.5,
        ['match', ['get', 'widthClass'], 3, 1.15, 2, 0.65, 0.32],
        7,
        ['match', ['get', 'widthClass'], 3, 2.2, 2, 1.35, 0.75],
      ],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 3.5, 0.18, 5, 0.42, 7, 0.7],
      'line-blur': 0.25,
    },
  } as any)

  map.addLayer({
    id: 'region-border',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'regions',
    minzoom: 3.8,
    paint: {
      'line-color': '#cbd5e1',
      'line-width': ['interpolate', ['linear'], ['zoom'], 3.8, 0, 4.5, 0.18, 6, 0.38, 8, 0.65],
      'line-opacity': ['interpolate', ['linear'], ['zoom'], 3.8, 0, 4.5, 0.14, 6, 0.28, 8, 0.45],
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
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 1.0, 5, 1.55, 8, 1.85],
      'line-opacity': 0.95,
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
    id: 'selected-country-border-glow',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'countries',
    filter: selectedCountryFilter(selectedTag),
    paint: {
      'line-color': '#facc15',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 2.6, 6, 4.0],
      'line-opacity': 0.28,
      'line-blur': 1.2,
    },
  } as any)

  map.addLayer({
    id: 'selected-country-border-main',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'countries',
    filter: selectedCountryFilter(selectedTag),
    paint: {
      'line-color': '#fde047',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 1.4, 6, 2.25],
      'line-opacity': 0.95,
    },
  } as any)

  map.addLayer({
    id: 'selected-owned-regions-glow',
    type: 'line',
    source: 'selected-owned-regions',
    paint: {
      'line-color': '#facc15',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 2.8, 6, 5],
      'line-opacity': 0.34,
      'line-blur': 1.4,
    },
  } as any)

  map.addLayer({
    id: 'selected-owned-regions-main',
    type: 'line',
    source: 'selected-owned-regions',
    paint: {
      'line-color': '#fde047',
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 1.2, 6, 2.2],
      'line-opacity': 0.92,
    },
  } as any)

  map.addLayer({
    id: 'selected-microstate-border-glow',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'microstates',
    filter: selectedCountryFilter(selectedTag),
    paint: {
      'line-color': '#facc15',
      'line-width': ['interpolate', ['linear'], ['zoom'], 3, 2.8, 7, 5],
      'line-opacity': 0.38,
      'line-blur': 1.2,
    },
  } as any)

  map.addLayer({
    id: 'selected-microstate-border-main',
    type: 'line',
    source: 'pax1933',
    'source-layer': 'microstates',
    filter: selectedCountryFilter(selectedTag),
    paint: {
      'line-color': '#fde047',
      'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1.4, 7, 2.3],
      'line-opacity': 0.95,
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
    id: 'region-labels',
    type: 'symbol',
    source: 'pax1933',
    'source-layer': 'region_label_points',
    minzoom: 4.35,
    layout: {
      'text-field': ['get', 'label'],
      'text-size': [
        'interpolate',
        ['linear'],
        ['zoom'],
        4.35,
        8.5,
        5.3,
        ['coalesce', ['get', 'labelSize'], 10],
        7,
        ['+', ['coalesce', ['get', 'labelSize'], 10], 2],
      ],
      'text-font': ['Open Sans Regular'],
      'text-allow-overlap': false,
      'text-ignore-placement': false,
      'text-variable-anchor': ['top', 'bottom', 'left', 'right'],
      'text-radial-offset': 0.35,
      'text-letter-spacing': 0.02,
      'symbol-sort-key': ['coalesce', ['get', 'labelPriority'], 1000],
    },
    paint: {
      'text-color': '#e5e7eb',
      'text-halo-color': '#020617',
      'text-halo-width': 1.4,
      'text-halo-blur': 0.35,
      'text-opacity': ['interpolate', ['linear'], ['zoom'], 4.3, 0, 4.8, 0.34, 5.4, 0.82, 7, 1],
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
      const tag = properties?.ownerTag || properties?.tag
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

function updateSelectedOwnedRegions(
  map: maplibregl.Map,
  overlayData: OverlayData | null,
  selectedTag: string,
) {
  const source = map.getSource('selected-owned-regions') as maplibregl.GeoJSONSource | undefined
  source?.setData(selectedOwnedRegions(overlayData, selectedTag))
}

function selectedOwnedRegions(overlayData: OverlayData | null, selectedTag: string): GeoJSON.FeatureCollection {
  if (!overlayData || !selectedTag) return EMPTY_GEOJSON

  return {
    type: 'FeatureCollection',
    features: overlayData.regions.features
      .filter((feature) => {
        const owner = overlayData.ownership[feature.properties.regionId] ?? feature.properties.ownerTag
        return owner === selectedTag
      })
      .map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          ownerTag: selectedTag,
        },
      })),
  }
}

function selectedCountryFilter(selectedTag: string): FilterSpecification {
  return ['any', ['==', ['get', 'ownerTag'], selectedTag], ['==', ['get', 'tag'], selectedTag]]
}

export { EUROPE_BOUNDS, WORLD_BOUNDS }
