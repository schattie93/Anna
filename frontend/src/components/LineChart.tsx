import { formatDate } from "../labels";

export interface Point {
  date: string; // ISO-Datum
  value: number;
}

export interface Series {
  label: string;
  color: string;
  points: Point[];
}

const W = 640;
const H = 220;
const PAD = { l: 44, r: 16, t: 14, b: 30 };

function niceStep(range: number): number {
  const raw = range / 4;
  const pow = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const n = raw / pow;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * pow;
}

/** Einfaches, responsives SVG-Liniendiagramm (Zeitachse), optional mit Ziel-Linie. */
export default function LineChart({
  series,
  target,
  yMin,
  yMax,
  unit,
  title,
}: {
  series: Series[];
  target?: number | null;
  yMin?: number;
  yMax?: number;
  unit?: string | null;
  title: string;
}) {
  const all = series.flatMap((s) => s.points);
  if (all.length === 0) return null;
  const times = all.map((p) => new Date(p.date).getTime());
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const values = [...all.map((p) => p.value), ...(target != null ? [target] : [])];
  let lo = yMin ?? Math.min(...values);
  let hi = yMax ?? Math.max(...values);
  if (hi === lo) {
    hi += 1;
    lo -= 1;
  }
  const step = niceStep(hi - lo);
  if (yMin === undefined) lo = Math.floor(lo / step) * step;
  if (yMax === undefined) hi = Math.ceil(hi / step) * step;

  const x = (t: number) => PAD.l + (t1 === t0 ? (W - PAD.l - PAD.r) / 2 : ((t - t0) / (t1 - t0)) * (W - PAD.l - PAD.r));
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 1000) / 1000);
  const dateTicks = [...new Set([times[0], times[times.length - 1], ...times])].sort((a, b) => a - b);
  const labelEvery = Math.ceil(dateTicks.length / 6);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="grid" />
            <text x={PAD.l - 6} y={y(v) + 4} textAnchor="end" className="tick">
              {String(v).replace(".", ",")}
            </text>
          </g>
        ))}
        {dateTicks.map((t, i) =>
          i % labelEvery === 0 ? (
            <text key={t} x={x(t)} y={H - 10} textAnchor="middle" className="tick">
              {formatDate(new Date(t).toISOString()).slice(0, 5)}
            </text>
          ) : null,
        )}
        {target != null && (
          <g>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(target)} y2={y(target)} className="target" />
            <text x={W - PAD.r} y={y(target) - 4} textAnchor="end" className="tick">
              Ziel {String(target).replace(".", ",")}
            </text>
          </g>
        )}
        {series.map((s) => {
          const pts = [...s.points].sort((a, b) => a.date.localeCompare(b.date));
          return (
            <g key={s.label} stroke={s.color} fill={s.color}>
              <polyline fill="none" strokeWidth={2.5} strokeLinejoin="round" points={pts.map((p) => `${x(new Date(p.date).getTime())},${y(p.value)}`).join(" ")} />
              {pts.map((p) => (
                <circle key={p.date + p.value} cx={x(new Date(p.date).getTime())} cy={y(p.value)} r={4}>
                  <title>
                    {s.label}: {String(p.value).replace(".", ",")}
                    {unit ? ` ${unit}` : ""} am {formatDate(p.date)}
                  </title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      {series.length > 1 && (
        <figcaption className="legend">
          {series.map((s) => (
            <span key={s.label}>
              <i style={{ background: s.color }} /> {s.label}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}
