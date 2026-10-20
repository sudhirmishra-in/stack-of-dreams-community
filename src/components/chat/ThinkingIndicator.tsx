export function ThinkingIndicator() {
  return (
    <div role="status" aria-live="polite" className="animate-fade-up flex items-center gap-3">
      <span className="grid h-8 w-8 place-items-center rounded-lg brand-gradient text-white">
        <span className="flex gap-0.5" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="dot h-1 w-1 rounded-full bg-white"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </span>
      </span>
      <span className="text-sm text-muted">Thinking…</span>
    </div>
  );
}
