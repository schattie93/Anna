import { useEffect, useMemo, useState } from "react";
import type { Appointment } from "../api";
import { AppointmentDialog, NewAppointmentDialog } from "../components/AppointmentDialog";
import { ErrorBox } from "../components/fields";
import { useApi } from "../hooks";
import { WEEKDAY, addDays, formatDate, formatTime, isoDate, weekStart } from "../labels";

const FIRST_HOUR = 7;
const LAST_HOUR = 20;
const HOUR_PX = 64;

function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => window.matchMedia("(max-width: 760px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 760px)");
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return narrow;
}

export default function CalendarPage() {
  const narrow = useNarrow();
  const [anchor, setAnchor] = useState(() => new Date());
  const [mode, setMode] = useState<"week" | "day" | null>(null);
  const view = mode ?? (narrow ? "day" : "week");
  const [selected, setSelected] = useState<Appointment | null>(null);
  const [creating, setCreating] = useState<Date | null>(null);

  const days = useMemo(() => {
    if (view === "day") return [new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate())];
    const mon = weekStart(anchor);
    return Array.from({ length: 6 }, (_, i) => addDays(mon, i));
  }, [anchor, view]);

  const from = days[0];
  const to = addDays(days[days.length - 1], 1);
  const { data, error, reload } = useApi<Appointment[]>(`/appointments?${new URLSearchParams({ start: from.toISOString(), end: to.toISOString() })}`);
  const shown = (data ?? []).filter((a) => a.status !== "cancelled");

  function shift(dir: number) {
    setAnchor((a) => addDays(a, dir * (view === "day" ? 1 : 7)));
  }

  function slotClick(day: Date, e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const minutes = Math.round((((e.clientY - rect.top) / HOUR_PX) * 60) / 15) * 15;
    const d = new Date(day);
    d.setHours(FIRST_HOUR, 0, 0, 0);
    d.setMinutes(minutes);
    setCreating(d);
  }

  const hours = Array.from({ length: LAST_HOUR - FIRST_HOUR }, (_, i) => FIRST_HOUR + i);
  const todayIso = isoDate(new Date());
  const title =
    view === "day"
      ? `${WEEKDAY[days[0].getDay()]}, ${formatDate(isoDate(days[0]))}`
      : `${formatDate(isoDate(days[0]))} – ${formatDate(isoDate(days[days.length - 1]))}`;

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Termine</h1>
        <div className="actions">
          <button className="btn" onClick={() => shift(-1)} aria-label="Zurück">
            ‹
          </button>
          <button className="btn" onClick={() => setAnchor(new Date())}>
            Heute
          </button>
          <button className="btn" onClick={() => shift(1)} aria-label="Weiter">
            ›
          </button>
          <button className={view === "day" ? "btn primary" : "btn"} onClick={() => setMode("day")}>
            Tag
          </button>
          <button className={view === "week" ? "btn primary" : "btn"} onClick={() => setMode("week")}>
            Woche
          </button>
          <button
            className="btn primary"
            onClick={() => {
              const d = new Date();
              d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
              setCreating(d);
            }}
          >
            + Termin
          </button>
        </div>
      </div>
      <p className="muted cal-title">{title}</p>
      <ErrorBox error={error} />

      <div className="cal card" style={{ ["--cols" as string]: days.length }}>
        <div className="cal-head">
          <span />
          {days.map((d) => (
            <div key={d.toISOString()} className={isoDate(d) === todayIso ? "cal-day today" : "cal-day"}>
              {WEEKDAY[d.getDay()]} {String(d.getDate()).padStart(2, "0")}.{String(d.getMonth() + 1).padStart(2, "0")}.
            </div>
          ))}
        </div>
        <div className="cal-body" style={{ height: hours.length * HOUR_PX }}>
          <div className="cal-hours">
            {hours.map((h) => (
              <span key={h} style={{ top: (h - FIRST_HOUR) * HOUR_PX }}>
                {String(h).padStart(2, "0")}:00
              </span>
            ))}
          </div>
          {days.map((d) => (
            <div key={d.toISOString()} className="cal-col" onClick={(e) => e.target === e.currentTarget && slotClick(d, e)}>
              {hours.map((h) => (
                <i key={h} style={{ top: (h - FIRST_HOUR) * HOUR_PX }} />
              ))}
              {shown
                .filter((a) => isoDate(new Date(a.start)) === isoDate(d))
                .map((a) => {
                  const s = new Date(a.start);
                  const e = new Date(a.end);
                  const top = ((s.getHours() - FIRST_HOUR) * 60 + s.getMinutes()) * (HOUR_PX / 60);
                  const height = Math.max(((e.getTime() - s.getTime()) / 60000) * (HOUR_PX / 60), 22);
                  const label = a.patient ? `${a.patient.last_name}, ${a.patient.first_name}` : (a.title ?? "Blockzeit");
                  return (
                    <button
                      key={a.id}
                      className={`appt ${a.status}${a.patient ? "" : " block"}`}
                      style={{ top, height }}
                      onClick={() => setSelected(a)}
                      title={`${formatTime(a.start)}–${formatTime(a.end)} ${label}`}
                    >
                      <strong>{label}</strong>
                      <span>
                        {formatTime(a.start)}
                        {a.prescription_label ? ` · ${a.prescription_label}` : ""}
                      </span>
                    </button>
                  );
                })}
            </div>
          ))}
        </div>
      </div>

      {selected && <AppointmentDialog appointment={selected} onClose={() => setSelected(null)} onChanged={reload} />}
      {creating && <NewAppointmentDialog start={creating} onClose={() => setCreating(null)} onSaved={reload} />}
    </div>
  );
}
