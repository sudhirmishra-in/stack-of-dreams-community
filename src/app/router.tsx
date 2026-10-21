import { lazy } from 'react';
import { Outlet, Route, Routes } from 'react-router';
import { AppShell } from './AppShell';
import { BrandingProvider, DEFAULT_BRANDING } from '../config/branding';
import { RequireAuth } from '../auth/RequireAuth';
import AuthCallbackPage from '../pages/AuthCallbackPage';
import ProgramOverviewPage from '../pages/ProgramOverviewPage';
import AIForGoodPage from '../features/aiForGood/pages/AIForGoodPage';
import FindResourcesPage from '../features/aiForGood/pages/FindResourcesPage';
import ResourceResultsPage from '../features/aiForGood/pages/ResourceResultsPage';
import ResourceDetailsPage from '../features/aiForGood/pages/ResourceDetailsPage';
import CoordinatorDashboardPage from '../features/aiForGood/pages/CoordinatorDashboardPage';
import VolunteerPage from '../features/aiForGood/pages/VolunteerPage';
import { AI_FOR_GOOD_CHAT } from '../features/aiForGood/config';
import ProjectDetailPage from '../pages/ProjectDetailPage';
import ProjectAppPage from '../pages/ProjectAppPage';
import HomePage from '../pages/HomePage';
import AgentsPage from '../pages/AgentsPage';
import ArchitecturePage from '../pages/ArchitecturePage';
import AboutPage from '../pages/AboutPage';
import PrivacyPage from '../pages/PrivacyPage';
import TermsPage from '../pages/TermsPage';

const ChatPage = lazy(() => import('../pages/ChatPage'));

function Layout() {
  return (
    <BrandingProvider branding={DEFAULT_BRANDING}>
      <AppShell>
        <Outlet />
      </AppShell>
    </BrandingProvider>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="text-3xl font-semibold">Page not found</h1>
      <p className="mt-2 text-muted">That page doesn't exist.</p>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route
          path="chat/:agentId?"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />
        <Route path="auth/callback" element={<AuthCallbackPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="ai-for-good" element={<AIForGoodPage />} />
        <Route path="ai-for-good/program" element={<ProgramOverviewPage />} />
        <Route path="ai-for-good/find" element={<FindResourcesPage />} />
        <Route path="ai-for-good/results" element={<ResourceResultsPage />} />
        <Route path="ai-for-good/resources/:resourceId" element={<ResourceDetailsPage />} />
        <Route path="ai-for-good/dashboard" element={<CoordinatorDashboardPage />} />
        <Route path="ai-for-good/volunteer" element={<VolunteerPage />} />
        <Route
          path="ai-for-good/assistant"
          element={
            <RequireAuth>
              <ChatPage context={AI_FOR_GOOD_CHAT} />
            </RequireAuth>
          }
        />
        <Route path="ai-for-good/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="architecture" element={<ArchitecturePage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="terms" element={<TermsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="ai-for-good/projects/:projectId/app" element={<ProjectAppPage />} />
    </Routes>
  );
}
