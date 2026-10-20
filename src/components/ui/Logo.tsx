import { Sparkles } from 'lucide-react';
import { useBranding } from '../../config/branding';

export function Logo({ compact = false }: { compact?: boolean }) {
  const { name, logo } = useBranding();
  const Icon = logo.icon ?? Sparkles;
  return (
    <span className="flex items-center gap-2.5">
      <span className="brand-gradient grid h-8 w-8 place-items-center overflow-hidden rounded-lg text-white">
        {logo.imageUrl ? (
          <img src={logo.imageUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <Icon size={16} aria-hidden />
        )}
      </span>
      {!compact && <span className="font-semibold tracking-tight">{name}</span>}
    </span>
  );
}
