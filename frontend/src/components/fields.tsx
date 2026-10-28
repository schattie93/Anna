import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";

type Setter<T> = <K extends keyof T>(key: K, value: T[K]) => void;

/** Kleiner Formular-State: hält ein Objekt und liefert einen typisierten Setter. */
export function useForm<T extends object>(initial: T): [T, Setter<T>, (v: T) => void] {
  const [values, setValues] = useState<T>(initial);
  const set: Setter<T> = (key, value) => setValues((v) => ({ ...v, [key]: value }));
  return [values, set, setValues];
}

const blankToNull = (s: string) => (s.trim() === "" ? null : s);

interface FieldProps {
  label: string;
  hint?: string;
  wide?: boolean;
  children: ReactNode;
}

export function Field({ label, hint, wide, children }: FieldProps) {
  return (
    <label className={wide ? "field wide" : "field"}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

interface TextProps {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  required?: boolean;
  type?: "text" | "date" | "email" | "tel" | "number" | "password";
  hint?: string;
  wide?: boolean;
  autoFocus?: boolean;
  placeholder?: string;
}

export function TextField({ label, value, onChange, required, type = "text", hint, wide, autoFocus, placeholder }: TextProps) {
  return (
    <Field label={label + (required ? " *" : "")} hint={hint} wide={wide}>
      <input
        type={type}
        value={value ?? ""}
        required={required}
        autoFocus={autoFocus}
        placeholder={placeholder}
        onChange={(e) => onChange(required ? e.target.value : blankToNull(e.target.value))}
      />
    </Field>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  required,
  rows = 3,
  placeholder,
}: Omit<TextProps, "type" | "wide"> & { rows?: number }) {
  return (
    <Field label={label + (required ? " *" : "")} wide>
      <textarea
        rows={rows}
        value={value ?? ""}
        required={required}
        placeholder={placeholder}
        onChange={(e) => onChange(required ? e.target.value : blankToNull(e.target.value))}
      />
    </Field>
  );
}

export function Select<V extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: V;
  options: Record<V, string>;
  onChange: (v: V) => void;
}) {
  return (
    <Field label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value as V)}>
        {(Object.keys(options) as V[]).map((k) => (
          <option key={k} value={k}>
            {options[k]}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

/** Schmerzskala NRS 0–10 als große Touch-Schaltflächen. Erneutes Tippen hebt die Auswahl auf. */
export function PainScale({ label, value, onChange }: { label: string; value: number | null; onChange: (v: number | null) => void }) {
  return (
    <div className="field wide">
      <span className="field-label">{label}</span>
      <div className="pain-scale" role="radiogroup" aria-label={label}>
        {Array.from({ length: 11 }, (_, n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            className={value === n ? "pain selected" : "pain"}
            style={{ "--pain": n } as CSSProperties}
            onClick={() => onChange(value === n ? null : n)}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Mehrfachauswahl als antippbare Chips (z. B. Maßnahmen, Warnzeichen). */
export function Chips({
  label,
  options,
  value,
  onChange,
  tone,
}: {
  label: string;
  options: Record<string, string>;
  value: string[];
  onChange: (v: string[]) => void;
  tone?: "warn";
}) {
  const toggle = (k: string) => onChange(value.includes(k) ? value.filter((x) => x !== k) : [...value, k]);
  return (
    <div className="field wide">
      <span className="field-label">{label}</span>
      <div className="chips">
        {Object.entries(options).map(([k, text]) => (
          <button
            key={k}
            type="button"
            aria-pressed={value.includes(k)}
            className={`chip${value.includes(k) ? " on" : ""}${tone ? " " + tone : ""}`}
            onClick={() => toggle(k)}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Dialog, der eine Pflicht-Begründung abfragt (Stornierung, Korrektur).
 * Wird per Portal an <body> gehängt, damit sein Formular nie in einem anderen Formular steckt.
 */
export function ReasonDialog({
  title,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  confirmLabel: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");
  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal();
  }, []);
  return createPortal(
    <dialog ref={ref} onCancel={onCancel} className="dialog">
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault();
          // React-Events laufen trotz Portal durch den Komponentenbaum nach oben
          e.stopPropagation();
          if (reason.trim()) onConfirm(reason.trim());
        }}
      >
        <h2>{title}</h2>
        <TextArea label="Begründung" value={reason} onChange={(v) => setReason(v ?? "")} required />
        <div className="actions">
          <button type="button" className="btn" onClick={onCancel}>
            Abbrechen
          </button>
          <button type="submit" className="btn primary" disabled={!reason.trim()}>
            {confirmLabel}
          </button>
        </div>
      </form>
    </dialog>,
    document.body,
  );
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? (
    <div className="error" role="alert">
      {error}
    </div>
  ) : null;
}
