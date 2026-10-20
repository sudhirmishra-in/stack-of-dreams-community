export const NOT_AVAILABLE = 'Not available';

export function formatNumber(n: number | undefined, unit?: string): string {
  if (n === undefined) return NOT_AVAILABLE;
  return `${n.toLocaleString('en-US')}${unit ? ` ${unit}` : ''}`;
}

export function formatUpdated(iso: string | undefined): string {
  if (!iso) return NOT_AVAILABLE;
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? NOT_AVAILABLE
    : d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

/** Phone numbers are only linked when they look like a real number. */
export function telHref(phone: string | undefined): string | undefined {
  const digits = phone?.replace(/[^\d+]/g, '');
  return digits && /^\+?\d{10,15}$/.test(digits) ? `tel:${digits}` : undefined;
}

export function directionsHref(r: {
  address?: string;
  zipCode?: string;
  verified: boolean;
}): string | undefined {
  if (!r.address || !r.verified) return undefined;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${r.address} ${r.zipCode ?? ''}`.trim())}`;
}
