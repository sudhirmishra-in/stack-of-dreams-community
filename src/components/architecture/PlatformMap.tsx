import { ArrowDown, ArrowRight } from 'lucide-react';
import { Card } from '../ui/Card';
import { StatusBadge } from './StatusBadge';
import type { FlowStep, Layer, Pipeline } from './architectureData';

export function PlatformMap({ layers }: { layers: Layer[] }) {
  return (
    <div className="flex flex-col">
      {layers.map((layer, i) => (
        <div key={layer.id} className="flex flex-col items-stretch">
          <section
            aria-label={layer.title}
            className="rounded-2xl border border-line bg-surface-2/40 p-4"
          >
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-accent-2">
                {layer.title}
              </h3>
              <p className="text-xs text-muted">{layer.caption}</p>
            </div>
            <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-[repeat(auto-fit,minmax(15rem,1fr))]">
              {layer.nodes.map((n) => (
                <li key={n.name}>
                  <Card className="h-full !p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="text-sm font-semibold">{n.name}</h4>
                      <StatusBadge status={n.status} />
                    </div>
                    {n.region && <p className="mt-1 text-xs text-accent">{n.region}</p>}
                    <p className="mt-2 text-sm text-muted">{n.detail}</p>
                  </Card>
                </li>
              ))}
            </ul>
          </section>
          {i < layers.length - 1 && layer.next && (
            <div className="my-2 flex items-center justify-center gap-2 px-4 text-center text-xs text-muted">
              <ArrowDown size={18} className="shrink-0 text-accent-2" aria-hidden />
              <span>{layer.next}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function RequestFlow({ steps }: { steps: FlowStep[] }) {
  return (
    <ol aria-label="How a question flows" className="grid gap-3 md:grid-cols-2">
      {steps.map((s, i) => (
        <li key={s.title}>
          <Card className="flex h-full gap-3 !p-4">
            <span className="brand-gradient grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold text-white">
              {i + 1}
            </span>
            <div>
              <h3 className="text-sm font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-muted">{s.detail}</p>
            </div>
          </Card>
        </li>
      ))}
    </ol>
  );
}

export function PipelineStrip({ pipeline }: { pipeline: Pipeline }) {
  return (
    <section
      aria-label={pipeline.title}
      className="rounded-2xl border border-line bg-surface-2/40 p-4"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-accent-2">
        {pipeline.title}
      </h3>
      <ol className="flex flex-col items-stretch gap-2 md:flex-row md:items-stretch">
        {pipeline.steps.map((s, i) => (
          <li key={s.name} className="flex flex-col items-center gap-2 md:flex-1 md:flex-row">
            <Card className="h-full w-full !p-3">
              <p className="text-sm font-semibold">{s.name}</p>
              <p className="mt-1 text-xs text-muted">{s.detail}</p>
            </Card>
            {i < pipeline.steps.length - 1 && (
              <>
                <ArrowDown size={16} className="shrink-0 text-accent-2 md:hidden" aria-hidden />
                <ArrowRight
                  size={16}
                  className="hidden shrink-0 text-accent-2 md:block"
                  aria-hidden
                />
              </>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
