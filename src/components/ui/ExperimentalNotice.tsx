import { FlaskConical } from 'lucide-react';

export function ExperimentalNotice({ className = '' }: { className?: string }) {
  return (
    <p
      role="note"
      className={`flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300 ${className}`}
    >
      <FlaskConical size={14} className="mt-0.5 shrink-0" aria-hidden />
      <span>
        Experimental AI demo. Responses may be inaccurate. Do not enter confidential, personal, or
        regulated information.
      </span>
    </p>
  );
}
