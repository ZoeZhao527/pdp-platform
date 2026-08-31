import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { setToastHandler } from "../../api/request";

interface ToastItem {
  id: number;
  message: string;
  type: "error" | "success";
}

interface ToastContextValue {
  error: (message: string) => void;
  success: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let _id = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const add = useCallback((message: string, type: "error" | "success") => {
    const id = ++_id;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => remove(id), 3500);
  }, [remove]);

  const error = useCallback((m: string) => add(m, "error"), [add]);
  const success = useCallback((m: string) => add(m, "success"), [add]);

  useEffect(() => {
    // Register with the axios interceptor
    setToastHandler({ error, success });
  }, [error, success]);

  return (
    <ToastContext.Provider value={{ error, success }}>
      {children}
      <div style={{
        position: "fixed",
        top: 16,
        right: 16,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "none",
      }}>
        {toasts.map((t) => (
          <div
            key={t.id}
            style={{
              padding: "10px 16px",
              borderRadius: 8,
              fontSize: 14,
              color: "#fff",
              background: t.type === "error" ? "#e74c3c" : "#27ae60",
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
              maxWidth: 360,
              wordBreak: "break-word",
              animation: "toast-in 0.2s ease-out",
            }}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Fallback for calls outside provider
    return { error: (m: string) => console.error(m), success: (m: string) => console.log(m) };
  }
  return ctx;
}

// CSS keyframes injected via style tag
if (typeof document !== "undefined" && !document.getElementById("toast-keyframes")) {
  const style = document.createElement("style");
  style.id = "toast-keyframes";
  style.textContent = `@keyframes toast-in { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }`;
  document.head.appendChild(style);
}
