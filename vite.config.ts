/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // Pre-bundle the (lazily imported) map library at startup so the dev server never re-optimizes mid-session,
  // which makes already-open pages request stale module URLs (HTTP 504).
  optimizeDeps: { include: ['maplibre-gl'] },
  // Tests must not depend on a developer's local .env (real API URLs, auth settings): read env files from an
  // empty directory under test so every run sees the documented defaults.
  envDir: mode === 'test' ? './src/tests/noenv' : undefined,
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.ts'],
    css: false,
    exclude: ['backend/**', 'platform/**', 'node_modules/**', 'dist/**'],
  },
}));
