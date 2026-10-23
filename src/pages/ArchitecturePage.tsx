import { Card } from '../components/ui/Card';
import { PipelineStrip, PlatformMap, RequestFlow } from '../components/architecture/PlatformMap';
import { StatusBadge } from '../components/architecture/StatusBadge';
import {
  DATA_PIPELINE,
  GUARDRAILS,
  LAYERS,
  OBSERVABILITY,
  REQUEST_FLOW,
  STATUS,
} from '../components/architecture/architectureData';

export default function ArchitecturePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <p className="inline-block rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
        Live pilot
      </p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Architecture</h1>
      <p className="mt-2 max-w-3xl text-muted">
        The pilot is live on AWS. This is how a question travels from the browser to an answer, what
        keeps the directory fresh, and which controls protect cost and privacy. Each part is marked
        Live, Legacy, Planned or Off, so nothing here is claimed that does not exist.
      </p>

      <h2 className="mt-10 mb-4 text-xl font-semibold">System map</h2>
      <PlatformMap layers={LAYERS} />
      <p className="mt-3 text-xs text-muted">
        Regions: an organization policy blocks several services in us-east-1, so everything new runs
        in us-east-2. The general assistant&apos;s agent and the legacy chat path stay in us-east-1.
      </p>

      <h2 className="mt-12 mb-4 text-xl font-semibold">How a question flows</h2>
      <RequestFlow steps={REQUEST_FLOW} />

      <h2 className="mt-12 mb-4 text-xl font-semibold">Data and monitoring</h2>
      <div className="flex flex-col gap-4">
        <PipelineStrip pipeline={DATA_PIPELINE} />
        <PipelineStrip pipeline={OBSERVABILITY} />
      </div>

      <h2 className="mt-12 mb-4 text-xl font-semibold">Guardrails</h2>
      <ul className="grid gap-4 md:grid-cols-2">
        {GUARDRAILS.map((g) => (
          <li key={g.title}>
            <Card className="h-full !p-4">
              <h3 className="text-sm font-semibold">{g.title}</h3>
              <p className="mt-1 text-sm text-muted">{g.detail}</p>
            </Card>
          </li>
        ))}
      </ul>

      <h2 className="mt-12 mb-4 text-xl font-semibold">What is built and what is not</h2>
      <div className="overflow-x-auto rounded-2xl border border-line">
        <table aria-label="Status of each part" className="w-full text-left text-sm">
          <thead className="bg-surface-2 text-xs uppercase tracking-wider text-muted">
            <tr>
              <th scope="col" className="px-4 py-2">
                Part
              </th>
              <th scope="col" className="px-4 py-2">
                Status
              </th>
              <th scope="col" className="px-4 py-2">
                Note
              </th>
            </tr>
          </thead>
          <tbody>
            {STATUS.map((r) => (
              <tr key={r.item} className="border-t border-line align-top">
                <td className="px-4 py-3 font-medium">{r.item}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-4 py-3 text-muted">{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
