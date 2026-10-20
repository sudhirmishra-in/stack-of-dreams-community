import { useBranding } from '../../config/branding';

export function Footer() {
  const { footer } = useBranding();
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-6 text-sm text-muted sm:flex-row">
        <p>
          {footer.prefix}{' '}
          <a
            href={footer.linkUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-fg underline decoration-accent-2 underline-offset-4 hover:text-accent"
          >
            {footer.linkLabel}
          </a>
        </p>
        {footer.note && <p>{footer.note}</p>}
      </div>
    </footer>
  );
}
