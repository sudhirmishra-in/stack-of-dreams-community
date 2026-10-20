import { Suspense, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';

/** Header + content + footer. Branding comes from the nearest BrandingProvider. */
export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const isChat = pathname.startsWith('/chat') || pathname === '/ai-for-good/assistant';
  return (
    <div className="flex min-h-full flex-col">
      <Header />
      <main className="flex-1">
        <Suspense fallback={<p className="p-8 text-center text-muted">Loading…</p>}>
          {children}
        </Suspense>
      </main>
      {!isChat && <Footer />}
    </div>
  );
}
