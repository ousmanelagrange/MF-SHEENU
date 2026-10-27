// Trafic de l'API par tranche de 15 minutes : une barre par tranche, la part en erreur
// serveur en rouge au pied de la barre. Dessiné à la main en SVG (pas de bibliothèque).

type Bucket = { at: string; requests: number; errors_4xx: number; errors_5xx: number; avg_ms: number; max_ms: number };

export function TrafficChart({ data }: { data: Bucket[] }) {
  const W = 960;
  const H = 180;
  const left = 44;
  const bottom = 24;
  if (data.length === 0) return <p className="empty-note">Pas encore de trafic enregistré.</p>;
  const max = Math.max(1, ...data.map((d) => d.requests));
  const start = new Date(data[0].at).getTime();
  const end = new Date(data[data.length - 1].at).getTime() + 15 * 60_000;
  const x = (iso: string) => left + ((new Date(iso).getTime() - start) / (end - start)) * (W - left - 8);
  const barW = Math.max(2, ((W - left - 8) * 15 * 60_000) / (end - start) - 1);
  const y = (n: number) => H - bottom - (n / max) * (H - bottom - 12);
  const hours = Array.from(new Set(data.map((d) => new Date(d.at).setMinutes(0, 0, 0)))).filter((_, i, a) => a.length < 12 || i % Math.ceil(a.length / 12) === 0);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="traffic-chart" role="img" aria-label="Requêtes par quart d'heure">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={left} x2={W - 8} y1={y(max * f)} y2={y(max * f)} className="traffic-chart__grid" />
          <text x={left - 8} y={y(max * f) + 4} textAnchor="end" className="traffic-chart__tick">
            {Math.round(max * f)}
          </text>
        </g>
      ))}
      {data.map((d) => (
        <g key={d.at}>
          <title>{`${new Date(d.at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })} : ${d.requests} requêtes, ${d.errors_5xx} erreurs serveur, ${d.avg_ms} ms en moyenne`}</title>
          <rect x={x(d.at)} y={y(d.requests)} width={barW} height={H - bottom - y(d.requests)} className="traffic-chart__bar" />
          {d.errors_5xx > 0 && <rect x={x(d.at)} y={y(d.errors_5xx)} width={barW} height={H - bottom - y(d.errors_5xx)} className="traffic-chart__error" />}
        </g>
      ))}
      {hours.map((h) => (
        <text key={h} x={x(new Date(h).toISOString())} y={H - 6} className="traffic-chart__tick">
          {new Date(h).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
        </text>
      ))}
    </svg>
  );
}
