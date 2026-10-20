import { ArchitectureFlow, ARCH_NODES } from '../components/ui/ArchitectureFlow';
import { Card } from '../components/ui/Card';

export default function ArchitecturePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <p className="inline-block rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-300">
        Target Architecture
      </p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Architecture</h1>
      <p className="mt-2 max-w-2xl text-muted">
        This is the planned design. Until the backend integration is complete, the frontend uses a
        local mock service and none of the AWS components below are connected.
      </p>

      <div className="my-10">
        <ArchitectureFlow />
      </div>

      <h2 className="mb-4 text-xl font-semibold">Component responsibilities</h2>
      <ul className="grid gap-4 md:grid-cols-2">
        {ARCH_NODES.map((n, i) => (
          <li key={n.name}>
            <Card className="h-full">
              <p className="text-xs text-accent-2">Step {i + 1}</p>
              <h3 className="font-semibold">{n.name}</h3>
              <p className="text-xs text-muted">{n.role}</p>
              <p className="mt-2 text-sm text-muted">{n.detail}</p>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
