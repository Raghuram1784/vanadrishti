import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import { MapPin } from "lucide-react";
import type { Camera } from "@/types/api";
import { Empty } from "@/components/ui/shared";
function Fit({ cameras }: { cameras: Camera[] }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(
      L.latLngBounds(cameras.map((c) => [c.latitude, c.longitude])),
      { padding: [50, 50], maxZoom: 14 },
    );
  }, [map, cameras]);
  return null;
}
const colors: Record<string, string> = {
  CORE: "#bf9b59",
  RESTRICTED: "#d28a55",
  BUFFER: "#65a78c",
  PUBLIC: "#86aab0",
};
export function CameraMap({ cameras }: { cameras: Camera[] }) {
  const [tileError, setTileError] = useState(false);
  return (
    <section className="panel map-panel">
      <div className="panel-heading">
        <div>
          <h2>Forest camera network</h2>
          <p>
            <MapPin size={12} /> Simulated camera locations for prototype
            demonstration
          </p>
        </div>
        <span className="subtle-badge">{cameras.length} LOCATIONS</span>
      </div>
      {cameras.length ? (
        <div className="map-wrap">
          <MapContainer
            center={[cameras[0].latitude, cameras[0].longitude]}
            zoom={12}
            scrollWheelZoom={false}
            className="forest-map"
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              eventHandlers={{ tileerror: () => setTileError(true) }}
            />
            <Fit cameras={cameras} />
            {cameras.map((camera) => (
              <CircleMarker
                key={camera.id}
                center={[camera.latitude, camera.longitude]}
                radius={9}
                pathOptions={{
                  color: "#fff",
                  weight: 2,
                  fillColor: colors[camera.zone] || "#65a78c",
                  fillOpacity: 1,
                }}
              >
                <Popup>
                  <strong>{camera.name}</strong>
                  <br />
                  {camera.id} · {camera.zone}
                  <br />
                  Allowed hours:{" "}
                  {camera.allowed_hours
                    ? `${camera.allowed_hours.start}–${camera.allowed_hours.end}`
                    : "Unrestricted"}
                  <br />
                  Status: {camera.active ? "Active" : "Inactive"}
                  <br />
                  <b>Simulated Location</b>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
          {tileError && (
            <div className="map-notice">
              Map tiles unavailable. Simulated camera markers remain available.
            </div>
          )}
        </div>
      ) : (
        <Empty title="Camera map unavailable">
          Connect to the backend to load the simulated registry.
        </Empty>
      )}
      <div className="map-legend">
        {Object.entries(colors).map(([zone, color]) => (
          <span key={zone}>
            <i style={{ background: color }} />
            {zone}
          </span>
        ))}
        <span className="legend-note">DEMONSTRATION LOCATIONS ONLY</span>
      </div>
    </section>
  );
}
