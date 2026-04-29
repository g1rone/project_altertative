import { useEffect, useRef } from 'react'
import type maplibregl from 'maplibre-gl'
import { buildDynamicCountryLabels } from './labelEngine'
import type { DynamicCountryLabel, LngLat, OverlayData, OverlayRegionFeature } from './overlayTypes'

type Props = {
  map: maplibregl.Map | null
  overlayData: OverlayData | null
  selectedTag: string
}

export default function MapOverlay({ map, overlayData, selectedTag }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (!map || !overlayData || !hostRef.current || !canvasRef.current) return

    const host = hostRef.current
    const canvas = canvasRef.current
    const draw = () => drawOverlay(map, overlayData, selectedTag, host, canvas)
    const observer = new ResizeObserver(draw)
    observer.observe(host)

    map.on('render', draw)
    map.on('move', draw)
    map.on('zoom', draw)
    map.on('resize', draw)
    draw()

    return () => {
      observer.disconnect()
      map.off('render', draw)
      map.off('move', draw)
      map.off('zoom', draw)
      map.off('resize', draw)
    }
  }, [map, overlayData, selectedTag])

  return (
    <div className="map-overlay" ref={hostRef} aria-hidden="true">
      <canvas ref={canvasRef} />
    </div>
  )
}

function drawOverlay(
  map: maplibregl.Map,
  overlayData: OverlayData,
  selectedTag: string,
  host: HTMLDivElement,
  canvas: HTMLCanvasElement,
) {
  const width = host.clientWidth
  const height = host.clientHeight
  const ratio = window.devicePixelRatio || 1
  if (width <= 0 || height <= 0) return

  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio)
    canvas.height = Math.round(height * ratio)
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
  }

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  ctx.clearRect(0, 0, width, height)

  drawSelectedGlow(ctx, map, overlayData, selectedTag)

  const labels = buildDynamicCountryLabels(overlayData.regions, overlayData.ownership, overlayData.countries, map.getZoom())
  for (const label of labels) drawCountryLabel(ctx, map, label)
}

function drawSelectedGlow(
  ctx: CanvasRenderingContext2D,
  map: maplibregl.Map,
  overlayData: OverlayData,
  selectedTag: string,
) {
  if (!selectedTag) return
  const selected = overlayData.regions.features.filter((feature) => {
    const owner = overlayData.ownership[feature.properties.regionId] ?? feature.properties.ownerTag
    return owner === selectedTag
  })
  if (!selected.length) return

  ctx.save()
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.strokeStyle = '#facc15'
  ctx.shadowColor = '#facc15'
  ctx.shadowBlur = 18
  ctx.globalAlpha = 0.34
  ctx.lineWidth = 5
  drawRegionPaths(ctx, map, selected)
  ctx.stroke()

  ctx.shadowBlur = 0
  ctx.globalAlpha = 0.88
  ctx.lineWidth = 1.8
  drawRegionPaths(ctx, map, selected)
  ctx.stroke()
  ctx.restore()
}

function drawRegionPaths(ctx: CanvasRenderingContext2D, map: maplibregl.Map, features: OverlayRegionFeature[]) {
  ctx.beginPath()
  for (const feature of features) {
    const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates
    for (const polygon of polygons) {
      const ring = polygon[0]
      if (!ring?.length) continue
      ring.forEach((coordinate, index) => {
        const point = map.project({ lng: coordinate[0], lat: coordinate[1] })
        if (index === 0) ctx.moveTo(point.x, point.y)
        else ctx.lineTo(point.x, point.y)
      })
      ctx.closePath()
    }
  }
}

function drawCountryLabel(ctx: CanvasRenderingContext2D, map: maplibregl.Map, label: DynamicCountryLabel) {
  const anchor = label.kind === 'line' && label.anchorLine ? midpoint(label.anchorLine[0], label.anchorLine[label.anchorLine.length - 1]) : label.anchorPoint
  if (!anchor) return
  const projected = map.project({ lng: anchor[0], lat: anchor[1] })
  const angle = label.kind === 'line' && label.anchorLine ? screenAngle(map, label.anchorLine) : 0

  ctx.save()
  ctx.translate(projected.x, projected.y)
  ctx.rotate(angle)
  ctx.globalAlpha = label.opacity
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.font = `800 ${label.fontSize}px "Open Sans", Inter, system-ui, sans-serif`
  ctx.lineJoin = 'round'
  ctx.shadowColor = 'rgba(2, 6, 23, 0.82)'
  ctx.shadowBlur = label.labelClass === 'major' ? 10 : 6
  ctx.strokeStyle = '#020617'
  ctx.lineWidth = label.labelClass === 'major' ? 7 : 5
  drawLetterSpacedText(ctx, label.text, 0, 0, label.letterSpacing, true)
  ctx.shadowBlur = 4
  ctx.fillStyle = '#f8fafc'
  drawLetterSpacedText(ctx, label.text, 0, 0, label.letterSpacing, false)
  ctx.restore()
}

function drawLetterSpacedText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  spacing: number,
  stroke: boolean,
) {
  const chars = [...text]
  const totalWidth = chars.reduce((sum, char, index) => sum + ctx.measureText(char).width + (index ? spacing : 0), 0)
  let cursor = x - totalWidth / 2
  for (const char of chars) {
    const charWidth = ctx.measureText(char).width
    if (stroke) ctx.strokeText(char, cursor + charWidth / 2, y)
    else ctx.fillText(char, cursor + charWidth / 2, y)
    cursor += charWidth + spacing
  }
}

function midpoint(a: LngLat, b: LngLat): LngLat {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}

function screenAngle(map: maplibregl.Map, line: LngLat[]) {
  const start = map.project({ lng: line[0][0], lat: line[0][1] })
  const end = map.project({ lng: line[line.length - 1][0], lat: line[line.length - 1][1] })
  let angle = Math.atan2(end.y - start.y, end.x - start.x)
  if (angle > Math.PI / 2) angle -= Math.PI
  if (angle < -Math.PI / 2) angle += Math.PI
  return angle
}
