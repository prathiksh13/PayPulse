import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(() => {});

const ICONS = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
};

let toastId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (message, type = 'info', opts = {}) => {
      const id = ++toastId;
      const toast = { id, message, type, description: opts.description };
      setToasts((prev) => [...prev.slice(-4), toast]);
      const timer = setTimeout(() => dismiss(id), opts.duration ?? 4200);
      timers.current.set(id, timer);
      return id;
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack" role="region" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICONS[t.type] || Info;
          return (
            <div key={t.id} className={`toast toast-${t.type}`}>
              <span className="toast-icon">
                <Icon size={16} />
              </span>
              <div className="toast-copy">
                <strong>{t.message}</strong>
                {t.description ? <span>{t.description}</span> : null}
              </div>
              <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Dismiss">
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}