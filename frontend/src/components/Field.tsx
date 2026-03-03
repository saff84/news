export function HelpText({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-xs text-slate-500">{children}</p>;
}

export function HintBox({ children }: { children: React.ReactNode }) {
  return <div className="mt-3 rounded border bg-slate-50 p-3 text-xs text-slate-700">{children}</div>;
}

export function InstructionBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border bg-slate-50 p-3 text-xs text-slate-700">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-600">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

