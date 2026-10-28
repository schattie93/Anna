import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Modaler Dialog (Portal an <body>, Escape und Klick auf den Hintergrund schließen). */
export default function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal();
  }, []);
  return createPortal(
    <dialog
      ref={ref}
      className={wide ? "dialog wide-dialog" : "dialog"}
      onCancel={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
    >
      <div className="dialog-body">
        <div className="page-head">
          <h2>{title}</h2>
          <button type="button" className="btn small" onClick={onClose}>
            Schließen
          </button>
        </div>
        {children}
      </div>
    </dialog>,
    document.body,
  );
}
