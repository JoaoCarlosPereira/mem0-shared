export function MemoryTableSkeleton() {
  const loadingCards = Array(8).fill(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2.5 px-0.5">
        <div className="h-4 w-4 animate-pulse rounded bg-slate-800" />
        <div className="h-3.5 w-28 animate-pulse rounded bg-slate-800" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {loadingCards.map((_, index) => (
          <div
            key={index}
            className="flex min-h-[168px] flex-col overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-800/40 via-slate-950/90 to-slate-950"
          >
            <div className="h-1 w-full bg-slate-700" />
            <div className="flex flex-1 flex-col p-4 pt-3">
              <div className="mb-3 flex justify-between">
                <div className="h-4 w-4 animate-pulse rounded bg-slate-800" />
                <div className="h-5 w-16 animate-pulse rounded-full bg-slate-800" />
              </div>
              <div className="mb-4 flex-1 space-y-2">
                <div className="h-4 w-full animate-pulse rounded bg-slate-800" />
                <div className="h-4 w-4/5 animate-pulse rounded bg-slate-800" />
              </div>
              <div className="mt-auto flex items-center justify-between border-t border-white/5 pt-3">
                <div className="h-7 w-7 animate-pulse rounded-full bg-slate-800" />
                <div className="h-3 w-16 animate-pulse rounded bg-slate-800" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
