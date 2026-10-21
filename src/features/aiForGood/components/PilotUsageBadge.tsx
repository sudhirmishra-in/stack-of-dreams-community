import { useEffect, useState } from 'react';
import {
  getPilotUsage,
  PILOT_USAGE_EVENT,
  type PilotUsage,
} from '../../../services/pilotAssistantService';

/** Shows the signed-in user's remaining pilot quota, straight from the server (never computed locally). */
export function PilotUsageBadge() {
  const [usage, setUsage] = useState<PilotUsage | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getPilotUsage(ctrl.signal)
      .then(setUsage)
      .catch(() => {
        /* the badge is informational; chat still reports limits when they are hit */
      });
    const onUpdate = (e: Event) => setUsage((e as CustomEvent<PilotUsage>).detail);
    window.addEventListener(PILOT_USAGE_EVENT, onUpdate);
    return () => {
      ctrl.abort();
      window.removeEventListener(PILOT_USAGE_EVENT, onUpdate);
    };
  }, []);

  if (!usage) return null;
  if (usage.accountStatus === 'pending') {
    return (
      <p
        role="status"
        className="rounded-lg border border-amber-500/40 px-3 py-1.5 text-xs text-amber-700 dark:text-amber-300"
      >
        Your account is waiting for approval. You can use the pilot once an administrator approves
        it.
      </p>
    );
  }
  const low = usage.daily.remaining <= 3;
  return (
    <p
      role="status"
      className={`rounded-lg border px-3 py-1.5 text-xs ${low ? 'border-amber-500/40 text-amber-700 dark:text-amber-300' : 'border-line text-muted'}`}
    >
      {usage.disabled
        ? 'Your pilot access is currently disabled.'
        : `${usage.daily.remaining} of ${usage.daily.limit} questions left today · ${usage.monthly.remaining} this month`}
    </p>
  );
}
