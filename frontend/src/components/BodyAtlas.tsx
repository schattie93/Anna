import type { BodyMark, BodyView, MarkKind } from "../api";

export const KIND_COLOR: Record<MarkKind, string> = {
  pain: "#d92d20",
  tension: "#f79009",
  numbness: "#7a5af8",
  swelling: "#0e9edb",
  scar: "#667085",
  other: "#12b76a",
};

export const VB_W = 200;
export const VB_H = 470;

const SKIN = "var(--atlas-fill)";
const LINE = "var(--atlas-line)";

function Limb({ a, b, w }: { a: [number, number]; b: [number, number]; w: number }) {
  return <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={SKIN} strokeWidth={w} strokeLinecap="round" />;
}

/** Stilisierte Körpersilhouette (Vorder-/Rückansicht). Koordinaten im viewBox 0 0 200 470. */
function Silhouette({ view }: { view: BodyView }) {
  const mirror = (p: [number, number]): [number, number] => [VB_W - p[0], p[1]];
  const limbs: [[number, number], [number, number], number][] = [
    [[58, 84], [36, 150], 20], // Oberarm
    [[36, 150], [26, 214], 16], // Unterarm
    [[80, 246], [76, 334], 32], // Oberschenkel
    [[76, 334], [76, 428], 23], // Unterschenkel
  ];
  return (
    <g>
      {limbs.map(([a, b, w], i) => (
        <g key={i}>
          <Limb a={a} b={b} w={w} />
          <Limb a={mirror(a)} b={mirror(b)} w={w} />
        </g>
      ))}
      <circle cx={26} cy={226} r={9} fill={SKIN} />
      <circle cx={174} cy={226} r={9} fill={SKIN} />
      <ellipse cx={72} cy={450} rx={15} ry={8} fill={SKIN} />
      <ellipse cx={128} cy={450} rx={15} ry={8} fill={SKIN} />
      <path d="M60 76 Q100 64 140 76 L146 196 Q148 232 138 262 Q100 276 62 262 Q52 232 54 196 Z" fill={SKIN} />
      <rect x={91} y={54} width={18} height={20} rx={6} fill={SKIN} />
      <ellipse cx={100} cy={33} rx={20} ry={25} fill={SKIN} />
      <g stroke={LINE} strokeWidth={1.2} fill="none" opacity={0.7}>
        {view === "front" ? (
          <>
            <path d="M100 96 L100 232" />
            <path d="M74 108 Q100 120 126 108" />
            <circle cx={100} cy={176} r={1.8} fill={LINE} />
            <path d="M82 230 Q100 240 118 230" />
          </>
        ) : (
          <>
            <path d="M100 66 L100 238" strokeDasharray="3 3" />
            <path d="M72 100 Q82 128 90 140 M128 100 Q118 128 110 140" />
            <path d="M82 236 Q100 250 118 236" />
          </>
        )}
      </g>
    </g>
  );
}

export default function BodyAtlas({
  view,
  marks,
  onPlace,
  selectedId,
  onSelect,
}: {
  view: BodyView;
  marks: BodyMark[];
  onPlace?: (x: number, y: number) => void;
  selectedId?: number | null;
  onSelect?: (m: BodyMark) => void;
}) {
  function click(e: React.PointerEvent<SVGSVGElement>) {
    if (!onPlace) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    onPlace(Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000);
  }

  return (
    <svg
      className={onPlace ? "atlas placing" : "atlas"}
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      role="img"
      aria-label={view === "front" ? "Körper von vorne" : "Körper von hinten"}
      onPointerUp={click}
    >
      <Silhouette view={view} />
      <text x={6} y={14} className="atlas-side">{view === "front" ? "R" : "L"}</text>
      <text x={VB_W - 6} y={14} textAnchor="end" className="atlas-side">{view === "front" ? "L" : "R"}</text>
      {marks
        .filter((m) => m.view === view && !m.voided)
        .map((m) => {
          const r = 5 + (m.intensity ?? 5) * 0.9;
          const cx = m.x * VB_W;
          const cy = m.y * VB_H;
          return (
            <g
              key={m.id}
              className={selectedId === m.id ? "mark selected" : "mark"}
              onPointerUp={(e) => {
                if (onSelect) {
                  e.stopPropagation();
                  onSelect(m);
                }
              }}
            >
              <circle cx={cx} cy={cy} r={r} fill={KIND_COLOR[m.kind]} fillOpacity={0.45} stroke={KIND_COLOR[m.kind]} strokeWidth={selectedId === m.id ? 3 : 1.5} />
              {m.intensity !== null && (
                <text x={cx} y={cy + 3.5} textAnchor="middle" className="mark-label">
                  {m.intensity}
                </text>
              )}
            </g>
          );
        })}
    </svg>
  );
}
