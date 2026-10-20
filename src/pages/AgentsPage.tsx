import { AgentDirectory } from '../components/agents/AgentDirectory';

export default function AgentsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">Agent directory</h1>
      <p className="mt-2 mb-8 max-w-2xl text-muted">
        Agents available on the platform. Only the AI Assistant has a working demo; the others are
        planned and are not deployed.
      </p>
      <AgentDirectory />
    </div>
  );
}
