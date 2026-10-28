import { useCallback, useEffect, useRef, useState } from "react";

interface Stroke {
  color: string;
  width: number;
  points: { x: number; y: number; p: number }[];
}

const COLORS = ["#111111", "#d92d20", "#0e9edb", "#12b76a"];

/**
 * Zeichenfläche für Stift und Finger (Pointer Events, Druckempfindlichkeit, Handballen-Ablehnung).
 * Optional mit Hintergrundbild (zum Einzeichnen in Fotos). Liefert ein PNG über onSave.
 */
export default function DrawingCanvas({
  background,
  onSave,
  onCancel,
  saving,
}: {
  background?: string;
  onSave: (png: Blob) => void;
  onCancel: () => void;
  saving?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const strokes = useRef<Stroke[]>([]);
  const current = useRef<Stroke | null>(null);
  const penSeen = useRef(false);
  const [color, setColor] = useState(COLORS[0]);
  const [width, setWidth] = useState(3);
  const [size, setSize] = useState({ w: 1200, h: 800 });
  const [count, setCount] = useState(0);

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (imageRef.current) ctx.drawImage(imageRef.current, 0, 0, canvas.width, canvas.height);
    ctx.lineCap = ctx.lineJoin = "round";
    for (const s of [...strokes.current, ...(current.current ? [current.current] : [])]) {
      ctx.strokeStyle = s.color;
      for (let i = 1; i < s.points.length; i++) {
        const a = s.points[i - 1];
        const b = s.points[i];
        ctx.lineWidth = s.width * (0.5 + b.p);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      if (s.points.length === 1) {
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(s.points[0].x, s.points[0].y, s.width / 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }, []);

  useEffect(() => {
    if (!background) {
      redraw();
      return;
    }
    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      const scale = Math.min(1, 1600 / Math.max(img.naturalWidth, img.naturalHeight));
      setSize({ w: Math.round(img.naturalWidth * scale), h: Math.round(img.naturalHeight * scale) });
    };
    img.src = background;
  }, [background, redraw]);

  useEffect(redraw, [size, redraw]);

  function pos(e: React.PointerEvent<HTMLCanvasElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * size.w,
      y: ((e.clientY - rect.top) / rect.height) * size.h,
      p: e.pointerType === "pen" && e.pressure > 0 ? e.pressure : 0.5,
    };
  }

  function down(e: React.PointerEvent<HTMLCanvasElement>) {
    if (e.pointerType === "pen") penSeen.current = true;
    if (e.pointerType === "touch" && penSeen.current) return; // Handballen ignorieren, sobald ein Stift benutzt wurde
    e.currentTarget.setPointerCapture(e.pointerId);
    current.current = { color, width: width * (size.w / 600), points: [pos(e)] };
    redraw();
  }
  function move(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!current.current) return;
    const events = e.nativeEvent.getCoalescedEvents?.() ?? [e.nativeEvent];
    const rect = e.currentTarget.getBoundingClientRect();
    for (const ev of events) {
      current.current.points.push({
        x: ((ev.clientX - rect.left) / rect.width) * size.w,
        y: ((ev.clientY - rect.top) / rect.height) * size.h,
        p: ev.pointerType === "pen" && ev.pressure > 0 ? ev.pressure : 0.5,
      });
    }
    redraw();
  }
  function up() {
    if (!current.current) return;
    strokes.current.push(current.current);
    current.current = null;
    setCount(strokes.current.length);
    redraw();
  }

  function undo() {
    strokes.current.pop();
    setCount(strokes.current.length);
    redraw();
  }
  function clear() {
    strokes.current = [];
    setCount(0);
    redraw();
  }
  function save() {
    canvasRef.current?.toBlob((b) => b && onSave(b), "image/png");
  }

  return (
    <div className="stack drawing">
      <div className="toolbar">
        {COLORS.map((c) => (
          <button key={c} type="button" className={c === color ? "swatch on" : "swatch"} style={{ background: c }} onClick={() => setColor(c)} aria-label={`Farbe ${c}`} />
        ))}
        {[2, 4, 8].map((w) => (
          <button key={w} type="button" className={w === width ? "btn small primary" : "btn small"} onClick={() => setWidth(w)}>
            {w === 2 ? "dünn" : w === 4 ? "mittel" : "dick"}
          </button>
        ))}
        <button type="button" className="btn small" onClick={undo} disabled={count === 0}>
          ↶ Rückgängig
        </button>
        <button type="button" className="btn small" onClick={clear} disabled={count === 0}>
          Leeren
        </button>
      </div>
      <canvas
        ref={canvasRef}
        width={size.w}
        height={size.h}
        className="canvas"
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
      />
      <div className="actions">
        <button type="button" className="btn" onClick={onCancel}>
          Abbrechen
        </button>
        <button type="button" className="btn primary big" onClick={save} disabled={saving || (count === 0 && !background)}>
          Speichern
        </button>
      </div>
    </div>
  );
}
