import * as Toast from "@radix-ui/react-toast";
import React, { createContext, useCallback, useContext, useMemo, useState } from "react";

type ToastVariant = "default" | "success" | "error";

export type ToastInput = {
  title?: string;
  description: string;
  variant?: ToastVariant;
};

type ToastItem = ToastInput & { id: string; open: boolean };

type ToastCtx = {
  push: (t: ToastInput) => void;
};

const Ctx = createContext<ToastCtx | null>(null);

function toastClasses(variant: ToastVariant) {
  if (variant === "success") return "border-emerald-200 bg-emerald-50 text-emerald-900";
  if (variant === "error") return "border-red-200 bg-red-50 text-red-900";
  return "border-slate-200 bg-white text-slate-900";
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((t: ToastInput) => {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const it: ToastItem = { id, open: true, variant: t.variant ?? "default", title: t.title, description: t.description };
    setItems((prev) => [it, ...prev].slice(0, 3));
  }, []);

  const ctx = useMemo(() => ({ push }), [push]);

  return (
    <Ctx.Provider value={ctx}>
      <Toast.Provider swipeDirection="right">
        {children}
        {items.map((t) => (
          <Toast.Root
            key={t.id}
            open={t.open}
            duration={t.variant === "error" ? 7000 : 4000}
            onOpenChange={(open) => {
              setItems((prev) => prev.map((x) => (x.id === t.id ? { ...x, open } : x)).filter((x) => x.open));
            }}
            className={`w-[360px] max-w-[calc(100vw-32px)] rounded-lg border p-3 shadow-lg ${toastClasses(t.variant ?? "default")}`}
          >
            {t.title ? <Toast.Title className="text-sm font-semibold">{t.title}</Toast.Title> : null}
            <Toast.Description className="mt-1 text-sm opacity-90">{t.description}</Toast.Description>
          </Toast.Root>
        ))}
        <Toast.Viewport className="fixed bottom-4 right-4 z-50 flex w-[360px] max-w-[calc(100vw-32px)] flex-col gap-2 outline-none" />
      </Toast.Provider>
    </Ctx.Provider>
  );
}

export function useToast() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useToast must be used within ToastProvider");
  return v;
}

