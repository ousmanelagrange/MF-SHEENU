// Carte du monde (projection Equal Earth) avec un cercle par pays, d'aire proportionnelle
// au nombre de personnes qui y vivent. Les données des frontières se chargent à la demande.

import { geoArea, geoCentroid, geoEqualEarth, geoPath } from "d3-geo";
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";
import { useEffect, useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import { isoOf } from "./countries";

type CountryFeature = Feature<Polygon | MultiPolygon, { name: string }>;
export type Point = { country: string; count: number };

const W = 960;
const H = 470;

/** Centre du plus grand morceau d'un pays : la France reste en Europe malgré la Guyane. */
function mainCentroid(f: CountryFeature): [number, number] {
  if (f.geometry.type !== "MultiPolygon") return geoCentroid(f);
  const parts = f.geometry.coordinates.map((coordinates) => ({ type: "Polygon" as const, coordinates }));
  const biggest = parts.reduce((a, b) => (geoArea(b) > geoArea(a) ? b : a));
  return geoCentroid(biggest);
}

export function DiasporaMap({ points, selected, onSelect }: { points: Point[]; selected: string | null; onSelect: (c: string) => void }) {
  const [countries, setCountries] = useState<CountryFeature[] | null>(null);

  useEffect(() => {
    void import("world-atlas/countries-110m.json").then((m) => {
      const topo = m.default as unknown as Topology<{ countries: GeometryCollection<{ name: string }> }>;
      const fc = feature(topo, topo.objects.countries) as unknown as FeatureCollection<Polygon | MultiPolygon, { name: string }>;
      setCountries(fc.features.filter((f) => f.properties.name !== "Antarctica"));
    });
  }, []);

  const projection = useMemo(() => geoEqualEarth().fitExtent([[8, 8], [W - 8, H - 8]], { type: "Sphere" }), []);
  const path = useMemo(() => geoPath(projection), [projection]);

  const dots = useMemo(() => {
    if (!countries) return [];
    const byId = new Map(countries.map((f) => [String(f.id), f]));
    const max = Math.max(1, ...points.map((p) => p.count));
    return points
      .map((p) => {
        const f = byId.get(isoOf(p.country) ?? "");
        const xy = f ? projection(mainCentroid(f)) : null;
        return xy ? { ...p, x: xy[0], y: xy[1], r: 4 + 30 * Math.sqrt(p.count / max) } : null;
      })
      .filter((d): d is NonNullable<typeof d> => d !== null)
      .sort((a, b) => b.r - a.r); // les petits cercles dessinés par-dessus restent cliquables
  }, [countries, points, projection]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="diaspora-map" role="img" aria-label="Carte des pays où vit la famille">
      <path d={path({ type: "Sphere" }) ?? ""} className="diaspora-map__sea" />
      {countries?.map((f) => (
        <path key={String(f.id) + f.properties.name} d={path(f) ?? ""} className="diaspora-map__land" />
      ))}
      {dots.map((d) => (
        <g key={d.country} className={`diaspora-map__dot${selected === d.country ? " is-selected" : ""}`} onClick={() => onSelect(d.country)}>
          <circle cx={d.x} cy={d.y} r={d.r}>
            <title>{`${d.country} : ${d.count}`}</title>
          </circle>
          {d.r > 14 && (
            <text x={d.x} y={d.y + 4} textAnchor="middle">
              {d.count}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
