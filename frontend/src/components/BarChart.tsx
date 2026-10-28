export interface Bar {
  label: string;
  value: number;
}

const H = 180;
const PAD = { t: 18, b: 24, l: 8, r: 8 };

/** Einfaches Balkendiagramm (SVG). */
export default function BarChart({ bars, title, format = (v: number) => String(v) }: { bars: Bar[]; title: string; format?: (v: number) => string }) {
  const max = Math.max(1, ...bars.map((b) => b.value));
  const W = Math.max(320, bars.length * 44);
  const slot = (W - PAD.l - PAD.r) / bars.length;
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} className="grid" />
        {bars.map((b, i) => {
          const h = (b.value / max) * (H - PAD.t - PAD.b);
          const x = PAD.l + i * slot + slot * 0.15;
          return (
            <g key={b.label}>
              <rect x={x} y={H - PAD.b - h} width={slot * 0.7} height={h} rx={3} fill="var(--primary)">
                <title>
                  {b.label}: {format(b.value)}
                </title>
              </rect>
              {b.value > 0 && (
                <text x={x + slot * 0.35} y={H - PAD.b - h - 4} textAnchor="middle" className="tick">
                  {format(b.value)}
                </text>
              )}
              <text x={x + slot * 0.35} y={H - 8} textAnchor="middle" className="tick">
                {b.label}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
