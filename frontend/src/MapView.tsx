import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { API } from './lib/auth'

type Station = { code: string; name: string; latitude: number; longitude: number }
type Mission = { id: string; objective: string; status: string }
type Vehicle = { id: string; registration_number: string }

// Core expedition supply route coordinates
const EXPEDITION_ROUTE: [number, number][] = [
  [73.8278, 15.4989], // Goa (NCPOR HQ)
  [72.8777, 19.0760], // Mumbai Port
  [18.4241, -33.9249], // Cape Town (Staging Hub)
  [76.18, -69.4], // Bharati Station (Larsemann Hills)
  [11.95, 78.92], // Himadri Station (Svalbard)
]

/** Live Map (MapLibre + Esri Light Gray Canvas — no key required)
 * Shows Stations, Active Field Teams, Vehicles & Maritime Supply Route.
 */
export default function MapView({ token }: { token: string }) {
  const divRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const h = { Authorization: `Bearer ${token}` }
    let map: maplibregl.Map | null = null
    let dead = false

    async function get<T>(path: string): Promise<T[]> {
      try {
        const r = await fetch(`${API}${path}`, { headers: h })
        return r.ok ? ((await r.json()) as T[]) : []
      } catch {
        return []
      }
    }

    ;(async () => {
      const [stations, missions, vehicles] = await Promise.all([
        get<Station>('/api/v1/stations'),
        get<Mission>('/api/v1/field-missions'),
        get<Vehicle>('/api/v1/vehicles'),
      ])
      if (dead || !divRef.current) return

      map = new maplibregl.Map({
        container: divRef.current,
        style: {
          version: 8,
          sources: {
            esri_base: {
              type: 'raster',
              tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}'],
              tileSize: 256,
              attribution: 'Esri, HERE, Garmin, OpenStreetMap contributors',
            },
            esri_ref: {
              type: 'raster',
              tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}'],
              tileSize: 256,
            },
          },
          layers: [
            { id: 'esri_base_layer', type: 'raster', source: 'esri_base' },
            { id: 'esri_ref_layer', type: 'raster', source: 'esri_ref' },
          ],
        },
        center: [55.0, -35.0],
        zoom: 2,
      })

      map.on('load', () => {
        if (!map) return

        // Add Supply Route Line
        map.addSource('route', {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'LineString',
              coordinates: EXPEDITION_ROUTE,
            },
          },
        })

        map.addLayer({
          id: 'route-line-bg',
          type: 'line',
          source: 'route',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#0284c7',
            'line-width': 4,
            'line-opacity': 0.3,
          },
        })

        map.addLayer({
          id: 'route-line-dash',
          type: 'line',
          source: 'route',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
          paint: {
            'line-color': '#0369a1',
            'line-width': 2,
            'line-dasharray': [2, 3],
          },
        })
      })

      // Station Markers
      stations.forEach((s) => {
        const el = document.createElement('div')
        el.className = 'w-4 h-4 bg-sky-500 rounded-full border-2 border-white shadow-md cursor-pointer hover:scale-125 transition-transform'
        
        new maplibregl.Marker({ element: el })
          .setLngLat([s.longitude, s.latitude])
          .setPopup(
            new maplibregl.Popup({ className: 'polar-map-popup', offset: 12 }).setHTML(`
              <div class="p-2 bg-white text-slate-800 rounded border border-slate-200 text-xs shadow-sm">
                <div class="font-bold text-sky-700">${s.code} — ${s.name}</div>
                <div class="text-[10px] text-slate-500 mt-1">Lat: ${s.latitude.toFixed(2)}° | Lng: ${s.longitude.toFixed(2)}°</div>
              </div>
            `)
          )
          .addTo(map!)
      })

      // Mission Markers
      missions
        .filter((m) => m.status === 'ACTIVE' || m.status === 'DEPLOYED')
        .forEach((m, i) => {
          const el = document.createElement('div')
          el.className = 'w-4 h-4 bg-rose-500 rounded-full border-2 border-white animate-pulse shadow-md cursor-pointer hover:scale-125 transition-transform'

          new maplibregl.Marker({ element: el })
            .setLngLat([76.18 + (i + 1) * 0.6, -69.4 + (i + 1) * 0.35])
            .setPopup(
              new maplibregl.Popup({ className: 'polar-map-popup', offset: 12 }).setHTML(`
                <div class="p-2 bg-white text-slate-800 rounded border border-rose-200 text-xs shadow-sm">
                  <div class="font-bold text-rose-600">Mission: ${m.id}</div>
                  <div class="mt-1">${m.objective}</div>
                  <span class="inline-block mt-1 px-1.5 py-0.5 text-[9px] font-mono bg-rose-50 text-rose-700 rounded border border-rose-200 font-bold">${m.status}</span>
                </div>
              `)
            )
            .addTo(map!)
        })

      // Vehicle Markers
      vehicles.forEach((v, i) => {
        const el = document.createElement('div')
        el.className = 'w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white shadow-md cursor-pointer hover:scale-125 transition-transform'

        new maplibregl.Marker({ element: el })
          .setLngLat([76.18 - (i + 1) * 0.5, -69.4 - (i + 1) * 0.3])
          .setPopup(
            new maplibregl.Popup({ className: 'polar-map-popup', offset: 12 }).setHTML(`
              <div class="p-2 bg-white text-slate-800 rounded border border-emerald-200 text-xs shadow-sm">
                <div class="font-bold text-emerald-700">Vehicle Assets</div>
                <div class="mt-1 font-mono text-[11px]">${v.registration_number || v.id}</div>
              </div>
            `)
          )
          .addTo(map!)
      })
    })()

    return () => {
      dead = true
      map?.remove()
    }
  }, [token])

  return (
    <div className="card overflow-hidden relative">
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-sky-500 animate-ping"></span>
          Geospatial Polar Operations Map
        </h3>
        <span className="text-[11px] font-mono text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200 font-semibold">
          ESRI LIGHT GRAY · KEYLESS
        </span>
      </div>

      <div ref={divRef} className="h-[420px] w-full rounded-xl overflow-hidden border border-slate-200 shadow-inner" />

      <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <div className="flex items-center gap-2 bg-slate-50 p-2 rounded-lg border border-slate-200">
          <span className="w-3 h-3 rounded-full bg-sky-500 border border-white shadow-xs"></span>
          <span className="text-slate-700 font-medium">Research Stations</span>
        </div>
        <div className="flex items-center gap-2 bg-slate-50 p-2 rounded-lg border border-slate-200">
          <span className="w-3 h-3 rounded-full bg-rose-500 border border-white shadow-xs animate-pulse"></span>
          <span className="text-slate-700 font-medium">Active Field Missions</span>
        </div>
        <div className="flex items-center gap-2 bg-slate-50 p-2 rounded-lg border border-slate-200">
          <span className="w-3 h-3 rounded-full bg-emerald-500 border border-white shadow-xs"></span>
          <span className="text-slate-700 font-medium">Deployed Vehicles</span>
        </div>
        <div className="flex items-center gap-2 bg-slate-50 p-2 rounded-lg border border-slate-200">
          <span className="w-6 h-0 border-t-2 border-dashed border-sky-600"></span>
          <span className="text-slate-700 font-medium">Maritime Supply Route</span>
        </div>
      </div>
    </div>
  )
}
